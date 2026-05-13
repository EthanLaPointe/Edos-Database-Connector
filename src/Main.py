"""_summary_."""
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app import App

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Edos Database Connector")

    # Load Style Sheet
    with Path.open(os.path.join(os.path.dirname(__file__), "style.qss"), "r") as f:  # noqa: PTH118, PTH120
        app.setStyleSheet(f.read())

    window = App()
    window.show()
    sys.exit(app.exec())
