"""To be finished later.""" # noqa: CPY001

import traceback
from functools import partial
from pathlib import Path

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.data_cache import DataCache
from src.db_connection import (
    Customer,
    CustomerAlias,
    DAOFactory,
    DBConnector,
    Manufacturer,
)
from src.file_handler import FileHandler
from src.report import Report

# Shared Constants
RESULT_CODES: dict[int, tuple[str, str, bool]] = {
    0: ("Success", "Report inserted successfully.", False),
    1: ("Manufacturer Unknown", "The manufacturer could not be identified.", True),
    2: ("Unknown Aliases", "Unknown customer aliases were encountered in the report.",
        True,
    ),
    3: ("Report Already Present",
        "Report for this manufacturer and period already present in database.", True,
    ),
    4: ("Insert Cancelled", "Insert operation was cancelled.", False),
}

STATUS_COLORS: dict[str, str] = {
    "queued":     "#94a3b8",
    "processing": "#60a5fa",
    "success":    "#22c55e",
    "warning":    "#f59e0b",
    "duplicate":  "#70faed",
    "error":      "#ef4444",
}

CODE_TO_STATUS: dict[int, str] = {
    0: "success",
    1: "warning",
    2: "warning",
    3: "duplicate",
    4: "error",
}

# Codes for which the user can open the resolution dialog
RESOLVABLE_CODES: frozenset[int] = frozenset({1, 2, 3})

# Qt item-data roles used in the file-queue list
ROLE_FILEPATH = Qt.UserRole
ROLE_CODE     = Qt.UserRole + 1

MANUFACTURER_CLASSIFICATIONS: list[tuple[str, str]] = [
    ("heating", "Heating"),
    ("plumbing", "Plumbing"),
]

