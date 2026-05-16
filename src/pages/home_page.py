"""To be finished later."""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pages.protocols import AppController
from pages.sidebar import Sidebar


class HomePage(QWidget):
    """Class containing homepage UI and functionality.

    Functionality to be expanded later.
    """

    def __init__(self, controller: AppController) -> None:
        """Initialize home page and start UI building.

        Args:
            controller (AppController):
                Protocol containing required methods and attributes from main App.

        """
        super().__init__()
        self.controller = controller
        self.sidebar = None
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

        # Header
        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")
        content.addWidget(self.page_title)
        content.addSpacing(4)

        self.welcome_label = QLabel("Welcome back!")
        self.welcome_label.setObjectName("welcomeLabel")
        content.addWidget(self.welcome_label)
        content.addSpacing(24)

        # Recent Reports
        content.addWidget(self._build_table())
        content.addStretch()

    def _build_table(self) -> None:
        container = QFrame()
        container.setObjectName("tableContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)

        # Title
        tbl_title = QLabel("Recent Reports")
        tbl_title.setObjectName("tableTitle")
        tbl_title.setStyleSheet("font-size: 15px;")
        tbl_title.setContentsMargins(20, 16, 20, 12)
        layout.addWidget(tbl_title)

        headers = ["Report ID", "Manufacturer", "Month", "Year"]
        rows = [
            ("1", "Legend", "January", "2026"),
            ("2", "OS&B", "February", "2026"),
            ("3", "Bocchi", "February", "2026"),
            ("4", "Halo", "February", "2026"),
        ]

        # Header Row
        header_frame = QFrame()
        header_frame.setObjectName("tableHeader")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        for h in headers:
            lbl = QLabel(h)
            lbl.setObjectName("tableHeaderCell")
            header_layout.addWidget(lbl)

        wrap = QFrame()
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(16, 0, 16, 0)
        wrap_layout.setSpacing(0)
        wrap_layout.addWidget(header_frame)
        layout.addWidget(wrap)

        # Data Rows
        for r, row, in enumerate(rows):
            row_frame = QFrame()
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(28, 10, 28, 10)
            for cell in row:
                lbl = QLabel(cell)
                lbl.setObjectName("tableCell")
                row_layout.addWidget(lbl)
            layout.addWidget(row_frame)

            # Row Divider
            if r < len(rows) - 1:
                div = QFrame()
                div.setObjectName("rowDivider")
                div.setFixedHeight(1)
                div.setContentsMargins(16, 0, 16, 0)
                layout.addWidget(div)

        return container

    def on_show(self) -> None:
        """Retrieve current user from controller and update page.

        Functionality to be expanded to building recent report table on show.
        """
        user = self.controller.current_user or "User"
        self.welcome_label.setText(f"Welcome back, {user}!")
        self.sidebar.update_user(user)
