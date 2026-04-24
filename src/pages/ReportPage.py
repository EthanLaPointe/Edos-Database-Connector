from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from datetime import date
 
from pages.Sidebar import Sidebar

class ReportPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        self._build_ui()
        
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar(controller=self.controller, active_page="report")
        root.addWidget(self.sidebar)
        
        # Content Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)