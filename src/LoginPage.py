from collections.abc import Callable

from numpy.f2py.auxfuncs import show

from LabeledEntry import LabeledEntry

import customtkinter as ctk

class LoginPage(ctk.CTkFrame):
    def __init__(self, *args, width: int, height: int, data_callback, command: Callable = None, **kwargs):
        super().__init__(*args, width = width, height = height, **kwargs)

        self.command = command
        self.database_name = ""
        self.username = ""
        self.password = ""
        self.host = ""
        self.port = ""
        self.data_callback = data_callback

        self.configure(fg_color = ("gray78", "gray18"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        #self.grid_rowconfigure(0, weight=1)
        #self.grid_rowconfigure(1, weight=1)

        self.page_label = ctk.CTkLabel(self, text = "Edos Database Connector", font = ("Arial", 24, "bold"))
        self.page_label.grid(row = 0, column = 0, pady = (30, 0), sticky = "nsew", columnspan = 3)

        # Data entry frames
        self.db_entry = LabeledEntry(self, label_name = "Database Name:", color = self._fg_color)
        self.db_entry.grid(row = 1, column = 1, pady = (120, 15), sticky = "nsew")
        self.username_entry = LabeledEntry(self, label_name = "Username:", entry_padx = 40, color = self._fg_color)
        self.username_entry.grid(row = 2, column = 1, pady = (0, 15), sticky = "nsew")
        self.password_entry = LabeledEntry(self, label_name = "Password:", entry_padx = 40, color = self._fg_color)
        self.password_entry.entry.configure(show ="*")
        self.password_entry.grid(row = 3, column = 1, pady = (0, 15), sticky = "nsew")
        self.host_entry = LabeledEntry(self, label_name = "Host:", entry_padx = 80, color = self._fg_color)
        self.host_entry.grid(row = 4, column = 1, pady = (0, 15), sticky = "nsew")
        self.port_entry = LabeledEntry(self, label_name = "Port:", entry_padx = 83, color = self._fg_color)
        self.port_entry.grid(row = 5, column = 1, pady = (0, 15), sticky = "nsew")

        self.login_button = ctk.CTkButton(self, text = "Login", width = 50, height = 30, command = self.login_button_callback)
        self.login_button.grid(row = 6, column = 1, pady = (10, 0), sticky = "nsew")

    def login_button_callback(self) -> dict[str, str] | None:
        if self.command is not None:
            self.command()
        try:
            self.database_name = str(self.db_entry.get())
            self.username = str(self.username_entry.get())
            self.password = str(self.password_entry.get())
            self.host = str(self.host_entry.get())
            self.port = str(self.port_entry.get())

            self.data_callback(self.get())
        except ValueError:
            return

    def get(self):
        try:
            return {"database": self.database_name, "user": self.username, "password": self.password, "host": self.host, "port": self.port}
        except ValueError:
            return None