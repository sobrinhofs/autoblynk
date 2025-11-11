"""
Classe DialGauge: um gauge tipo velocímetro desenhado em tk.Canvas.
Exibe um arco de 270 graus, marcas de escala e um ponteiro (needle).
"""
import tkinter as tk
import ttkbootstrap as tb
import math

class DialGauge:
    """Gauge tipo velocímetro com arco de 270 graus.
    Parâmetros:
    - parent: widget pai (frame/window)
    - title: título do gauge
    - value: valor inicial
    - min_val/max_val: faixa de valores
    - color: cor principal do gauge
    - size: tamanho aproximado do gauge
    - unit: sufixo para o valor (ex: '°C', '%')
    - invert: inverte a orientação (sentido horário vs anti-horário)
    """
    class _CanvasWrapper:
        """Compatibilidade com API antiga"""
        def __init__(self, widget):
            self._w = widget
        def get_tk_widget(self):
            return self._w

    def __init__(self, parent, title, value=0, min_val=0, max_val=100, color='#4f81bd', size=220, unit='', invert=False):
        self.parent = parent
        self.title = title
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.color = color
        self.unit = unit
        self.invert = bool(invert)
        self.size = size

        # Frame para centralização
        self._frame = tb.Frame(self.parent)

        # Canvas com proporção altura/largura ~0.7 para semicírculo
        h = int(self.size * 0.7)
        w = int(self.size * 1.8)  # mais largo para labels não cortadas
        try:
            bg = self._frame.cget('background')
        except Exception:
            bg = 'white'
        self._canvas = tk.Canvas(self._frame, width=w, height=h, bg=bg, highlightthickness=0)
        self._canvas.pack()

        # Geometria do arco
        self.cx = w // 2
        self.cy = int(h * 0.9)  # círculo embaixo
        self.radius = int(min(self.cx, self.cy) * 0.9)

        # Desenhar fundo (arco e marcas)
        self._draw_background()

        # Ponteiro (needle) e textos (título e valor)
        self.needle = self._canvas.create_line(
            self.cx, self.cy, self.cx, self.cy - self.radius + 10,
            fill=self.color, width=3
        )
        self.value_text = self._canvas.create_text(
            self.cx, int(h*0.40),
            text=str(int(value)) + (self.unit or ''),
            font=('Segoe UI', 12, 'bold'),
            fill=self.color
        )
        self.title_text = self._canvas.create_text(
            self.cx, int(h*0.72),
            text=self.title,
            font=('Segoe UI', 9),
            fill=self.color
        )

        # Wrapper compatível com API antiga
        self.canvas = DialGauge._CanvasWrapper(self._frame)

        # Valor inicial
        self.update(value)

    def _angle_for_value(self, value):
        """Mapeia valor na faixa [min_val, max_val] para ângulo [-270°, 0°]."""
        try:
            v = max(self.min_val, min(self.max_val, value))
            if self.invert:
                # Para gauge invertido: valores altos à esquerda (-270°), baixos à direita (0°)
                frac = 1.0 - ((v - self.min_val) / max(self.max_val - self.min_val, 1))
            else:
                # Para gauge normal: valores baixos à esquerda (-270°), altos à direita (0°)
                frac = (v - self.min_val) / max(self.max_val - self.min_val, 1)
            angle = -270 + frac * 270
            return angle
        except Exception:
            return -360

    def _polar(self, angle_deg, r):
        """Converte coordenadas polares para cartesianas."""
        angle_rad = math.radians(angle_deg)
        x = self.cx + r * math.cos(angle_rad)
        y = self.cy + r * math.sin(angle_rad)
        return x, y

    def _draw_background(self):
        """Desenha arco de fundo e escala."""
        # Arco principal
        x0 = self.cx - self.radius
        y0 = self.cy - self.radius
        x1 = self.cx + self.radius
        y1 = self.cy + self.radius
        try:
            self._canvas.create_arc(
                x0, y0, x1, y1,
                start=-270, extent=270,
                style='arc', width=12,
                outline=self.color
            )
        except Exception:
            pass

        # Marcas (ticks) e rótulos
        steps = 20
        # Queremos 5 labels principais (início, 25%, 50%, 75%, fim) adaptadas à faixa min_val..max_val
        label_count = 5
        label_interval = max(1, steps // (label_count - 1))  # intervalo de ticks entre labels
        for i in range(steps + 1):
            frac = i / steps
            try:
                # Valor representado por este tick (considera inversão)
                if self.invert:
                    val = self.max_val - frac * (self.max_val - self.min_val)
                else:
                    val = self.min_val + frac * (self.max_val - self.min_val)
                angle = self._angle_for_value(val)
            except Exception:
                angle = -270 + frac * 270

            # Desenhar marca (tick)
            outer = self._polar(angle, self.radius)
            inner = self._polar(angle, self.radius - 14)
            self._canvas.create_line(
                outer[0], outer[1], inner[0], inner[1],
                fill='#333', width=2
            )

            # Desenhar labels principais: distribuídos uniformemente sobre a faixa
            if i % label_interval == 0:
                # calcular valor correspondente ao tick (usar fração exata para evitar acumulação de erro)
                lbl_val = self.min_val + frac * (self.max_val - self.min_val)
                # formatar valor como inteiro se ambos min/max forem inteiros, senão com 1 casa
                if abs(self.max_val - int(self.max_val)) < 1e-6 and abs(self.min_val - int(self.min_val)) < 1e-6:
                    label_text = str(int(round(lbl_val)))
                else:
                    label_text = f"{lbl_val:.1f}"
                label_pos = self._polar(angle, self.radius - 60)
                self._canvas.create_text(
                    label_pos[0], label_pos[1],
                    text=label_text,
                    font=('Segoe UI', 9)
                )

    def update(self, value):
        """Atualiza posição do ponteiro e texto de valor."""
        try:
            v = max(self.min_val, min(self.max_val, float(value)))
        except Exception:
            v = self.min_val

        # Atualizar ponteiro
        angle = self._angle_for_value(v)
        x, y = self._polar(angle, self.radius - 18)
        try:
            self._canvas.coords(self.needle, self.cx, self.cy, x, y)
            txt = f"{int(v)}{self.unit}"
            self._canvas.itemconfigure(self.value_text, text=txt)
        except Exception:
            pass