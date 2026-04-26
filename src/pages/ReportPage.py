import os
from pathlib import Path
from collections import Counter

from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QPushButton,
    QSizePolicy, QMessageBox, QListWidget, QFileDialog,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from datetime import date

from pages.Sidebar import Sidebar
from pages.ReportFlagDialog import (
    ReportFlagDialog,
    RESULT_CODES, STATUS_COLORS, CODE_TO_STATUS, RESOLVABLE_CODES,
    ROLE_FILEPATH, ROLE_CODE,
)
from src.ReportHandler import ReportHandler
from src.Report import Report
from src.DBConnection import *

class InsertWorker(QThread):
    # 0 - Success
    # 1 - Manufacturer Unknown
    # 2 - Unknown Aliases
    # 3 - Report Already Exists
    # 4 - Cancelled
    file_done = Signal(int, int)
    all_done = Signal()
    
    def __init__(self, reports: list[Report] = None, connector: DBConnector = None):
        super().__init__()
        self.factory = DAOFactory(connector)
        self.reports = reports
        self.handler = ReportHandler(connector, self.factory)
        self.handler.update_lists()
        
    def run(self):
        for i, report in enumerate(self.reports):
            code = self._insert_report(report)
            self.file_done.emit(i, code)
        self.all_done.emit()
        
    def _insert_report(self, report: Report) -> int:
        report = self.handler.standardize(report)
        valid = self.handler.check_report(report)
        
        unknown_list = valid[1]
        manufacturer_exists = valid[0][0]
        report_already_exists = valid[0][1]
        
        if (report_already_exists):
            return 3
        if (manufacturer_exists) and len(unknown_list) == 0:
            self.handler.insert_report(report)
            return 0
        elif not manufacturer_exists:
            return 1
        elif len(unknown_list) > 0:
            report.unknown_aliases = unknown_list
            return 2

class ResultDialog(QMessageBox):
    def __init__(self, parent: QWidget, filepath: str, code: int):
        super().__init__(parent)
        
        title, message, is_warning = RESULT_CODES.get(code, ("Unknown Result", f"Received unexpected code {code}.", True))
        
        self.setWindowTitle(f"{title}")
        self.setText(f"<b>{Path(filepath).name}</b>")
        self.setInformativeText(message)
        self.setStandardButtons(QMessageBox.Ok)
        self.setIcon(QMessageBox.Warning if is_warning else QMessageBox.Information)
            
