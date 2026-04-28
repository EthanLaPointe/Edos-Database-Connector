from pathlib import Path

from PySide6.QtWidgets import(
    QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QPushButton, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from pages.Sidebar import Sidebar
from src.DBConnection import *

STATUS_COLORS = {
    "pending": "#94a3b8",
    "success": "#22c55e",
    "error": "#ef4444",
    "duplicate": "#f59e0b",
}

# Insert Worker

class AliasInsertWorker(QThread):
    # Signals:
    #   0 - inserted successfully
    #   1 - alias already mapped (duplicate)
    #   2 - customer not found in database
    #   3 - unexpected error
    
    row_done = Signal(int, int)
    all_done = Signal()
    
    def __init__(self, mappings: list[tuple[str, str]], connector: DBConnector,):
        super().__init__()
        self.mappings = mappings
        self.connector = connector
        self._factory = DAOFactory(connector)
        
    def run(self):
        for i, (alias, customer) in enumerate(self.mappings):
            code = self._insert(alias, customer)
            self.row_done.emit(i, code)
        self.all_done.emit()
        
    def _insert(self, alias: str, customer: str) -> int:
        try:
            # TODO add insert functionality and validity checks
            return 0
        except Exception:
            return 3
        
# Alias Upload Page
class AliasPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.worker: AliasInsertWorker | None = None
        self._mappings: list[tuple[str, str]] = []
        self._build_ui()
        
    # UI Builder
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        self.sidebar = Sidebar(controller=self.controller, active_page="alias")
        root.addWidget(self.sidebar)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)
        
        content = QWidget()
        content.setObjectName("content")
        scroll.setWidget(content)
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)
        
        # Header
        title = QLabel("Upload Alias Mappings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(4)
        
        sub = QLabel(
            "Select a CSV file with two columns: alias and customer name."
            "Preview the mappings below, then click Insert to save them."
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(28)
        
        # File Selection
        
        