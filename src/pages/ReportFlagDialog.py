from pathlib import Path
from functools import partial
import traceback
 
from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, 
    QDialog, QCompleter,
)
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QFont
 
from src.FileHandler import FileHandler
from src.Report import Report
from DataCache import DataCache
from src.DBConnection import *

# Shared Constants
RESULT_CODES: dict[int, tuple[str, str, bool]] = {
    0: ("Success",               "Report inserted successfully.",                                        False),
    1: ("Manufacturer Unknown",  "The manufacturer could not be identified.",                            True),
    2: ("Unknown Aliases",       "Unknown customer aliases were encountered in the report.",              True),
    3: ("Report Already Present","Report for this manufacturer and period already present in database.",  True),
    4: ("Insert Cancelled",      "Insert operation was cancelled.",                                      False),
}
 
STATUS_COLORS: dict[str, str] = {
    "queued":     "#94a3b8",
    "processing": "#60a5fa",
    "success":    "#22c55e",
    "warning":    "#f59e0b",
    "error":      "#ef4444",
}
 
CODE_TO_STATUS: dict[int, str] = {
    0: "success",
    1: "warning",
    2: "warning",
    3: "warning",
    4: "error",
}
 
# Codes for which the user can open the resolution dialog
RESOLVABLE_CODES: frozenset[int] = frozenset({1, 2, 3})
 
# Qt item-data roles used in the file-queue list
ROLE_FILEPATH = Qt.UserRole
ROLE_CODE     = Qt.UserRole + 1

