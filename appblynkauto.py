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

obter_dados()
root.mainloop()
