from app import App
from DBConnection import DBConnector
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication, QWidget, QMainWindow, QPushButton
import sys


#if __name__ == "__main__":
#    connector = DBConnector()
#    app = App(connector)
#   app.mainloop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Edos Database Connector")
    
    # Load Style Sheet
    with open("style.qss", "r") as f:
        app.setStyleSheet(f.read())
        
    window = App()
    window.show()
    sys.exit(app.exec())
