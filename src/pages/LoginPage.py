from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt

class LoginPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()
        
    def _build_ui(self):
        # Outer Layout
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(0, 0, 0, 0)
        
        # Card
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(400, 460)
        outer.addWidget(card)
        
        # Card Layout
        layout = QVBoxLayout(card)
        layout.setContentsMargins(40, 44, 40, 44)
        layout.setSpacing(0)
        
        # Title
        title = QLabel("Edos Database Connector")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Please login to continue")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        
        # Database name
        database_label = QLabel("Database Name")
        database_label.setObjectName("inputLabel1")
        layout.addWidget(database_label)
        layout.addSpacing(4)
        
        self.database_input = QLineEdit()
        self.database_input.setPlaceholderText("Enter database name")
        self.database_input.setMinimumHeight(42)
        self.username_input.returnPressed.connect(self.set_focus)
        layout.addWidget(self.database_input)
        layout.addSpacing(14)
        
        # Username
        username_label = QLabel("Username")
        username_label.setObjectName("inputLabel2")
        layout.addWidget(username_label)
        layout.addSpacing(4)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        self.username_input.setMinimumHeight(42)
        self.username_input.returnPressed.connect(self.set_focus)
        layout.addWidget(self.username_input)
        layout.addSpacing(14)
        
        # Password
        password_label = QLabel("Password")
        password_label.setObjectName("inputLabel3")
        layout.addWidget(password_label)
        layout.addSpacing(4)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setMinimumHeight(42)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.set_focus)
        layout.addWidget(self.password_input)
        layout.addSpacing(14)
        
        # Host
        host_label = QLabel("Host")
        host_label.setObjectName("inputLabel4")
        layout.addWidget(host_label)
        layout.addSpacing(4)
        
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Enter host (default: localhost)")
        self.host_input.setMinimumHeight(42)
        self.host_input.returnPressed.connect(self.set_focus)
        layout.addWidget(self.host_input)
        layout.addSpacing(14)
        
        # Port
        port_label = QLabel("Port")
        port_label.setObjectName("inputLabel5")
        layout.addWidget(port_label)
        layout.addSpacing(4)
        
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Enter port (default: 5432)")
        self.port_input.setMinimumHeight(42)
        self.port_input.returnPressed.connect(self._handle_login)
        layout.addWidget(self.port_input)
        layout.addSpacing(28)
        
        # Error Message
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        layout.addSpacing(20)
        
        # Login Button
        self.login_button = QPushButton("Sign In")
        self.login_button.setMinimumHeight(44)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self._handle_login)
        layout.addWidget(self.login_button)
        
        layout.addStretch()
        
    def set_focus(self):
        if self.database_input.text() == "":
            self.database_input.setFocus()
        elif self.username_input.text() == "":
            self.username_input.setFocus()
        elif self.password_input.text() == "":
            self.password_input.setFocus()
        elif self.host_input.text() == "":
            self.host_input.setFocus()
        elif self.port_input.text() == "":
            self.port_input.setFocus()
        else:
            pass
        
    def _handle_login(self):
        database = self.database_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        host = self.host_input.text() or "localhost"
        port = self.port_input.text() or "5432"
        
        if not all([database, username, password]):
            self.error_label.setText("Please fill in all required fields.")
            self.error_label.setVisible(True)
            return
        
        
        
        