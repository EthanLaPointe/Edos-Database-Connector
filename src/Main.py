from app import App
from PySide6.QtWidgets import QApplication
import sys
import os

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Edos Database Connector")
    
    # Load Style Sheet
    with open(os.path.join(os.path.dirname(__file__), 'style.qss'), 'r') as f:
        app.setStyleSheet(f.read())
        
    window = App()
    window.show()
    sys.exit(app.exec())
