"""Contains implementation for RepPage class and any related worker classes."""

import traceback
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
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pages.protocols import AppController
from pages.sidebar import Sidebar
from src.data_cache import DataCache
from src.db_connection import (
    DAOFactory,
    DBConnector,
    Representative,
    RepresentativeTeam,
    RepTeamCustomerLocation,
)
from src.file_handler import REP_MAPPING_FIELD_LIST, FileHandler

# Table Column Indices
COL_NAME = 0
COL_SUPERPARENT = 1

_COLUMN_HEADERS = [
    "Name", "Superparent", "City", "State", "New Team", "Heating", "Plumbing",
]

# Table Class
class RepMappingModel(QAbstractTableModel):
    """Table model used for holding/previewing representative mapping data."""

    HEADERS: ClassVar[list[str]] = _COLUMN_HEADERS

    def __init__(self, parent: QObject = None) -> None:
        """Initialize mapping model.

        Args:
            parent (QObject, optional):
                Parent object. Defaults to None.

        """
        super().__init__(parent)
        self._mappings: pd.DataFrame = pd.DataFrame(columns=REP_MAPPING_FIELD_LIST)

    # Qt Overrides
    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: ANN001, B008, N802
        """Get rowcount of the current table.

        Returns:
            int: Number of rows in table.

        """
        return 0 if parent.isValid() else len(self._mappings)

    def columnCount(self, parent=QModelIndex()) -> int: # noqa: ANN001, B008, N802
        """Get column count of the curernt table.

        Returns:
            int:
                Number of columns in table.

        """
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(
        self,
        index: QModelIndex,
        role: Qt.ItemDataRole = Qt.DisplayRole,
    ) -> str | None:
        """Retrieve cell data based on index and role.

        Args:
            index (QModelIndex):
                The cell to retrieve data from.
            role (Qt.ItemDataRole, optional):
                The specific ItemDataRole to be used when retrieving data.
                Defaults to Qt.DisplayRole.

        Returns:
            str | None:
                The cell contents as a str for Qt.DisplayRole, otherwise None.

        """
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            row_data = self._mappings.iloc[index.row()]
            field = REP_MAPPING_FIELD_LIST[index.column()]
            return str(row_data[field])

        return None

    def header_data(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: Qt.ItemDataRole = Qt.DisplayRole,
    ) -> str | None:
        """Retrieve the header of a section.

        Args:
            section (int): Section index.
            orientation (Qt.Orientation): Header orientation.
            role (Qt.ItemDataRole, optional): Role requeste. Defaults to DisplayRole.

        Returns:
            str | None:
                str of a header name or None if section not in HEADERS.

        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def load(self, df: pd.DataFrame) -> None:
        """Load a dataframe into the table model.

        Args:
            df (pd.DataFrame):
                DataFrame to be loaded.

        """
        self.beginResetModel()
        self._mappings = df.reset_index(drop=True)
        self.endResetModel()

    def clear(self) -> None:
        """Reset current table model to an empty dataframe."""
        self.beginResetModel()
        self._mappings = pd.DataFrame(columns=REP_MAPPING_FIELD_LIST)
        self.endResetModel()

class _Task(Enum):
    # Read CSV from disk and validate
    READ_AND_CHECK = auto()
    # Insert representative mappings
    INSERT = auto()

class RepWorker(QThread):
    """All database access and file I/O happens within run(), on the worker thread.

    Signals
    -------
    check_done(mappings, valid):
        emitted after READ_AND_CHECK
    all_done(success):
        emitted after INSERT
    error(message, traceback):
        emitted on unexpected exception

    """

    check_done = Signal(pd.DataFrame, bool)
    all_done = Signal(bool)
    error = Signal(str, str)

    def __init__(self, cache: DataCache) -> None:
        """Initialize a new RepWorker instance.

        Args:
            cache (DataCache):
                The DataCache of the main app.

        """
        super().__init__()
        self.cache = cache
        self.mappings: pd.DataFrame = pd.DataFrame()
        self._task: _Task | None = None
        self._path: str | None = None

    def run(self) -> None:
        """Start the worker and delegate to correct private method.

        Opens and closes its own DB connection.
        Calls the appropriate private method based on self._task.
        Unhandled exceptions emit error() and all_done(False) if in INSERT.
        """
        connector = DBConnector()
        try:
            connector.connect()
            factory = DAOFactory(connector)
            handler = FileHandler(factory, self.cache)

            if self._task == _Task.READ_AND_CHECK:
                self._read_and_check(handler)
            elif self._task == _Task.INSERT:
                self._insert(handler)

        except Exception as e: # noqa: BLE001
            self.error.emit(str(e), traceback.format_exc())
            if self._task == _Task.INSERT:
                self.all_done.emit(False)  # noqa: FBT003

        finally:
            connector.close()

    def _read_and_check(self, handler: FileHandler) -> None:
        self.mappings = handler.read_mappings(self._path)
        self.mappings, valid = handler.check_rep_mappings(self.mappings)
        self.check_done.emit(self.mappings, valid)

    def _insert(self, handler: FileHandler) -> None:
        success = handler.insert_rep_mappings(self.mappings)
        self.all_done.emit(bool(success))

    def start_read_and_check(self, path: str) -> None:
        """Read csv at path and validate. Emits check_done."""
        self._path = path
        self._task = _Task.READ_AND_CHECK
        self.start()

    def start_insert(self) -> None:
        """Insert representative mappings. Emits all_done."""
        self._task = _Task.INSERT
        self.start()

class _ManageTask(Enum):
    """Tasks handled by ManageWorker."""

    CREATE_REP = auto()
    CREATE_TEAM = auto()
    CREATE_MEMBER = auto()
    CREATE_RTCL = auto()
    LOAD_TEAM_MEMBERS = auto()

class ManageWorker(QThread):
    """Handles single-record creation of reps, teams, and their relationships.

    This worker intentionally calls straight into the existing DAO layer
    (DAOFactory) rather than a dedicated FileHandler method, since the
    single record creation/validation flows (duplicate handling, referential
    checks, ect.) are still TODOs on the backend. Swap the bodies of the
    '_create_*' the public start_* API and emitted signals are meant to
    stay stable so the UI in RepPage does not need to change.

    Signals
    -------
    rep_created(success, message):
        emitted after CREATE_REP
    team_created(success, message):
        emitted after CREATE_TEAM
    member_created(success, message):
        emitted after CREATE_MEMBER
    rtcl_created(success, message):
        emitted after CREATE_RTCL
    members_loaded(members):
        emitted after LOAD_TEAM_MEMBERS
    error(message, traceback):
        emitted on unexpected exception

    """

    rep_created = Signal(bool, str)
    team_created = Signal(bool, str)
    member_created = Signal(bool, str)
    rtcl_created = Signal(bool, str)
    members_loaded = Signal(list)
    error = Signal(str, str)

    def __init__(self, cache: DataCache | None) -> None:
        """Initialize a new ManageWorker instance.

        Args:
            cache (DataCache | None):
                The DataCache of the main app. May be None until login.

        """
        super().__init__()
        self.cache = cache
        self._task: _ManageTask | None = None

        # Payloads set by the start_* methods below.
        self._rep_name: str = ""
        self._team_name: str = ""
        self._member_team_id: int | None = None
        self._member_rep_id: int | None = None
        self._member_classification: str = ""
        self._rtcl_team_id: int | None = None
        self._rtcl_customer_id: int | None = None
        self._rtcl_location_id: int | None = None

    def run(self) -> None:
        """Open a connection, dispatch to the correct handler, then close it."""
        connector = DBConnector()
        try:
            connector.connect()
            factory = DAOFactory(connector)

            match self._task:
                case _ManageTask.CREATE_REP:
                    self._create_rep(factory)
                case _ManageTask.CREATE_TEAM:
                    self._create_team(factory)
                case _ManageTask.CREATE_MEMBER:
                    self._create_member(factory)
                case _ManageTask.CREATE_RTCL:
                    self._create_rtcl(factory)
                case _ManageTask.LOAD_TEAM_MEMBERS:
                    self._load_team_members(factory)

        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e), traceback.format_exc())

        finally:
            connector.close()

    # Private Worker Tasks
    def _create_rep(self, factory: DAOFactory) -> None:
        # TODO: backend - RepresentativeDAO.create() needs a duplicate check
        # (ON CONFLICT DO NOTHING currently returns None and will raise here).
        rep = factory.representative.create(
            Representative(representative_id=None, representative_name=self._rep_name),
        )
        if self.cache is not None:
            self.cache.refresh_representatives()
        self.rep_created.emit(
            True, f"Representative '{rep.representative_name}' added.",
        )

    def _create_team(self, factory: DAOFactory) -> None:
        # TODO: backend - RepresentativeTeamsDAO.create() needs a duplicate check.
        team = factory.rep_teams.create(
            RepresentativeTeam(team_id=None, team_name=self._team_name),
        )
        if self.cache is not None:
            self.cache.refresh_rep_teams()
        if team is not None:
            self.team_created.emit(True, f"Team '{team.team_name}' added.")
        else:
            self.team_created.emit(
                False, f"'{self._team_name}' already exists or could not be added.",
            )

    def _create_member(self, factory: DAOFactory) -> None:
        factory.team_members.create(
            self._member_team_id,
            self._member_rep_id,
            self._member_classification,
        )
        self.member_created.emit(True, "Representative assigned to team.")

    def _create_rtcl(self, factory: DAOFactory) -> None:
        factory.rtcl.create(
            RepTeamCustomerLocation(
                team_id=self._rtcl_team_id,
                customer_id=self._rtcl_customer_id,
                location_id=self._rtcl_location_id,
            ),
        )
        self.rtcl_created.emit(True, "Customer location assigned to team.")

    def _load_team_members(self, factory: DAOFactory) -> None:
        members = factory.team_members.get_by_team(self._member_team_id)
        self.members_loaded.emit(list(members))

    # Public worker methods
    def start_create_representative(self, name: str) -> None:
        """Create a new representative. Emits rep_created."""
        self._rep_name = name
        self._task = _ManageTask.CREATE_REP
        self.start()

    def start_create_team(self, name: str) -> None:
        """Create a new representative team. Emits team_created."""
        self._team_name = name
        self._task = _ManageTask.CREATE_TEAM
        self.start()

    def start_create_member(
        self, team_id: int, rep_id: int, classification: str,
    ) -> None:
        """Assign a representative to a team. Emits member_created."""
        self._member_team_id = team_id
        self._member_rep_id = rep_id
        self._member_classification = classification
        self._task = _ManageTask.CREATE_MEMBER
        self.start()

    def start_create_rtcl(
        self, team_id: int, customer_id: int, location_id: int,
    ) -> None:
        """Link a team to a customer location. Emits rtcl_created."""
        self._rtcl_team_id = team_id
        self._rtcl_customer_id = customer_id
        self._rtcl_location_id = location_id
        self._task = _ManageTask.CREATE_RTCL
        self.start()

    def start_load_team_members(self, team_id: int) -> None:
        """Load all members of a team. Emits members_loaded."""
        self._member_team_id = team_id
        self._task = _ManageTask.LOAD_TEAM_MEMBERS
        self.start()

class RepPage(QWidget):
    """Class for displaying and handling of representative mapping files."""

    def __init__(self, controller: AppController) -> None:
        """Initialize rep page.

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
        self.worker: RepWorker | None = None
        controller.cache_updated.connect(self._on_cache_updated)
        self._mappings: pd.DataFrame = pd.DataFrame()

        self.manage_worker = ManageWorker(self._cache)
        self._wire_manage_worker()

        self._build_ui()

    # UI Builder
    def _build_ui(self) -> None:  # noqa: PLR0915
        """Build all UI elements and set spacing and sizing."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(controller=self.controller, active_page="rep")
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
        title = QLabel("Upload Representative Mappings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(4)

        sub = QLabel(
            "Select a CSV file mapping customers to representative teams. "
            "Preview the mappings below, then click Insert to save the.",
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

        hint = QLabel(
            "Expected columns: name, superparent, city, state, "
            "new team, heating, plumbing.",
        )
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)
        layout.addSpacing(6)

        table_frame = QFrame()
        table_frame.setObjectName("formSection")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(16, 16, 16, 16)

        self._model = RepMappingModel(self)

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NAME, QHeaderView.Stretch,
        )
        self.table.horizontalHeader().setSectionResizeMode(
            COL_SUPERPARENT, QHeaderView.Stretch,
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(260)
        self.table.setObjectName("repTable")
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
        self.insert_btn.clicked.connect(self._handler_insert)
        submit_row.addWidget(self.insert_btn)

        layout.addLayout(submit_row)
        layout.addStretch()

    # Worker Setup
    def _create_worker(self) -> RepWorker:
        """Create a new worker instance.

        Discard any previous worker, create a new one, and wire all signals.
        """
        self._discard_worker()

        worker = RepWorker(self._cache)
        worker.check_done.connect(self._on_check_done)
        worker.all_done.connect(self._on_all_done)
        worker.error.connect(self._on_worker_error)

        if not self._mappings.empty:
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

    # File Selection and Parsing
    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Representative CSV", "", "CSV Files (*.csv);;All Files (*)",
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

    # Insert
    def _handler_insert(self) -> None:
        if not self._ensure_worker_available():
            return

        self.worker.mappings = self._mappings
        self.worker.start_insert()

    def _on_check_done(self, mappings: pd.DataFrame, valid: bool) -> None: # noqa: FBT001
        self._lock_ui(locked=False)

        if not valid:
            QMessageBox.warning(
                self,
                "Invalid File",
                "Selected file is not a valid representative mappings file.\n\n"
                f"Expected columns {', '.join(REP_MAPPING_FIELD_LIST)}",
            )
            return

        self._mappings = mappings.reset_index(drop=True)
        self._populate_table(self._mappings)
        self.clear_btn.setEnabled(True)
        self.insert_btn.setEnabled(not self._mappings.empty)

    def _on_all_done(self, success: bool) -> None: # noqa: FBT001
        self._lock_ui(locked=False)

        msg = QMessageBox(self)

        if success:
            msg.setWindowTitle("Insert Complete")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"Processed {self._model.rowCount()} mapping(s).")
            self.insert_btn.setEnabled(False)
        else:
            msg.setWindowTitle("Insert Failed")
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Failed to insert represetntative mapping file.")

        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    def _on_cache_updated(self, cache: DataCache) -> None:
        self._cache = cache
        if self.worker:
            self.worker.cache = cache

    def _on_worker_error(self, message: str, trace: str) -> None:
        self._lock_ui(locked=False)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Unexpected Error")
        box.setText("An error occurred while processing the representative file.")
        box.setInformativeText(message)
        box.setDetailedText(trace)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    # Helpers
    def _lock_ui(self, *, locked: bool) -> None:
        self.choose_btn.setEnabled(not locked)
        self.clear_btn.setEnabled(not locked)
        self.insert_btn.setEnabled(not locked)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        return lbl

    def on_show(self) -> None:
        """Update user and sidebar to reflect current page."""
        user = self.controller.current_user or "User"
        self.sidebar.update_user(user)
