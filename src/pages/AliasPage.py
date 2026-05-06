from pathlib import Path
import csv
import pandas as pd

from PySide6.QtWidgets import(
    QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QPushButton, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QTableView,
)
from PySide6.QtCore import Qt, QThread, Signal, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from pages.Sidebar import Sidebar
from src.DBConnection import *
from FileHandler import FileHandler
from DataCache import DataCache

# Table Column Indices
COL_ALIAS = 0
COL_CUSTOMER = 1
COL_STATUS = 2

# Status Code Colors
STATUS_COLORS = {
    "pending": "#94a3b8",
    "valid": "#33bccb",
    "success": "#22c55e",
    "error": "#ef4444",
    "duplicate": "#f59e0b",
}

# Table Class
class AliasMappingModel(QAbstractTableModel):
    HEADERS = ["Alias", "Customer Name", "Status"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mappings: pd.DataFrame = pd.DataFrame(columns=["alias", "customer", "status"])
        
    # Qt Overrides
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._mappings)
    
    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        col = index.column()
        row_data = self._mappings.iloc[index.row()]
        
        if role == Qt.DisplayRole:
            if col == COL_ALIAS:
                return str(row_data["alias"])
            if col == COL_CUSTOMER:
                return str(row_data["customer"])
            if col == COL_STATUS:
                code = int(row_data["status"])
                return {0: "Valid", 1: "Duplicate", 2: "Customer Not Found",
                        3: "Error", 4: "Inserted"}.get(code, "Unknown")
                
        if role == Qt.ForegroundRole and col == COL_STATUS:
            code = int(row_data["status"])
            key = {0: "valid", 1: "duplicate", 2: "error",
                   3: "error", 4: "success"}.get(code, "error")
            return QColor(STATUS_COLORS.get(key, "#ef4444"))
        
        if role == Qt.TextAlignmentRole and col == COL_STATUS:
            return Qt.AlignCenter
        
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None
    
    def load(self, df: pd.DataFrame):
        """Replace the entire dataset"""
        self.beginResetModel()
        df.columns = ["alias", "customer", "status"]
        self._mappings = df.reset_index(drop=True)
        self.endResetModel()
        
    def update_row(self, row: int, code: int):
        """Patch a single status cell"""
        self._mappings.at[row, "status"] = code
        idx = self.index(row, COL_STATUS)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])
        
    def clear(self):
        self.beginResetModel()
        self._mappings = pd.DataFrame(columns=["alias", "customer", "status"])
        self.endResetModel()

# Alias Worker
class AliasWorker(QThread):
    # Signals:
    #   0 - inserted successfully
    #   1 - alias already mapped (duplicate)
    #   2 - customer not found in database
    #   3 - unexpected error
    
    check_done = Signal(pd.DataFrame, bool)
    row_done = Signal(int, int)
    all_done = Signal()
    
    def __init__(self, cache: DataCache):
        super().__init__()
        self.mappings: pd.DataFrame = None
        self.cache = cache
        self.connector = DBConnector()
        self.connector.connect()
        self._factory = DAOFactory(self.connector)
        self.handler = FileHandler(self._factory, self.cache)
       
    def check(self, path: str):
        file_path = path
        self.mappings = self.handler.read_mappings(file_path)
        self.mappings, valid = self.handler.check_mappings(self.mappings)
        
        self.check_done.emit(self.mappings, valid)
        
    def run(self):
        for i, (alias, customer) in enumerate(self.mappings):
            code = self._insert(alias, customer)
            self.row_done.emit(i, code)
        self.all_done.emit()
        
    def insert(self, alias: str, customer: str) -> int:
        # TODO
        # Trim status column off mappings and send to handler for insertion
        # Lock insert button until all unknown customers are added?
        # Add FlagDialog for alias page to handle unknowns?
        pass
        
