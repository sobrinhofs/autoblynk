import os
import cv2
import sys
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from login_manager import LoginManager

class UserManager:
    def __init__(self, parent, face_processor=None):
        self.parent = parent
        self.face_processor = face_processor
        self.capture = None
        self.login_manager = LoginManager(parent)
        # Resolve corretamente o diretório de recursos quando empacotado
        def _resource_path(relative_path: str):
            try:
                base_path = sys._MEIPASS  # type: ignore[attr-defined]
            except Exception:
                base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
            return os.path.join(base_path, relative_path)

        self.faces_dir = _resource_path("faces")
        
        # Criar diretório de faces se não existir
        if not os.path.exists(self.faces_dir):
            os.makedirs(self.faces_dir)
    
    def show_add_user_window(self):
        """Abre janela para adicionar novo usuário"""
        def on_login_complete(success):
            if success and self.login_manager.is_admin():
                self._show_add_user_form()
            elif success and not self.login_manager.is_admin():
                messagebox.showerror(
                    "Erro",
                    "Apenas administradores podem cadastrar novos usuários"
                )
        
        # Verificar se já está logado como admin
        if self.login_manager.is_logged_in():
            if self.login_manager.is_admin():
                self._show_add_user_form()
            else:
                messagebox.showerror(
                    "Erro", 
                    "Apenas administradores podem cadastrar novos usuários"
                )
        else:
            # Se não estiver logado, mostrar tela de login
            self.login_manager.show_login_window(callback=on_login_complete)

    def _show_add_user_form(self):
        """Mostra o formulário de cadastro de usuário"""
        self.add_window = tk.Toplevel(self.parent)
        self.add_window.title("Adicionar Novo Usuário")
        
        # Definir dimensões maiores para a janela
        window_width = 1000
        window_height = 900
        
        # Centralizar a janela na tela
        screen_width = self.add_window.winfo_screenwidth()
        screen_height = self.add_window.winfo_screenheight()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.add_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.add_window.resizable(True, True)  # Permitir redimensionamento
        self.add_window.minsize(800, 700)  # Tamanho mínimo
        # Tentar carregar ícone 'escudo.ico' para a janela de cadastro (opcional)
        try:
            # usar caminho de recurso compatível com PyInstaller
            try:
                base_res = sys._MEIPASS  # type: ignore[attr-defined]
            except Exception:
                base_res = os.path.dirname(os.path.abspath(sys.argv[0]))
            ico_path = os.path.join(base_res, 'escudo.ico')
            if os.path.exists(ico_path):
                try:
                    self.add_window.iconbitmap(ico_path)
                except Exception:
                    try:
                        _img = tk.PhotoImage(file=ico_path)
                        self.add_window.wm_iconphoto(False, _img)
                    except Exception:
                        pass
        except Exception:
            pass
        
        # Frame superior para título e instruções
        header_frame = tb.Frame(self.add_window)
        header_frame.pack(pady=10, padx=10, fill='x')
        
        tb.Label(header_frame, 
                text="Cadastro de Novo Usuário",
                font=("Segoe UI", 12, "bold")).pack()
                
        tb.Label(header_frame,
                text="1. Digite o nome do usuário\n2. Posicione o rosto no centro da câmera\n3. Clique em 'Capturar Foto' quando a face for detectada",
                justify='left',
                font=("Segoe UI", 9)).pack(pady=5)
        
        # Frame para entrada de dados
        input_frame = tb.Frame(self.add_window)
        input_frame.pack(pady=5, padx=10, fill='x')
        
        # Campos de usuário e senha
        tb.Label(input_frame, text="Nome do Usuário:", 
                font=("Segoe UI", 10, "bold")).pack(side='left', padx=5)
        self.name_entry = tb.Entry(input_frame, width=20)
        self.name_entry.pack(side='left', padx=5)
        
        tb.Label(input_frame, text="Senha:", 
                font=("Segoe UI", 10, "bold")).pack(side='left', padx=5)
        self.password_entry = tb.Entry(input_frame, width=20, show="•")
        self.password_entry.pack(side='left', padx=5)
        
        # Checkbox para privilégios de admin (somente admin pode ver)
        if self.login_manager.is_admin():
            self.is_admin_var = tk.BooleanVar(value=False)
            tb.Checkbutton(
                input_frame,
                text="Administrador",
                variable=self.is_admin_var,
                bootstyle="danger-round-toggle"
            ).pack(side='left', padx=10)
        
        # Frame para preview da câmera
        self.preview_frame = tb.LabelFrame(self.add_window, 
                                         text="Preview da Câmera",
                                         padding=10)
        self.preview_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Container para centralizar o preview
        preview_container = tb.Frame(self.preview_frame)
        preview_container.pack(fill='both', expand=True)
        preview_container.grid_rowconfigure(0, weight=1)
        preview_container.grid_columnconfigure(0, weight=1)
        
        self.preview_label = tk.Label(preview_container, text="Inicializando câmera...")
        self.preview_label.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Frame para status e contagem
        status_frame = tb.Frame(self.add_window)
        status_frame.pack(pady=5, padx=10, fill='x')
        
        self.status_var = tk.StringVar(value="Aguardando detecção de face...")
        self.photos_count_var = tk.StringVar(value="Fotos capturadas: 0")
        
        tb.Label(status_frame, 
                textvariable=self.status_var,
                font=("Segoe UI", 9, "bold"),
                bootstyle="primary").pack(side='left', padx=5)
                
        tb.Label(status_frame,
                textvariable=self.photos_count_var,
                font=("Segoe UI", 9)).pack(side='right', padx=5)
        
        # Frame para botões
        btn_frame = tb.Frame(self.add_window)
        btn_frame.pack(pady=10, padx=10)
        
        # Botão de captura com ícone de câmera
        self.capture_btn = tb.Button(
            btn_frame,
            text="📸 Capturar Foto",
            command=self.capture_photo,
            bootstyle="success",
            width=15
        )
        self.capture_btn.pack(side='left', padx=5)
        
        # Botão de salvar com ícone
        tb.Button(
            btn_frame,
            text="💾 Concluir Cadastro",
            command=self.save_and_close,
            bootstyle="primary",
            width=15
        ).pack(side='left', padx=5)
        
        # Iniciar captura
        self.start_capture()
        
        # Configurar fechamento
        self.add_window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def start_capture(self):
        """Inicia captura da câmera"""
        try:
            self.capture = cv2.VideoCapture(0)
            if not self.capture.isOpened():
                messagebox.showerror("Erro", "Não foi possível abrir a câmera")
                self.add_window.destroy()
                return
                
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao iniciar câmera: {e}")
            self.add_window.destroy()
    
    def draw_face_guide(self, frame):
        """Desenha guias de posicionamento no frame"""
        h, w = frame.shape[:2]
        
        # Retângulo guia central (área ideal para a face)
        guide_w = int(w * 0.4)
        guide_h = int(h * 0.6)
        x1 = (w - guide_w) // 2
        y1 = (h - guide_h) // 2
        x2 = x1 + guide_w
        y2 = y1 + guide_h
        
        # Desenhar retângulo guia pontilhado
        color = (100, 200, 100)  # Verde claro
        thickness = 2
        dash_length = 20
        
        # Linhas horizontais pontilhadas
        for x in range(x1, x2, dash_length*2):
            cv2.line(frame, (x, y1), (min(x + dash_length, x2), y1), color, thickness)
            cv2.line(frame, (x, y2), (min(x + dash_length, x2), y2), color, thickness)
            
        # Linhas verticais pontilhadas    
        for y in range(y1, y2, dash_length*2):
            cv2.line(frame, (x1, y), (x1, min(y + dash_length, y2)), color, thickness)
            cv2.line(frame, (x2, y), (x2, min(y + dash_length, y2)), color, thickness)
            
        # Linhas de centro
        cv2.line(frame, (w//2, 0), (w//2, h), (80, 80, 80), 1)
        cv2.line(frame, (0, h//2), (w, h//2), (80, 80, 80), 1)
        
        return frame, (x1, y1, x2, y2)

    def update_preview(self):
        """Atualiza preview da câmera"""
        if self.capture is None or not self.capture.isOpened():
            return
            
        ret, frame = self.capture.read()
        if ret:
            # Redimensionar para um tamanho maior
            frame = cv2.resize(frame, (800, 600))
            
            # Desenhar guias de posicionamento
            frame, guide_rect = self.draw_face_guide(frame)
            
            face_in_position = False
            # Processar frame com detector facial se disponível
            if self.face_processor is not None:
                face_detected, frame = self.face_processor.process_frame(frame)
                if face_detected:
                    # Verificar se a face está dentro da área guia
                    faces = self.face_processor.face_cascade.detectMultiScale(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                        scaleFactor=1.1,
                        minNeighbors=5,
                        minSize=(80, 80)
                    )
                    
                    if len(faces) > 0:
                        x, y, w, h = faces[0]
                        face_center_x = x + w//2
                        face_center_y = y + h//2
                        
                        # Verificar se o centro da face está na área guia
                        if (guide_rect[0] < face_center_x < guide_rect[2] and
                            guide_rect[1] < face_center_y < guide_rect[3]):
                            face_in_position = True
                            cv2.putText(frame, "POSIÇÃO CORRETA", (20, 30),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Atualizar status e botão de captura
                if face_in_position:
                    self.status_var.set("✅ Face detectada - Clique em Capturar")
                    self.capture_btn.configure(state='normal')
                else:
                    self.status_var.set("⚠️ Centralize o rosto na área pontilhada")
                    self.capture_btn.configure(state='disabled')
            
            # Converter para formato tkinter
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            try:
                from PIL import Image, ImageTk
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image=image)
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
            except Exception as e:
                print(f"Erro ao atualizar preview: {e}")
        
        if self.add_window.winfo_exists():
            self.add_window.after(50, self.update_preview)
    
    def capture_photo(self):
        """Captura foto do usuário"""
        if self.capture is None or not self.capture.isOpened():
            messagebox.showerror("Erro", "Câmera não está ativa")
            return
            
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Aviso", "Digite um nome para o usuário")
            self.name_entry.focus()
            return
            
        ret, frame = self.capture.read()
        if ret:
            # Gerar nome único para o arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.jpg"
            filepath = os.path.join(self.faces_dir, filename)
            
            # Salvar imagem
            try:
                cv2.imwrite(filepath, frame)
                
                # Atualizar contador de fotos
                current_count = int(self.photos_count_var.get().split(": ")[1])
                self.photos_count_var.set(f"Fotos capturadas: {current_count + 1}")
                
                # Feedback visual e sonoro
                self.status_var.set("✅ Foto capturada com sucesso!")
                self.add_window.bell()  # Som de notificação
                
                if current_count == 0:
                    messagebox.showinfo(
                        "Primeira Foto Capturada",
                        "Foto salva com sucesso!\n\n"
                        "Recomendamos capturar mais 2-3 fotos em poses ligeiramente diferentes "
                        "para melhor reconhecimento.\n\n"
                        "Quando terminar, clique em 'Concluir Cadastro'."
                    )
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar foto: {e}")
    
    def save_and_close(self):
        """Finaliza o cadastro do usuário"""
        photos_count = int(self.photos_count_var.get().split(": ")[1])
        username = self.name_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            messagebox.showwarning("Aviso", "Preencha o nome de usuário e senha")
            return
            
        if photos_count == 0:
            if not messagebox.askyesno(
                "Nenhuma Foto",
                "Nenhuma foto foi capturada ainda.\n\n"
                "Tem certeza que deseja sair sem cadastrar?"
            ):
                return
        else:
            if messagebox.askyesno(
                "Confirmar Cadastro",
                f"Foram capturadas {photos_count} foto(s).\n\n"
                "Deseja finalizar o cadastro?"
            ):
                # Adicionar usuário ao sistema de login
                is_admin = getattr(self, 'is_admin_var', tk.BooleanVar(value=False)).get()
                success, message = self.login_manager.add_user(username, password, is_admin=is_admin)
                
                if success:
                    messagebox.showinfo(
                        "Cadastro Concluído",
                        f"Usuário cadastrado com sucesso com {photos_count} foto(s)!\n\n"
                        "O sistema já pode reconhecer este usuário."
                    )
                    self.on_closing()
                else:
                    messagebox.showerror("Erro", message)
    
    def on_closing(self):
        """Limpa recursos ao fechar"""
        if self.capture is not None:
            self.capture.release()
        self.capture = None
        try:
            self.add_window.destroy()
        except:
            pass