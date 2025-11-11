import tkinter as tk
import ttkbootstrap as tb
from tkinter import messagebox
import os
import json
import sys

class LoginManager:
    def __init__(self, parent):
        self.parent = parent
        # Usar caminho absoluto no mesmo diretório do executável
        try:
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.argv[0])))
            self.users_file = os.path.join(base_dir, "users.json")
        except Exception:
            self.users_file = "users.json"  # fallback para o diretório atual
        self.current_user = None
        self._load_users()
    
    def _load_users(self):
        """Carrega usuários do arquivo JSON"""
        if not os.path.exists(self.users_file):
            self._save_users({})
            self.users = {}
            return

        try:
            with open(self.users_file, 'r') as f:
                content = f.read().strip()
                if not content:  # arquivo vazio
                    self.users = {}
                    return
                    
                # tenta fazer parse do JSON
                self.users = json.loads(content)
                if not self.users:  # se for {} vazio
                    self.users = {}
                
        except json.JSONDecodeError:
            # arquivo corrompido ou mal formatado
            self.users = {}
            # faz backup do arquivo corrompido
            try:
                backup_file = self.users_file + '.bak'
                os.rename(self.users_file, backup_file)
                print(f"Arquivo corrompido. Backup salvo em: {backup_file}")
            except:
                pass
        except:
            self.users = {}
    
    def _save_users(self, users_data):
        """Salva usuários no arquivo JSON"""
        try:
            with open(self.users_file, 'w') as f:
                json.dump(users_data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar usuários: {e}")
    
    def add_user(self, username, password, is_admin=None):
        """Adiciona um novo usuário
        
        Args:
            username: nome do usuário
            password: senha do usuário
            is_admin: se True, será admin; se None, será admin apenas se for o primeiro usuário
        """
        if not username or not password:
            return False, "Usuário e senha são obrigatórios"
            
        if username in self.users:
            return False, "Usuário já existe"
            
        # Define privilégios de admin
        if is_admin is None:
            is_admin = len(self.users) == 0  # primeiro usuário é admin
            
        self.users[username] = {
            "password": password,
            "is_admin": bool(is_admin)  # garante que seja boolean
        }
        
        # Debug para ver o que está sendo salvo
        print(f"\nAdicionando usuário: {username}")
        print(f"Admin: {self.users[username]['is_admin']}")
        
        self._save_users(self.users)
        return True, "Usuário cadastrado com sucesso"
    
    def login(self, username, password):
        """Verifica credenciais e faz login"""
        if username not in self.users:
            return False, "Usuário não encontrado"
            
        if self.users[username]["password"] != password:
            return False, "Senha incorreta"
            
        self.current_user = username
        return True, "Login realizado com sucesso"
    
    def is_logged_in(self):
        """Verifica se há usuário logado"""
        return self.current_user is not None
    
    def is_admin(self):
        """Verifica se usuário atual é admin"""
        if not self.current_user:
            return False
        return self.users[self.current_user].get("is_admin", False)
    
    def logout(self):
        """Faz logout do usuário atual"""
        self.current_user = None
    
    def debug_show_users(self):
        """Método de debug para mostrar usuários cadastrados"""
        try:
            with open(self.users_file, 'r') as f:
                users_data = json.load(f)
            print("\n=== Usuários Cadastrados ===")
            print(f"Arquivo: {self.users_file}")
            for username, data in users_data.items():
                is_admin = data.get('is_admin', False)
                print(f"Usuário: {username} | Admin: {is_admin}")
            print("===========================\n")
        except Exception as e:
            print(f"Erro ao ler arquivo de usuários: {e}")
    
    def show_login_window(self, callback=None):
        """Mostra janela de login"""
        login_window = tk.Toplevel(self.parent)
        login_window.title("Login")
        login_window.geometry("500x400")  # Aumentei a altura para acomodar os botões
        login_window.resizable(False, False)
        
        # Carregar ícone
        try:
            try:
                base_res = sys._MEIPASS
            except Exception:
                base_res = os.path.dirname(os.path.abspath(sys.argv[0]))
            ico_path = os.path.join(base_res, 'escudo.ico')
            if os.path.exists(ico_path):
                try:
                    login_window.iconbitmap(ico_path)
                except Exception:
                    try:
                        _img = tk.PhotoImage(file=ico_path)
                        login_window.wm_iconphoto(False, _img)
                    except Exception:
                        pass
        except Exception:
            pass
        
        # Centralizar na tela
        login_window.transient(self.parent)
        login_window.grab_set()
        
        def center_window():
            login_window.update_idletasks()
            width = login_window.winfo_width()
            height = login_window.winfo_height()
            x = (login_window.winfo_screenwidth() // 2) - (width // 2)
            y = (login_window.winfo_screenheight() // 2) - (height // 2)
            login_window.geometry(f'{width}x{height}+{x}+{y}')
        center_window()
        
        # Frame principal com título
        main_frame = tb.Frame(login_window, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # Título com ícone
        tb.Label(
            main_frame,
            text="🔐 Login do Sistema",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        ).pack(pady=(0,15))
        
        # Campos de usuário e senha
        tb.Label(main_frame, text="👤 Usuário:", font=("Segoe UI", 10)).pack(anchor='w')
        username_entry = tb.Entry(main_frame, width=30)
        username_entry.pack(pady=(0,10))
        
        tb.Label(main_frame, text="🔑 Senha:", font=("Segoe UI", 10)).pack(anchor='w')
        password_entry = tb.Entry(main_frame, width=30, show="•")
        password_entry.pack(pady=(0,20))
        
        # Frame para os botões
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(pady=5)
        
        def handle_login():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            
            if not username or not password:
                messagebox.showwarning("Aviso ⚠️", "Preencha todos os campos")
                return
                
            success, message = self.login(username, password)
            if success:
                login_window.destroy()
                if callback:
                    callback(True)
            else:
                # Mensagem mais amigável
                if "não encontrado" in message:
                    # Encontrar usuários admin para mostrar na dica
                    admin_users = []
                    for user, data in self.users.items():
                        if data.get('is_admin', False):
                            admin_users.append(user)
                    
                    if admin_users:
                        admin_list = ", ".join(admin_users)
                        messagebox.showerror(
                            "Erro ❌",
                            f"Usuário não encontrado!\n\n" +
                            f"Dica: Os seguintes usuários são administradores:\n" +
                            f"{admin_list}"
                        )
                    else:
                        messagebox.showerror(
                            "Erro ❌",
                            "Usuário não encontrado!\nVerifique se digitou corretamente."
                        )
                elif "incorreta" in message:
                    messagebox.showerror(
                        "Erro ❌",
                        "Senha incorreta!\nTente novamente."
                    )
                else:
                    messagebox.showerror("Erro ❌", message)
                password_entry.delete(0, 'end')  # Limpa a senha
                password_entry.focus()  # Foco no campo de senha
                if callback:
                    callback(False)
        
        # Botão OK (Entrar)
        tb.Button(
            btn_frame,
            text="OK",
            command=handle_login,
            bootstyle="success",
            width=10
        ).pack(side='left', padx=5)
        
        def handle_cancel():
            if callback:
                callback(False)  # Avisa que o login foi cancelado
            login_window.destroy()
            
        # Botão Cancelar
        tb.Button(
            btn_frame,
            text="Cancelar",
            command=handle_cancel,
            bootstyle="secondary",
            width=10
        ).pack(side='left', padx=5)
        
        # Se não houver usuários cadastrados, mostrar botão de primeiro cadastro
        if not self.users:
            # Quando não há usuários, mostrar apenas a tela de criação do primeiro admin
            login_window.title("Criar Primeiro Usuário")
            
            # Esconder campos de login normal
            for widget in btn_frame.winfo_children():
                widget.pack_forget()
            
            def handle_first_signup():
                username = username_entry.get().strip()
                password = password_entry.get().strip()
                
                if not username or not password:
                    messagebox.showwarning(
                        "Aviso ⚠️", 
                        "Preencha o nome de usuário e senha para criar o administrador"
                    )
                    return
                
                # Força o primeiro usuário como admin
                success, message = self.add_user(username, password, is_admin=True)
                if success:
                    messagebox.showinfo(
                        "Sucesso ✅",
                        "Usuário administrador criado com sucesso!\n\n" +
                        "👉 Agora você pode fazer login."
                    )
                    login_window.destroy()
                    # Abrir nova janela de login
                    self.show_login_window(callback)
                else:
                    messagebox.showerror("Erro ❌", message)
            
            # Frame para primeiro acesso (mais destacado)
            first_access_frame = tb.Frame(main_frame)
            first_access_frame.pack(fill='x', pady=10)
            
            tb.Label(
                first_access_frame,
                text="⚠️ Nenhum usuário cadastrado!",
                font=("Segoe UI", 11, "bold"),
                bootstyle="warning"
            ).pack(pady=(0,10))
            
            tb.Label(
                first_access_frame,
                text="📝 Crie o primeiro usuário administrador:",
                font=("Segoe UI", 10, "bold"),
                bootstyle="info"
            ).pack(pady=(0,5))
            
            # Botão mais destacado
            tb.Button(
                first_access_frame,
                text="✨ Criar Usuário Administrador",
                command=handle_first_signup,
                bootstyle="success",
                width=25
            ).pack(pady=10)
            
            # Botão para sair
            tb.Button(
                first_access_frame,
                text="❌ Cancelar",
                command=handle_cancel,
                bootstyle="secondary",
                width=25
            ).pack()
        
        # Foco inicial no campo de usuário
        username_entry.focus()
        
        # Enter em qualquer campo faz login
        def on_enter(event):
            handle_login()
        username_entry.bind('<Return>', on_enter)    
        password_entry.bind('<Return>', on_enter)
        
        # Escape fecha a janela
        login_window.bind('<Escape>', lambda e: handle_cancel())
        
        # Aguardar fechamento da janela
        login_window.wait_window()