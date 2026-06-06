import sys
import os
import ctypes
from ctypes import wintypes
# pyrefly: ignore [missing-import]
import vgamepad as vg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFrame, QComboBox, QGraphicsDropShadowEffect, QStyleFactory)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QFont, QPalette

# ==============================================================================
# ESTRUTURAS E CONSTANTES WINMM (MULTIMÉDIA WINDOWS)
# ==============================================================================
JOY_RETURNALL = 0xFF
JOYERR_NOERROR = 0

class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('dwXpos', wintypes.DWORD),
        ('dwYpos', wintypes.DWORD),
        ('dwZpos', wintypes.DWORD),
        ('dwRpos', wintypes.DWORD),
        ('dwUpos', wintypes.DWORD),
        ('dwVpos', wintypes.DWORD),
        ('dwButtons', wintypes.DWORD),
        ('dwButtonNumber', wintypes.DWORD),
        ('dwPOV', wintypes.DWORD),
        ('dwReserved1', wintypes.DWORD),
        ('dwReserved2', wintypes.DWORD)
    ]

class JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ('wMid', ctypes.c_ushort),
        ('wPid', ctypes.c_ushort),
        ('szPname', ctypes.c_wchar * 32),
        ('wXmin', ctypes.c_uint),
        ('wXmax', ctypes.c_uint),
        ('wYmin', ctypes.c_uint),
        ('wYmax', ctypes.c_uint),
        ('wZmin', ctypes.c_uint),
        ('wZmax', ctypes.c_uint),
        ('wNumButtons', ctypes.c_uint),
        ('wPeriodMin', ctypes.c_uint),
        ('wPeriodMax', ctypes.c_uint),
        ('wRmin', ctypes.c_uint),
        ('wRmax', ctypes.c_uint),
        ('wUmin', ctypes.c_uint),
        ('wUmax', ctypes.c_uint),
        ('wVmin', ctypes.c_uint),
        ('wVmax', ctypes.c_uint),
        ('wCaps', ctypes.c_uint),
        ('wMaxAxes', ctypes.c_uint),
        ('wNumAxes', ctypes.c_uint),
        ('wMaxButtons', ctypes.c_uint),
        ('szRegKey', ctypes.c_wchar * 32),
        ('szOEMVxD', ctypes.c_wchar * 260),
    ]

try:
    winmm = ctypes.windll.winmm
except:
    winmm = None

