from collections.abc import Callable
from LabeledEntry import LabeledEntry

import customtkinter as ctk

class HomePage(ctk.CTkFrame):
    def __init__(self, *args, width: int, height: int, data_callback, command: Callable = None, **kwargs):
        super().__init__(*args, width = width, height = height, **kwargs)

        self.command = command
        self.data_callback = data_callback

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        self.page_label = ctk.CTkLabel(self, text="Home Page", font=("Arial", 24, "bold"))
        self.page_label.grid(row=0, column=0, pady=(30, 0), sticky="nsew", columnspan=3)