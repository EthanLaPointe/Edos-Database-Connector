"""Contains implementation for RepPage class and any related worker classes.""" # noqa: CPY001

import traceback
import typing
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
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
    CustomerLocation,
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

# Classifications for team member assignment
CLASSIFICATIONS: list[tuple[str, str]] = [
    ("heating", "Heating"),
    ("plumbing", "Plumbing"),
]

class NoPropagateListWidget(QListWidget):
    """QListWidget that prevents wheel event propagation.

    Class swallows wheel events instead of letting them reach a parent scroll area
    when the list hits its scroll limit.
    """

    @typing.override
    def wheelEvent(self, event: QWheelEvent) -> None:
        super().wheelEvent(event)
        event.accept()

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
    DELETE_RTCL = auto()
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
    rtcl_created(message, success):
        emitted after CREATE_RTCL
    members_loaded(members):
        emitted after LOAD_TEAM_MEMBERS
    error(message, traceback):
        emitted on unexpected exception

    """

    rep_created = Signal(str, bool)
    team_created = Signal(str, bool)
    member_created = Signal(str, bool)
    rtcl_created = Signal(str, bool)
    rtcl_deleted = Signal(str, bool)
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
                case _ManageTask.DELETE_RTCL:
                    self._delete_rtcl(factory)
                case _ManageTask.LOAD_TEAM_MEMBERS:
                    self._load_team_members(factory)

        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e), traceback.format_exc())

        finally:
            connector.close()

    # Private Worker Tasks
    def _create_rep(self, factory: DAOFactory) -> None:
        rep = factory.representatives.create(
            Representative(representative_id=None, representative_name=self._rep_name),
        )
        success = bool(rep)
        if success:
            if self.cache is not None:
                self.cache.refresh_representatives()
            self.rep_created.emit(
                f"Representative '{rep.representative_name}' added.",
                success,
            )
        else:
            self.rep_created.emit(
                f"Representative '{self._rep_name}' already exists "
                "or could not be added. ",
                success,
            )

    def _create_team(self, factory: DAOFactory) -> None:
        team = factory.rep_teams.create(
            RepresentativeTeam(team_id=None, team_name=self._team_name),
        )
        success = bool(team)
        if self.cache is not None:
            self.cache.refresh_rep_teams()
        if success:
            self.team_created.emit(f"Team '{team.team_name}' added.", success)
        else:
            self.team_created.emit(
                f"'{self._team_name}' already exists or could not be added.",
                success,
            )

    def _create_member(self, factory: DAOFactory) -> None:
        team_member = factory.team_members.create(
            self._member_team_id,
            self._member_rep_id,
            self._member_classification,
        )
        success = bool(team_member)
        if success:
            self.member_created.emit("Representative assigned to team.", success)
        else:
            self.member_created.emit(
                "Representative already assigned to that team or could not be added.",
                success,
            )

    def _create_rtcl(self, factory: DAOFactory) -> None:
        cl = factory.customer_locations.get(
            self._rtcl_customer_id,
            self._rtcl_location_id,
        )
        if cl is None:
            cl = CustomerLocation(
                self._rtcl_customer_id,
                self._rtcl_location_id,
            )
            factory.customer_locations.create(cl)

        rtcl = factory.rtcl.create(
            RepTeamCustomerLocation(
                team_id=self._rtcl_team_id,
                customer_location=cl,
            ),
        )
        success = bool(rtcl)
        if success:
            self.rtcl_created.emit("Customer location assigned to team.", success)
        else:
            self.rtcl_created.emit(
                "Relationship already exists or could not be added.",
                success,
            )

    def _delete_rtcl(self, factory: DAOFactory) -> None:
        cl = CustomerLocation(
            self._rtcl_customer_id,
            self._rtcl_location_id,
        )
        factory.rtcl.delete(
            RepTeamCustomerLocation(
                team_id=self._rtcl_team_id,
                customer_location=cl,
            ),
        )
        self.rtcl_deleted.emit("Team-customer location relationship removed.", True)  # noqa: FBT003

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

    def start_delete_rtcl(
        self, team_id: int, customer_id: int, location_id: int,
    ) -> None:
        """Remove a team's link to a customer location. Emits rtcl_deleted."""
        self._rtcl_team_id = team_id
        self._rtcl_customer_id = customer_id
        self._rtcl_location_id = location_id
        self._task = _ManageTask.DELETE_RTCL
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
    def _build_ui(self) -> None:
        """Build all UI elements and set spacing and sizing."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(controller=self.controller, active_page="rep")
        root.addWidget(self.sidebar)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_bulk_tab(), "Bulk Mapping Import")
        self.tabs.addTab(self._build_manage_tab(), "Representatives && Teams")
        root.addWidget(self.tabs)

    # Tab 1: Bulk CSV Mapping
    def _build_bulk_tab(self) -> QWidget:  # noqa: PLR0915
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

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
            "Select a CSV file mapping customers to representative teams."
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

        return scroll

    # Tab 2: Manage Representatives, Teams, and relations
    def _build_manage_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("content")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)

        title = QLabel("Manage Representatives && Teams")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(4)

        sub = QLabel(
            "Create individual representatives and teams, assign representatives "
            "to teams, and link teams to customer locations. ",
        )
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(24)

        layout.addWidget(self._build_representative_section())
        layout.addSpacing(20)
        layout.addWidget(self._build_team_section())
        layout.addSpacing(20)
        layout.addWidget(self._build_team_member_section())
        layout.addSpacing(20)
        layout.addWidget(self._build_rtcl_section())
        layout.addStretch()

        return scroll

    def _build_representative_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("formSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._section_label("Representatives"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.rep_name_input = QLineEdit()
        self.rep_name_input.setPlaceholderText("Representative name")
        self.rep_name_input.setMinimumHeight(40)
        self.rep_name_input.returnPressed.connect(self._handle_create_representative)
        row.addWidget(self.rep_name_input, stretch=1)

        self.add_rep_btn = QPushButton("Add Representative")
        self.add_rep_btn.setCursor(Qt.PointingHandCursor)
        self.add_rep_btn.setMinimumHeight(40)
        self.add_rep_btn.clicked.connect(self._handle_create_representative)
        row.addWidget(self.add_rep_btn)

        layout.addLayout(row)

        self.rep_status_lbl = QLabel("")
        self.rep_status_lbl.setWordWrap(True)
        self.rep_status_lbl.setVisible(False)
        layout.addWidget(self.rep_status_lbl)

        hint = QLabel("Existing representatives:")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        self.rep_list = NoPropagateListWidget()
        self.rep_list.setMaximumHeight(140)
        layout.addWidget(self.rep_list)

        return frame

    def _build_team_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("formSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._section_label("Representative Teams"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.team_name_input = QLineEdit()
        self.team_name_input.setPlaceholderText("Team name")
        self.team_name_input.setMaximumHeight(40)
        self.team_name_input.returnPressed.connect(self._handle_create_team)
        row.addWidget(self.team_name_input, stretch=1)

        self.add_team_btn = QPushButton("Add Team")
        self.add_team_btn.setCursor(Qt.PointingHandCursor)
        self.add_team_btn.setMinimumHeight(40)
        self.add_team_btn.clicked.connect(self._handle_create_team)
        row.addWidget(self.add_team_btn)

        layout.addLayout(row)

        self.team_status_lbl = QLabel("")
        self.team_status_lbl.setWordWrap(True)
        self.team_status_lbl.setVisible(False)
        layout.addWidget(self.team_status_lbl)

        hint = QLabel("Existing teams:")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        self.team_list = NoPropagateListWidget()
        self.team_list.setMaximumHeight(140)
        layout.addWidget(self.team_list)

        return frame

    def _build_team_member_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("formSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._section_label("Team Members"))

        hint = QLabel(
            "Assign a representative to a team for a given service classification.",
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        self.member_team_combo = QComboBox()
        self.member_team_combo.setMinimumHeight(40)
        self.member_team_combo.currentIndexChanged.connect(
            self._on_member_team_changed,
        )
        form_row.addWidget(self.member_team_combo, stretch=1)

        self.member_rep_combo = QComboBox()
        self.member_team_combo.setMinimumHeight(40)
        form_row.addWidget(self.member_rep_combo, stretch=1)

        self.member_class_combo = QComboBox()
        for value, label in CLASSIFICATIONS:
            self.member_class_combo.addItem(label, userData=value)
        self.member_class_combo.setMinimumHeight(40)
        self.member_class_combo.setFixedWidth(130)
        form_row.addWidget(self.member_class_combo)

        layout.addLayout(form_row)

        self.add_member_btn = QPushButton("Assign Representative to Team")
        self.add_member_btn.setCursor(Qt.PointingHandCursor)
        self.add_member_btn.setMinimumHeight(40)
        self.add_member_btn.clicked.connect(self._handle_create_member)
        layout.addWidget(self.add_member_btn)

        self.member_status_lbl = QLabel("")
        self.member_status_lbl.setWordWrap(True)
        self.member_status_lbl.setVisible(False)
        layout.addWidget(self.member_status_lbl)

        hint2 = QLabel("Current members of selected team:")
        hint2.setObjectName("hintLabel")
        layout.addWidget(hint2)

        self.team_member_list = NoPropagateListWidget()
        self.team_member_list.setMaximumHeight(140)
        layout.addWidget(self.team_member_list)

        return frame

    def _build_rtcl_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("formSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._section_label("Team Customer Locations"))

        hint = QLabel(
            "Link a representative team to a customer's location. Reports for "
            "this customer/location pair will route to the assigned team.",
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form_row = QHBoxLayout()
        form_row.setSpacing(10)

        self.rtcl_team_combo = QComboBox()
        self.rtcl_team_combo.setMinimumHeight(40)
        form_row.addWidget(self.rtcl_team_combo, stretch=1)

        self.rtcl_customer_combo = QComboBox()
        self.rtcl_customer_combo.setMinimumHeight(40)
        form_row.addWidget(self.rtcl_customer_combo, stretch=1)

        self.rtcl_location_combo = QComboBox()
        self.rtcl_location_combo.setMinimumHeight(40)
        form_row.addWidget(self.rtcl_location_combo, stretch=1)

        layout.addLayout(form_row)

        self.add_rtcl_btn = QPushButton("Assign Team to Customer Location")
        self.add_rtcl_btn.setCursor(Qt.PointingHandCursor)
        self.add_rtcl_btn.setMinimumHeight(40)
        self.add_rtcl_btn.clicked.connect(self._handle_create_rtcl)
        layout.addWidget(self.add_rtcl_btn)

        self.delete_rtcl_btn = QPushButton("Remove Team from Customer Location")
        self.delete_rtcl_btn.setCursor(Qt.PointingHandCursor)
        self.delete_rtcl_btn.setMinimumHeight(40)
        self.delete_rtcl_btn.setObjectName("dangerButton")
        self.delete_rtcl_btn.clicked.connect(self._handle_delete_rtcl)
        layout.addWidget(self.delete_rtcl_btn)

        self.rtcl_status_lbl = QLabel("")
        self.rtcl_status_lbl.setWordWrap(True)
        self.rtcl_status_lbl.setVisible(False)
        layout.addWidget(self.rtcl_status_lbl)

        return frame

    # Manage Worker Wiring
    def _wire_manage_worker(self) -> None:
        self.manage_worker.rep_created.connect(self._on_rep_created)
        self.manage_worker.team_created.connect(self._on_team_created)
        self.manage_worker.member_created.connect(self._on_member_created)
        self.manage_worker.rtcl_created.connect(self._on_rtcl_created)
        self.manage_worker.rtcl_deleted.connect(self._on_rtcl_deleted)
        self.manage_worker.members_loaded.connect(self._on_members_loaded)
        self.manage_worker.error.connect(self._on_manage_worker_error)

    def _manage_worker_busy(self, status_lbl: QLabel) -> bool:
        if self.manage_worker.isRunning():
            self._show_manage_status(
                status_lbl, "Please wait for the current action to finish.",
                error=True,
            )
            return True
        return False

    # Manage Tab Handlers - Representatives
    def _handle_create_representative(self) -> None:
        name = self.rep_name_input.text().strip()
        if not name:
            self._show_manage_status(
                self.rep_status_lbl, "Please enter a name.", error=True,
            )
            return
        if self._manage_worker_busy(self.rep_status_lbl):
            return
        self.manage_worker.start_create_representative(name.lower())

    def _on_rep_created(self, message: str, success: bool) -> None:  # noqa: FBT001
        if success:
            self._show_manage_status(self.rep_status_lbl, message, error=False)
            self.rep_name_input.clear()
            self._refresh_manage_lists()
        else:
            self._show_manage_status(self.rep_status_lbl, message, error=True)

    # Manage Tab Handlers - Teams
    def _handle_create_team(self) -> None:
        name = self.team_name_input.text().strip()
        if not name:
            self._show_manage_status(
                self.team_status_lbl, "Please enter a team name.", error=True,
            )
            return
        if self._manage_worker_busy(self.team_status_lbl):
            return
        self.manage_worker.start_create_team(name.lower())

    def _on_team_created(self, message: str, success: bool) -> None:  # noqa: FBT001
        if success:
            self._show_manage_status(self.team_status_lbl, message, error=False)
            self.team_name_input.clear()
            self._refresh_manage_lists()
        else:
            self._show_manage_status(self.team_status_lbl, message, error=True)

    # Manage Tab Handlers - Team Members
    def _on_member_team_changed(self) -> None:
        team_id = self.member_team_combo.currentData()
        self.team_member_list.clear()
        if team_id is not None and not self.manage_worker.isRunning():
            self.manage_worker.start_load_team_members(team_id)

    def _handle_create_member(self) -> None:
        team_id = self.member_team_combo.currentData()
        rep_id = self.member_rep_combo.currentData()
        classification = self.member_class_combo.currentData()
        if team_id is None or rep_id is None:
            self._show_manage_status(
                self.member_status_lbl,
                "Select a team and representative first.",
                error=True,
            )
            return
        if self._manage_worker_busy(self.member_status_lbl):
            return
        self.manage_worker.start_create_member(team_id, rep_id, classification)
        if team_id is not None and not self.manage_worker.isRunning():
                    self.manage_worker.start_load_team_members(team_id)

    def _on_member_created(self, message: str, success: bool) -> None:  # noqa: FBT001
        if success:
            self._show_manage_status(self.member_status_lbl, message, error=False)
            team_id = self.member_team_combo.currentData()
            if team_id is not None:
                self.manage_worker.start_load_team_members(team_id)
        else:
            self._show_manage_status(self.member_status_lbl, message, error=True)

    def _on_members_loaded(self, members: list) -> None:
        self.team_member_list.clear()
        id_to_name = (
            {v: k for k, v in self._cache.representatives.items()}
            if self._cache else {}
        )
        for member in members:
            rep_name = id_to_name.get(
                member.representative_id, str(member.representative_id),
            )
            self.team_member_list.addItem(
                f"{rep_name.title()} - {member.rep_classification}",
            )

    # Manage Tab Handlers - RTCL
    def _handle_create_rtcl(self) -> None:
        team_id = self.rtcl_team_combo.currentData()
        customer_id = self.rtcl_customer_combo.currentData()
        location_id = self.rtcl_location_combo.currentData()
        if team_id is None or customer_id is None or location_id is None:
            self._show_manage_status(
                self.rtcl_status_lbl,
                "Select a team, customer, and location.",
                error=True,
            )
            return
        if self._manage_worker_busy(self.rtcl_status_lbl):
            return
        self.manage_worker.start_create_rtcl(team_id, customer_id, location_id)

    def _on_rtcl_created(self, message: str, success: bool) -> None:  # noqa: FBT001
        if success:
            self._show_manage_status(self.rtcl_status_lbl, message, error=False)
        else:
            self._show_manage_status(self.rtcl_status_lbl, message, error=True)

    def _handle_delete_rtcl(self) -> None:
        team_id = self.rtcl_team_combo.currentData()
        customer_id = self.rtcl_customer_combo.currentData()
        location_id = self.rtcl_location_combo.currentData()
        if team_id is None or customer_id is None or location_id is None:
            self._show_manage_status(
                self.rtcl_status_lbl,
                "Select a team, customer, and location.",
                error=True,
            )
            return
        if self._manage_worker_busy(self.rtcl_status_lbl):
            return

        confirm = QMessageBox.question(
            self,
            "Remove Relationship",
            "Remove this team's link to the selected customer location?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        self.manage_worker.start_delete_rtcl(team_id, customer_id, location_id)

    def _on_rtcl_deleted(self, message: str, success: bool) -> None:  # noqa: FBT001
        self._show_manage_status(self.rtcl_status_lbl, message, error=not success)

    def _on_manage_worker_error(self, message: str, trace: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Unexpected Error")
        box.setText("An error occurred while processing the request.")
        box.setInformativeText(message)
        box.setDetailedText(trace)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    # Mangage Tab Data Refresh
    def _refresh_manage_lists(self) -> None:
        if not self._cache:
            return

        self.rep_list.clear()
        for name in sorted(self._cache.representatives):
            self.rep_list.addItem(name.title())
        self._reload_combo(self.member_rep_combo, self._cache.representatives)

        self.team_list.clear()
        for name in sorted(self._cache.rep_teams):
            self.team_list.addItem(name.title())
        self._reload_combo(self.member_team_combo, self._cache.rep_teams)
        self._reload_combo(self.rtcl_team_combo, self._cache.rep_teams)

        self._reload_combo(self.rtcl_customer_combo, self._cache.customers)

        current_location = self.rtcl_location_combo.currentData()
        self.rtcl_location_combo.blockSignals(True)  # noqa: FBT003
        self.rtcl_location_combo.clear()
        for (city, state), location_id in (self._cache.locations.items()):
            self.rtcl_location_combo.addItem(
                f"{str(city).title() if city else ""}, "
                f"{str(state).upper() if state else ""}",
                userData=location_id,
            )
        if current_location is not None:
            idx = self.rtcl_location_combo.findData(current_location)
            if idx >= 0:
                self.rtcl_location_combo.setCurrentIndex(idx)
        self.rtcl_location_combo.blockSignals(True)  # noqa: FBT003

    def _reload_combo(self, combo: QComboBox, mapping: dict | set) -> None:
        current = combo.currentData()
        combo.blockSignals(True)  # noqa: FBT003
        combo.clear()
        for name in sorted(mapping):
            display = name.title() if isinstance(name, str) else str(name)
            combo.addItem(display, userData=mapping[name])
        if current is not None:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)  # noqa: FBT003

    def _show_manage_status(self, label: QLabel, text: str, *, error: bool) -> None:
        label.setObjectName("errorLabel" if error else "successLabel")
        label.style().unpolish(label)
        label.style().polish(label)
        label.setText(text)
        label.setVisible(True)

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
        self.manage_worker.cache = cache
        self._refresh_manage_lists()

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
