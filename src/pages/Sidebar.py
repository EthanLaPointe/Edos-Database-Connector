from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class Sidebar(QFrame):
    def __init__(self, controller, active_page: str):
        super().__init__()
        self.controller = controller
        self.setObjectName("sidebar")
        self.active_page = active_page
        self.setFixedWidth(200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 20)
        layout.setSpacing(0)
        
        # Title
        title = QLabel("Edos Connector")
        title.setObjectName("sidebarTitle")
        title.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(title)
        layout.addSpacing(28)
        
        # Navigation Label
        nav_label = QLabel("Navigation")
        nav_label.setObjectName("navLabel")
        nav_label.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(nav_label)
        layout.addSpacing(8)
        
        # Buttons
        nav_items = [
            ("Dashboard", "home", lambda: controller.show_home()),
            ("Insert Report", "report", lambda: controller.show_report()),
            ("Alias Mapping", "alias", lambda: controller.show_alias()),
        ]
        
        for label, key, action in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navBtnActive" if key == active_page else "navBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, a=action: a())
            layout.addWidget(btn)
            layout.addSpacing(4)
            
        # Spacer
        layout.addStretch()
        
        # Divider
        divider = QFrame()
        divider.setObjectName("rowDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        layout.addSpacing(12)
        
        # User Label
        self.user_label = QLabel()
        self.user_label.setObjectName("userLabel")
        self.user_label.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(self.user_label)
        layout.addSpacing(4)
        
        # Logout Button
        logout_btn = QPushButton("Sign Out")
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.clicked.connect(controller.logout)
        layout.addWidget(logout_btn)
    
    def update_user(self, username: str):
        self.user_label.setText(f"Logged in as: {username}")