class ReportFlagDialog(QDialog):
    # Emitted after successful retry
    retry_done = Signal(int, int) # (queue_index, new_code)
    
    def __init__(self, parent: QWidget, report: Report, code: int, queue_index: int, cache: DataCache):
        super().__init__(parent)
        self.report = report
        self.code = code
        self.queue_index = queue_index
        self.connector = DBConnector()
        self.connector.connect()
        self._factory = DAOFactory(self.connector)
        self._handler = FileHandler(self._factory, cache)
        self.cache = cache
        self.cache.refresh()
        self._resolution_panel = None
        self._status_lbl = None
        self._mfr_input = None
        self._customer_model: QStringListModel | None = None
        self._alias_inputs: dict[str, QLineEdit] = {}
        
        self.setWindowTitle("Resolve Flag")
        self.setMinimumWidth(750)
        self.setModal(True)
        
        self._build_ui()
        
    def _build_ui(self):
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
        badge = QLabel(f" {badge_text} ")
        badge.setObjectName("statusBadge")
        badge.setStyleSheet(f"background-color: {badge_color};")
        badge.setFixedHeight(22)
        badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        root.addWidget(badge)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        root.addWidget(separator)
        
        # Issue Description
        _, description, _ = RESULT_CODES.get(self.code, ("", "Unknown issue.", True))
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setObjectName("subtitle")
        root.addWidget(desc_lbl)
        
        # Code Specific Resolution Panel
        self._resolution_panel = QFrame()
        self._resolution_panel.setObjectName("formSection")
        panel_layout = QVBoxLayout(self._resolution_panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(12)
        
        if self.code == 1:
            self._build_manufacturer_panel(panel_layout)
        elif self.code == 2:
            self._build_aliases_panel(panel_layout)
        elif self.code == 3:
            self._build_overwrite_panel(panel_layout)
            
        root.addWidget(self._resolution_panel)
        
        # Status Label After Retry
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.hide()
        root.addWidget(self._status_lbl)
        
        # Button Row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setObjectName("cancelBtn")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        
        root.addLayout(btn_row)
        
    # Code 1: Manufacturer Unknown
    def _build_manufacturer_panel(self, layout: QVBoxLayout):
        raw_name = self.report.manufacturerName
        
        info = QLabel(
            f"The manufacturer <b>{raw_name}</b> was not found in the database.\n"
            "Enter the correct name to add, then retry insertion."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        form = QFormLayout()
        form.setSpacing(8)
        self._mfr_input = QLineEdit() 
        self._mfr_input.setPlaceholderText("Exact manufacturer name...")
        self._mfr_input.setText(raw_name if raw_name != "-" else "")
        form.addRow("Manufacturer name:", self._mfr_input)
        layout.addLayout(form)
        
        add_btn = QPushButton("Add Manufacturer & Retry")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setMinimumHeight(38)
        add_btn.clicked.connect(self._resolve_manufacturer)
        layout.addWidget(add_btn)
        
    def _resolve_manufacturer(self):
        name = self._mfr_input.text().strip().lower()
        if not name:
            self._show_status("Please enter a manufacturer name.", error=True)
            return
        try:
            manufacturer = self._factory.manufacturers.create(Manufacturer(manufacturer_id=None, manufacturer_name=name))
            if manufacturer.manufacturer_name == self.report.manufacturerName.strip().lower():
                self.cache.manufacturers[manufacturer.manufacturer_name] = manufacturer.manufacturer_id
                self._retry_insert()
            else:
                print("names do not match")
        except Exception as e:
            self._show_status(f"Error adding manufacturer: {e}", error=True)
            
    # Code 2: Uknown Aliases
    def _build_aliases_panel(self, layout: QVBoxLayout):
        unknown_aliases: list[str] = getattr(self.report, "unknown_aliases", [])
        
        info = QLabel(
            f"{len(unknown_aliases)} unrecognised customer alias(es) were found. \n"
            "Map each alias to an existing customer name then retry."
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
        inner_layout = QFormLayout(inner)
        inner_layout.setSpacing(8)
        
        self._alias_inputs: dict[str, QLineEdit] = {}
        for alias in unknown_aliases:
            row = QHBoxLayout()
            #row.addStretch()
            field = QLineEdit()
            field.setPlaceholderText("Type to search customers...")
            field.setCompleter(self._make_completer())
            row.addWidget(field, stretch=10)
            add_cust_btn = QPushButton("Add as new customer")
            add_cust_btn.clicked.connect(partial(self._add_as_new_customer, alias))
            row.addWidget(add_cust_btn)
            inner_layout.addRow(f"{alias}:", row)
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
        add_cust_btn.clicked.connect(lambda: self._add_new_customer(field.text().strip()))
        lower_layout.addWidget(add_cust_btn)
        layout.addWidget(lower)
        
        save_btn = QPushButton("Save Mappings & Retry")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setMinimumHeight(38)
        save_btn.clicked.connect(self._resolve_aliases)
        layout.addWidget(save_btn)
        
    def _make_completer(self) -> QCompleter:
        """Return a new QCompleter based on the shared customer model"""
        completer = QCompleter(self._customer_model, self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setMaxVisibleItems(12)
        return completer
    
    def _refresh_name_completers(self):
        """Update shared customer model after a customer is added"""
        customer_names = sorted(self.cache.customers.keys())
        self._customer_model.setStringList(customer_names)
        
    def _add_new_customer(self, cust_name: str):
        try: 
            customer = self._factory.customers.create(Customer(customer_id=None, customer_name=cust_name))
            self.cache.customer_aliases[customer.customer_name] = customer.customer_id
            self._refresh_name_completers()
            self._show_status(f"{customer.customer_name} successfully added as a new customer", error=False)
        except Exception as e:
            self._show_status(f"Failed to insert new customer: {e}", error=True)
        
    def _add_as_new_customer(self, alias: str):
        if alias in self._alias_inputs:
            try:
                customer = self._factory.customers.create(Customer(customer_id=None, customer_name=alias))
                self.cache.customer_aliases[customer.customer_name] = customer.customer_id
                self._refresh_name_completers()
                self._show_status(f"{customer.customer_name} successfully added as new customer", error=False)
                #self._alias_inputs.pop(alias)
                
            except Exception as e:
                self._show_status(f"Failed to insert new customer: {e}", error=True)
        
    def _resolve_aliases(self):
        valid_names = set(self.cache.customer_aliases.keys())
        mappings = {alias: field.text().strip() for alias, field in self._alias_inputs.items()}
        
        unmapped = [a for a, v in mappings.items() if not v]
        if unmapped:
            self._show_status(
                f"Please map all aliases before retrying. Missing. {', '.join(unmapped)}",
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
            alias_list: list[CustomerAlias] = [] 
            for alias, customer in mappings.items():
                customer_id = self.cache.customers[customer]
                if customer_id:
                    alias_list.append(CustomerAlias(alias=alias, customer_id=customer_id))
                
            success = self._factory.customer_aliases.create_bulk(alias_list)
            if(success):
                self.cache.refresh()
                self._retry_insert()
            else:
                raise ValueError("Aliases failed to insert.")
        except Exception as e:
            self._show_status(f"Error saving mappings: {e}", error=True)
            
    # Code 3: Report Already Present
    def _build_overwrite_panel(self, layout: QVBoxLayout):
        mfr = getattr(self.report, "manufacturerName", "Unknown")
        month = getattr(self.report, "month", "Unknown")
        year = getattr(self.report, "year", "Unknown")
        
        info = QLabel(
            f"A report for <b>{mfr}</b> - month <b>{month}</b> - year <b>{year}</b> already exists.\n"
            "You can overwrite the existing record or leave it unchanged."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        overwrite_btn = QPushButton("Overwrite Existing Report")
        overwrite_btn.setCursor(Qt.PointingHandCursor)
        overwrite_btn.setMinimumHeight(38)
        overwrite_btn.clicked.connect(self._resolve_overwrite)
        layout.addWidget(overwrite_btn)
        
    def _resolve_overwrite(self):
        try:
            # TODO: update the existing report with the data from the current report
            # Update lists
            self._emit_retry(0)
        except Exception as e:
            self._show_status(f"Error overwriting report: {e}", error=True)
            
    def _retry_insert(self):
        try:
            valid = self._handler.check_report(self.report)
            
            unknown_list = valid[1]
            manufacturer_exists = valid[0][0]
            report_already_exists = valid[0][1]
            
            if report_already_exists:
                new_code = 3
            elif manufacturer_exists and len(unknown_list) == 0:
                self._handler.insert_report(self.report)
                new_code = 0
            elif not manufacturer_exists:
                new_code = 1
            else:
                self.report.unknown_aliases = unknown_list
                new_code = 2
                
            self._emit_retry(new_code)
        except Exception as e:
            self._show_status(f"Retry failed: {traceback.format_exc()},", error=True)
    
    def _emit_retry(self, new_code: int):
        self.retry_done.emit(self.queue_index, new_code)
        _, message, _ = RESULT_CODES.get(new_code, ("", "Unknown result.", True))
        if new_code == 0:
            self._show_status(f"Success - {message}", error=False)
            self._resolution_panel.setEnabled(False)
            self.connector.close()
        else:
            self._show_status(f"Still flagged: {message}", error=True)
            
    def _badge_info(self) -> tuple[str, str]:
        status = CODE_TO_STATUS.get(self.code, "error")
        label = RESULT_CODES.get(self.code, ("Unknown",))[0]
        color = STATUS_COLORS.get(status, "#94a3b8")
        return label, color
    
    def _show_status(self, text: str, *, error: bool):
        self._status_lbl.setObjectName("errorLabel" if error else "successLabel")
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)
        self._status_lbl.setText(text)
        self._status_lbl.show()
        
    def closeEvent(self, event):
        self._factory = None
        self._handler = None
        self.connector.close()
        super().closeEvent(event)