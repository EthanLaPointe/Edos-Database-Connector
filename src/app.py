from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget
from PySide6.QtCore import Qt
from pages.LoginPage import LoginPage
from pages.HomePage import HomePage
from pages.ReportPage import ReportPage
from DBConnection import *
from ReportHandler import ReportHandler

class App(QMainWindow):
    def __init__(self, connector: DBConnector=None):
        super().__init__()
        self.setWindowTitle("Edos Database Connector")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # Shared State
        self.current_user: str | None = None
        self.connector = connector
        self.factory = None
        self.handler = None
        
        # Central Widget
        self.stack = QStackedWidget()
        self.stack.setObjectName("central")
        self.setCentralWidget(self.stack)
        
        self.login_page = LoginPage(controller=self)
        self.home_page = HomePage(controller=self)
        self.report_page = ReportPage(controller=self)
        
        for page in (self.login_page, self.home_page, self.report_page):
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
                self.current_user = self.connector.get_credentials()["user"]
                self.factory = DAOFactory(self.connector)
                self.handler = ReportHandler(self.connector, self.factory)
                self.show_page(self.home_page)
        else:
            self.show_page(self.login_page)
        
    # Page Navigation
    def show_page(self, page: QWidget):
        self.stack.setCurrentWidget(page)
        if hasattr(page, "on_show"):
            page.on_show()
            
    def login(self, username: str):
        self.current_user = username
        self.show_page(self.home_page)
        
    def logout(self):
        self.current_user = None
        self.show_page(self.login_page)
        
    def show_home(self):
        self.show_page(self.home_page)
        
    def show_report(self):
        self.show_page(self.report_page)
        
        
        