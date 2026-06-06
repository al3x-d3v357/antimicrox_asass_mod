import sys
import os
import shutil
import zipfile
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QLabel, QFrame, QGraphicsDropShadowEffect, QStyleFactory)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor, QPalette

# ==============================================================================
# 1. LÓGICA DE NEGÓCIOS (Substitui o asass-mod.ps1)
# ==============================================================================
class AntiMicroXManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.ini_path = os.path.join(base_dir, "bin", "antimicrox_settings.ini")
        self.ps1_dir = os.path.join(base_dir, "ps1")
        self.ps3_dir = os.path.join(base_dir, "ps3")

    def _backup_settings(self):
        """Cria um backup rápido das configurações atuais antes de modificá-las."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(self.base_dir, "bin", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"antimicrox_settings.ini.{timestamp}.bak")
        shutil.copy2(self.ini_path, backup_path)
        return os.path.basename(backup_path)

    def setup(self, clean_missing=False):
        """
        Corrige os caminhos absolutos no arquivo .ini, re-ancorando-os ao diretório atual.
        Se clean_missing for True, zera referências a perfis inexistentes.
        """
        if not os.path.exists(self.ini_path):
            raise FileNotFoundError(f"Arquivo de configurações não encontrado: {self.ini_path}")

        backup_name = self._backup_settings()
        
        ps1_dir_fwd = self.ps1_dir.replace('\\', '/')
        ps3_dir_fwd = self.ps3_dir.replace('\\', '/')
        
        fixed = 0
        cleaned = 0
        new_lines = []

        with open(self.ini_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_section = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                new_lines.append(line)
                continue

            if '=' in line and current_section in ('General', 'Controllers'):
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()

                if key == "LastProfileDir":
                    new_lines.append(f"{key}={ps1_dir_fwd}\n")
                    fixed += 1
                    continue

                # Identifica chaves de mapeamento de perfil do controle
                is_profile_key = ("LastSelected" in key) or any(f"ConfigFile{i}" in key for i in range(1, 10))
                if is_profile_key:
                    if not val:
                        new_lines.append(line)
                        continue

                    filename = os.path.basename(val)
                    ps1_candidate = os.path.join(self.ps1_dir, filename)
                    ps3_candidate = os.path.join(self.ps3_dir, filename)

                    # Verifica existência real do perfil
                    if os.path.exists(ps1_candidate):
                        new_path = ps1_candidate.replace('\\', '/')
                        new_lines.append(f"{key}={new_path}\n")
                        fixed += 1
                    elif os.path.exists(ps3_candidate):
                        new_path = ps3_candidate.replace('\\', '/')
                        new_lines.append(f"{key}={new_path}\n")
                        fixed += 1
                    else:
                        # Arquivo ausente fisicamente
                        if "/ps1/" in val:
                            new_path = f"{ps1_dir_fwd}/{filename}"
                            new_lines.append(f"{key}={new_path}\n")
                        elif "/ps3/" in val:
                            new_path = f"{ps3_dir_fwd}/{filename}"
                            new_lines.append(f"{key}={new_path}\n")
                        else:
                            if clean_missing:
                                new_lines.append(f"{key}=\n")
                                cleaned += 1
                            else:
                                new_lines.append(line)
                    continue

            new_lines.append(line)

        with open(self.ini_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        msg = f"[OK] Portabilidade concluída!\n- Backup: bin/backups/{backup_name}\n- Caminhos corrigidos: {fixed}"
        if clean_missing:
            msg += f"\n- Referências órfãs limpas: {cleaned}"
        return msg

    def audit(self):
        """Audita as referências no .ini e gera um relatório docs/settings-audit.md."""
        if not os.path.exists(self.ini_path):
            raise FileNotFoundError(f"Arquivo de configurações não encontrado: {self.ini_path}")

        with open(self.ini_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        results = []
        current_section = None
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped[1:-1]
                continue

            if '=' in line and current_section in ('General', 'Controllers'):
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()

                is_target_key = (key == "LastProfileDir") or ("LastSelected" in key) or any(f"ConfigFile{i}" in key for i in range(1, 10))
                if is_target_key:
                    if not val:
                        results.append({'key': key, 'value': val, 'status': 'empty'})
                        continue

                    normalized = val.replace('/', os.sep)
                    exists = os.path.exists(normalized)
                    status = 'ok' if exists else 'missing'
                    results.append({'key': key, 'value': val, 'status': status})

        total = len(results)
        ok_count = sum(1 for r in results if r['status'] == 'ok')
        missing_count = sum(1 for r in results if r['status'] == 'missing')
        empty_count = sum(1 for r in results if r['status'] == 'empty')

        # Cria relatório markdown
        docs_dir = os.path.join(self.base_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        doc_path = os.path.join(docs_dir, "settings-audit.md")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        md_lines = [
            "# Settings Audit\n\n",
            f"Gerado em: {timestamp}\n\n",
            f"- Total: {total}\n",
            f"- OK: {ok_count}\n",
            f"- Missing: {missing_count}\n",
            f"- Empty: {empty_count}\n\n",
            "## Referencias nao OK\n\n",
            "| Key | Status | Value |\n",
            "| --- | --- | --- |\n"
        ]

        non_ok = [r for r in results if r['status'] != 'ok']
        for r in non_ok:
            escaped_val = r['value'].replace('|', '\\|')
            md_lines.append(f"| {r['key']} | {r['status']} | {escaped_val} |\n")

        if not non_ok:
            md_lines.append("| - | - | Nenhuma pendência |\n")

        with open(doc_path, 'w', encoding='utf-8') as f:
            f.writelines(md_lines)

        return f"[INFO] Auditoria Concluída!\n- Total: {total} | OK: {ok_count} | Ausentes: {missing_count} | Vazias: {empty_count}\n- Relatório salvo em: docs/settings-audit.md"

    def backup_pack(self):
        """Gera um pacote .zip com o estado atual das configurações e perfis."""
        archives_dir = os.path.join(self.base_dir, "archives")
        os.makedirs(archives_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        zip_name = f"asass-mod-pack-{timestamp}.zip"
        zip_path = os.path.join(archives_dir, zip_name)

        items = [
            ("bin/antimicrox_settings.ini", "bin/antimicrox_settings.ini"),
            ("ps1", "ps1"),
            ("ps3", "ps3"),
            ("themes", "themes")
        ]

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for rel_path, arc_path in items:
                full_path = os.path.join(self.base_dir, rel_path)
                if not os.path.exists(full_path):
                    continue
                if os.path.isdir(full_path):
                    for root, _, files in os.walk(full_path):
                        for file in files:
                            file_full_path = os.path.join(root, file)
                            file_rel_path = os.path.relpath(file_full_path, self.base_dir)
                            zip_file.write(file_full_path, file_rel_path)
                else:
                    zip_file.write(full_path, arc_path)

        return f"[OK] Pacote de Backup criado com sucesso!\n- Arquivo: archives/{zip_name}"

    def run_app(self, vanilla=False):
        """Inicializa o AntiMicroX em segundo plano."""
        exe_name = "asass-mod.exe"
        exe_path = os.path.join(self.base_dir, "bin", exe_name)
        if not os.path.exists(exe_path):
            exe_name = "antimicrox.exe"
            exe_path = os.path.join(self.base_dir, "bin", exe_name)

        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"Executável do AntiMicroX não encontrado na pasta bin/")

        env = os.environ.copy()
        env["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

        # Detecta gamepad USB
        has_gamepad = self.check_gamepad_connected()
        msg_gamepad = "Controle USB ativo detectado." if has_gamepad else "NENHUM controle USB ativo detectado."

        if vanilla:
            subprocess.Popen([exe_path], env=env)
            return f"[OK] AntiMicroX iniciado no modo padrão (Vanilla).\n- Status: {msg_gamepad}"
        else:
            theme_path = os.path.join(self.base_dir, "themes", "neo-carbon.qss")
            if not os.path.exists(theme_path):
                raise FileNotFoundError(f"Tema visual neo-carbon.qss não encontrado.")
            theme_path_fwd = theme_path.replace('\\', '/')
            subprocess.Popen([exe_path, "-style", "Fusion", "-stylesheet", theme_path_fwd], env=env)
            return f"[OK] AntiMicroX iniciado com Tema Customizado (Neo-Carbon).\n- Status: {msg_gamepad}"

    def check_gamepad_connected(self):
        """Executa um teste rápido via powershell para validar conexão de gamepad."""
        try:
            cmd = "Get-CimInstance Win32_PNPEntity -Filter \"PNPClass = 'HIDClass'\" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'controller|gamepad|joystick|direc|manche|controlador' }"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
            return bool(res.stdout.strip())
        except:
            return False


# ==============================================================================
# 2. WORKER THREAD (Processamento assíncrono livre de travamentos)
# ==============================================================================
class WorkerThread(QThread):
    finished = pyqtSignal(str, str) # Mensagem, Cor HTML

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.task_func(*self.args, **self.kwargs)
            color = "#107C10" if "[OK]" in res or "[INFO]" in res else "#DCE6EE"
            self.finished.emit(res, color)
        except Exception as e:
            self.finished.emit(f"[ERRO] {str(e)}", "#FF5555")


# ==============================================================================
# 3. INTERFACE GRÁFICA (PyQt6)
# ==============================================================================
class ASASSModGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ASASS Mod Manager")
        self.setFixedSize(500, 420)
        
        # Frameless (Sem bordas padrão do Windows) + Fundo Transparente
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.drag_position = QPoint()
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.manager = AntiMicroXManager(self.base_dir)
        self.worker = None

        self.init_ui()

    def init_ui(self):
        # Frame de fundo estilizado
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.main_frame.resize(500, 420)

        # Sombra externa de app premium
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # --- Cabeçalho ---
        header = QHBoxLayout()
        title = QLabel("🎮 ASASS Mod Manager")
        title.setObjectName("Title")
        
        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseBtn")
        btn_close.clicked.connect(self.close)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        
        header.addWidget(title)
        header.addWidget(btn_close)
        layout.addLayout(header)

        # --- Grid de Botões (2 Colunas) ---
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(15)

        # Coluna 1: Configurações
        col1 = QVBoxLayout()
        lbl_col1 = QLabel("CONFIGURAÇÕES E SETUP")
        lbl_col1.setObjectName("ColLabel")
        col1.addWidget(lbl_col1)

        self.btn_setup = self.create_button("🔧 Corrigir Caminhos", "NeoCarbonButton")
        self.btn_setup.clicked.connect(lambda: self.run_task(self.manager.setup, clean_missing=False))
        col1.addWidget(self.btn_setup)

        self.btn_clean = self.create_button("🧹 Limpar Referências", "NeoCarbonButton")
        self.btn_clean.clicked.connect(lambda: self.run_task(self.manager.setup, clean_missing=True))
        col1.addWidget(self.btn_clean)

        self.btn_audit = self.create_button("📋 Auditar Settings", "NeoCarbonButton")
        self.btn_audit.clicked.connect(lambda: self.run_task(self.manager.audit))
        col1.addWidget(self.btn_audit)
        grid_layout.addLayout(col1)

        # Coluna 2: Execução
        col2 = QVBoxLayout()
        lbl_col2 = QLabel("EXECUÇÃO E MANUTENÇÃO")
        lbl_col2.setObjectName("ColLabel")
        col2.addWidget(lbl_col2)

        self.btn_run = self.create_button("🎮 Iniciar (Tema Custom)", "AccentButton")
        self.btn_run.clicked.connect(lambda: self.run_task(self.manager.run_app, vanilla=False))
        col2.addWidget(self.btn_run)

        self.btn_vanilla = self.create_button("⚙️ Iniciar (Vanilla)", "NeoCarbonButton")
        self.btn_vanilla.clicked.connect(lambda: self.run_task(self.manager.run_app, vanilla=True))
        col2.addWidget(self.btn_vanilla)

        self.btn_backup = self.create_button("📦 Gerar Backup (.zip)", "NeoCarbonButton")
        self.btn_backup.clicked.connect(lambda: self.run_task(self.manager.backup_pack))
        col2.addWidget(self.btn_backup)
        grid_layout.addLayout(col2)

        layout.addLayout(grid_layout)

        # --- Console de Logs ---
        self.log_console = QTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log_console)

        self.log("Sistema inicializado. Pronto para operar.", "#56D4FF")
        self.log("Tema Neo-Carbon carregado.", "#93A8B8")

    def create_button(self, text, obj_name):
        btn = QPushButton(text)
        btn.setObjectName(obj_name)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(38)
        return btn



    def log(self, message, color="#DCE6EE"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Substitui quebras de linha para formatação HTML
        formatted_message = message.replace('\n', '<br>')
        self.log_console.append(f'<span style="color:{color};">[{timestamp}] {formatted_message}</span>')
        cursor = self.log_console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_console.setTextCursor(cursor)

    def run_task(self, task_func, *args, **kwargs):
        self.set_buttons_enabled(False)
        self.log("Processando tarefa...", "#56D4FF")
        
        self.worker = WorkerThread(task_func, *args, **kwargs)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.start()

    def on_task_finished(self, result, color):
        self.log(result, color)
        self.set_buttons_enabled(True)

    def set_buttons_enabled(self, enabled):
        for btn in [self.btn_setup, self.btn_clean, self.btn_audit, self.btn_run, self.btn_vanilla, self.btn_backup]:
            btn.setEnabled(enabled)

    # --- Controle de Arrasto da Janela ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


# ==============================================================================
# 4. PONTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    
    # 1. Força o estilo Fusion (neutro, ideal para temas customizados)
    app.setStyle(QStyleFactory.create("Fusion"))

    # 2. Cria a Paleta Dark Mode (Usando as cores do Neo-Carbon)
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window,          QColor(18, 23, 29))   # #12171D
    dark_palette.setColor(QPalette.ColorRole.WindowText,      QColor(170, 170, 170))# #AAAAAA
    dark_palette.setColor(QPalette.ColorRole.Base,            QColor(10, 14, 19))   # #0A0E13 (Console)
    dark_palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(18, 23, 29))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.Text,            QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.Button,          QColor(26, 31, 38))   # #1A1F26
    dark_palette.setColor(QPalette.ColorRole.ButtonText,      QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.BrightText,      QColor(255, 85, 85))  # #FF5555 (Vermelho)
    dark_palette.setColor(QPalette.ColorRole.Link,            QColor(86, 212, 255)) # #56D4FF (Ciano)
    dark_palette.setColor(QPalette.ColorRole.Highlight,       QColor(86, 212, 255)) # Fundo ao selecionar texto
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))      # Texto selecionado (Preto)

    # Aplica a paleta globalmente
    app.setPalette(dark_palette)

    # 3. Carrega o tema QSS e anexa os estilos específicos da janela principal
    qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", "neo-carbon.qss")
    qss_content = ""
    if os.path.exists(qss_path):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                qss_content = f.read()
        except Exception as e:
            print(f"[AVISO] Erro ao ler neo-carbon.qss: {e}")
            
    custom_qss = """
        #MainFrame { background-color: #12171D; border-radius: 12px; border: 1.5px solid #2A3440; }
        #Title { color: #56D4FF; font-size: 18px; font-weight: bold; }
        #ColLabel { color: #93A8B8; font-size: 11px; font-weight: bold; margin-bottom: 5px; }
        #CloseBtn { background: transparent; color: #93A8B8; font-size: 14px; font-weight: bold; border: none; border-radius: 6px; width: 30px; height: 30px; }
        #CloseBtn:hover { background-color: #FF5555; color: white; }
        
        QPushButton#NeoCarbonButton {
            background-color: #1D2630;
            color: #E6EEF2;
            border: 1px solid #344252;
            border-radius: 8px;
            font-weight: bold;
        }
        QPushButton#NeoCarbonButton:hover {
            background-color: #243242;
            border: 1px solid #4DB6D6;
            color: #FFFFFF;
        }
        QPushButton#NeoCarbonButton:pressed {
            background-color: #2A3B4D;
            border: 1px solid #56D4FF;
        }
        QPushButton#NeoCarbonButton:disabled {
            background-color: #1A222B;
            border: 1px solid #2A3440;
            color: #71808E;
        }

        QPushButton#AccentButton {
            background-color: #1A3445;
            color: #E6EEF2;
            border: 1px solid #2F89A7;
            border-radius: 8px;
            font-weight: bold;
        }
        QPushButton#AccentButton:hover {
            background-color: #23465D;
            border: 1px solid #56D4FF;
            color: #FFFFFF;
        }
        QPushButton#AccentButton:pressed {
            background-color: #2F5C7B;
            border: 1px solid #56D4FF;
        }
        QPushButton#AccentButton:disabled {
            background-color: #1A222B;
            border: 1px solid #2A3440;
            color: #71808E;
        }

        #LogConsole {
            background-color: #0F1419;
            color: #DCE6EE;
            border: 1px solid #2B3845;
            border-radius: 8px;
            padding: 5px;
        }
    """
    app.setStyleSheet(qss_content + custom_qss)
    
    window = ASASSModGUI()
    window.show()
    sys.exit(app.exec())
