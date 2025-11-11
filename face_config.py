# --- Variáveis e configuração de face ---
try:
    # Importar o processador de face personalizado
    from face_processor import FaceProcessor
    face_processor = FaceProcessor()
    FACE_DETECTION_AVAILABLE = True
except Exception as e:
    print(f"Erro ao importar/inicializar detector facial: {e}")
    face_processor = None
    FACE_DETECTION_AVAILABLE = False

# Variáveis para controle facial
face_detected = False
face_authorized = False
last_face_check = None
FACE_CHECK_INTERVAL = 0.3  # Intervalo entre verificações
FACE_MEMORY_FRAMES = 10    # Frames para "lembrar" uma face
face_memory_counter = 0