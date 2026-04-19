from collections.abc import Callable
from src.LabeledEntry import LabeledEntry
from src.pages.ReportPage import ReportPage

import customtkinter as ctk

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(sidebar, text="MyApp", font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkButton(sidebar, text="Home", command=lambda: controller.show_frame(HomePage)).pack(pady=4, padx=12)
        ctk.CTkButton(sidebar, text="New Report", command=lambda: controller.show_frame(ReportPage)).pack(pady=4, padx=12)

        content = ctk.CTkFrame(self)
        content.pack(side="right", fill="both", expand=True)

