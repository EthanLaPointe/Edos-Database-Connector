from collections.abc import Callable
from typing import Union

import customtkinter as ctk

class LabeledEntry(ctk.CTkFrame):
    def __init__(self, *args, width: int = 100, height: int = 32, entry_padx: int = 0, label_name: str = "", color: str = "black", **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)
        self.label_name = label_name
        self.entry_padx = entry_padx

        self.configure(fg_color = color)
        self.grid_columnconfigure(0, weight = 0)
        self.grid_columnconfigure(1, weight = 1)

        self.label = ctk.CTkLabel(self, text=self.label_name, font=("Arial", 16, "bold"))
        self.label.grid(row=0, column=0, padx=10)

        self.entry = ctk.CTkEntry(self, width=width - (2 * height), height=height - 6, border_width=0)
        self.entry.grid(row=0, column=1, columnspan=1, padx=(entry_padx, 1), pady=1, sticky="ew")

    def get(self) -> Union[str, None]:
        try:
            return self.entry.get()
        except ValueError:
            return None

    def set(self, value: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)