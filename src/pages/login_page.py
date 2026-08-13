"""To be finished later.""" # noqa: CPY001

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pages.protocols import AppController


class LoginPage(QWidget):
    """Class for displaying and handling of user login."""

    def __init__(self, controller: AppController) -> None:
        """Set page controller and default attributes and begin UI building.

        Args:
            controller (AppController):
                Protocol containing required methods and attributes from main App.

        """
        super().__init__()
        self.controller = controller
        self.database_input = None
        self.username_input = None
        self.password_input = None
        self.host_input = None
        self.port_input = None
        self.error_label = None
        self.login_button = None
        self.input_spacing = 14

        self._build_ui()

    def _build_ui(self) -> None:  # noqa: PLR0915 TODO Look at separation into multiple functions
        # Outer Layout
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(0, 0, 0, 0)

        # Card
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(400, 600)
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
        self.database_input.returnPressed.connect(self.set_focus)
        layout.addWidget(self.database_input)
        layout.addSpacing(self.input_spacing)

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
        layout.addSpacing(self.input_spacing)

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
        layout.addSpacing(self.input_spacing)

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
        layout.addSpacing(self.input_spacing)

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

    def set_focus(self) -> None:
        """Set focused input based on earliest empty input text."""
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

    def _handle_login(self) -> None:
        database = self.database_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        host = self.host_input.text() or "localhost"
        port = self.port_input.text() or "5432"

        if not all([database, username, password]):
            self.error_label.setText("Please fill in all required fields.")
            self.error_label.setVisible(True)
            return

        self.controller.connector.set_credentials(database, username, password, host,
                                                  port)
        connection_status = 0

        if self.controller.connector.check_credentials():
            try:
                self.controller.connector.connect()
                connection_status = self.controller.connector.conn.status
            except Exception as e:  # noqa: BLE001
                self.show_error(f"Connection failed: {e!s}")
                return

        if connection_status == 1:
            self.controller.login(username)

    def show_error(self, message: str) -> None:
        """Display error label if message is not None else hide label."""
        if message:
            self.error_label.setText(message)
            self.error_label.setVisible(True)
        else:
            self.error_label.setText("")
            self.error_label.setVisible(False)
