import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import ttk
import requests
from functools import partial
from datetime import datetime
from collections import deque
import threading
import os
import platform
# Matplotlib removido — usamos ttkbootstrap.Meter (TTBGauge) em vez de AngularGauge

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

# Variáveis de UI para mostrar o gesto atual e a ação tomada (inicializadas após root existir)
current_gesture_var = None
current_action_var = None

# Variáveis de controle do reconhecimento
gesture_thread = None
gesture_running = False
gesture_hold_count = 0
gesture_last_detected = None
GESTURE_HOLD_THRESHOLD = 6  # frames consecutivos para confirmar um gesto
# Histórico curto para estabilizar detecções por frame (reduz flicker entre 1/2)
detection_history = deque(maxlen=8)

# --- Utilitários para parsing e cores dos gauges
import re

def _to_float(val):
    """Tenta extrair um float de strings que podem conter unidades.
    Retorna None se não for possível.
    """
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if s == '--' or s == '':
            return None
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if m:
            return float(m.group(0))
    except Exception:
        pass
    return None

def _gauge_color_by_value(value, minv=0.0, maxv=100.0):
    """Retorna uma cor hex simples baseada em thresholds (verde/amarelo/vermelho).
    Ajuste thresholds conforme necessidade.
    """
    if value is None:
        return "#888888"
    try:
        ratio = (value - minv) / (maxv - minv) if maxv != minv else 0.0
    except Exception:
        ratio = 0.0
    if ratio <= 0.6:
        return "#00a050"
    elif ratio <= 0.8:
        return "#f0a000"
    else:
        return "#c00000"

def _apply_gauge_color(gauge, color):
    """Tenta aplicar a cor ao gauge de forma segura. Retorna True se aplicado.
    Suporta algumas APIs possíveis do DialGauge/TTBGauge.
    """
    try:
        # API preferida
        if hasattr(gauge, 'set_color'):
            try:
                gauge.set_color(color)
                return True
            except Exception:
                pass
        # atributo direto
        if hasattr(gauge, 'color'):
            try:
                setattr(gauge, 'color', color)
                if hasattr(gauge, 'redraw'):
                    try:
                        gauge.redraw()
                    except Exception:
                        pass
                return True
            except Exception:
                pass
        # TTBGauge wrapper (meter)
        if hasattr(gauge, 'meter') and gauge.meter is not None:
            try:
                gauge.meter.configure(barcolor=color)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False

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



# Inicialização da janela principal com tema ttkbootstrap
root = tb.Window(themename="flatly")  # Tema mais claro e moderno
root.title("Automação Residencial - Blynk")
root.geometry("1100x700")
root.minsize(600, 600)
root.resizable(True, True)

# Configurar estilos para interface clara
style = root.style
style.configure(".", background="white")  # Configuração global
style.configure("TNotebook", background="white")
style.configure("TNotebook.Tab", background="white")
style.configure("TFrame", background="white")
style.configure("TLabelframe", background="white")
style.configure("TLabelframe.Label", background="white")

setpoint_temp = tk.DoubleVar(value=35.0)
setpoint_umid = tk.DoubleVar(value=20.0)
rele_alarme_temp = tk.StringVar(value='Nenhum')
rele_alarme_umid = tk.StringVar(value='Nenhum')