# Alias Upload Page
class AliasPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.worker: AliasWorker | None = None
        self._mappings: pd.DataFrame
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
        layout.addWidget(self._section_label("Select File"))
        layout.addSpacing(8)
        
        file_frame = QFrame()
        file_frame.setObjectName("formSection")
        file_layout = QVBoxLayout(file_frame)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(12)
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        
        self.choose_btn = QPushButton("Choose CSV File")
        self.choose_btn.setMinimumHeight(42)
        self.choose_btn.setCursor(Qt.PointingHandCursor)
        self.choose_btn.clicked.connect(self._choose_file)
        btn_row.addWidget(self.choose_btn)
        
        btn_row.addStretch()
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("cancelBtn")
        self.clear_btn.setMinimumHeight(42)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self.clear_btn)
        
        file_layout.addLayout(btn_row)
        
        self.file_label = QLabel("No file selected.")
        self.file_label.setObjectName("subtitle")
        file_layout.addWidget(self.file_label)
        
        layout.addWidget(file_frame)
        layout.addSpacing(24)
        
        # Preview Table
        layout.addWidget(self._section_label("Mapping Preview"))
        layout.addSpacing(4)
        
        hint = QLabel("Two-column CSV: first column alias, second column customer name.")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)
        layout.addSpacing(6)
        
        table_frame = QFrame()
        table_frame.setObjectName("formSection")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(16, 16, 16, 16)
        
        self._model = AliasMappingModel(self)
        
        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.horizontalHeader().setSectionResizeMode(COL_ALIAS, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_CUSTOMER, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        #self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(260)
        self.table.setObjectName("aliasTable")
        table_layout.addWidget(self.table)
        
        layout.addWidget(table_frame)
        layout.addSpacing(24)
        
        # Submit Row
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        
        self.insert_btn = QPushButton("Insert Mappings")
        self.insert_btn.setMinimumSize(180, 44)
        self.insert_btn.setCursor(Qt.PointingHandCursor)
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self._handle_insert)
        submit_row.addWidget(self.insert_btn)
        
        layout.addLayout(submit_row)
        layout.addStretch()
        
    # File Selection & Parsing
    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Alias CSV", "", "CSV Files (*.csv);;All FIles (*)"
        )
        if not path:
            return
        
        self.file_label.setText(f"{Path(path).name}")
        self.worker = AliasWorker(self.controller.cache)
        self.worker.check_done.connect(self._on_check_done)
        self.worker.check(path)
        
    # Table
    def _populate_table(self, mappings: pd.DataFrame):
        self._model.load(mappings)
            
    def _set_row_status(self, row: int, code: int):
        self._model.update_row(row, code)
        
    # Clear    
    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        self._model.clear()
        self._mappings = pd.DataFrame()
        self.file_label.setText("No file selected.")
        self.clear_btn.setEnabled(False)
        self.insert_btn.setEnabled(False)
        
    # Insert
    def _handle_insert(self):
        pass
    
    def _on_row_done(self, row: int, code: int):
        self._set_row_status(row, code)
        
    def _on_check_done(self, mappings: pd.DataFrame, valid: bool):
        # TODO populate rows with status of each mapping row
        
        if not valid:
            QMessageBox.warning(self, "Invalid File", "Selected file is not a valid alias mapping file")
            return
        
        self._mappings = mappings
        
        self._populate_table(self._mappings)
        self.clear_btn.setEnabled(True)
        self.insert_btn.setEnabled(True)
        
    def _on_all_done(self, mappings: pd.DataFrame):
        self._lock_ui(False)
        
        inserted = sum(1 for r in range(self.table.rowCount()) if self.table.item(r, COL_STATUS).text() == "Inserted")
        duplicates = sum(1 for r in range(self.table.rowCount()) if self.table.item(r, COL_STATUS).text() == "Duplicate")
        errors = self.table.rowCount() - inserted - duplicates
        
        lines = []
        if inserted:
            lines.append(f"{inserted} mapping(s) inserted successfully")
        if duplicates:
            lines.append(f"{duplicates} skipped (already mapped)")
        if errors:
            lines.append(f"{errors} failed")
            
        has_issues = duplicates or errors
        msg = QMessageBox(self)
        msg.setWindowTitle("Insert Complete")
        msg.setIcon(QMessageBox.Warning if has_issues else QMessageBox.Information)
        msg.setText(f"Processed {self.table.rowCount()} mapping(s).")
        msg.setInformativeText("\n".join(lines))
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        
    # Helpers
    def _lock_ui(self, locked: bool):
        self.choose_btn.setEnabled(not locked)
        self.clear_btn.setEnabled(not locked)
        self.insert_btn.setEnabled(not locked)
        self.insert_btn.setText("Inserting..." if locked else "Insert Mappings")
        
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl
    
    def on_show(self):
        user = self.controller.current_user or "User"
        self.sidebar.update_user(user)