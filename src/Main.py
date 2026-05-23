"""_summary_."""  # noqa: N999
import os
import sys
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app import App


def _apply_dark_pallete(app: QApplication) -> None:
    palette = QPalette()

    # Background Roles
    bg = QColor("#0f1117")
    surface = QColor("#1a1d27")
    mid = QColor("#13151f")

    # Foreground / Text Roles
    text = QColor("#e2e8f0")
    dim_text = QColor("#64748b")

    # Accent Roles
    highlight = QColor("#3b82f6")
    hi_text = QColor("#ffffff")

    border = QColor("#1e2130")

    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        palette.setColor(group, QPalette.Window,          bg)
        palette.setColor(group, QPalette.WindowText,      text)
        palette.setColor(group, QPalette.Base,            mid)
        palette.setColor(group, QPalette.AlternateBase,   surface)
        palette.setColor(group, QPalette.ToolTipBase,     surface)
        palette.setColor(group, QPalette.ToolTipText,     text)
        palette.setColor(group, QPalette.Text,            text)
        palette.setColor(group, QPalette.Button,          surface)
        palette.setColor(group, QPalette.ButtonText,      text)
        palette.setColor(group, QPalette.BrightText,      hi_text)
        palette.setColor(group, QPalette.Highlight,       highlight)
        palette.setColor(group, QPalette.HighlightedText, hi_text)
        palette.setColor(group, QPalette.Link,            highlight)
        palette.setColor(group, QPalette.LinkVisited,     QColor("#818cf8"))
        palette.setColor(group, QPalette.Mid,             mid)
        palette.setColor(group, QPalette.Dark,            border)
        palette.setColor(group, QPalette.Shadow,          QColor("#000000"))
        palette.setColor(group, QPalette.Light,           surface)

    palette.setColor(QPalette.Disabled, QPalette.WindowText, dim_text)
    palette.setColor(QPalette.Disabled, QPalette.Text, dim_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, dim_text)

    app.setPalette(palette)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Edos Database Connector")
    app.setStyle("Fusion")
    _apply_dark_pallete(app)

    # Load Style Sheet
    qss_path = Path(os.path.join(os.path.dirname(__file__), "style.qss"))  # noqa: PTH118, PTH120
    with qss_path.open("r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())

    window = App()
    window.show()
    sys.exit(app.exec())
