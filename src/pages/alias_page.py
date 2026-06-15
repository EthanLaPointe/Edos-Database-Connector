"""To Be Finished Later."""

import csv
from enum import Enum, auto
from pathlib import Path
from typing import ClassVar

import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pages.protocols import AppController
from pages.sidebar import Sidebar
from src.data_cache import DataCache
from src.db_connection import (
    Customer,
    DAOFactory,
    DBConnector,
)
from src.file_handler import MAPPING_CODES, FileHandler

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
    """Mapping model used for holding alias mapping data."""

    HEADERS: ClassVar[list[str]] = ["Alias", "Customer Name", "Status"]

    def __init__(self, parent: QObject=None) -> None:
        """Initialize mapping model.

        Args:
            parent (QObject, optional): _description_. Defaults to None.

        """
        super().__init__(parent)
        self._mappings: pd.DataFrame = pd.DataFrame(columns=["alias", "parent",
                                                             "status"])

    # Qt Overrides
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: ANN001, B008, N802
        """Get row count of the current table.

        Returns:
            int: Number of rows in table

        """
        return 0 if parent.isValid() else len(self._mappings)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: ANN001, B008, N802
        """Get column count of the current table.

        Returns:
            int: Number of columns in table

        """
        return 0 if parent.isValid() else 3

    def data(  # noqa: PLR0911
        self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole,
    ) -> (str | QColor | Qt.AlignmentFlag | None):
        """Retrieve cell data or rendering information based on index and role.

        Args:
            index (QModelIndex):
                The column to retreive data from
            role (Qt.ItemDataRole, optional):
               The specific ItemDataRole to be used when retrieving data.
               Defaults to Qt.DisplayRole.

        Returns:
            str (if role == Qt.DisplayRole):
                Return column data at index as str.
                Translate status code to label.
            QColor (if role == Qt.ForegroundRole):
                Return

        """
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

    def header_data(
        self, section: int,
        orientation: Qt.Orientation,
        role: Qt.ItemDataRole=Qt.DisplayRole,
        ) -> str | None:
        """Retrieve the header of a section.

        Args:
            section (_type_): _description_
            orientation (_type_): _description_
            role (_type_, optional): _description_. Defaults to Qt.DisplayRole.

        Returns:
            str | None: str of header name or none if section not in HEADERS.

        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def load(self, df: pd.DataFrame) -> None:
        """Load a dataframe into the table model.

        Args:
            df (pd.DataFrame): DataFrame to be loaded

        """
        self.beginResetModel()
        df.columns = ["alias", "parent", "status"]
        self._mappings = df.reset_index(drop=True)
        self.endResetModel()

    def update_row(self, row: int, code: int) -> None:
        """Patch a single status cell."""
        self._mappings.loc[row, "status"] = code
        idx = self.index(row, COL_STATUS)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ForegroundRole])

    def update_rows(self, rows: list[int], code: int) -> None:
        """Patch multiple status cells and emit a single range update."""
        if not rows:
            return
        rows = sorted(set(rows))
        self._mappings.loc[rows, "status"] = code
        top = self.index(rows[0], COL_STATUS)
        bottom = self.index(rows[-1], COL_STATUS)
        self.dataChanged.emit(top, bottom, [Qt.DisplayRole, Qt.ForegroundRole])

    def unknown_customers(self) -> set[str]:
        """Return a set of customer names that are not present in the database."""
        mask = self._mappings["status"] == MAPPING_CODES["unknown customer"]
        return set(self._mappings.loc[mask, "parent"])

    def mark_customers_inserted(self, names: set[str]) -> None:
        """Mark previously unknown customers as pending to be checked again."""
        mask = (
                self._mappings["parent"].isin(names) &
                self._mappings["status"] == MAPPING_CODES["unknown customer"]
        )
        self._mappings.loc[mask, "status"] = 0
        if mask.any():
            rows = self._mappings.index[mask]
            top = self.index(rows[0], COL_STATUS)
            btm = self.index(rows[-1], COL_STATUS)
            self.dataChanged.emit(top, btm, [Qt.DisplayRole, Qt.ForegroundRole])

    def clear(self) -> None:
        """Reset current table model and rename empty table columns.

        Columns renamed to ["alias", "parent", "status"]
        """
        self.beginResetModel()
        self._mappings = pd.DataFrame(columns=["alias", "parent", "status"])
        self.endResetModel()

class _Task(Enum):
    READ_AND_CHECK = auto() # Read CSV from disk and validate
    CHECK = auto()          # Re-validate currently loaded mappings
    INSERT_UNKNOWN = auto() # Bulk create unknown customers
    INSERT = auto()         # Insert alias mappings

# Alias Worker
class AliasWorker(QThread):
    """All database access and file I/O happens within run(), on the worker thread.

    Signals
    -------
    check_done(mappings, valid):
        emitted after READ_AND_CHECK or CHECK
    unknown_insert_done():
        emitted after INSERT_UNKNOWN
    all_done(success):
        emitted after INSERT
    error(message):
        emitted on unexpected exception
    """

    check_done = Signal(pd.DataFrame, bool)
    unknown_insert_done = Signal()
    all_done = Signal(bool)
    error = Signal(str)

    def __init__(self, cache: DataCache) -> None:
        """Initialize a new AliasWorker isntance.

        Args:
            cache (DataCache): The DataCache of the main app

        """
        super().__init__()
        self.cache = cache
        self.mappings: pd.DataFrame = pd.DataFrame()
        self._task: _Task | None = None
        self._path: str | None = None
        self._unknown_names: set[str] = set()

    def run(self) -> None:
        """Start the worker and delegate to correct private method.

        Opens and closes its own DB connection.
        Calls the appropriate private method based on self._task.
        Unhandled exceptions emit error() and all_done(False) if in INSERT.
        """
        insert_completed = False
        connector = DBConnector()
        try:
            connector.connect()
            factory = DAOFactory(connector)
            handler = FileHandler(factory, self.cache)

            if self._task == _Task.READ_AND_CHECK:
                self._read_and_check(handler)
            elif self._task == _Task.CHECK:
                self._check(handler)
            elif self._task == _Task.INSERT_UNKNOWN:
                self._insert_unknown(factory)
            elif self._task == _Task.INSERT:
                self._insert(handler)

        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
            if self._task == _Task.INSERT:
                self.all_done.emit(insert_completed)

        finally:
            connector.close()

    # Private Worker Tasks

    def _read_and_check(self, handler: FileHandler) -> None:
        self.mappings = handler.read_mappings(self._path)
        self.mappings, valid = handler.check_mappings(self.mappings)
        self.check_done.emit(self.mappings, valid)

    def _check(self, handler: FileHandler) -> None:
        self.mappings, valid = handler.check_mappings(self.mappings)
        self.check_done.emit(self.mappings, valid)

    def _insert_unknown(self, factory: DAOFactory) -> None:
        customer_list = [
            Customer(customer_id=None, customer_name=name)
            for name in self._unknown_names
        ]
        factory.customers.create_bulk(customer_list)
        self.cache.refresh_customer_aliases()
        self.unknown_insert_done.emit()

    def _insert(self, handler: FileHandler) -> None:
        filtered = (
            self.mappings[self.mappings["status"] != 1]
            .drop(columns=["status"])
        )
        success = handler.insert_alias_mappings(filtered)
        self.cache.refresh_customer_aliases()
        self.all_done.emit(success)

    # Public worker methods

    def start_read_and_check(self, path:str) -> None:
        """Read csv at path and validate. Emits check_done."""
        self._path = path
        self._task = _Task.READ_AND_CHECK
        self.start()

    def start_check(self) -> None:
        """Re-validate already loaded mappings. Emits check_done."""
        self._task = _Task.CHECK
        self.start()

    def start_insert_unknown(self, names: set[str]) -> None:
        """Bulk insert unknown customer names. Emits unknown_insert_done."""
        self._unknown_names = names
        self._task = _Task.INSERT_UNKNOWN
        self.start()

    def start_insert(self) -> None:
        """Insert alias mappings. Emits all_done."""
        self._task = _Task.INSERT
        self.start()

# Alias Upload Page
class AliasPage(QWidget):
    """Class for displaying and handling of alias mapping files."""

    def __init__(self, controller: AppController) -> None:
        """Initialize alias page.

        Set variables to default values.
        Connect controller cache_updated signal to internal handling.
        Build page UI.

        Args:
            controller (AppController):
                Protocol containing required methods and attributes from main App.

        """
        super().__init__()
        self.controller = controller
        self._cache: DataCache | None = None
        self.worker: AliasWorker | None = None
        controller.cache_updated.connect(self._on_cache_updated)
        self._mappings: pd.DataFrame
        self._build_ui()

    # UI Builder
    def _build_ui(self) -> None:  # noqa: PLR0915
        """Build all UI elements and set spacing and sizing."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(controller=self.controller,
                                             active_page="alias")
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
            "Select a CSV file with two columns: alias and customer name. "
            "Preview the mappings below, then click Insert to save them.",
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

        hint = QLabel("Two-column CSV: first column alias, second column parent name.")
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
        self.table.horizontalHeader().setSectionResizeMode(COL_ALIAS,
                                                           QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_CUSTOMER,
                                                           QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS,
                                                           QHeaderView.ResizeToContents)
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

        self.export_btn = QPushButton("Export Aliases")
        self.export_btn.setMinimumSize(160, 44)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setObjectName("secondaryBtn")
        self.export_btn.clicked.connect(self._export_aliases)
        submit_row.addWidget(self.export_btn)

        submit_row.addSpacing(10)

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

    # Worker Setup

    def _create_worker(self) -> AliasWorker:
        """Create a new worker instance.

        Discard any previous worker, create a new one, and wire all signals.
        """
        self._discard_worker()

        worker = AliasWorker(self._cache)
        worker.check_done.connect(self._on_check_done)
        worker.unknown_insert_done.connect(self._on_unknown_inserted)
        worker.all_done.connect(self._on_all_done)
        worker.error.connect(self._on_worker_error)

        if hasattr(self, "_mappings"):
            worker.mappings = self._mappings

        return worker

    def _discard_worker(self) -> None:
        """Wait for any running worker to finish before discarding."""
        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.wait()
            self.worker = None

    def _ensure_worker_available(self) -> bool:
        if self.worker is not None and self.worker.isRunning():
            return False
        self.worker = self._create_worker()
        self._lock_ui(locked=True)
        return True

    # File Selection & Parsing
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Alias CSV", "", "CSV Files (*.csv);;All FIles (*)",
        )
        if not path:
            return

        self.file_label.setText(f"{Path(path).name}")
        self._lock_ui(locked=True)

        self.worker = self._create_worker()
        self.worker.start_read_and_check(path)

    # Table
    def _populate_table(self, mappings: pd.DataFrame) -> None:
        self._model.load(mappings)

    # Clear
    def _clear(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self._discard_worker()
        self._model.clear()
        self._mappings = pd.DataFrame()
        self.file_label.setText("No file selected.")
        self.clear_btn.setEnabled(False)
        self.insert_btn.setEnabled(False)
        self.unknown_btn.setEnabled(False)

    # Insert
    def _handle_insert(self) -> None:
         if not self._ensure_worker_available():
             return

         self.worker.mappings = self._mappings
         self.worker.start_insert()

    def _handle_insert_unknown(self) -> None:
        unknown = self._model.unknown_customers()
        if not unknown:
            QMessageBox.information(
                self, "Nothing to Insert",
                "No unknown customers found in the current mapping",
            )
            return

        reply = QMessageBox.question(
            self,
            "Insert Unknown Customers",
            f"{len(unknown)} customer(s) were not found in the database "
            f"and will be created.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        if not self._ensure_worker_available():
            return

        self.unknown_btn.setText("Inserting Customers...")
        self.worker.mappings = self._mappings
        self.worker.start_insert_unknown(unknown)

    def _on_check_done(self, mappings: pd.DataFrame, valid: bool) -> None:  # noqa: FBT001

        if not valid:
            self._lock_ui(locked=False)
            QMessageBox.warning(
                self,
                "Invalid File",
                "Selected file is not a valid alias mapping file",
            )
            return

        self._mappings = mappings.reset_index(drop=True)
        self._populate_table(self._mappings)
        self.clear_btn.setEnabled(True)

        has_unknown = bool(self._model.unknown_customers())
        self.insert_btn.setEnabled(not has_unknown)
        self._refresh_unknown_btn()

    def _on_all_done(self, success: bool) -> None:  # noqa: FBT001
        self._lock_ui(locked=False)

        msg = QMessageBox(self)

        if success:
            rows_to_update: list[int] = [
                row_num
                for row_num, (_, row) in enumerate(self._mappings.iterrows())
                if row["alias"] in self._cache.customer_aliases
            ]
            self._model.update_rows(rows_to_update, 4)

            msg.setWindowTitle("Insert Complete")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"Processed {self._model.rowCount()} mapping(s).")
        else:
            msg.setWindowTitle("Insert Failed")
            msg.setIcon(QMessageBox.Information)
            msg.setText("Failed to insert chosen mapping file")

        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

        self.insert_btn.setEnabled(False)
        self._refresh_unknown_btn()

    def _on_unknown_inserted(self) -> None:
        self._lock_ui(locked=True)
        self.unknown_btn.setText("Insert Unknown Customers")
        self.worker = self._create_worker()
        self.worker.mappings = self._mappings
        self.worker.start_check()

    def _refresh_unknown_btn(self) -> None:
        """Enable the unknown customers button only when unknowns exist."""
        has_unknown = bool(self._model.unknown_customers())
        self.unknown_btn.setEnabled(has_unknown)

    def _on_cache_updated(self, cache: DataCache) -> None:
        self._cache = cache
        if self.worker:
            self.worker.cache = cache

    def _on_worker_error(self, message: str) -> None:
        self._lock_ui(locked=False)
        QMessageBox.critical(
            self, "Unexpected Error",
            f"An error occurred while processing:\n\n{message}",
        )

    def _export_aliases(self) -> None:
        if not self._cache:
            QMessageBox.warning(self, "Not Ready", "Cache is not yet loaded.")
            return

        # Invert customer dict
        id_to_name: dict[int, str] = {
            cid: name for name, cid in self._cache.customers.items()
        }

        rows: list[tuple[str, str]] = []
        for alias, customer_id in self._cache.customer_aliases.items():
            customer_name = id_to_name.get(customer_id, "")
            rows.append((alias, customer_name))

        rows.sort(key=lambda r: (r[1], r[0]))

        if not rows:
            QMessageBox.information(
                self, "Nothing to Export", "No alias mappings found.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Alias Mappings",
            "alias_export.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            with Path(path).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["alias", "customer_name"])
                writer.writerows(rows)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(rows)} alias mappings to:\n{Path(path).name}",
            )
        except OSError as e:
            QMessageBox.critical(
                self, "Export Failed", f"Could not write file:\n{e}",
            )

    # Helpers
    def _lock_ui(self, *, locked: bool) -> None:
        self.choose_btn.setEnabled(not locked)
        self.clear_btn.setEnabled(not locked)
        self.unknown_btn.setEnabled(not locked)
        self.insert_btn.setEnabled(not locked)
        self.export_btn.setEnabled(not locked)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    def on_show(self) -> None:
        """Update user and sidebar to reflect current page."""
        user = self.controller.current_user or "User"
        self.sidebar.update_user(user)