# ==============================================================================
# CLASSE PRINCIPAL DA APLICAÇÃO
# ==============================================================================
class XboxPassthrough(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xbox 360 Passthrough")
        self.setFixedSize(350, 450)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.drag_position = QPoint()

        # Estado
        self.gamepad = None
        self.joystick_id = None
        self.running = False
        self.button_widgets = {}
        self.connected_joysticks = []

        self.init_ui()
        self.detect_joysticks()

        # Timer para ler o controle 60x por segundo (~16ms)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)

    def init_ui(self):
        # Container principal com sombra e bordas arredondadas
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.resize(350, 450)
        self.main_frame.setStyleSheet("""
            #MainFrame {
                background-color: #12171D;
                border-radius: 12px;
                border: 1.5px solid #2A3441;
            }
        """)

        # Adiciona sombra projetada premium
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(5)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.main_frame.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Cabeçalho
        header = QHBoxLayout()
        title = QLabel("🎮 Xbox 360 Passthrough")
        title.setStyleSheet("color: #56D4FF; font-size: 16px; font-weight: bold;")
        
        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { background: transparent; color: #FF5555; font-size: 14px; 
                         font-weight: bold; border: none; border-radius: 12px; width: 24px; height: 24px; }
            QPushButton:hover { background-color: #FF5555; color: white; }
        """)
        btn_close.clicked.connect(self.close)
        
        header.addWidget(title)
        header.addWidget(btn_close)
        layout.addLayout(header)

        # Seletor de Controle
        lbl_select = QLabel("Selecione o Controle:")
        lbl_select.setStyleSheet("color: #93A8B8; font-size: 11px; font-weight: bold;")
        layout.addWidget(lbl_select)
        
        self.combo_joystick = QComboBox()
        self.combo_joystick.setStyleSheet("""
            QComboBox { background-color: #1A1F26; color: #E6EEF2; border: 1px solid #2A3441; 
                       border-radius: 6px; padding: 6px; font-size: 12px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #1A1F26; color: #E6EEF2; 
                                         selection-background-color: #2F89A7; }
        """)
        self.combo_joystick.currentIndexChanged.connect(self.on_joystick_selected)
        layout.addWidget(self.combo_joystick)

        # Grid visual dos botões (Layout estilo Xbox)
        self.btn_grid = QFrame()
        self.btn_grid.setStyleSheet("""
            QFrame { background-color: #0A0E13; border-radius: 8px; 
                    border: 1px solid #2B3845; padding: 10px; }
        """)
        grid_layout = QVBoxLayout(self.btn_grid)
        
        # Linha 1: Botões de ombro
        row1 = QHBoxLayout()
        row1.addWidget(self.create_button_widget("LB", "#5C5C5C"))
        row1.addWidget(self.create_button_widget("RB", "#5C5C5C"))
        grid_layout.addLayout(row1)
        
        # Linha 2: ABXY
        row2 = QHBoxLayout()
        row2.addWidget(self.create_button_widget("Y", "#F1C40F"))  # Amarelo
        row2.addWidget(self.create_button_widget("X", "#2ECC71"))  # Verde
        row2.addWidget(self.create_button_widget("B", "#E74C3C"))  # Vermelho
        row2.addWidget(self.create_button_widget("A", "#3498DB"))  # Azul
        grid_layout.addLayout(row2)
        
        # Linha 3: D-Pad e Sticks
        row3 = QHBoxLayout()
        row3.addWidget(self.create_button_widget("BACK", "#95A5A6"))
        row3.addWidget(self.create_button_widget("XBOX", "#56D4FF"))
        row3.addWidget(self.create_button_widget("START", "#95A5A6"))
        grid_layout.addLayout(row3)
        
        # Linha 4: Sticks (L3/R3)
        row4 = QHBoxLayout()
        row4.addWidget(self.create_button_widget("L3", "#5C5C5C"))
        row4.addWidget(self.create_button_widget("R3", "#5C5C5C"))
        grid_layout.addLayout(row4)
        
        layout.addWidget(self.btn_grid)

        # Status
        self.lbl_status = QLabel("⚪ Aguardando conexão...")
        self.lbl_status.setStyleSheet("color: #AAAAAA; font-size: 11px; padding: 3px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Botão de Ativar
        self.btn_toggle = QPushButton("▶ INICIAR EMULAÇÃO")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton { background-color: #107C10; color: white; font-size: 13px; 
                         font-weight: bold; border: none; border-radius: 8px; 
                         min-height: 40px; }
            QPushButton:hover { background-color: #138913; }
            QPushButton:pressed { background-color: #0B5A0B; }
            QPushButton:disabled { background-color: #1A222B; color: #71808E; border: 1px solid #2A3440; }
        """)
        self.btn_toggle.clicked.connect(self.toggle_emulation)
        layout.addWidget(self.btn_toggle)

    def create_button_widget(self, name, color):
        lbl = QLabel(name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(55, 30)
        lbl.setStyleSheet(f"""
            QLabel {{ background-color: {color}15; color: {color}; 
                     border: 2px solid {color}; border-radius: 6px; 
                     font-weight: bold; font-size: 10px; }}
        """)
        lbl.setProperty("base_color", color)
        self.button_widgets[name] = lbl
        return lbl

    def detect_joysticks(self):
        if winmm is None:
            self.lbl_status.setText("⚠ API de áudio/jogos do Windows não disponível!")
            self.lbl_status.setStyleSheet("color: #FF5555; font-size: 11px; padding: 3px;")
            self.btn_toggle.setEnabled(False)
            return

        self.combo_joystick.clear()
        self.connected_joysticks = []
        
        num_devs = winmm.joyGetNumDevs()
        for i in range(num_devs):
            info = JOYINFOEX()
            info.dwSize = ctypes.sizeof(JOYINFOEX)
            info.dwFlags = JOY_RETURNALL
            res = winmm.joyGetPosEx(i, ctypes.byref(info))
            if res == JOYERR_NOERROR:
                caps = JOYCAPSW()
                winmm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(JOYCAPSW))
                name = caps.szPname
                self.combo_joystick.addItem(f"{name} (ID: {i})")
                self.connected_joysticks.append((i, name))
                
        count = len(self.connected_joysticks)
        if count == 0:
            self.lbl_status.setText("⚠ Nenhum controle USB detectado!")
            self.lbl_status.setStyleSheet("color: #FF5555; font-size: 11px; padding: 3px;")
            self.btn_toggle.setEnabled(False)
        else:
            self.lbl_status.setText(f"✅ {count} controle(s) encontrado(s).")
            self.lbl_status.setStyleSheet("color: #107C10; font-size: 11px; padding: 3px;")
            # Seleciona automaticamente o primeiro controle
            self.on_joystick_selected(0)

    def on_joystick_selected(self, index):
        if 0 <= index < len(self.connected_joysticks):
            self.joystick_id = self.connected_joysticks[index][0]
            name = self.connected_joysticks[index][1]
            self.lbl_status.setText(f"🎯 Selecionado: {name}")
            self.lbl_status.setStyleSheet("color: #56D4FF; font-size: 11px; padding: 3px;")
            self.btn_toggle.setEnabled(True)

    def toggle_emulation(self):
        if not self.running:
            # Iniciar
            try:
                self.gamepad = vg.VX360Gamepad()
                self.running = True
                self.timer.start(16)  # ~60 FPS
                self.btn_toggle.setText("⏹ PARAR EMULAÇÃO")
                self.btn_toggle.setStyleSheet("""
                    QPushButton { background-color: #C62828; color: white; font-size: 13px; 
                                 font-weight: bold; border: none; border-radius: 8px; 
                                 min-height: 40px; }
                    QPushButton:hover { background-color: #E53935; }
                    QPushButton:pressed { background-color: #B71C1C; }
                """)
                self.lbl_status.setText("🟢 Emulação ATIVA - Controle virtual de Xbox 360 criado!")
                self.lbl_status.setStyleSheet("color: #107C10; font-size: 11px; padding: 3px;")
            except Exception as e:
                self.lbl_status.setText(f"❌ Falha: ViGEmBus instalado? {str(e)[:40]}")
                self.lbl_status.setStyleSheet("color: #FF5555; font-size: 11px; padding: 3px;")
        else:
            # Parar
            self.running = False
            self.timer.stop()
            if self.gamepad:
                self.gamepad.reset()
                self.gamepad = None
            self.btn_toggle.setText("▶ INICIAR EMULAÇÃO")
            self.btn_toggle.setStyleSheet("""
                QPushButton { background-color: #107C10; color: white; font-size: 13px; 
                             font-weight: bold; border: none; border-radius: 8px; 
                             min-height: 40px; }
                QPushButton:hover { background-color: #138913; }
                QPushButton:pressed { background-color: #0B5A0B; }
            """)
            self.lbl_status.setText("🔴 Emulação desativada.")
            self.lbl_status.setStyleSheet("color: #AAAAAA; font-size: 11px; padding: 3px;")
            self.reset_visual_buttons()

    def update_loop(self):
        if not self.running or self.joystick_id is None or not self.gamepad:
            return

        info = JOYINFOEX()
        info.dwSize = ctypes.sizeof(JOYINFOEX)
        info.dwFlags = JOY_RETURNALL
        res = winmm.joyGetPosEx(self.joystick_id, ctypes.byref(info))
        
        if res != JOYERR_NOERROR:
            # Controle desconectado repentinamente
            self.toggle_emulation()
            self.detect_joysticks()
            return

        # Reseta os botões no controle virtual
        self.gamepad.reset()

        # --- Mapeamento DirectInput Genérico -> Xbox 360 ---
        # Mapeamento de botões por bitmask (0 a 11)
        button_map = {
            0: ("A", vg.XUSB_BUTTON.XUSB_GAMEPAD_A),
            1: ("B", vg.XUSB_BUTTON.XUSB_GAMEPAD_B),
            2: ("X", vg.XUSB_BUTTON.XUSB_GAMEPAD_X),
            3: ("Y", vg.XUSB_BUTTON.XUSB_GAMEPAD_Y),
            4: ("LB", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER),
            5: ("RB", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER),
            6: ("BACK", vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK),
            7: ("START", vg.XUSB_BUTTON.XUSB_GAMEPAD_START),
            8: ("L3", vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB),
            9: ("R3", vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB),
            10: ("XBOX", vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE),
        }

        # Lendo e mapeando botões digitais
        for btn_idx, (name, xbox_btn) in button_map.items():
            pressed = bool(info.dwButtons & (1 << btn_idx))
            if pressed:
                self.gamepad.press_button(button=xbox_btn)
                self.highlight_button(name, True)
            else:
                self.highlight_button(name, False)

        # Lendo e mapeando D-Pad (dwPOV)
        if info.dwPOV != 65535:
            angle = info.dwPOV
            if 31500 <= angle <= 36000 or 0 <= angle <= 4500:
                self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP)
            if 13500 <= angle <= 22500:
                self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN)
            if 4500 <= angle <= 13500:
                self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT)
            if 22500 <= angle <= 31500:
                self.gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT)

        # Lendo analógicos (Sticks) - Converte de 0-65535 para -32768 a 32767
        lx = info.dwXpos - 32768
        ly = -(info.dwYpos - 32768)  # Inversão do eixo Y padrão do DirectInput
        self.gamepad.left_joystick(x_value=lx, y_value=ly)

        # Stick Direito (Z = X, R = Y na maioria dos controles DirectInput twin)
        rx = info.dwZpos - 32768
        ry = -(info.dwRpos - 32768)
        self.gamepad.right_joystick(x_value=rx, y_value=ry)

        # Gatilhos analógicos LT/RT (eixos U/V se disponíveis, caso contrário ficam zerados)
        lt_val = int((info.dwUpos / 65535) * 255) if info.dwUpos else 0
        rt_val = int((info.dwVpos / 65535) * 255) if info.dwVpos else 0
        self.gamepad.left_trigger(value=lt_val)
        self.gamepad.right_trigger(value=rt_val)

        # Envia a atualização do estado do controle para o Windows
        self.gamepad.update()

    def highlight_button(self, name, pressed):
        if name in self.button_widgets:
            lbl = self.button_widgets[name]
            base_color = lbl.property("base_color")
            if pressed:
                lbl.setStyleSheet(f"""
                    QLabel {{ background-color: {base_color}; color: #000; 
                             border: 2px solid #FFF; border-radius: 6px; 
                             font-weight: bold; font-size: 10px; }}
                """)
            else:
                lbl.setStyleSheet(f"""
                    QLabel {{ background-color: {base_color}15; color: {base_color}; 
                             border: 2px solid {base_color}; border-radius: 6px; 
                             font-weight: bold; font-size: 10px; }}
                """)

    def reset_visual_buttons(self):
        for name in self.button_widgets:
            self.highlight_button(name, False)

    # --- Eventos de Arrasto da Janela ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def closeEvent(self, event):
        if self.running:
            self.toggle_emulation()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Define paleta escura global
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window,          QColor(18, 23, 29))
    dark_palette.setColor(QPalette.ColorRole.WindowText,      QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.Base,            QColor(10, 14, 19))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(18, 23, 29))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.Text,            QColor(170, 170, 170))
    dark_palette.setColor(QPalette.ColorRole.Button,          QColor(26, 31, 38))
    dark_palette.setColor(QPalette.ColorRole.ButtonText,      QColor(170, 170, 170))
    app.setPalette(dark_palette)
    
    window = XboxPassthrough()
    window.show()
    sys.exit(app.exec())
