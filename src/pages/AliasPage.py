from pathlib import Path
import pandas as pd

from PySide6.QtWidgets import(
    QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QPushButton, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView, QTableView,
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
        self._mappings: pd.DataFrame = pd.DataFrame(columns=["alias", "parent", "status"])
        
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
                return str(row_data["parent"])
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
        df.columns = ["alias", "parent", "status"]
        self._mappings = df.reset_index(drop=True)
        self.endResetModel()
        
    def update_row(self, row: int, code: int):
        """Patch a single status cell"""
        self._mappings.at[row, "status"] = code
        idx = self.index(row, COL_STATUS)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])
        
    def update_rows(self, rows: list[int], code: int):
        """Patch multiple status cells and emit a single range update."""
        if not rows:
            return
        rows = sorted(set(rows))
        self._mappings.loc[rows, "status"] = code
        top = self.index(rows[0], COL_STATUS)
        bottom = self.index(rows[-1], COL_STATUS)
        self.dataChanged.emit(top, bottom, [Qt.DisplayRole, Qt.ForegroundRole])
    
    def unknown_customers(self) -> set[str]:
        """Returns a set of customer names that are not present in the database"""
        mask = self._mappings["status"] == 2
        return set(self._mappings.loc[mask, "parent"])
    
    def mark_customers_inserted(self, names: set[str]):
        """Mark previously unknown customers as pending to be checked again"""
        mask = self._mappings["parent"].isin(names) & (self._mappings["status"] == 2)
        self._mappings.loc[mask, "status"] = 0
        if mask.any():
            rows = self._mappings.index[mask]
            top = self.index(rows[0], COL_STATUS)
            btm = self.index(rows[-1], COL_STATUS)
            self.dataChanged.emit(top, btm, [Qt.DisplayRole, Qt.ForegroundRole])
        
    def clear(self):
        self.beginResetModel()
        self._mappings = pd.DataFrame(columns=["alias", "parent", "status"])
        self.endResetModel()

# Alias Worker
class AliasWorker(QThread):
    # Signals:
    #   0 - inserted successfully
    #   1 - alias already mapped (duplicate)
    #   2 - customer not found in database
    #   3 - unexpected error
    
    check_done = Signal(pd.DataFrame, bool)
    unknown_insert_done = Signal()
    all_done = Signal(bool)
    
    def __init__(self, cache: DataCache):
        super().__init__()
        self.mappings: pd.DataFrame = None
        self.cache = cache
        self.connector = DBConnector()
        self.connector.connect()
        self._factory = DAOFactory(self.connector)
        self._handler = FileHandler(self._factory, self.cache)
        
    def read_file(self, path: str):
        """Read csv file located at path"""
        self.mappings = self._handler.read_mappings(path)
       
    def check(self):
        """Check validity of mappings file and mapping pairs"""
        self.mappings, valid = self._handler.check_mappings(self.mappings)
        self.check_done.emit(self.mappings, valid)
        
    def insert_unknown_customers(self, names: set[str]):
        """Insert each unknown name as a new customer in the database.
        Calls check after insertion"""
        customer_list: list[Customer] = []
        for name in names:
            customer_list.append(Customer(customer_id=None, customer_name=name))
            
        self._factory.customers.create_bulk(customer_list)
        self.cache.refresh()
        self.unknown_insert_done.emit()
        
    def insert(self):
        """Insert mapping list and refresh cache upon successful insertion"""
        
        # Drop any rows containing duplicate aliases
        filtered_mappings = self.mappings[self.mappings["status"] != 1]
        filtered_mappings = filtered_mappings.drop(columns=["status"])
        success = self._handler.insert_alias_mappings(filtered_mappings)
        self.cache.refresh()
    
        self._handler = None
        self._factory = None
        self.connector.close()
        self.all_done.emit(success)
        
# Alias Upload Page
class AliasPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._cache: DataCache | None = None
        self.worker: AliasWorker | None = None
        controller.cache_updated.connect(self._on_cache_updated)
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
        
        self.unknown_btn = QPushButton("Insert Unknown Customers")
        self.unknown_btn.setMinimumSize(200, 44)
        self.unknown_btn.setCursor(Qt.PointingHandCursor)
        self.unknown_btn.setEnabled(False)
        self.unknown_btn.setObjectName("secondaryBtn")
        self.unknown_btn.clicked.connect(self._handle_insert_unknown)
        submit_row.addWidget(self.unknown_btn)
        
        submit_row.addSpacing(10)
        
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
        self.worker = AliasWorker(self._cache)
        self.worker.check_done.connect(self._on_check_done)
        self.worker.read_file(path)
        self.worker.check()
        
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
         self.worker.all_done.connect(self._on_all_done)
         self.worker.insert()
    
    def _handle_insert_unknown(self):
        unknown = self._model.unknown_customers()
        if not unknown:
            QMessageBox.information(self, "Nothing to Insert", "No unknown customers found in the current mapping")
            
        reply = QMessageBox.question(
            self,
            "Insert Unknown Customers",
            f"{len(unknown)} customer(s) were not found in the database"
            f"and will be created.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        
        self._lock_ui(True)
        self.unknown_btn.setText("Inserting Customers...")
        
        self.worker.unknown_insert_done.connect(self._on_unknown_inserted)
        self.worker.insert_unknown_customers(unknown)
    
    def _on_row_done(self, row: int, code: int):
        self._set_row_status(row, code)
        
    def _on_check_done(self, mappings: pd.DataFrame, valid: bool):
        
        if not valid:
            QMessageBox.warning(self, "Invalid File", "Selected file is not a valid alias mapping file")
            return
        
        self._mappings = mappings.reset_index(drop=True)
        self._populate_table(self._mappings)
        self.clear_btn.setEnabled(True)
        has_unknown = bool(self._model.unknown_customers())
        self.insert_btn.setEnabled(not has_unknown)
        self._refresh_unknown_btn()
        
    def _on_all_done(self, success: bool):
        self._lock_ui(False)
            
        msg = QMessageBox(self)
        
        if success:
            rows_to_update: list[int] = []
            for i, alias, _, _ in self._mappings.itertuples(index=True):
                if alias in self._cache.customer_aliases:
                    rows_to_update.append(i)
            self._model.update_rows(rows_to_update, 4)
            
            msg.setWindowTitle("Insert Complete")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"Processed {self._model.rowCount()} mapping(s).")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            
            self.insert_btn.setEnabled(False)
            self._refresh_unknown_btn()
        else:
            msg.setWindowTitle("Insert Failed")
            msg.setIcon(QMessageBox.Information)
            msg.setText("Failed to insert chosen mapping file")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            
            self.insert_btn.setEnabled(False)
            self._refresh_unknown_btn()
        
    def _on_unknown_inserted(self):
        self._lock_ui(False)
        self.unknown_btn.setText("Insert Unknown Customers")
        self.worker.check()
        
        self._refresh_unknown_btn()
        
    def _refresh_unknown_btn(self):
        """Enable the unknown customers button only when unknowns exist."""
        has_unknown = bool(self._model.unknown_customers())
        self.unknown_btn.setEnabled(has_unknown)
    
    def _on_cache_updated(self, cache: DataCache):
        self._cache = cache
        
        if self.worker:
            self.worker.cache = cache
    
    # Helpers
    def _lock_ui(self, locked: bool):
        self.choose_btn.setEnabled(not locked)
        self.clear_btn.setEnabled(not locked)
        self.unknown_btn.setEnabled(not locked)
        self.insert_btn.setEnabled(not locked)
        
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl
    
    def on_show(self):
        user = self.controller.current_user or "User"
        self.sidebar.update_user(user)