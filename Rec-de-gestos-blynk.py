
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import ttk
import requests
from functools import partial
from datetime import datetime
from collections import deque
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import threading
import os
import platform

# --- Reconhecimento de gestos (opcional: OpenCV + MediaPipe) ---
try:
    import cv2
    import mediapipe as mp
    GESTURE_AVAILABLE = True
except Exception:
    cv2 = None
    mp = None
    GESTURE_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

# preview UI widget (inicializado depois que controls_frame existir)
preview_label = None

# Variáveis de controle do reconhecimento
gesture_thread = None
gesture_running = False
gesture_hold_count = 0
gesture_last_detected = None
GESTURE_HOLD_THRESHOLD = 6  # frames consecutivos para confirmar um gesto

BLYNK_TOKEN = '_Cm7fdhv3ndn2LobfQwCxsgn4cTNxO1d'
BLYNK_URL_GET = f'https://blynk.cloud/external/api/getAll?token={BLYNK_TOKEN}'
BLYNK_URL_SET = f'https://blynk.cloud/external/api/update'

RELE_VPINS = {
    'PORTAO': 'v3',
    'SALA': 'v6',
    'QUARTO': 'v7',
    'CORREDOR': 'v8',
    'GARAGEM': 'v9',
    'GERAL': 'v10'
}
RELES_LIST = ['Nenhum'] + list(RELE_VPINS.keys())[:-1]
label_por_vpin = {v: k for k, v in RELE_VPINS.items()}
icones = {
    'PORTAO': '\U0001F50C', #U0001F50C
    'SALA': '\U0001F4A1', #U0001F50C
    'QUARTO': '\U0001F6CF', #U0001F4A1
    'CORREDOR': '\U0001F6A7', #U0001F6A7
    'GARAGEM': '\U0001F50C', #U0001F6CF
    'GERAL': '\U0001F3E0' #U0001F3E0
}
ESTADO = {}

# Histórico para o gráfico
historico_horas = deque(maxlen=100)
historico_temp = deque(maxlen=100)
historico_umid = deque(maxlen=100)

# Inicialização da janela principal com tema ttkbootstrap
root = tb.Window(themename="yeti")
root.title("Automação Residencial - Blynk")
root.geometry("1100x700")
root.minsize(600, 600)
root.resizable(True, True)

setpoint_temp = tk.DoubleVar(value=30.0)
setpoint_umid = tk.DoubleVar(value=70.0)
rele_alarme_temp = tk.StringVar(value='Nenhum')
rele_alarme_umid = tk.StringVar(value='Nenhum')

# variável para ativar/desativar alarmes (mover para cima para uso no Checkbutton)
alarme_ativo = tk.BooleanVar(value=True)

# Tema dinâmico
def mudar_tema(event=None):
    tema = tema_var.get()
    root.style.theme_use(tema)

temas_disponiveis = list(root.style.theme_names())
tema_var = tk.StringVar(value=root.style.theme_use())

# Notebook para abas
notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=5, pady=5)

# --- Aba Home ---
frame_home = ttk.Frame(notebook)
notebook.add(frame_home, text="Home")

# Seleção de tema
frame_tema = tb.Frame(frame_home)
frame_tema.pack(fill='x', pady=5, padx=10)
tb.Label(frame_tema, text="Tema:", font=("Segoe UI", 10)).pack(side='left')
combo_tema = tb.Combobox(frame_tema, values=temas_disponiveis, textvariable=tema_var, width=15, state="readonly")
combo_tema.pack(side='left', padx=5)
combo_tema.bind("<<ComboboxSelected>>", mudar_tema)

# Checkbutton para ativar/desativar alarmes (fica ao lado da seleção de tema)
tb.Checkbutton(frame_tema, text="Alarmes Ativados", variable=alarme_ativo, bootstyle="success", width=16).pack(side='left', padx=10)

# Checkbutton para ativar/desativar reconhecimento de gestos (opcional)
gestos_ativos = tk.BooleanVar(value=False)
gestos_label_text = tk.StringVar(value=("Gestos: disponível" if GESTURE_AVAILABLE else "Gestos: não disponível (instale mediapipe + opencv)"))
tb.Checkbutton(frame_tema, text="Gestos Ativados", variable=gestos_ativos, bootstyle="info", width=14).pack(side='left', padx=10)
tb.Label(frame_tema, textvariable=gestos_label_text, font=("Segoe UI", 9)).pack(side='left', padx=6)
# Checkbutton separado para abrir/fechar preview externo (janela separada)
preview_externa_ativa = tk.BooleanVar(value=False)
tb.Checkbutton(frame_tema, text="Preview Externo", variable=preview_externa_ativa, bootstyle="secondary", width=14).pack(side='left', padx=10)
# Checkbutton para desenhar landmarks (variável definida aqui)
preview_draw_landmarks = tk.BooleanVar(value=True)
tb.Checkbutton(frame_tema, text="Desenhar landmarks", variable=preview_draw_landmarks, bootstyle="info", width=18).pack(side='left', padx=6)

# Frames de temperatura e umidade com setpoint e seleção de relé, separados
temperatura_var = tk.StringVar()
umidade_var = tk.StringVar()