# Report Page
class ReportPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.worker: InsertWorker | None = None
        self.sidebar = None
        self.single_file_btn = None
        self.folder_btn = None
        self.clear_btn = None
        self.submit_btn = None
        self.queue_label = None
        self._last_codes: list[int] = []
        self._queued_reports: list[Report] = []
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
        
        content_widget = QWidget()
        content_widget.setObjectName("content")
        scroll.setWidget(content_widget)
        
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(0)
        
        # Header
        title = QLabel("Insert Reports")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(4)
        
        sub = QLabel("Select a single report file or a folder to queue multiple reports.")
        sub.setObjectName("subtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(28)
        
        # File Selection
        layout.addWidget(self._section_label("Select Files"))
        layout.addSpacing(8)
        
        select_frame = QFrame()
        select_frame.setObjectName("formSection")
        select_layout = QVBoxLayout(select_frame)
        select_layout.setContentsMargins(20, 20, 20, 20)
        select_layout.setSpacing(12)
        
        # Button Row
        btn_select_row = QHBoxLayout()
        btn_select_row.setSpacing(10)
        
        self.single_file_btn = QPushButton("Add File")
        self.single_file_btn.setMinimumHeight(42)
        self.single_file_btn.setCursor(Qt.PointingHandCursor)
        self.single_file_btn.clicked.connect(self._select_single_file)
        btn_select_row.addWidget(self.single_file_btn)
        
        self.folder_btn = QPushButton("Add Folder")
        self.folder_btn.setMinimumHeight(42)
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(self._select_folder)
        btn_select_row.addWidget(self.folder_btn)
        
        btn_select_row.addStretch()
        
        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.setObjectName("cancelBtn")
        self.clear_btn.setMinimumHeight(42)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_queue)
        btn_select_row.addWidget(self.clear_btn)
        
        select_layout.addLayout(btn_select_row)
        
        # Queue Count Label
        self.queue_label = QLabel("No files queued.")
        self.queue_label.setObjectName("subtitle")
        select_layout.addWidget(self.queue_label)
        
        layout.addWidget(select_frame)
        layout.addSpacing(24)
        
        # Queue List
        layout.addWidget(self._section_label("File Queue"))
        layout.addSpacing(4)
        
        hint = QLabel("Click a flagged item to open the resolution panel.")
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)
        layout.addSpacing(6)
        
        list_frame = QFrame()
        list_frame.setObjectName("formSection")
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(0)
        
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(220)
        self.file_list.setSpacing(2)
        self.file_list.setObjectName("fileQueue")
        self.file_list.itemClicked.connect(self._on_item_clicked)
        list_layout.addWidget(self.file_list)
        
        layout.addWidget(list_frame)
        layout.addSpacing(24)
        
        # Submit Row
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        
        self.submit_btn = QPushButton("Insert Reports")
        self.submit_btn.setMinimumSize(180, 44)
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self._handle_insert)
        submit_row.addWidget(self.submit_btn)
        
        layout.addLayout(submit_row)
        layout.addStretch()
        
    # File Selection
    def _select_single_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Report File(s)",
            "",
            "Report Files (*.csv);;All Files (*)"
        )    
        if paths:
            report = Report()
            report.set_info(paths[0])
            self._add_to_queue([report, ])
            
    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Report Folder",
            "",
            QFileDialog.ShowDirsOnly
        )
        if not folder:
            return
        
        # Get all supported files in the folder
        supported = {".csv"}
        paths = [
            str(p) for p in Path(folder).iterdir()
            if p.is_file() and p.suffix.lower() in supported
        ]
        
        if not paths:
            QMessageBox.information(
                self,
                "No Files Found",
                "The selected folder contains no supported report files\n"
                "(.csv)."
            )
            return
        
        reports = []
        for path in paths:
            report = Report()
            report.set_info(path)
            reports.append(report)
        self._add_to_queue(reports)
    
    def _add_to_queue(self, reports: list[Report]):
        existing = set(self._queued_reports)
        added = 0
        for report in reports:
            if report not in existing:
                self._queued_reports.append(report)
                existing.add(report)
                self._add_list_item(report, "queued", code=None)
                added += 1
        
        self._update_queue_label()
        # TODO look into changing added to checking if queued paths is empty
        if added:
            self.submit_btn.setEnabled(True)
            
    def _add_list_item(self, report: Report, status: str, code: int | None) -> QListWidgetItem:
        color = STATUS_COLORS[status]
        filename = Path(report.filePath).name
        folder = str(Path(report.filePath).parent)
        label = RESULT_CODES[code][0] if code is not None else status.capitalize()
        
        item = QListWidgetItem(f"{filename} - {folder} -- {label}")
        item.setForeground(QColor(color))
        item.setData(ROLE_FILEPATH, str(report.filePath))
        item.setData(ROLE_CODE, code)
        
        if code in RESOLVABLE_CODES:
            item.setToolTip("Click to resolve")
        
        self.file_list.addItem(item)
        return item
    
    def _clear_queue(self):
        if self.worker and self.worker.isRunning():
            return # Don't clear queue while processing
        self._queued_reports.clear()
        self.file_list.clear()
        self._update_queue_label()
        self.submit_btn.setEnabled(False)
        
    def _update_queue_label(self):
        n = len(self._queued_reports)
        if n == 0:
            self.queue_label.setText("No files queued.")
        else:
            self.queue_label.setText(f"{n} file(s) queued")
            
    def _on_item_clicked(self, item: QListWidgetItem):
        if self.worker and self.worker.isRunning():
            return
        
        code = item.data(ROLE_CODE)
        if code not in RESOLVABLE_CODES:
            return
        
        filepath = item.data(ROLE_FILEPATH)
        if filepath is None:
            return
        filepath = str(filepath)
        report = next(
            (r for r in self._queued_reports if str(r.filePath) == filepath), None
        )        
        if report is None:
            return
        
        queue_index = next(
            (i for i, r in enumerate(self._queued_reports) if str(r.filePath) == filepath), None,
        )
        
        dialog = ReportFlagDialog(
            parent = self.window(),
            report = report,
            code = code,
            queue_index = queue_index,
            connector = self.controller.connector,
        )
        dialog.retry_done.connect(self._on_flag_resolved)
        dialog.exec()
        
    def _on_flag_resolved(self, queue_index: int, new_code: int):
        item = self.file_list.item(queue_index)
        if item is None:
            return
        
        report = self._queued_reports[queue_index]
        status = CODE_TO_STATUS.get(new_code, "error")
        color = STATUS_COLORS[status]
        label = RESULT_CODES.get(new_code, ("Unknown", ))[0]
        filename = Path(report.filePath).name
        folder = str(Path(report.filePath).parent)
        
        item.setText(f"{filename} - {folder} -- {label}")
        item.setForeground(QColor(color))
        item.setData(ROLE_CODE, new_code)
        item.setToolTip("Click to resolve this flag" if new_code in RESOLVABLE_CODES else "")
    
    # Insertion
    def _handle_insert(self):
        if not self._queued_reports:
            return
        
        self._last_codes.clear()
        # Lock UI while inserting
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("Inserting...")
        self.single_file_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # Mark all items in list as queued/pending
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            filepath = item.data(ROLE_FILEPATH)
            item.setText(f"{Path(filepath).name} - {str(Path(filepath).parent)} -- Queued")
            item.setForeground(QColor(STATUS_COLORS["queued"]))
            item.setData(ROLE_CODE, None)
            
        self.worker = InsertWorker(reports=list(self._queued_reports), connector=self.controller.connector)
        self.worker.file_done.connect(self._on_file_done)
        self.worker.all_done.connect(self._on_all_done)
        self.worker.start()
        
    def _on_file_done(self, index: int, code: int):
        # Update the list item status
        filepath = str(self._queued_reports[index].filePath)
        item = self.file_list.item(index)
        self._last_codes.append(code)
        
        status = CODE_TO_STATUS.get(code, "error")
        color = STATUS_COLORS[status]
        label = RESULT_CODES[code][0]
        
        if item:
            filename = Path(filepath).name
            folder = str(Path(filepath).parent)
            item.setText(f"{filename} - {folder} -- {label}")
            item.setForeground(QColor(color))
            item.setData(ROLE_CODE, code)
            item.setToolTip("Click to resolve this flag" if code in RESOLVABLE_CODES else "")
            self.file_list.scrollToItem(item)
        
    def _on_all_done(self):
        self.submit_btn.setText("Insert Reports")
        self.submit_btn.setEnabled(bool(self._queued_reports))
        self.single_file_btn.setEnabled(True)
        self.folder_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # Summary popup
        counts = Counter(CODE_TO_STATUS.get(code, "error") for code in self._last_codes)
        lines = []
        
        if counts.get("success"):
            lines.append(f"{counts["success"]} inserted successfully")
        if counts.get("warning"):
            lines.append(f"{counts["warning"]} completed with warnings")
        if counts.get("error"):
            lines.append(f"{counts["error"]} failed")
            
        msg = QMessageBox(self)
        msg.setWindowTitle("Batch Complete")
        msg.setIcon(QMessageBox.Warning if (counts.get("warning") or counts.get("error")) else QMessageBox.Information)
        msg.setText(f"Processed {len(self._queued_reports)} file(s).")
        msg.setInformativeText("\n".join(lines))
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        
    # Helpers
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("pageTitle")
        lbl.setStyleSheet("font-size: 15px;")
        return lbl
    
    def on_show(self):
        user = self.controller.current_user or "User"
        self.sidebar.update_user(user)