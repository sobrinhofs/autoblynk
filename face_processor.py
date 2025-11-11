import cv2
import numpy as np
from datetime import datetime, timedelta

class FaceProcessor:
    def __init__(self):
        try:
            # Carregar o classificador Haar Cascade para faces
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
            
            # Histórico de detecções para estabilização
            self.detection_history = []
            self.history_max_size = 30
            self.min_confidence = 0.6  # Mínimo de frames positivos na janela
            
            # Controle de tempo
            self.last_check = None
            self.check_interval = 0.2  # segundos
            
            # Estado atual
            self.face_detected = False
            self.face_authorized = False
            
            print("FaceProcessor inicializado com sucesso")
            
        except Exception as e:
            print(f"Erro ao inicializar FaceProcessor: {e}")
            self.face_cascade = None
            self.eye_cascade = None
            
    def draw_face_guide(self, frame, face_detected=False):
        """Desenha guias de posicionamento no frame"""
        if frame is None:
            return frame, None
            
        h, w = frame.shape[:2]
        
        # Retângulo guia central (área ideal para a face)
        guide_w = int(w * 0.4)
        guide_h = int(h * 0.6)
        x1 = (w - guide_w) // 2
        y1 = (h - guide_h) // 2
        x2 = x1 + guide_w
        y2 = y1 + guide_h
        
        # Definir cor baseada na detecção
        color = (0, 255, 0) if face_detected else (0, 0, 255)  # Verde se detectado, vermelho se não
        thickness = 2
        
        # Desenhar retângulo guia
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        
        # Linhas de centro
        cv2.line(frame, (w//2, 0), (w//2, h), color, 1)
        cv2.line(frame, (0, h//2), (w, h//2), color, 1)
        
        # Adicionar texto de status
        status_text = "Face Detectada" if face_detected else "Aguardando Face"
        cv2.putText(frame, status_text, (10, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Desenhar marcadores nos pontos de referência
        face_points = [
            ((x1 + x2)//2, y1 + int(guide_h * 0.2)),  # Topo da cabeça
            (x1 + int(guide_w * 0.3), y1 + int(guide_h * 0.35)),  # Olho esquerdo
            (x1 + int(guide_w * 0.7), y1 + int(guide_h * 0.35)),  # Olho direito
            ((x1 + x2)//2, y1 + int(guide_h * 0.5)),  # Nariz
            ((x1 + x2)//2, y1 + int(guide_h * 0.7))   # Boca
        ]
        
        for point in face_points:
            cv2.circle(frame, point, 3, color, -1)
            
        return frame, (x1, y1, x2, y2)
    
    def process_frame(self, frame):
        """
        Processa um frame para detecção facial aprimorada.
        Retorna: (face_detected, annotated_frame)
        """
        if self.face_cascade is None:
            return False, frame
            
        try:
            # Controle de taxa de verificação
            now = datetime.now()
            if self.last_check and (now - self.last_check).total_seconds() < self.check_interval:
                return self.face_detected, self.draw_face_guide(frame.copy(), self.face_detected)[0]
                
            self.last_check = now
            
            # Converter para escala de cinza
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Corrigido para GRAY
            gray = cv2.equalizeHist(gray)  # Melhorar contraste
            
            # Detectar faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.3,
                minNeighbors=6,
                minSize=(60, 60),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Atualizar histórico
            self.detection_history.append(len(faces) > 0)
            if len(self.detection_history) > self.history_max_size:
                self.detection_history.pop(0)
                
            # Calcular confiança baseada no histórico
            if self.detection_history:
                confidence = sum(self.detection_history) / len(self.detection_history)
                self.face_detected = confidence >= self.min_confidence
            else:
                self.face_detected = False
            
            # Criar uma cópia do frame para desenhar
            annotated_frame = frame.copy()
            
            # Desenhar guia de face com cor baseada na detecção
            annotated_frame, guide_rect = self.draw_face_guide(annotated_frame, self.face_detected)
            
            # Processar cada face detectada
            for (x, y, w, h) in faces:
                # Desenhar retângulo em volta da face
                color = (0, 255, 0) if self.face_detected else (0, 0, 255)
                cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), color, 2)
                
                # ROI para detecção de olhos
                roi_gray = gray[y:y+h, x:x+w]
                
                # Detectar olhos
                eyes = self.eye_cascade.detectMultiScale(roi_gray)
                
                # Status texto com cor dinâmica
                status = "Face + Olhos" if len(eyes) >= 2 else "Face Detectada"
                cv2.putText(annotated_frame, status, (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                           
                # Desenhar pontos dos olhos se detectados
                for (ex, ey, ew, eh) in eyes:
                    center = (x + ex + ew//2, y + ey + eh//2)
                    cv2.circle(annotated_frame, center, 3, color, -1)
                
                # Pontos de referência (aproximados)
                eye_y = y + int(h * 0.35)
                left_eye_x = x + int(w * 0.3)
                right_eye_x = x + int(w * 0.7)
                nose_x = x + int(w * 0.5)
                nose_y = y + int(h * 0.5)
                mouth_y = y + int(h * 0.7)
                
                # Desenhar pontos de referência
                cv2.circle(frame, (left_eye_x, eye_y), 3, (255, 255, 255), -1)
                cv2.circle(frame, (right_eye_x, eye_y), 3, (255, 255, 255), -1)
                cv2.circle(frame, (nose_x, nose_y), 3, (255, 255, 255), -1)
                cv2.circle(frame, (nose_x, mouth_y), 3, (255, 255, 255), -1)
                
            return self.face_detected, annotated_frame
            
        except Exception as e:
            print(f"Erro no processamento facial: {e}")
            # Em caso de erro, desenhar guia vermelho
            annotated = frame.copy()
            annotated, _ = self.draw_face_guide(annotated, False)
            return False, annotated