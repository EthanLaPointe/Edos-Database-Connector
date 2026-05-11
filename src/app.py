from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget
from PySide6.QtCore import Signal
from pages.LoginPage import LoginPage
from pages.HomePage import HomePage
from pages.ReportPage import ReportPage
from pages.AliasPage import AliasPage
from DBConnection import *
from DataCache import DataCache

class App(QMainWindow):
    
    cache_updated = Signal(DataCache)
    
    def __init__(self):
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
        
        for page in (self.login_page, self.home_page, self.report_page, self.alias_page):
            self.stack.addWidget(page)
        
        connection_status = 0
        if self.connector.check_credentials():
            try:
                self.connector.connect()
                connection_status = self.connector.conn.status
            except Exception as e:
                self.show_page(self.login_page)
                self.login_page._show_error(e)
            
            if connection_status == 1:
                self.login(self.connector.get_credentials()["user"])
        else:
            self.show_page(self.login_page)
        
    # Page Navigation
    def show_page(self, page: QWidget):
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_show"):
            page.on_show()
            
    def login(self, username: str):
        self.current_user = username
        self.factory = DAOFactory(self.connector)
        self.cache = DataCache(self.factory)
        self.cache_updated.emit(self.cache)
        self.show_home()
        
    def logout(self):
        self.current_user = None
        self.show_page(self.login_page)
        
    def show_home(self):
        self.show_page(self.home_page)
        
    def show_report(self):
        self.show_page(self.report_page)
        
    def show_alias(self):
        self.show_page(self.alias_page)
        
        
        