frame_temp = tb.LabelFrame(frame_home, text="Temperatura", bootstyle="secondary", padding=10)
frame_temp.pack(fill='x', pady=(20, 10), padx=20)
tb.Label(frame_temp, textvariable=temperatura_var, font=("Segoe UI", 16, 'bold'), bootstyle="warning").grid(row=0, column=0, sticky='w', padx=5)
tb.Label(frame_temp, text="Setpoint:", bootstyle="warning").grid(row=0, column=1, padx=5)
tb.Entry(frame_temp, textvariable=setpoint_temp, width=6, font=("Segoe UI", 12)).grid(row=0, column=2, padx=5)
tb.Label(frame_temp, text="Relé:", bootstyle="warning").grid(row=0, column=3, padx=5)
tb.Combobox(frame_temp, values=RELES_LIST, textvariable=rele_alarme_temp, width=10, font=("Segoe UI", 12), state="readonly").grid(row=0, column=4, padx=5)

frame_umid = tb.LabelFrame(frame_home, text="Umidade", bootstyle="secondary", padding=10)
frame_umid.pack(fill='x', pady=(0, 20), padx=20)
tb.Label(frame_umid, textvariable=umidade_var, font=("Segoe UI", 16, 'bold'), bootstyle="info").grid(row=0, column=0, sticky='w', padx=5)
tb.Label(frame_umid, text="Setpoint:", bootstyle="info").grid(row=0, column=1, padx=5)
tb.Entry(frame_umid, textvariable=setpoint_umid, width=6, font=("Segoe UI", 12)).grid(row=0, column=2, padx=5)
tb.Label(frame_umid, text="Relé:", bootstyle="info").grid(row=0, column=3, padx=5)
tb.Combobox(frame_umid, values=RELES_LIST, textvariable=rele_alarme_umid, width=10, font=("Segoe UI", 12), state="readonly").grid(row=0, column=4, padx=5)

# Planta baixa com canvas
frame_plan = tb.Frame(frame_home)
frame_plan.pack(fill='both', padx=10, pady=10)

canvas_w = 520
canvas_h = 360
plan_canvas = tk.Canvas(frame_plan, width=canvas_w, height=canvas_h, bg='#f7f7f7', highlightthickness=1, highlightbackground='#cccccc')
plan_canvas.pack(side='left', padx=10, pady=5)

