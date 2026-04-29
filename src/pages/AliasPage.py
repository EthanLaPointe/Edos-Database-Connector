from pathlib import Path
import csv

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

# Table Column Indices
COL_ALIAS = 0
COL_CUSTOMER = 1
COL_STATUS = 2

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
    
    def __init__(self, mappings: list[tuple[str, str]], connector: DBConnector, factory: DAOFactory):
        super().__init__()
        self.mappings = mappings
        self.connector = connector
        self._factory = factory
        
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
        
        btn_row.addStretch
        
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
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Alias", "Customer Name", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(COL_ALIAS, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_CUSTOMER, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        
        #mappings, error = self._parse_csv(path)
        mappings = ("testAlias", "testCustomer")
        error = None
        
        if error:
            QMessageBox.warning(self, "Invalid File", error)
            return
        
        self._mappings = mappings
        self.file_label.setText(f"{Path(path).name} - {len(mappings)} mapping(s) found")
        self._populate_table(mappings)
        self.clear_btn.setEnabled(True)
        self.insert_btn.setEnable(True)
        
    # TODO move csv parsing to report handler
        
    # Table
    def _populate_table(self, mappings: list[tuple[str, str]]):
        self.table.setRowCount(0)
        for alias, customer in mappings:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, COL_ALIAS, QTableWidgetItem(alias))
            self.table.setItem(row, COL_CUSTOMER, QTableWidgetItem(customer))
            status_item = QTableWidgetItem("Pending")
            status_item.setForeground(QColor(STATUS_COLORS["pending"]))
            self.table.setItem(row, COL_STATUS, status_item)
            
    def _set_row_status(self, row: int, code: int):
        labels = {0: "Inserted", 1: "Duplicate", 2: "Customer Not Found", 3: "Error"}
        keys = {0: "success", 1: "duplicate", 2: "error", 3: "error"}
        text = labels.get(code, "Unknown")
        color = STATUS_COLORS.get(keys.get(code, "error"), "#ef4444")
        
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        self.table.setItem(row, COL_STATUS, item)
        self.table.scrollToItem(item)
        
    # Clear    
    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        self._mappings.clear()
        self.table.setRowCount(0)
        self.file_label.setText("No file selected.")
        self.clear_btn.setEnabled(False)
        self.insert_btn.setEnabled(False)
        
    # Insert
    def _handle_insert(self):
        pass
    
    def _on_row_done(self, row: int, code: int):
        self._set_row_status(row, code)
        
    def _on_all_done(self):
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