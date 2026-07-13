"""To be finished later."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from pages.alias_page import AliasPage
from pages.home_page import HomePage
from pages.login_page import LoginPage
from pages.rep_page import RepPage
from pages.report_page import ReportPage
from src.data_cache import DataCache
from src.db_connection import (
    DAOFactory,
    DBConnector,
)


class App(QMainWindow):
    """_summary_.

    Args:
        QMainWindow (_type_): _description_

    """

    cache_updated = Signal(DataCache)

    def __init__(self) -> None:
        """Initialize main app window.

        Set window title and minimum size.
        Initialize class variables to default values.
        Load page classes into stack.
        Check connection status and display home_page or login_page accordingly.
        """
        super().__init__()
        self.setWindowTitle("Edos Database Connector")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)

        # Shared State
        self.current_user: str | None = None
        self.connector = DBConnector()
        self.factory: DAOFactory = None
        self.cache: DataCache = None

        # Central Widget
        self.stack = QStackedWidget()
        self.stack.setObjectName("central")
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage(controller=self)
        self.home_page = HomePage(controller=self)
        self.report_page = ReportPage(controller=self)
        self.alias_page = AliasPage(controller=self)
        self.rep_page = RepPage(controller=self)

        for page in (
            self.login_page,
            self.home_page,
            self.report_page,
            self.alias_page,
            self.rep_page,
        ):
            self.stack.addWidget(page)

        connection_status = 0
        if self.connector.check_credentials():
            try:
                self.connector.connect()
                connection_status = self.connector.conn.status
            except Exception as e:  # noqa: BLE001
                self.show_page(self.login_page)
                self.login_page.show_error(e)

            if connection_status == 1:
                self.login(self.connector.get_credentials()["user"])
        else:
            self.show_page(self.login_page)

    # Page Navigation
    def show_page(self, page: QWidget) -> None:
        """Display specified page from within stack.

        Calls on_show() if page contains on_show() method.

        Args:
            page (QWidget):
                The page to be displayed.

        """
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_show"):
            page.on_show()

    def login(self, username: str) -> None:
        """Login to home page and initialize connection dependant variables.

        Sets current user to username. Initializes factory and cache.
        Emits cache_updated signal to send cache reference to pages.
        Displays home_page.

        Args:
            username (str): Username of the current user logging in

        """
        self.current_user = username
        self.factory = DAOFactory(self.connector)
        self.cache = DataCache(self.factory)
        self.cache_updated.emit(self.cache)
        self.show_home()

    def logout(self) -> None:
        """Set current_user to None and display login_page."""
        self.current_user = None
        self.show_page(self.login_page)

    def show_home(self) -> None:  # noqa: D102
        self.show_page(self.home_page)

    def show_report(self) -> None:  # noqa: D102
        self.show_page(self.report_page)

    def show_alias(self) -> None:  # noqa: D102
        self.show_page(self.alias_page)

    def show_rep(self) -> None:  # noqa: D102
        self.show_page(self.rep_page)