# Desenho simples da planta (retângulos para cômodos)
# Quarto (esquerda superior)
q_coords = (20, 20, 260, 170)
plan_canvas.create_rectangle(*q_coords, fill='#ffffff', outline='#666666', width=2)
plan_canvas.create_text((q_coords[0]+q_coords[2])//2, q_coords[1]+14, text="QUARTO", font=("Segoe UI", 12, "bold"))

# Sala (direita superior)
s_coords = (280, 20, 500, 170)
plan_canvas.create_rectangle(*s_coords, fill='#ffffff', outline='#666666', width=2)
plan_canvas.create_text((s_coords[0]+s_coords[2])//2, s_coords[1]+14, text="SALA", font=("Segoe UI", 12, "bold"))

# Corredor (centro)
c_coords = (20, 190, 500, 260)
plan_canvas.create_rectangle(*c_coords, fill='#ffffff', outline='#666666', width=2)
plan_canvas.create_text((c_coords[0]+c_coords[2])//2, c_coords[1]+14, text="CORREDOR", font=("Segoe UI", 12, "bold"))

# Garagem (inferior)
g_coords = (20, 280, 500, 350)
plan_canvas.create_rectangle(*g_coords, fill='#ffffff', outline='#666666', width=2)
plan_canvas.create_text((g_coords[0]+g_coords[2])//2, g_coords[1]+14, text="GARAGEM", font=("Segoe UI", 12, "bold"))

# Espaço para controles à direita do canvas (opcional)
controls_frame = tb.Frame(frame_plan)
controls_frame.pack(side='left', fill='y', padx=8)

def alternar_estado(vpin):
    if vpin == 'v10':
        novo_estado = 0 if any(ESTADO.get(r, 0) for r in ['v6','v7','v8','v9']) else 1
        for r in ['v6','v7','v8','v9']:
            url = f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&{r}={novo_estado}"
            try:
                requests.get(url)
            except Exception as e:
                print("Erro ao enviar comando:", e)
        url_mestre = f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&v10={novo_estado}"
        try:
            requests.get(url_mestre)
        except Exception as e:
            print("Erro ao enviar comando para mestre:", e)
    else:
        estado_atual = ESTADO.get(vpin, 0)
        novo_estado = 0 if estado_atual == 1 else 1
        try:
            url = f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&{vpin}={novo_estado}"
            requests.get(url)
        except Exception as e:
            print("Erro ao enviar comando:", e)

# Cria botões de cada cômodo e posiciona sobre o canvas usando create_window
botoes = {}

# Helper para criar botão e inserir no canvas
def _create_room_button(vpin, center_x, center_y):
    btn = tb.Button(plan_canvas,
                    text=f"{icones.get(label_por_vpin.get(vpin,''), '')}\n{label_por_vpin.get(vpin,'')}\nOFF",
                    width=16,
                    bootstyle="danger",    # usa estilo do ttkbootstrap
                    cursor="hand2",
                    command=partial(alternar_estado, vpin))
    # cria widget dentro do canvas (o ttk.Button centraliza o texto por padrão)
    plan_canvas.create_window(center_x, center_y, window=btn)
    botoes[vpin] = btn

# Coordenadas centrais calculadas para cada cômodo
_create_room_button('v7', (q_coords[0]+q_coords[2])//2, (q_coords[1]+q_coords[3])//2)   # QUARTO -> v7
_create_room_button('v6', (s_coords[0]+s_coords[2])//2, (s_coords[1]+s_coords[3])//2)   # SALA -> v6
_create_room_button('v8', (c_coords[0]+c_coords[2])//2, (c_coords[1]+c_coords[3])//2)   # CORREDOR -> v8
_create_room_button('v9', (g_coords[0]+g_coords[2])//2, (g_coords[1]+g_coords[3])//2)   # GARAGEM -> v9

# Botão mestre abaixo do canvas, em controls_frame
tb.Label(controls_frame, text="Controles Rápidos", font=("Segoe UI", 10, "bold")).pack(pady=(6,8))

# frame para agrupar botões do painel direito (mestre + portao)
btn_panel = tb.Frame(controls_frame)
btn_panel.pack(pady=6)

# Botão PORTAO (v3)
btn_portao = tb.Button(btn_panel,
                       text=f"{icones.get('PORTAO','')}\nPORTAO\nOFF",
                       width=12,
                       bootstyle="danger",
                       cursor="hand2",
                       command=partial(alternar_estado, 'v3'))
btn_portao.pack(side='left', padx=6)
botoes['v3'] = btn_portao

# Botão GERAL / MESTRE (v10)
btn_mestre = tb.Button(btn_panel,
                       text=f"{icones.get('GERAL','')}\nGERAL\nOFF",
                       width=12,
                       bootstyle="danger",
                       cursor="hand2",
                       command=partial(alternar_estado, 'v10'))
btn_mestre.pack(side='left', padx=6)
botoes['v10'] = btn_mestre

# Legenda para estados
leg_frame = tb.Frame(controls_frame)
leg_frame.pack(pady=(12,0))
tb.Label(leg_frame, text="Legenda:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, pady=(0,6))
tb.Label(leg_frame, text="ON", bootstyle="success", anchor='center', width=6).grid(row=1, column=0, padx=10)
tb.Label(leg_frame, text="OFF", bootstyle="danger", anchor='center', width=6).grid(row=1, column=1, padx=10)

# Nota: removido preview pequeno do painel. Use a janela de Preview (Landmarks) como único preview.
# preview_label será o widget de preview pequeno abaixo dos botões (inicializado abaixo)
preview_label = None
preview_cap = None
# Ajuste de tamanho padrão solicitado: 400 x 350
# preview size defaults
preview_width_var = tk.IntVar(value=400)
preview_height_var = tk.IntVar(value=350)
# seleção de índice da câmera
camera_index_var = tk.IntVar(value=0)
preview_hands = None
preview_running = False

def start_preview_capture(camera_index=0):
    """Abre a câmera e inicia loop de preview no thread principal via root.after."""
    global preview_cap, preview_hands, preview_running
    if preview_cap is not None:
        return
    if cv2 is None:
        print("OpenCV não disponível; instale opencv-python para usar preview de câmera.")
        gestos_ativos.set(False)
        return
    # se camera_index não fornecido explicitamente, usa valor da UI
    if camera_index is None:
        camera_index = int(camera_index_var.get())

    # informação básica
    print(f"Tentando abrir câmera index={camera_index}")
    preview_cap = cv2.VideoCapture(camera_index)
    if not preview_cap.isOpened():
        print(f"Erro: não foi possível abrir a câmera (index={camera_index})")
        preview_cap = None
        gestos_ativos.set(False)
        return
    # criar objeto MediaPipe para preview/detecção, se disponível
    if GESTURE_AVAILABLE and mp is not None:
        try:
            preview_hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.6)
        except Exception:
            preview_hands = None
    else:
        preview_hands = None
    preview_running = True
    # iniciar loop de preview
    root.after(0, preview_loop)


def _on_camera_index_change(*args):
    # Reinicia captura com novo índice se estiver rodando
    try:
        if preview_running:
            print("Reiniciando captura com novo índice de câmera...")
            stop_preview_capture()
            start_preview_capture()
    except Exception as e:
        print(f"Erro ao reiniciar captura: {e}")


def log_msg(msg: str, level: str = 'INFO'):
    # mensagens simples no console — debug UI removido
    try:
        print(f"{datetime.now().strftime('%H:%M:%S')} [{level}] {msg}")
    except Exception:
        pass

def stop_preview_capture():
    """Para captura e libera recursos da câmera e do MediaPipe."""
    global preview_cap, preview_hands, preview_running
    preview_running = False
    try:
        if preview_cap:
            preview_cap.release()
    except Exception:
        pass
    preview_cap = None
    try:
        if preview_hands is not None:
            preview_hands.close()
    except Exception:
        pass
    preview_hands = None
    # limpar preview pequeno
    try:
        if preview_label is not None:
            preview_label.config(image='', text='Preview\n(inativo)')
            preview_label.image = None
    except Exception:
        pass
    log_msg("Captura da câmera parada.", level='DEBUG')


def preview_loop():
    """Loop chamado via root.after que captura um frame, atualiza previews e executa detecção leve."""
    global preview_cap, preview_hands, gesture_hold_count, gesture_last_detected
    if not preview_running or preview_cap is None:
        return
    try:
        ret, frame = preview_cap.read()
        if not ret:
            print("Erro: falha ao ler frame da câmera")
            # parar captura e desmarcar checkbox
            try:
                gestos_ativos.set(False)
            except Exception:
                pass
            stop_preview_capture()
            return

        # preparar imagem RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        annotated = rgb

        detected = None
        # processar landmarks se disponível
        if preview_hands is not None:
            try:
                results = preview_hands.process(rgb)
                if results and results.multi_hand_landmarks:
                    hand = results.multi_hand_landmarks[0]
                    detected = _gesture_count_fingers(hand, None)
                    if preview_draw_landmarks.get():
                        try:
                            mp.solutions.drawing_utils.draw_landmarks(annotated, hand, mp.solutions.hands.HAND_CONNECTIONS)
                        except Exception:
                            pass
            except Exception as e:
                # falha no processing não impede preview
                print("MediaPipe processing error:", e)

        # atualizar small preview (usar frame anotado com landmarks se desenhado)
        try:
            if PIL_AVAILABLE and preview_label is not None:
                try:
                    if preview_draw_landmarks.get():
                        # annotated é RGB; _update_preview_image_from_bgr espera BGR
                        bgr_for_small = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
                        _update_preview_image_from_bgr(bgr_for_small)
                    else:
                        _update_preview_image_from_bgr(frame.copy())
                except Exception:
                    # fallback simples
                    _update_preview_image_from_bgr(frame.copy())
        except Exception:
            pass

        # atualizar large preview se aberto
        try:
            if preview_window_open and preview_large_label is not None:
                _update_large_preview_from_rgb(annotated)
        except Exception:
            pass

        # debouncing da detecção e acionamento
        try:
            if detected is not None:
                if detected == gesture_last_detected:
                    gesture_hold_count += 1
                else:
                    gesture_hold_count = 1
                    gesture_last_detected = detected
                if gesture_hold_count >= GESTURE_HOLD_THRESHOLD:
                    trigger_gesture_action(detected)
                    gesture_hold_count = 0
                    gesture_last_detected = None
            else:
                gesture_hold_count = 0
                gesture_last_detected = None
        except Exception:
            pass
        # debug info (apenas print simplificado)
        try:
            print(f"Frame lido (w={frame.shape[1]}, h={frame.shape[0]}) detected={detected}")
        except Exception:
            pass

    finally:
        # agendar próximo frame
        try:
            if preview_running and preview_cap is not None:
                root.after(100, preview_loop)
        except Exception:
            pass


# Janela de preview grande com landmarks
preview_window = None
preview_large_label = None
preview_window_open = False

def open_preview_window():
    global preview_window, preview_large_label, preview_window_open
    if preview_window_open:
        return
    preview_window = tk.Toplevel(root)
    preview_window.title("Preview - Landmarks")
    preview_window.geometry("480x360")
    preview_large_label = tk.Label(preview_window, text="Aguardando câmera...", bg="#000", fg="#fff")
    preview_large_label.pack(fill='both', expand=True)
    preview_window_open = True

    def _on_close():
        global preview_window_open, preview_window, preview_large_label
        # usuário fechou a janela manualmente: desativa gestos (desmarca checkbox)
        preview_window_open = False
        try:
            preview_window.destroy()
        except:
            pass
        preview_window = None
        preview_large_label = None
        try:
            # força desmarcar o checkbutton (isso acionará _on_gestos_toggle)
            gestos_ativos.set(False)
        except Exception:
            pass

    print("Janela de preview externa aberta.")

    preview_window.protocol("WM_DELETE_WINDOW", _on_close)

def close_preview_window():
    global preview_window_open, preview_window
    if not preview_window_open:
        return
    try:
        preview_window.destroy()
    except:
        pass
    preview_window_open = False
    preview_window = None
    print("Janela de preview externa fechada.")



# Small preview (below PORTAO/MESTRE)
preview_small_frame = tb.Frame(controls_frame, width=preview_width_var.get(), height=preview_height_var.get())
preview_small_frame.pack(pady=(8,6))
preview_small_frame.pack_propagate(False)
preview_label = tk.Label(preview_small_frame, text="Preview\n(inativo)", bg="#000", fg="#fff")
preview_label.pack(fill='both', expand=True)

# Controls para ajustar tamanho do preview (largura x altura)
size_frame = tb.Frame(controls_frame)
size_frame.pack(pady=(2,6))
tb.Label(size_frame, text="Preview size:", font=("Segoe UI", 9)).pack(side='left', padx=(0,6))
spin_w = tk.Spinbox(size_frame, from_=80, to=640, width=5, textvariable=preview_width_var)
spin_w.pack(side='left')
tk.Label(size_frame, text="x").pack(side='left')
spin_h = tk.Spinbox(size_frame, from_=60, to=480, width=5, textvariable=preview_height_var)
spin_h.pack(side='left', padx=(0,6))
    # 'Desenhar landmarks' foi movido para a barra superior (frame_tema)

# Nota: use apenas o Checkbutton 'Gestos Ativados' para abrir/fechar o preview.

# Controls: camera index
cam_frame = tb.Frame(controls_frame)
cam_frame.pack(pady=(6,6))
tb.Label(cam_frame, text="Camera index:", font=("Segoe UI", 9)).pack(side='left')
spin_idx = tk.Spinbox(cam_frame, from_=0, to=4, width=4, textvariable=camera_index_var)
spin_idx.pack(side='left', padx=(4,8))

# ligar trace para reagir a mudanças do índice e redimensionamento do preview
camera_index_var.trace_add('write', lambda *a: _on_camera_index_change())
preview_width_var.trace_add('write', lambda *a: preview_small_frame.config(width=int(preview_width_var.get())))
preview_height_var.trace_add('write', lambda *a: preview_small_frame.config(height=int(preview_height_var.get())))

# --- Aba Dashboards ---
frame_dash = ttk.Frame(notebook)
notebook.add(frame_dash, text="Dashboards")

# Filtros de data/hora
frame_filtros = tb.LabelFrame(frame_dash, text="Filtros", bootstyle="secondary", padding=10)
frame_filtros.pack(fill='x', pady=10, padx=10)

filtro_tipo = tk.StringVar(value="dia")
filtro_data = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

tb.Label(frame_filtros, text="Tipo:").pack(side='left', padx=5)
combo_tipo = tb.Combobox(frame_filtros, values=["hora", "dia", "mes", "ano"], textvariable=filtro_tipo, width=8, state="readonly")
combo_tipo.pack(side='left', padx=5)
tb.Label(frame_filtros, text="Data:").pack(side='left', padx=5)
entry_data = tb.Entry(frame_filtros, textvariable=filtro_data, width=12)
entry_data.pack(side='left', padx=5)
btn_buscar = tb.Button(frame_filtros, text="Buscar", bootstyle="primary", width=10)
btn_buscar.pack(side='left', padx=10)

# Área de gráficos
frame_graficos = tb.LabelFrame(frame_dash, text="Gráficos", bootstyle="secondary", padding=10)
frame_graficos.pack(fill='both', expand=True, padx=10, pady=10)

# Criação do gráfico (sem dados iniciais)
fig = Figure(figsize=(6, 3), dpi=100)
ax = fig.add_subplot(111)
canvas = FigureCanvasTkAgg(fig, master=frame_graficos)
canvas.get_tk_widget().pack(fill='both', expand=True)
frame_graficos.update_idletasks()

# --- Funções principais ---
def obter_dados():
    try:
        resposta = requests.get(BLYNK_URL_GET)
        if resposta.status_code == 200:
            dados = resposta.json()
            atualizar_interface(dados)
        else:
            print("Erro ao obter dados:", resposta.status_code)
    except Exception as e:
        print("Erro:", e)
    root.after(5000, obter_dados)

def atualizar_interface(dados):
    global popup_portao
    temperatura = dados.get('v4', '--')
    umidade = dados.get('v5', '--')
    temperatura_var.set(f"\U0001F321 {temperatura} °C")
    umidade_var.set(f"\U0001F4A7 {umidade} %")

    # Checa alarmes
    try:
        temp = float(temperatura)
        if temp >= setpoint_temp.get() and rele_alarme_temp.get() != "Nenhum":
            frame_temp.config(bootstyle="danger")
            acionar_rele_alarme(rele_alarme_temp.get())
            mostrar_alarme("ATENÇÃO!\nTemperatura Alta")
        else:
            frame_temp.config(bootstyle="secondary")
    except:
        frame_temp.config(bootstyle="secondary")
    try:
        umid = float(umidade)
        if umid >= setpoint_umid.get() and rele_alarme_umid.get() != "Nenhum":
            frame_umid.config(bootstyle="danger")
            acionar_rele_alarme(rele_alarme_umid.get())
            mostrar_alarme("ATENÇÃO!\nUmidade Relativa Alta")
        elif umid < setpoint_umid.get() and alarme_ativo.get():  # Alarme de umidade baixa
            mostrar_alarme("ATENÇÃO!\nUmidade Relativa Baixa")
            frame_umid.config(bootstyle="danger")
        else:
            frame_umid.config(bootstyle="secondary")
    except:
        frame_umid.config(bootstyle="secondary")

    # Atualiza botões dos relés
    for nome, vpin in RELE_VPINS.items():
        estado = int(dados.get(vpin, 0))
        ESTADO[vpin] = estado
        cor = "success" if estado else "danger"
        botoes[vpin].config(bootstyle=cor)
        botoes[vpin]['text'] = f"{icones.get(nome, '')} {nome}\n{'ON' if estado else 'OFF'}"

    # Ajuste do botão mestre conforme os relés individuais
    relays = [ESTADO.get('v6', 0), ESTADO.get('v7', 0), ESTADO.get('v8', 0), ESTADO.get('v9', 0)]
    if all(r == 1 for r in relays):
        botoes['v10'].config(bootstyle="success")
        botoes['v10']['text'] = f"{icones.get('MESTRE', '')} Mestre\nON"
    else:
        botoes['v10'].config(bootstyle="danger")
        botoes['v10']['text'] = f"{icones.get('MESTRE', '')} Mestre\nOFF"

    # --- Portão: mostrar popup  alarme quando v3 estiver aberto (1) ---
    try:
        estado_portao = ESTADO.get('v3', 0)
        if estado_portao == 1 and alarme_ativo.get():
            if popup_portao is None:
                mostrar_alarme_portao("ATENÇÃO!\nPORTÃO ABERTO")
        else:
            if popup_portao:
                try:
                    # parar som antes de destruir
                    stop_alarm_sound()
                    popup_portao.destroy()
                except:
                    pass
                popup_portao = None
    except Exception:
        pass        

    # --- Atualiza histórico e gráfico ---
    try:
        temp = float(temperatura)
        umid = float(umidade)
        hora = datetime.now().strftime('%H:%M:%S')
        historico_horas.append(hora)
        historico_temp.append(temp)
        historico_umid.append(umid)
    except:
        pass

    ax.clear()
    ax.plot(list(historico_horas), list(historico_temp), label="Temperatura", color="orange")
    ax.plot(list(historico_horas), list(historico_umid), label="Umidade", color="blue")
    ax.set_title("Histórico Tempo Real")
    ax.set_xlabel("Hora")
    ax.set_ylabel("Valor")
    ax.legend()
    ax.tick_params(axis='x', rotation=45)

    # Mostra no máximo 10 rótulos espaçados, sempre os últimos
    horas = list(historico_horas)
    n = len(horas)
    max_labels = 10
    if n > 1:
        step = max(1, n // max_labels)
        xticks = [horas[i] for i in range(0, n, step)]
        # Garante que o último ponto sempre aparece como rótulo
        if horas[-1] not in xticks:
            xticks.append(horas[-1])
        ax.set_xticks(xticks)
    fig.tight_layout(rect=[0, 0.1, 1, 1])

    canvas.draw()

def acionar_rele_alarme(nome_rele):
    if nome_rele == "Nenhum":
        return
    vpin = RELE_VPINS.get(nome_rele)
    if vpin and ESTADO.get(vpin, 0) == 0:
        url = f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&{vpin}=1"
        try:
            requests.get(url)
        except:
            pass
        
#alarme_ativo = tk.BooleanVar(value=True)
popup_alarme = None
alarme_piscando = False
popup_portao = None
portao_piscando = False

def mostrar_alarme(msg):
    global popup_alarme, alarme_piscando
    if not alarme_ativo.get():
        return
    if popup_alarme is not None:
        return
    popup_alarme = tk.Toplevel(root)
    popup_alarme.overrideredirect(True)
    popup_alarme.configure(bg='red')
    popup_alarme.attributes('-topmost', True)
    largura, altura = 300, 120
    x = root.winfo_x() + (root.winfo_width() // 2) - (largura // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (altura // 2)
    popup_alarme.geometry(f"{largura}x{altura}+{x}+{y}")

    label = tk.Label(popup_alarme, text=msg, font=("Segoe UI", 10, "bold"),
                     fg="yellow", bg="red")
    label.pack(expand=True, fill='both')

    def piscar():
        if popup_alarme is None:
            return
        # alterna entre amarelo e vermelho (texto piscante visível)
        cor = "yellow" if label.cget("fg") == "red" else "red"
        label.config(fg=cor)
        popup_alarme.after(400, piscar)
    alarme_piscando = True
    piscar()

    def fechar_popup(event=None):
        global popup_alarme, alarme_piscando
        if popup_alarme:
            try:
                popup_alarme.destroy()
            except:
                pass
            popup_alarme = None
            alarme_piscando = False

    popup_alarme.bind("<Button-1>", fechar_popup)
    popup_alarme.after(8000, fechar_popup)
    
def mostrar_alarme_portao(msg):
    global popup_portao, portao_piscando
    if not alarme_ativo.get():
        return
    if popup_portao is not None:
        return
    popup_portao = tk.Toplevel(root)
    popup_portao.overrideredirect(True)
    popup_portao.configure(bg='red')
    popup_portao.attributes('-topmost', True)
    largura, altura = 300, 90
    #margem = 12
    x = root.winfo_x() + (root.winfo_width() // 2) - (largura // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (altura // 2)
    # calcula posição no canto superior direito da janela principal
    #x = root.winfo_x() + max(0, root.winfo_width() - largura - margem)
    #y = root.winfo_y() + margem
    popup_portao.geometry(f"{largura}x{altura}+{x}+{y}")

    label = tk.Label(popup_portao, text=msg, font=("Segoe UI", 12, "bold"),
                     fg="yellow", bg="red", justify='center')
    label.pack(expand=True, fill='both')

    def piscar_portao():
        if popup_portao is None:
            return
        cor = "yellow" if label.cget("fg") == "red" else "red"
        label.config(fg=cor)
        popup_portao.after(300, piscar_portao)
    portao_piscando = True
    piscar_portao()

    # inicia som do alarme (arquivo 'alarme.mp3' na mesma pasta do script)
    start_alarm_sound('alarme.mp3')

    def fechar(event=None):
        global popup_portao, portao_piscando
        # para o som ao fechar o popup
        stop_alarm_sound()
        if popup_portao:
            try:
                popup_portao.destroy()
            except:
                pass
            popup_portao = None
            portao_piscando = False

    popup_portao.bind("<Button-1>", fechar)
    popup_portao.after(12000, fechar)    

    def fechar(event=None):
        global popup_portao, portao_piscando
        if popup_portao:
            try:
                popup_portao.destroy()
            except:
                pass
            popup_portao = None
            portao_piscando = False

    popup_portao.bind("<Button-1>", fechar)
    popup_portao.after(12000, fechar)
    
import subprocess

try:
    import pygame
    PYGAME_AVAILABLE = True
    try:
        pygame.mixer.init()
    except Exception:
        PYGAME_AVAILABLE = False
except Exception:
    PYGAME_AVAILABLE = False

# winsound disponível apenas no Windows (para WAV)
if platform.system() == 'Windows':
    try:
        import winsound
    except Exception:
        winsound = None
else:
    winsound = None

# controle de reprodução
sound_thread = None
sound_playing = False
audio_process = None

def start_alarm_sound(filename='alarme.mp3'):
    """
    Tenta tocar o arquivo em loop:
    - usa pygame se disponível (suporta MP3/WAV)
    - se Windows e arquivo WAV, usa winsound (loop)
    - fallback: tenta chamar um reprodutor via subprocess (não recomendado)
    """
    global sound_thread, sound_playing, audio_process
    if sound_playing:
        return

    if not os.path.isabs(filename):
        base = os.path.dirname(__file__)
        filename = os.path.join(base, filename)

    # pygame (melhor opção)
    if PYGAME_AVAILABLE:
        try:
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play(-1)  # loop infinito
            sound_playing = True
            return
        except Exception as e:
            print("pygame play error:", e)

    # winsound (Windows, apenas WAV confiável)
    if winsound:
        try:
            # winsound requer WAV; se não for WAV, tenta tocar de qualquer forma (pode falhar)
            winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            sound_playing = True
            return
        except Exception as e:
            print("winsound error:", e)

    # Fallback: tentar usar 'ffplay' (parte do ffmpeg) para loop -- se disponível no PATH
    try:
        audio_process = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loop", "0", filename],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        sound_playing = True
        return
    except Exception as e:
        print("fallback audio error (ffplay):", e)

    print("Nenhum método de reprodução de áudio disponível. Instale pygame (pip install pygame) ou converta alarme.mp3 para alarme.wav para uso com winsound.")

def stop_alarm_sound():
    """Para a reprodução iniciada por start_alarm_sound."""
    global sound_thread, sound_playing, audio_process
    try:
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        elif winsound:
            winsound.PlaySound(None, winsound.SND_PURGE)
        elif audio_process:
            try:
                audio_process.kill()
            except:
                pass
            audio_process = None
    except Exception as e:
        print("stop sound error:", e)
    sound_playing = False    

# --- Reconhecimento de gestos: implementação simples com MediaPipe Hands ---
def trigger_gesture_action(fingers_count):
    """
    Mapear contagem de dedos para ações de relé.
    0 -> todos OFF (mestre OFF)
    5 -> todos ON (mestre ON)
    1 -> PORTAO (v3)
    2 -> SALA (v6)
    3 -> QUARTO (v7)
    4 -> CORREDOR (v8)
    """
    try:
        # 'THUMB' é gesto de "joia/ polegar" para alternar o portão (v3)
        if fingers_count == 'THUMB':
            alternar_estado('v3')
            print("Gesto: POLEGAR -> alternando PORTAO (v3)")
            return

        # 5 dedos: ligar Mestre (v10) e os relés principais (v6,v7,v8,v9), exceto v3
        if fingers_count == 5:
            for r in ['v6','v7','v8','v9']:
                try:
                    requests.get(f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&{r}=1")
                except Exception:
                    pass
            try:
                requests.get(f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&v10=1")
            except Exception:
                pass
            print("Gesto: 5 dedos -> Mestre ON (v10) e relés v6,v7,v8,v9 ligados")
            return

        # 0 dedos: desligar Mestre e relés principais
        if fingers_count == 0:
            for r in ['v6','v7','v8','v9']:
                try:
                    requests.get(f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&{r}=0")
                except Exception:
                    pass
            try:
                requests.get(f"{BLYNK_URL_SET}?token={BLYNK_TOKEN}&v10=0")
            except Exception:
                pass
            print("Gesto: 0 dedos -> Mestre OFF e relés v6,v7,v8,v9 desligados")
            return

        # Mapear contagens para relés individuais conforme solicitado
        if fingers_count == 1:
            alternar_estado('v6')  # 1 dedo -> QUARTO (v6)
            print("Gesto: 1 dedo -> alterna QUARTO (v6)")
            return
        if fingers_count == 2:
            alternar_estado('v7')  # 2 dedos -> SALA (v7)
            print("Gesto: 2 dedos -> alterna SALA (v7)")
            return
        if fingers_count == 3:
            alternar_estado('v8')  # 3 dedos -> CORREDOR (v8)
            print("Gesto: 3 dedos -> alterna CORREDOR (v8)")
            return
        if fingers_count == 4:
            alternar_estado('v9')  # 4 dedos -> GARAGEM (v9)
            print("Gesto: 4 dedos -> alterna GARAGEM (v9)")
            return
    except Exception as e:
        print("Erro ao acionar via gesto:", e)


def _gesture_count_fingers(hand_landmarks, handedness):
    """Conta dedos estendidos com base em landmarks do MediaPipe (heurística simples)."""
    # índices dos dedos: dedo polegar é tratado separadamente
    tips_ids = [4, 8, 12, 16, 20]
    count = 0
    lm = hand_landmarks.landmark
    extended = [False] * 5
    # Polegar: heurística simples comparando x do tip com o ponto anterior
    try:
        if lm[tips_ids[0]].x < lm[tips_ids[0]-1].x:
            extended[0] = True
            count += 1
    except Exception:
        pass
    # outros dedos: comparar y do ponta com y do ponto abaixo
    for idx, id in enumerate(tips_ids[1:], start=1):
        try:
            if lm[id].y < lm[id-2].y:
                extended[idx] = True
                count += 1
        except Exception:
            pass

    # Se apenas o polegar estiver estendido -> interpretar como 'THUMB' (joia/polegar)
    try:
        if count == 1 and extended[0] and not any(extended[1:]):
            return 'THUMB'
    except Exception:
        pass

    return count


def _update_preview_image_from_bgr(bgr_frame):
    """Converte BGR (OpenCV) para ImageTk e atualiza o preview_label via root.after."""
    if preview_label is None:
        return
    if not PIL_AVAILABLE:
        return
    try:
        # converte BGR -> RGB
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        # redimensionar para caber no label (usar valores do spinbox)
        try:
            w = int(preview_width_var.get())
            h = int(preview_height_var.get())
        except Exception:
            w, h = 220, 160
        img.thumbnail((w, h))
        imgtk = ImageTk.PhotoImage(image=img)

        def _setimg():
            try:
                preview_label.config(image=imgtk, text='')
                preview_label.image = imgtk
            except Exception:
                pass

        root.after(0, _setimg)
    except Exception as e:
        # não propaga erro de preview
        print("Preview error:", e)


def _update_large_preview_from_rgb(rgb_frame):
    """Atualiza a janela grande de preview (rgb_frame é um array RGB)."""
    global preview_window_open, preview_large_label
    if not preview_window_open or preview_large_label is None:
        return
    if not PIL_AVAILABLE:
        return
    try:
        img = Image.fromarray(rgb_frame)
        img.thumbnail((640, 480))
        imgtk = ImageTk.PhotoImage(image=img)

        def _setimg():
            try:
                preview_large_label.config(image=imgtk, text='')
                preview_large_label.image = imgtk
            except Exception:
                pass

        root.after(0, _setimg)
    except Exception as e:
        print("Large preview error:", e)


def gesture_worker(camera_index=0):
    # Nota: worker de gesto fica disponível, mas a captura/preview principal
    # agora é feita no thread principal via preview_loop().
    return


def start_gesture_thread():
    global gesture_thread, gesture_running
    # mantenha compatibilidade, mas não inicia mais thread separado.
    # A captura/processing é feita por preview_loop no thread principal.
    return


def stop_gesture_thread():
    global gesture_running, gesture_thread
    # compat: nothing to stop since we don't start the worker thread now
    gesture_running = False
    gesture_thread = None


# Vincular mudança do checkbutton para iniciar/parar o thread de gestos
def _on_gestos_toggle(*args):
    # Quando gestos ativados/desativados: inicia ou para a captura da câmera.
    try:
        if gestos_ativos.get():
            # iniciar captura (usa camera_index_var dentro da função se passarmos None)
            start_preview_capture(None)
        else:
            # fechar preview externo se estiver aberto e parar captura
            try:
                if preview_window_open:
                    close_preview_window()
            except Exception:
                pass
            stop_preview_capture()
            # resetar estado interno de detecção
            global gesture_hold_count, gesture_last_detected
            gesture_hold_count = 0
            gesture_last_detected = None
    except Exception as e:
        print(f"Erro no _on_gestos_toggle: {e}")

gestos_ativos.trace_add('write', lambda *a: _on_gestos_toggle())

# handler para preview externo (checkbox separado)
def _on_preview_externa_toggle(*args):
    if preview_externa_ativa.get():
        try:
            open_preview_window()
        except Exception:
            pass
    else:
        try:
            close_preview_window()
        except Exception:
            pass

# a câmera NÃO é inicializada automaticamente — inicia apenas quando
# o usuário marcar 'Gestos Ativados'.
obter_dados()
# garantir parada de threads ao fechar
def _on_close():
    try:
        stop_gesture_thread()
    except Exception:
        pass
    try:
        stop_alarm_sound()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", _on_close)
root.mainloop()