# variável para ativar/desativar alarmes (mover para cima para uso no Checkbutton)
alarme_ativo = tk.BooleanVar(value=False)

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
# Checkbutton separado para abrir/fechar preview externo (removido)
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
plan_canvas.create_text((c_coords[0]+c_coords[2])//2, c_coords[1]+20, text="CORREDOR", font=("Segoe UI", 12, "bold"))

# Garagem (inferior)
g_coords = (20, 280, 500, 350)
plan_canvas.create_rectangle(*g_coords, fill='#ffffff', outline='#666666', width=2)
plan_canvas.create_text((g_coords[0]+g_coords[2])//2, g_coords[1]+20, text="GARAGEM", font=("Segoe UI", 12, "bold"))

# Espaço para controles à direita do canvas (opcional)
controls_frame = tb.Frame(frame_plan)
controls_frame.pack(side='left', fill='y', padx=8)

# NOTE: o preview + painel de debug serão inseridos em uma linha (preview_row)
preview_row = None

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
    global current_gesture_var, current_action_var
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
                    # tenta obter handedness (Left/Right) se disponível
                    handedness_label = None
                    try:
                        if results.multi_handedness and len(results.multi_handedness) > 0:
                            handedness_label = results.multi_handedness[0].classification[0].label
                    except Exception:
                        handedness_label = None
                    detected = _gesture_count_fingers(hand, handedness_label)
                    if preview_draw_landmarks.get():
                        try:
                            mp.solutions.drawing_utils.draw_landmarks(annotated, hand, mp.solutions.hands.HAND_CONNECTIONS)
                        except Exception:
                            pass
            except Exception as e:
                # falha no processing não impede preview
                print("MediaPipe processing error:", e)

        # Estabiliza detecção por histórico curto para reduzir flutuação
        stable_detected = None
        try:
            # append valor simples (None também entra)
            detection_history.append(detected)
            # calcula moda simples
            from collections import Counter
            cnt = Counter(detection_history)
            most_common, most_count = cnt.most_common(1)[0]
            # exige ao menos 4 ocorrências na janela para considerar estável
            if most_common is not None and most_count >= 4:
                stable_detected = most_common
            else:
                # se 'None' for a moda com contagem alta, mantemos None
                if most_common is None and most_count >= 4:
                    stable_detected = None
                else:
                    stable_detected = None
        except Exception:
            stable_detected = detected

        # Atualiza variável de UI com o gesto estabilizado (pode ser None)
        try:
            if current_gesture_var is not None:
                current_gesture_var.set(str(stable_detected) if stable_detected is not None else 'Nenhum')
        except Exception:
            pass

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
            # usar a detecção estabilizada (stable_detected) para o debouncing/acionamento
            if stable_detected is not None:
                if stable_detected == gesture_last_detected:
                    gesture_hold_count += 1
                else:
                    gesture_hold_count = 1
                    gesture_last_detected = stable_detected
                if gesture_hold_count >= GESTURE_HOLD_THRESHOLD:
                    # antes de acionar, atualiza ação e chama o trigger
                    try:
                        if current_action_var is not None:
                            current_action_var.set('Executando...')
                    except Exception:
                        pass
                    trigger_gesture_action(stable_detected)
                    gesture_hold_count = 0
                    gesture_last_detected = None
            else:
                # se não há detecção estável, reseta o contador
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
        # usuário fechou a janela manually: desativa gestos (desmarca checkbox)
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
# Cria uma linha que conterá o preview pequeno e o painel de debug ao lado
preview_row = tb.Frame(controls_frame)
preview_row.pack(pady=(8,6))

# Preview (pequeno) dentro da linha
preview_small_frame = tb.Frame(preview_row, width=preview_width_var.get(), height=preview_height_var.get())
preview_small_frame.pack(side='left')
preview_small_frame.pack_propagate(False)
preview_label = tk.Label(preview_small_frame, text="Preview\n(inativo)", bg="#000", fg="#fff")
preview_label.pack(fill='both', expand=True)

# Painel de debug ao lado do preview: mostra gesto detectado e ação tomada
debug_frame = tb.Frame(preview_row, width=200, height=preview_height_var.get(), padding=6)
debug_frame.pack(side='left', padx=(8,0))
debug_frame.pack_propagate(False)

# Inicializar as StringVars de debug (agora que root existe)
try:
    current_gesture_var = tk.StringVar(value='Nenhum')
    current_action_var = tk.StringVar(value='Nenhuma ação')
except Exception:
    current_gesture_var = None
    current_action_var = None

tb.Label(debug_frame, text="Debug Gestos", font=("Segoe UI", 10, 'bold')).pack(anchor='nw')
tb.Separator(debug_frame, orient='horizontal').pack(fill='x', pady=4)
tb.Label(debug_frame, text="Gesto detectado:", font=("Segoe UI", 9)).pack(anchor='w')
lbl_gesto = tb.Label(debug_frame, textvariable=current_gesture_var, font=("Segoe UI", 11, 'bold'))
lbl_gesto.pack(anchor='w', pady=(0,6))
tb.Label(debug_frame, text="Ação tomada:", font=("Segoe UI", 9)).pack(anchor='w')
lbl_acao = tb.Label(debug_frame, textvariable=current_action_var, font=("Segoe UI", 10))
lbl_acao.pack(anchor='w')

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

# --- Funções principais ---
def obter_dados():
    if not root.winfo_exists():
        return
    try:
        resposta = requests.get(BLYNK_URL_GET)
        if resposta.status_code == 200:
            dados = resposta.json()
            atualizar_interface(dados)                     
        else:
            print("Erro ao obter dados:", resposta.status_code)
    except Exception as e:
        print("Erro:", e)
    # Só agenda próxima execução se a janela ainda existir
    if root.winfo_exists():
        # atualizar a cada 3 segundos para tempo quase real
        root.after(3000, obter_dados)

def atualizar_interface(dados):
    global popup_portao
    temperatura = dados.get('v4', '--')
    umidade = dados.get('v5', '--')
    temperatura_var.set(f"\U0001F321 {temperatura} °C")
    umidade_var.set(f"\U0001F4A7 {umidade} %")
    
    t = _to_float(temperatura)
    if t is not None:
        # tc é o valor real da temperatura (24.5)
        tc = max(0.0, min(100.0, t)) 

        # >>> CORREÇÃO: Inverter o valor para compensar o bug de inversão no DialGauge
         # Se o gauge está mostrando 100 - tc, precisamos enviar 100 - (100 - tc) para que a inversão dê o valor correto.
        tc_inverted = 100.0 - tc
            
        # Atualiza o label abaixo do gauge com o valor real
        temp_value_var.set(f"{tc:.1f} °C") 

        if temp_gauge:
            # Passa o valor invertido. O gauge (invertido) irá exibi-lo corretamente como 24.5.
            temp_gauge.update(tc_inverted) # Corrigido para tc_inverted     

    # Atualiza os gauges (se existirem) com os valores numéricos
    parsed_temp_val = None
    parsed_umid_val = None
    # temperatura -> tentar extrair número robustamente
    try:
        t = _to_float(temperatura)
        if t is not None:
            # clamp para 15-45°C (valor real para rótulo e alarmes)
            tc = max(0.0, min(100.0, t))
            
            # --- CORREÇÃO: Salvar 'tc' (real) no histórico ---
            try:
                temp_history.append(tc) 
                temp_normalized = (tc - 15.0) * (100.0 / 30.0)  # Valor normalizado (ex: 29.0)
            except Exception:
                temp_normalized = None
                
            # --- CORREÇÃO: usar valor REAL (tc) para o gauge e picos ---
            parsed_temp_val = tc # <--- Mantido para picos/alarmes
            try:
                if tc is not None: 
                    temp_gauge.update(tc) # <--- ENVIA O VALOR REAL (ex: 23.7) PARA O PONTEIRO
            except Exception:
                pass
            # ---------------- Fim da Correção -------------------------

            # atualiza label numérico abaixo do gauge com valor real em °C
            try:
                if temp_value_var is not None:
                    temp_value_var.set(f"{tc:.1f} °C")
            except Exception:
                pass
            # aplicar cor dinâmica conforme o valor normalizado (0..100)
            try:
                # A cor ainda pode ser baseada no valor normalizado (0-100)
                if temp_normalized is not None:
                    col = _gauge_color_by_value(temp_normalized, minv=0.0, maxv=100.0)
                    _apply_gauge_color(temp_gauge, col)
            except Exception:
                pass
    except Exception:
        pass

    # umidade -> extrai número
    try:
        u = _to_float(umidade)
        if u is not None:
            uc = max(0.0, min(100.0, u))
            try:
                umid_history.append(uc)
            except Exception:
                pass
            parsed_umid_val = uc
            try:
                umid_gauge.update(uc)
            except Exception:
                pass
            # atualiza label numérico abaixo do gauge
            try:
                if umid_value_var is not None:
                    umid_value_var.set(f"{uc:.1f} %")
            except Exception:
                pass
            # aplicar cor dinâmica conforme o valor
            try:
                colu = _gauge_color_by_value(uc, minv=0.0, maxv=100.0)
                _apply_gauge_color(umid_gauge, colu)
            except Exception:
                pass
    except Exception:
        pass

    # redesenha os gráficos em linha (tenta não falhar se canvas ainda não estiver pronto)
    try:
        # atualiza picos por hora antes de redesenhar (usa valores já parseados quando disponíveis)
        try:
            # _update_hourly_peaks agora recebe o valor real (tc) para temperatura
            _update_hourly_peaks(parsed_temp_val, parsed_umid_val, datetime.now())
        except Exception:
            pass
        _draw_charts()
    except Exception:
        pass

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
        try:
            # Tenta encontrar o caminho base do script
            base = os.path.dirname(__file__)
        except NameError:
            # Fallback se __file__ não estiver definido (ex: REPL)
            base = os.getcwd()
        filename = os.path.join(base, filename)


    # pygame (melhor opção)
    if PYGAME_AVAILABLE:
        try:
            if not os.path.exists(filename):
                print(f"Erro Pygame: Arquivo de alarme não encontrado em {filename}")
                return
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play(-1)  # loop infinito
            sound_playing = True
            return
        except Exception as e:
            print("pygame play error:", e)

    # winsound (Windows, apenas WAV confiável)
    if winsound:
        try:
            if not os.path.exists(filename):
                print(f"Erro Winsound: Arquivo de alarme não encontrado em {filename}")
                return
            # winsound requer WAV; se não for WAV, tenta tocar de qualquer forma (pode falhar)
            winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            sound_playing = True
            return
        except Exception as e:
            print("winsound error:", e)

    # Fallback: tentar usar 'ffplay' (parte do ffmpeg) para loop -- se disponível no PATH
    try:
        if not os.path.exists(filename):
            print(f"Erro Fallback: Arquivo de alarme não encontrado em {filename}")
            return
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
    global current_action_var
    try:
        # 'THUMB' é gesto de "joia/ polegar" para alternar o portão (v3)
        if fingers_count == 'THUMB':
            alternar_estado('v3')
            print("Gesto: POLEGAR -> alternando PORTAO (v3)")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET PORTAO')
            except Exception:
                pass
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
            print("Gesto: 5 dedos -> Mestre ON")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET Mestre ON')
            except Exception:
                pass
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
            try:
                if current_action_var is not None:
                    current_action_var.set('SET Mestre OFF')
            except Exception:
                pass
            return

        # Mapear contagens para relés individuais conforme solicitado
        if fingers_count == 1:
            alternar_estado('v7')  # 1 dedo -> QUARTO (v7)
            print("Gesto: 1 dedo -> alterna QUARTO (v7)")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET QUARTO')
            except Exception:
                pass
            return
        if fingers_count == 2:
            alternar_estado('v6')  # 2 dedos -> SALA (v6)
            print("Gesto: 2 dedos -> alterna SALA (v6)")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET SALA')
            except Exception:
                pass
            return
        if fingers_count == 3:
            alternar_estado('v8')  # 3 dedos -> CORREDOR (v8)
            print("Gesto: 3 dedos -> alterna CORREDOR (v8)")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET CORREDOR')
            except Exception:
                pass
            return
        if fingers_count == 4:
            alternar_estado('v9')  # 4 dedos -> GARAGEM (v9)
            print("Gesto: 4 dedos -> alterna GARAGEM (v9)")
            try:
                if current_action_var is not None:
                    current_action_var.set('SET GARAGEM')
            except Exception:
                pass
            return
    except Exception as e:
        print("Erro ao acionar via gesto:", e)


def _gesture_count_fingers(hand_landmarks, handedness):
    """Conta dedos estendidos com base em landmarks do MediaPipe."""
    # Índices dos pontos das pontas dos dedos e suas bases
    tips_ids = [4, 8, 12, 16, 20]  # pontas dos dedos
    pips_ids = [2, 6, 10, 14, 18]  # articulações intermediárias
    count = 0
    lm = hand_landmarks.landmark
    extended = [False] * 5

    try:
        # Polegar: usar distância entre ponta do polegar e base do indicador
        thumb_tip = lm[tips_ids[0]]
        index_base = lm[5]  # base do indicador
        
        # Calcular distância entre polegar e base do indicador
        thumb_dist = ((thumb_tip.x - index_base.x)**2 + (thumb_tip.y - index_base.y)**2)**0.5
        
        # Se o polegar está suficientemente longe da base do indicador, está estendido
        if thumb_dist > 0.1:  # ajuste este valor conforme necessário
            extended[0] = True
            count += 1

        # Outros dedos: comparar posição Y da ponta com a articulação
        for i in range(1, 5):  # para os 4 dedos restantes
            tip = lm[tips_ids[i]]
            pip = lm[pips_ids[i]]
            
            # Um dedo está estendido se sua ponta está acima (Y menor) que sua articulação
            if tip.y < pip.y - 0.05:  # margem para evitar falsos positivos
                extended[i] = True
                count += 1

        # Caso especial: apenas polegar estendido = gesto "THUMB"
        if count == 1 and extended[0] and not any(extended[1:]):
            return 'THUMB'

        # Debug info
        print(f"Dedos estendidos: {extended}, Contagem: {count}")
        
    except Exception as e:
        print(f"Erro na detecção de dedos: {e}")
        return 0

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



# a câmera NÃO é inicializada automaticamente — inicia apenas quando
# o usuário marcar 'Gestos Ativados'.

# --- Aba Dashboards ---
# Criar a aba de Dashboards antes do mainloop para que apareça na interface
frame_dashboard = ttk.Frame(notebook)
notebook.add(frame_dashboard, text="Dashboards")

# AngularGauge (Matplotlib) removido — usamos TTBGauge (ttkbootstrap.Meter) agora.


# Frame para centralizar os gauges
gauge_frame = tb.Frame(frame_dashboard)
gauge_frame.pack(expand=True, fill='both', padx=20, pady=20)

# Linha acima dos gauges: mostra temperatura e umidade com ícones (sem setpoint/reles)
top_values_row = tb.Frame(gauge_frame)
top_values_row.pack(fill='x', pady=(0,12))

# Temperatura (à esquerda) — usar LabelFrame parecido com a aba Home, sem setpoint/relés
temp_dashboard_frame = tb.LabelFrame(top_values_row, text="Temperatura", bootstyle="secondary", padding=6)
temp_dashboard_frame.pack(side='left', expand=True, fill='x', padx=(0,8))
tb.Label(temp_dashboard_frame, textvariable=temperatura_var, font=("Segoe UI", 14, 'bold'), bootstyle="warning").pack(anchor='w')

# Umidade (à direita) — LabelFrame como na Home
umid_dashboard_frame = tb.LabelFrame(top_values_row, text="Umidade", bootstyle="secondary", padding=6)
umid_dashboard_frame.pack(side='right', expand=True, fill='x', padx=(8,0))
tb.Label(umid_dashboard_frame, textvariable=umidade_var, font=("Segoe UI", 14, 'bold'), bootstyle="info").pack(anchor='e')

# Frame interno para alinhar os gauges horizontalmente no centro
gauge_container = tb.Frame(gauge_frame)
gauge_container.pack(expand=True)
# (Classe TTBGauge definida abaixo para ser usada pelas instâncias)

# Alternativa: gauge usando ttkbootstrap.Meter para um visual nativo e leve.
class TTBGauge:
    """Adapter simples que usa tb.Meter e expõe a API usada pelo código existente:
    - .update(value)
    - .canvas.get_tk_widget() -> widget (para pack)
    """
    class _CanvasWrapper:
        def __init__(self, widget):
            self._w = widget
        def get_tk_widget(self):
            return self._w

    def __init__(self, parent, title, value=0, min_val=0, max_val=100, color='#4f81bd'):
        self.parent = parent
        self.title = title
        self.min_val = min_val
        self.max_val = max_val

        # frame que contém o Meter
        self._frame = tb.Frame(self.parent)

        # escolher bootstyle aproximado pelo parâmetro de cor
        bootstyle = 'success' if color and (color.startswith('#00') or 'green' in color.lower()) else 'danger'

        # criar o Meter — amount será percentual (0-100)
        try:
            self.meter = tb.Meter(self._frame, metersize=160, amount=0, subtext=title, bootstyle=bootstyle)
            # empacotar o meter dentro do frame
            try:
                self.meter.pack(expand=True)
            except Exception:
                pass
        except Exception:
            # fallback para versões de ttkbootstrap que não tenham Meter
            self.meter = tb.Label(self._frame, text=title)

        # wrapper compatível com API antiga
        self.canvas = TTBGauge._CanvasWrapper(self._frame)

        # set initial value
        self.update(value)

    def update(self, value):
        # normalize to 0-100
        try:
            span = max(self.max_val - self.min_val, 1)
            pct = int((max(self.min_val, min(self.max_val, value)) - self.min_val) / span * 100)
        except Exception:
            pct = 0
        try:
            # Meter espera amount em 0-100
            if hasattr(self.meter, 'configure'):
                self.meter.configure(amount=pct)
            else:
                # se meter for apenas um Label (fallback), atualizar texto
                self.meter.config(text=f"{self.title}\n{int(value)}")
        except Exception:
            pass

# Importar a classe DialGauge do módulo dial_gauge
# (Certifique-se que dial_gauge.py está na mesma pasta)
try:
    from dial_gauge import DialGauge
except ImportError:
    print("ERRO: Não foi possível importar 'dial_gauge.py'. O gauge não funcionará.")
    print("Certifique-se que o arquivo 'dial_gauge.py' está na mesma pasta que 'AutoBlynk.py'.")
    # Cria um substituto simples para evitar que o app quebre
    class DialGauge:
        class _DummyCanvas:
            def __init__(self, w): self._w = w
            def get_tk_widget(self): return self._w
        def __init__(self, parent, title, *args, **kwargs):
            self._w = tb.Label(parent, text=f"Erro: '{title}'\n dial_gauge.py não encontrado.", bootstyle="danger")
            self.canvas = DialGauge._DummyCanvas(self._w)
        def update(self, val):
            pass


# Instanciar gauges tipo velocímetro para Temperatura e Umidade
# Colocar cada gauge dentro do seu LabelFrame respectivo (Dashboard)
# Assim os gauges ficam próximos aos valores/controles correspondentes

temp_gauge = DialGauge(temp_dashboard_frame, 'Temperatura', 0, 0, 50, color='#c00000', size=220, unit=' °C', invert=True)
temp_gauge.canvas.get_tk_widget().pack(fill='both', expand=True, padx=6, pady=(6,4))

umid_gauge = DialGauge(umid_dashboard_frame, 'Umidade', 0, 0, 100, color='#007f00', size=220, unit=' %', invert=False)
umid_gauge.canvas.get_tk_widget().pack(fill='both', expand=True, padx=6, pady=(6,4))

# Labels de valor em tempo real (numérico) abaixo de cada gauge (opcional, duplicado com o texto interno)
try:
    temp_value_var = tk.StringVar(value='-- °C')
    umid_value_var = tk.StringVar(value='-- %')
except Exception:
    temp_value_var = None
    umid_value_var = None

# Colocar os labels dentro dos frames dos gauges para alinhamento
try:
    if temp_value_var is not None:
        tb.Label(temp_gauge.canvas.get_tk_widget(), textvariable=temp_value_var,
                 font=("Segoe UI", 12, 'bold'), bootstyle='warning').pack(pady=(6,0))
    if umid_value_var is not None:
        tb.Label(umid_gauge.canvas.get_tk_widget(), textvariable=umid_value_var,
                 font=("Segoe UI", 12, 'bold'), bootstyle='info').pack(pady=(6,0))
except Exception:
    pass

# --- Mini-gráfico combinado (histórico) abaixo dos gauges ---
# Históricos em memória (últimos N pontos)
from collections import deque as _deque
HISTORY_MAX = 240
temp_history = _deque(maxlen=HISTORY_MAX)
umid_history = _deque(maxlen=HISTORY_MAX)

# Histórico de picos por hora (últimas N horas)
HOUR_PEAKS_MAX = 72  # guarda ~3 dias se desejar
hour_peaks_temp = _deque(maxlen=HOUR_PEAKS_MAX)
hour_peaks_umid = _deque(maxlen=HOUR_PEAKS_MAX)
hour_peaks_times = _deque(maxlen=HOUR_PEAKS_MAX)
# estado do bucket da hora corrente (não preenchido na inicialização)
_current_hour_ts = None
_current_hour_temp_peak = None
_current_hour_umid_peak = None

def _update_hourly_peaks(t_val, u_val, ts=None):
    """Atualiza o bucket do pico por hora.
    - t_val, u_val: valores atuais (reais, ex: 23.7°C e 56%) ou None
    - ts: datetime do sample (se None usa now())
    Lógica:
    - mantém um bucket para a hora atual (ex.: 2025-11-07 14:00:00)
    - dentro da hora atual atualiza o máximo observado
    - ao entrar em uma nova hora, empurra o pico da hora anterior para a fila
    """
    global _current_hour_ts, _current_hour_temp_peak, _current_hour_umid_peak
    try:
        if ts is None:
            ts = datetime.now()
        hour_ts = ts.replace(minute=0, second=0, microsecond=0)

        # primeira amostra
        if _current_hour_ts is None:
            _current_hour_ts = hour_ts
            _current_hour_temp_peak = float(t_val) if t_val is not None else None
            _current_hour_umid_peak = float(u_val) if u_val is not None else None
            return

        # mesma hora: atualizar máximos
        if hour_ts == _current_hour_ts:
            if t_val is not None:
                try:
                    if _current_hour_temp_peak is None:
                        _current_hour_temp_peak = float(t_val)
                    else:
                        _current_hour_temp_peak = max(_current_hour_temp_peak, float(t_val))
                except Exception:
                    _current_hour_temp_peak = float(t_val)
            if u_val is not None:
                try:
                    if _current_hour_umid_peak is None:
                        _current_hour_umid_peak = float(u_val)
                    else:
                        _current_hour_umid_peak = max(_current_hour_umid_peak, float(u_val))
                except Exception:
                    _current_hour_umid_peak = float(u_val)
            return

        # hora avançou: empurra o bucket anterior para as filas (pode haver saltos de várias horas)
        try:
            hour_peaks_temp.append(_current_hour_temp_peak if _current_hour_temp_peak is not None else 0.0)
            hour_peaks_umid.append(_current_hour_umid_peak if _current_hour_umid_peak is not None else 0.0)
            hour_peaks_times.append(_current_hour_ts)
        except Exception:
            pass

        # iniciar novo bucket com a amostra atual
        _current_hour_ts = hour_ts
        _current_hour_temp_peak = float(t_val) if t_val is not None else None
        _current_hour_umid_peak = float(u_val) if u_val is not None else None
    except Exception:
        # não deixar falhas quebrarem a UI
        return

# Frame que contém o gráfico combinado (posicionado abaixo dos gauges)
charts_frame = tb.Frame(gauge_frame)
charts_frame.pack(fill='both', pady=(12,0), expand=True)

# Canvas único para ambos (temperatura e umidade)
COMBINED_CHART_W = 1040
COMBINED_CHART_H = 160
combined_chart_canvas = tk.Canvas(charts_frame, width=COMBINED_CHART_W, height=COMBINED_CHART_H, bg='#ffffff', highlightthickness=1, highlightbackground='#cccccc')
combined_chart_canvas.pack(fill='both', expand=True)

def _draw_combined_chart(canvas, temp_data, umid_data):
    """Desenha um gráfico combinado (duas linhas) no mesmo canvas.
    temp_data (15-45) e umid_data (0-100).
    """
    try:
        canvas.delete('all')
        w = int(canvas.winfo_width() or COMBINED_CHART_W)
        h = int(canvas.winfo_height() or COMBINED_CHART_H)

        # fundo
        canvas.create_rectangle(0, 0, w, h, fill=canvas['bg'], outline='')

        # título e última leitura (à direita)
        # (Usa os dados reais do histórico)
        last_t = f"T: {temp_data[-1]:.1f}°C" if temp_data else "T: --"
        last_u = f"H: {umid_data[-1]:.1f}%" if umid_data else "H: --"
        canvas.create_text(8, 6, text='Histórico (Temperatura / Umidade)', anchor='nw', font=('Segoe UI', 9, 'bold'))
        canvas.create_text(w - 8, 6, text=f"{last_t}   {last_u}", anchor='ne', font=('Segoe UI', 9))

        # Margens
        left = 36
        right = 12
        top = 26
        bottom = 18
        plot_w = max(10, w - left - right)
        plot_h = max(10, h - top - bottom)

        # desenhar apenas rótulos Y (0,25,50,75,100) sem linhas de grade
        # (Esta escala agora representa % da altura do gráfico, não valores)
        for v in (0, 25, 50, 75, 100):
            y = top + (100 - v) / 100.0 * plot_h
            canvas.create_text(6, y, text=str(v), anchor='w', font=('Segoe UI', 7), fill='#666')

        # --- CORREÇÃO MANTIDA: Mapear pontos usando min/max para normalizar ---
        def _map_points(data, min_val=0.0, max_val=100.0): # MANTIDO
            n = len(data)
            pts = []
            if n == 0:
                return pts
            span = max(max_val - min_val, 1) # Evita divisão por zero
            for i, val in enumerate(data):
                x = left + (i / max(1, n-1)) * plot_w if n > 1 else left + plot_w/2
                # Normaliza o valor aqui dentro
                try:
                    normalized_val = (float(val) - min_val) / span
                except Exception:
                    normalized_val = 0.0
                y = top + (1.0 - max(0, min(1.0, normalized_val))) * plot_h # MANTIDO
                pts.append((x, y))
            return pts

        t_pts = _map_points(temp_data, min_val=15.0, max_val=45.0) # MANTIDO
        u_pts = _map_points(umid_data, min_val=0.0, max_val=100.0) # MANTIDO
        # --------------------- Fim da Correção MANTIDA -------------------------


        # desenhar linhas com suavização
        # Desenhar apenas as linhas principais de temperatura e umidade
        if t_pts:
            t_flat = [coord for p in t_pts for coord in p]
            canvas.create_line(*t_flat, fill='#c00000', width=2, smooth=True)
        if u_pts:
            u_flat = [coord for p in u_pts for coord in p]
            canvas.create_line(*u_flat, fill='#007f00', width=2, smooth=True)

        # Desenhar rótulos de tempo no eixo X (até 6 labels) — sem pequenos ticks verticais
        try:
            num_samples = len(temp_data)
            if num_samples > 1:
                # Calcula o tempo total em minutos (assumindo 1 sample a cada 3s)
                total_min = (num_samples * 3.0) / 60.0
                num_ticks = min(6, max(2, int(plot_w // 120)))
                
                for i in range(num_ticks):
                    x = left + (i / (num_ticks - 1)) * plot_w
                    # Calcula o rótulo em minutos
                    min_label = (i / (num_ticks - 1)) * total_min
                    label = f"{min_label:.0f} min"
                    
                    canvas.create_text(x, h - 4, text=label, anchor='s', font=('Segoe UI', 7), fill='#666')
        except Exception:
            pass

        # legenda simples (O código original já estava correto aqui)
        legend_x = left + 6
        legend_y = h - bottom + 2
        canvas.create_rectangle(legend_x, legend_y-8, legend_x+12, legend_y+4, fill='#c00000', outline='')
        canvas.create_text(legend_x+16, legend_y, text='Temperatura (°C)', anchor='w', font=('Segoe UI', 8))
        canvas.create_rectangle(legend_x+150, legend_y-8, legend_x+162, legend_y+4, fill='#007f00', outline='')
        canvas.create_text(legend_x+166, legend_y, text='Umidade (%)', anchor='w', font=('Segoe UI', 8))

    except Exception as e:
        print(f"Erro ao desenhar gráfico: {e}")
        pass

def _draw_charts():
    _draw_combined_chart(combined_chart_canvas, list(temp_history), list(umid_history))

obter_dados()
# garantir parada de threads ao fechar
def _on_close():
    try:
        # Cancela todos os callbacks pendentes
        root.after_cancel('all')
    except Exception:
        pass
    try:
        stop_gesture_thread()
    except Exception:
        pass
    try:
        stop_alarm_sound()
    except Exception:
        pass
    try:
        # Limpa referências dos gauges
        global temp_gauge, umid_gauge
        if temp_gauge:
            temp_gauge.canvas.get_tk_widget().destroy()
            temp_gauge = None
        if umid_gauge:
            umid_gauge.canvas.get_tk_widget().destroy()
            umid_gauge = None
    except Exception:
        pass
    root.quit()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", _on_close)


if __name__ == '__main__':
    try:
        root.mainloop()
    except KeyboardInterrupt:
        # permite encerrar com Ctrl+C quando executado a partir do terminal
        _on_close()