class ReportFlagDialog(QDialog):
    """Class for the displaying and handling of flagged reports.

    Displays flag specific window based on status code of report.
    Emits retry_done (Signal[int, int]) upon successful retry.
    """

    # Emitted after successful retry
    retry_done = Signal(int, int) # (queue_index, new_code)

    def __init__(
        self,
        parent: QWidget,
        report: Report,
        code: int,
        queue_index: int,
        cache: DataCache,
    ) -> None:
        """Initialize attributes to default values and connect to database.

        Args:
            parent (QWidget):
                Window of the page the dialog should be displayed on.
            report (Report):
                Flagged report to be resolved.
            code (int):
                The status code of the flagged report.
            queue_index (int):
                The index of the flagged report in the report queue.
            cache (DataCache):
                Reference to DataCache of main app.

        """
        super().__init__(parent)
        self.report = report
        self.code = code
        self.queue_index = queue_index
        self.cache = cache
        self.cache.refresh_all()
        self._resolution_panel = None
        self._status_lbl = None
        self._badge_lbl = None
        self._desc_lbl = None
        self._mfr_input = None
        self._mfr_classification_combo: QComboBox | None = None
        self._customer_model: QStringListModel | None = None
        self._alias_inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle("Resolve Flag")
        self.setMinimumWidth(800)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self) -> None: # noqa: PLR0915 TODO separate into multiple funcitons
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Header
        filename = Path(self.report.filePath).name
        title_lbl = QLabel(filename)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        root.addWidget(title_lbl)

        badge_text, badge_color = self._badge_info()
        self._badge_lbl = QLabel(f" {badge_text} ")
        self._badge_lbl.setObjectName("statusBadge")
        self._badge_lbl.setStyleSheet(f"background-color: {badge_color};")
        self._badge_lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        root.addWidget(self._badge_lbl)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        root.addWidget(separator)

        # Issue Description
        _, description, _ = RESULT_CODES.get(self.code, ("", "Unknown issue.", True))
        self._desc_lbl = QLabel(description)
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setObjectName("subtitle")
        root.addWidget(self._desc_lbl)

        # Code Specific Resolution Panel
        self._resolution_panel = QFrame()
        self._resolution_panel.setObjectName("formSection")
        panel_layout = QVBoxLayout(self._resolution_panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(12)

        self._populate_panel(self.code, panel_layout)

        root.addWidget(self._resolution_panel)

        # Status Label After Retry
        status_row = QHBoxLayout()

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        status_row.addWidget(self._status_lbl, stretch=1)

        self._clear_status_btn = QPushButton("Clear")
        self._clear_status_btn.setObjectName("cancelBtn")
        self._clear_status_btn.setCursor(Qt.PointingHandCursor)
        self._clear_status_btn.hide()
        self._clear_status_btn.clicked.connect(self._clear_status)
        status_row.addWidget(self._clear_status_btn)

        root.addLayout(status_row)

        # Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setObjectName("cancelBtn")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

    def _populate_panel(self, code: int, layout: QVBoxLayout) -> None:
        manuf_unknown = 1
        unknown_alias = 2
        already_exists = 3

        if code == manuf_unknown:
            self._build_manufacturer_panel(layout)
        elif code == unknown_alias:
            self._build_aliases_panel(layout)
        elif code == already_exists:
            self._build_overwrite_panel(layout)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
            elif sub_layout := item.layout():
                self._clear_layout(sub_layout)

    def _rebuild_panel_for_code(self, new_code: int) -> None:
        self.code = new_code

        # Update Badge Label
        badge_text, badge_color = self._badge_info()
        self._badge_lbl.setText(f" {badge_text} ")
        self._badge_lbl.setStyleSheet(f"background-color: {badge_color};")

        # Update Description Label
        _, description, _ = RESULT_CODES.get(new_code, ("", "Unknown issue.", True))
        self._desc_lbl.setText(description)

        # Clear all widgets from the panel layout
        self._clear_layout(self._resolution_panel.layout())

        # Reset per-panel state
        self._mfr_input = None
        self._mfr_classification_combo = None
        self._customer_model = None
        self._alias_inputs = {}

        # Rebuild for new code
        self._populate_panel(new_code, self._resolution_panel.layout())
        self._resolution_panel.setEnabled(True)
        self._status_lbl.setText("")
        self._clear_status_btn.hide()

    # Code 1: Manufacturer Unknown
    def _build_manufacturer_panel(self, layout: QVBoxLayout) -> None:
        raw_name = self.report.manufacturerName

        info = QLabel(
            f"The manufacturer <b>{raw_name}</b> was not found in the database.\n"
            "Enter the correct name to add, "
            "select classification, then retry insertion.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)

        # Name entry
        self._mfr_input = QLineEdit()
        self._mfr_input.setPlaceholderText("Exact manufacturer name...")
        self._mfr_input.setText(raw_name)
        name_row.addWidget(self._mfr_input, stretch=1)

        # Classification Dropdown
        self._mfr_classification_combo = QComboBox()
        for value, label in MANUFACTURER_CLASSIFICATIONS:
            self._mfr_classification_combo.addItem(label, userData=value)
        self._mfr_classification_combo.setMinimumHeight(38)
        self._mfr_classification_combo.setFixedWidth(130)
        name_row.addWidget(self._mfr_classification_combo)

        layout.addLayout(name_row)

        add_btn = QPushButton("Add Manufacturer && Retry")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setMinimumHeight(38)
        add_btn.setMinimumWidth(100)
        add_btn.clicked.connect(self._resolve_manufacturer)
        layout.addWidget(add_btn)

    def _resolve_manufacturer(self) -> None:
        connector = DBConnector()
        connector.connect()
        _factory = DAOFactory(connector)
        name = self._mfr_input.text().strip().lower()
        classification = str(self._mfr_classification_combo.currentData()).lower()
        if not name:
            self._show_status("Please enter a manufacturer name.", error=True)
            return
        try:
            manufacturer = _factory.manufacturers.create(
                Manufacturer(
                    manufacturer_id=None,
                    manufacturer_name=name,
                    manufacturer_classification=classification,
                ),
            )
            if (
                manufacturer.manufacturer_name
                == self.report.manufacturerName.strip().lower()
            ):
                key = manufacturer.manufacturer_name
                self.cache.manufacturers[key] = manufacturer.manufacturer_id
                self._retry_insert()
        except Exception:  # noqa: BLE001
            self._show_status(traceback.format_exc(), error=True)
        finally:
            connector.close()

    # Code 2: Unknown Aliases
    def _build_aliases_panel(self, layout: QVBoxLayout) -> None:
        unknown_aliases: list[str] = getattr(self.report, "unknown_aliases", [])
        unknown_aliases = sorted(unknown_aliases)

        info = QLabel(
            f"{len(unknown_aliases)} unrecognised customer alias(es) were found. \n"
            "Map each alias to an existing customer name then retry.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        hint = QLabel("Type to search - partial matches supported.")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        # Shared customer data string model
        customer_names = sorted(self.cache.customers.keys())
        self._customer_model = QStringListModel(customer_names)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(min(180, max(60, len(unknown_aliases) * 46)))

        inner = QWidget()
        self._inner_layout = QFormLayout(inner)
        self._inner_layout.setSpacing(8)

        self._alias_inputs: dict[str, QLineEdit] = {}
        for alias in unknown_aliases:
            row = QHBoxLayout()
            field = QLineEdit()
            field.setPlaceholderText("Type to search customers...")
            field.setCompleter(self._make_completer())
            row.addWidget(field, stretch=10)
            add_cust_btn = QPushButton("Add as new customer")
            add_cust_btn.clicked.connect(partial(self._add_as_new_customer, alias, row))
            row.addWidget(add_cust_btn)
            self._inner_layout.addRow(f"{alias}:", row)
            self._alias_inputs[alias] = field

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        lower = QWidget()
        lower_layout = QHBoxLayout(lower)
        lower_layout.setSpacing(8)

        field = QLineEdit()
        field.setPlaceholderText("New customer name...")
        lower_layout.addWidget(field)

        add_cust_btn = QPushButton("Add new customer")
        add_cust_btn.setCursor(Qt.PointingHandCursor)
        add_cust_btn.clicked.connect(
            lambda: self._add_new_customer(field.text().strip()),
        )
        lower_layout.addWidget(add_cust_btn)
        layout.addWidget(lower)

        save_btn = QPushButton("Save Mappings && Retry")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setMinimumHeight(38)
        save_btn.setMinimumWidth(180)
        save_btn.clicked.connect(self._resolve_aliases)
        layout.addWidget(save_btn)

    def _make_completer(self) -> QCompleter:
        #Return a new QCompleter based on the shared customer model.
        completer = QCompleter(self._customer_model, self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setMaxVisibleItems(12)
        return completer

    def _refresh_name_completers(self) -> None:
        #Update shared customer model after a customer is added
        customer_names = sorted(self.cache.customers.keys())
        self._customer_model.setStringList(customer_names)

    def _add_new_customer(self, cust_name: str) -> None:
        try:
            connector = DBConnector()
            connector.connect()
            _factory = DAOFactory(connector)
            customer = _factory.customers.create(
                Customer(customer_id=None, customer_name=cust_name),
            )
            self.cache.customers[customer.customer_name] = customer.customer_id
            self.cache.customer_aliases[customer.customer_name] = customer.customer_id
            self._refresh_name_completers()
            self._show_status(
                f"{customer.customer_name} successfully added as a new customer",
                error=False,
            )
        except Exception as e:  # noqa: BLE001
            self._show_status(f"Failed to insert new customer: {e}", error=True)
        finally:
            connector.close()

    def _add_as_new_customer(self, alias: str, row: QWidget) -> None:
        if alias in self._alias_inputs:
            try:
                connector = DBConnector()
                connector.connect()
                _factory = DAOFactory(connector)
                customer = _factory.customers.create(
                    Customer(customer_id=None, customer_name=alias),
                )
                self.cache.refresh_customer_aliases()
                self._refresh_name_completers()
                self._show_status(
                    f"{customer.customer_name} successfully added as new customer",
                    error=False,
                    )
                self._inner_layout.removeRow(row)
                self._alias_inputs.pop(alias)

            except Exception:  # noqa: BLE001
                self._show_status(
                    f"Failed to insert new customer: {traceback.format_exc()}",
                    error=True,
                )
            finally:
                connector.close()

    def _resolve_aliases(self) -> None:
        if len(self._alias_inputs) == 0:
            try:
                self._retry_insert()
            except Exception as e:  # noqa: BLE001
                self._show_status(f"Error saving mappings: {e}", error=True)
        else:
            valid_names = set(self.cache.customer_aliases.keys())
            mappings = {
                alias: field.text().strip()
                for alias, field in self._alias_inputs.items()
            }

            unmapped = [a for a, v in mappings.items() if not v]
            if unmapped:
                self._show_status(
                    "Please map all aliases before retrying. "
                    f"Missing. {', '.join(unmapped)}",
                    error=True,
                )
                return
            invalid = [a for a, v in mappings.items() if v and v not in valid_names]
            if invalid:
                self._show_status(
                    f"Unrecognized customer name(s) for : {', '.join(invalid)}. "
                    "Use the autocomplete suggestions or add customer first.",
                    error=True,
                )
                return

            try:
                connector = DBConnector()
                connector.connect()
                _factory = DAOFactory(connector)
                alias_list: list[CustomerAlias] = []
                for alias, customer in mappings.items():
                    customer_id = self.cache.customers[customer]
                    if customer_id:
                        alias_list.append(
                            CustomerAlias(alias=alias, customer_id=customer_id),
                        )

                success = _factory.customer_aliases.create_bulk(alias_list)
                if(success):
                    self.cache.refresh_customer_aliases()
                    self._retry_insert()
            except Exception as e:  # noqa: BLE001
                self._show_status(f"Error saving mappings: {e}", error=True)
            finally:
                connector.close()

    # Code 3: Report Already Present
    def _build_overwrite_panel(self, layout: QVBoxLayout) -> None:
        mfr = getattr(self.report, "manufacturerName", "Unknown")
        month = getattr(self.report, "month", "Unknown")
        year = getattr(self.report, "year", "Unknown")

        info = QLabel(
            f"A report for <b>{mfr}</b> - month <b>{month}</b> - year <b>{year}</b>",
            "already exists.\n",
            "You can overwrite the existing record or leave it unchanged.",
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        overwrite_btn = QPushButton("Overwrite Existing Report")
        overwrite_btn.setCursor(Qt.PointingHandCursor)
        overwrite_btn.setMinimumHeight(38)
        overwrite_btn.clicked.connect(self._resolve_overwrite)
        layout.addWidget(overwrite_btn)

    def _resolve_overwrite(self) -> None:
        try:
            # - TODO: update the existing report with the data from the current report
            # Update lists
            self._emit_retry(0)
        except Exception as e:  # noqa: BLE001
            self._show_status(f"Error overwriting report: {e}", error=True)

    def _retry_insert(self) -> None:
        try:
            connector = DBConnector()
            connector.connect()
            _factory = DAOFactory(connector)
            _handler = FileHandler(_factory, self.cache)
            valid = _handler.check_report(self.report)

            unknown_list = valid[1]
            manufacturer_exists = valid[0][0]
            report_already_exists = valid[0][1]

            if report_already_exists:
                new_code = 3
            elif manufacturer_exists and len(unknown_list) == 0:
                _handler.insert_report(self.report)
                new_code = 0
            elif not manufacturer_exists:
                new_code = 1
            else:
                self.report.unknown_aliases = unknown_list
                new_code = 2

            self._emit_retry(new_code)
        except Exception:  # noqa: BLE001
            self._show_status(f"Retry failed: {traceback.format_exc()},", error=True)
        finally:
            connector.close()

    def _emit_retry(self, new_code: int) -> None:
        self.retry_done.emit(self.queue_index, new_code)
        _, message, _ = RESULT_CODES.get(new_code, ("", "Unknown result.", True))
        if new_code == 0:
            self._show_status(f"Success - {message}", error=False)
            self._resolution_panel.setEnabled(False)
        elif new_code != self.code and new_code in RESOLVABLE_CODES:
            self._rebuild_panel_for_code(new_code)
        else:
            self._show_status(f"Still flagged: {message}", error=True)

    def _badge_info(self) -> tuple[str, str]:
        status = CODE_TO_STATUS.get(self.code, "error")
        label = RESULT_CODES.get(self.code, ("Unknown",))[0]
        color = STATUS_COLORS.get(status, "#94a3b8")
        return label, color

    def _show_status(self, text: str, *, error: bool) -> None:
        self._status_lbl.setObjectName("errorLabel" if error else "successLabel")
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)
        self._status_lbl.setText(text)
        self._clear_status_btn.show()

    def _clear_status(self) -> None:
        self._status_lbl.setText("")
        self._clear_status_btn.hide()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Clear connector dependant objects and close DB connection."""
        super().closeEvent(event)
