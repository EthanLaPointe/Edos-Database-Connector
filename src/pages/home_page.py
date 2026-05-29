"""To be finished later."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pages.protocols import AppController
from pages.sidebar import Sidebar
from src.db_connection import DAOFactory, DBConnector, SalesReportSummary
from src.report_exporter import ReportExporter


class _SummaryWorker(QThread):
    """Fetches report summaries on a background thread."""

    done = Signal(list)
    error = Signal(str)

    def run(self) -> None:
        """Connect, fetch summaries, and close the connection."""
        connector = DBConnector()
        try:
            connector.connect()
            factory = DAOFactory(connector)
            summaries = factory.sales_reports.list_summary(limit=10)
            self.done.emit(summaries)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            connector.close()

class _ExportWorker(QThread):
    """Exports a single report to CSV on a background thread."""

    done = Signal(int)
    error = Signal(int)

    def __init__(self, report_id: int, path: str) -> None:
        """Store export parameters.

        Args:
            report_id (int): ID of the report to export.
            path (str): Destination CSV file path.

        """
        super().__init__()
        self._report_id = report_id
        self._path = path

    def run(self) -> None:
        """Connect, export, always close the connection."""
        connector = DBConnector()
        try:
            connector.connect()
            exporter = ReportExporter(connector)
            count = exporter.export_to_csv(self._report_id, self._path)
            self.done.emit(count)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            connector.close()

class HomePage(QWidget):
    """Dashboard page - lists recent reports and provides per-report CSV export."""

    def __init__(self, controller: AppController) -> None:
        """Initialize home page and start UI building.

        Args:
            controller (AppController):
                Protocol containing required methods and attributes from main App.

        """
        super().__init__()
        self.controller = controller
        self.sidebar : Sidebar | None = None
        self.welcome_label: QLabel | None = None
        self._content_layout: QVBoxLayout | None = None
        self._table_container: QFrame | None = None
        self._summary_worker: _SummaryWorker | None = None
        self._export_worker: _ExportWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(controller=self.controller, active_page="home")
        root.addWidget(self.sidebar)

        # Content Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)

        content_widget = QWidget()
        content_widget.setObjectName("content")
        scroll.setWidget(content_widget)

        content = QVBoxLayout(content_widget)
        content.setContentsMargins(32, 28, 32, 28)
        content.setSpacing(0)
        self._content_layout = content

        # Header
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")
        content.addWidget(self.page_title)
        content.addSpacing(4)

        self.welcome_label = QLabel("Welcome back!")
        self.welcome_label.setObjectName("welcomeLabel")
        content.addWidget(self.welcome_label)
        content.addSpacing(24)

        # Table Placeholder
        self._table_container = self._build_table(summaries=None, loading=True)
        content.addWidget(self._table_container)

        content.addStretch()

    def _build_table(  # noqa: PLR0915
        self,
        summaries: list[SalesReportSummary] | None,
        *,
        loading: bool = False,
    ) -> None:
        container = QFrame()
        container.setObjectName("tableContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)

        # Title
        title_row = QHBoxLayout()
        title_row.setContentsMargins(20, 16, 20, 12)

        tbl_title = QLabel("Recent Reports")
        tbl_title.setObjectName("tableTitle")
        tbl_title.setStyleSheet("font-size: 15px;")
        title_row.addWidget(tbl_title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Column Headers
        headers = ["Report ID", "Manufacturer", "Month", "Year", ""]

        header_frame = QFrame()
        header_frame.setObjectName("tableHeader")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        for i, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setObjectName("tableHeaderCell")
            if i == len(headers) - 1:
                lbl.setFixedWidth(88)
            header_layout.addWidget(lbl)

        wrap = QFrame()
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(16, 0, 16, 0)
        wrap_layout.setSpacing(0)
        wrap_layout.addWidget(header_frame)
        layout.addWidget(wrap)

        # Placeholder states
        if loading or not summaries:
            msg = "Loading reports..." if loading else "No reports found."
            placeholder = QLabel(msg)
            placeholder.setObjectName("subtitle")
            placeholder.setContentsMargins(28, 16, 28, 16)
            layout.addWidget(placeholder)
            return container

        # Data Rows
        for r, summary in enumerate(summaries):
            row_frame = QFrame()
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(28, 10, 28, 10)

            for cell in (
                str(summary.report_id),
                summary.manufacturer_name.title(),
                summary.report_month.capitalize(),
                str(summary.report_year),
            ):
                lbl = QLabel(cell)
                lbl.setObjectName("tableCell")
                row_layout.addWidget(lbl)

            export_btn = QPushButton("Export")
            export_btn.setFixedWidth(80)
            export_btn.setObjectName("secondaryBtn")
            export_btn.setCursor(Qt.PointingHandCursor)

            export_btn.clicked.connect(
                lambda _checked=False, s=summary: self._start_export(s),
            )
            row_layout.addWidget(export_btn)
            layout.addWidget(row_frame)

            if r < len(summaries) - 1:
                div = QFrame()
                div.setObjectName("rowDivider")
                div.setFixedHeight(1)
                div.setContentsMargins(16, 0, 16, 0)
                layout.addWidget(div)

        return container

    # Table Replacement Helper
    def _replace_table(
        self,
        summaries: list[SalesReportSummary] | None,
        *,
        loading: bool = False,
    ) -> None:
        if self._table_container is not None:
            self._content_layout.removeWidget(self._table_container)
            self._table_container.deleteLater()

        self._table_container = self._build_table(summaries, loading=loading)
        stretch_index = self._content_layout.count()
        self._content_layout.insertWidget(stretch_index - 1, self._table_container)

    def _on_summaries_loaded(self, summaries: list[SalesReportSummary]) -> None:
        self._replace_table(summaries)

    def _on_summary_error(self, message: str) -> None:
        self._replace_table(None)

    # Export
    def _start_export(self, summary: SalesReportSummary) -> None:
        if self._export_worker and self._export_worker.isRunning():
            QMessageBox.information(
                self,
                "Export In Progress.",
                "Please wait for the current export to finish.",
            )
            return

        default_name = (
            f"{summary.manufacturer_name}_{summary.report_month}_{summary.report_year}.csv"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        self._export_worker = _ExportWorker(
            report_id=summary.report_id,
            path=path,
        )
        self._export_worker.done.connect(
            lambda count, p=path: self._on_export_done(count, p),
        )
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "Export Failed",
            f"Could not export report:\n\n{message}",
        )

    def on_show(self) -> None:
        """Retrieve current user from controller and update page.

        Functionality to be expanded to building recent report table on show.
        """
        user = self.controller.current_user or "User"
        self.welcome_label.setText(f"Welcome back, {user}!")
        self.sidebar.update_user(user)

        if self._summary_worker and self._summary_worker.isRunning():
            return

        self._replace_table(None, loading=True)

        self._summary_worker = _SummaryWorker()
        self._summary_worker.done.connect(self._on_summaries_loaded)
        self._summary_worker.error.connect(self._on_summary_error)
        self._summary_worker.start()

