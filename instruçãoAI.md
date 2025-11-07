<!-- Copilot / AI agent instructions for the Blink Automação repository -->
# Instruções rápidas para agentes AI (resumo)

Este repositório contém uma aplicação GUI Python principal: `Atuadorblynk.py`.
As instruções abaixo explicam o "porquê" e os pontos práticos que aceleram mudanças úteis.

- Arquivo principal: `Atuadorblynk.py` — único entrypoint GUI. Use esse arquivo para localizar a maior parte da lógica.
- Objetivo da aplicação: painel de automação residencial que: lê/escreve estados via Blynk Cloud, exibe gauges (ttkbootstrap), mostra preview de câmera, e permite controle por gestos (MediaPipe/OpenCV opcional).

Pontos arquiteturais e fluxos de dados importantes
- Comunicação com a nuvem: Blynk REST API é chamada por `obter_dados()` (GET em `BLYNK_URL_GET`) e por ações em `alternar_estado()` / `acionar_rele_alarme()` (requests para `BLYNK_URL_SET`). O estado local por cômodo é mantido no dicionário global `ESTADO`.
- UI e loop: UI é built com `ttkbootstrap` (alias `tb`) e `tkinter`. Atualizações periódicas do estado são agendadas com `root.after(3000, obter_dados)` (consulta a cada ~3s). Tome cuidado para não bloquear o thread principal.
- Gestos e preview: captura de câmera é feita por `start_preview_capture()` e o processamento por `preview_loop()` (usa OpenCV + MediaPipe quando disponíveis). A detecção usa janela de histórico (`detection_history`) e debouncing (`GESTURE_HOLD_THRESHOLD`). Função de ação é `trigger_gesture_action()`.
- Áudio/Alarmes: reprodução em `start_alarm_sound()` tenta `pygame.mixer`, depois `winsound` no Windows e por fim `ffplay` como fallback. Arquivo de som esperado: `alarme.mp3` (ou WAV para winsound).

Padrões e convenções do projeto (úteis para agente)
- Erros tratam-se com muitos blocos try/except: ao editar, preserve esse estilo defensivo e prefira falhar silenciosamente em UI non-critical.
- Widgets e wrappers: gauges possuem adaptadores `TTBGauge` e `SpeedometerGauge` com API compatível `.update(value)` e `.canvas.get_tk_widget()` — mantenha essa API ao adicionar novos widgets.
- Variáveis globais: várias partes do app usam variáveis modulares globais (ex.: `preview_label`, `preview_cap`, `ESTADO`, `temp_history`). Ao refatorar, localize e atualize todas referências.

Integrações e dependências externas
- Dependências principais (nomeadas no código): `ttkbootstrap`, `requests`, `Pillow` (`PIL`), `opencv-python` (`cv2`), `mediapipe` (`mp`), `pygame`. Nem todas são obrigatórias: gestos/preview funcionam somente se OpenCV + MediaPipe estiverem instalados.
- Plataforma: há código específico para Windows (uso de `winsound`). Teste em Windows preferencialmente para áudio com WAV.

Pontos sensíveis / segurança
- O token Blynk (`BLYNK_TOKEN`) está definido inline em `Atuadorblynk.py`. NÃO comite tokens em produção. Para mudanças que envolverem essa constante, recomende migrar para `os.getenv('BLYNK_TOKEN')` e documentar uso de variáveis de ambiente.

Como executar localmente (dev quick‑start)
1) Criar ambiente e instalar deps mínimas: `pip install ttkbootstrap requests pillow`
2) Para preview/gestos: `pip install opencv-python mediapipe` (pode ser pesado)
3) Opcional para áudio: `pip install pygame` ou ter `ffplay` no PATH
4) Executar: `python Atuadorblynk.py` (rodar numa sessão gráfica)

Arquivos e funções chave para edições rápidas (busca por nome):
- `obter_dados()` — loop de polling Blynk
- `atualizar_interface(dados)` — atualiza widgets/gauges/ESTADO
- `alternar_estado(vpin)` — dispara requests para alterar relé
- `start_preview_capture()` / `preview_loop()` — captura e detecção de gestos
- `trigger_gesture_action()` / `_gesture_count_fingers()` — mapeamento e contagem de dedos
- `SpeedometerGauge` / `TTBGauge` — implementações dos gauges
- `start_alarm_sound()` / `stop_alarm_sound()` — reprodução de alarmes

Melhores práticas específicas deste repositório
- Ao modificar polling (`obter_dados`), preserve `root.after(...)` para evitar bloquear GUI.
- Ao tocar áudio em Windows, prefira WAV se `winsound` for requerido; `pygame` suporta MP3 se instalado.
- Evite criar threads pesadas sem coordenação com `root.after`; o preview já usa `root.after` para trabalhar no main thread.

Se algo não estiver claro
- Peça para abrir trechos específicos de `Atuadorblynk.py` (por exemplo blocos em torno de preview_loop, SpeedometerGauge, e manipulação do `BLYNK_TOKEN`) e eu atualizo as instruções com exemplos de patch.

-- Fim --
