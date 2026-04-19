from collections.abc import Callable

from numpy.f2py.auxfuncs import show

from src.DBConnection import DBConnector
from src.LabeledEntry import LabeledEntry
from src.pages.HomePage import HomePage

import customtkinter as ctk

class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.login_button = None
        self.error_label = None
        self.password_entry = None
        self.username_entry = None
        self.controller = controller
        self.build_ui()

    def build_ui(self):

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Centered card
        card = ctk.CTkFrame(self, width=550, height=480, corner_radius=20)
        card.grid(row=0, column=0)
        card.grid_propagate(False)

        card.grid_rowconfigure(0, weight=1)
        card.grid_rowconfigure(9, weight=1)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=1, column=0, rowspan=8, sticky="nsew", padx=36)
        inner.grid_columnconfigure(0, weight=1)

        # Logo / app name
        ctk.CTkLabel(inner, text="⬡  Edos Database Connector", font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),).grid(row=0, column=0, pady=(0, 4), sticky="ew")
        ctk.CTkLabel(inner, text="Sign in to continue", font=ctk.CTkFont(size=13), text_color="gray60",).grid(row=1, column=0, pady=(0,24), sticky="ew")

        # Username
        ctk.CTkLabel(inner, text="Username", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w")
        self.username_entry = ctk.CTkEntry(inner, placeholder_text="Enter Username", height=40, corner_radius=8)
        self.username_entry.grid(row=3, column=0, pady=(4, 12), sticky="ew")

        # Password
        ctk.CTkLabel(inner, text="Password", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, sticky="ew")
        self.password_entry = ctk.CTkEntry(inner, placeholder_text="Enter Password", show="*", height=40, corner_radius=8)
        self.password_entry.grid(row=5, column=0, pady=(4, 6), sticky="ew")

        # Error label
        self.error_label = ctk.CTkLabel(inner, text="", text_color="red", font=ctk.CTkFont(size=12), anchor="w")
        self.error_label.grid(row=6, column=0, pady=(0, 12), sticky="ew")

        # Login button
        self.login_button = ctk.CTkButton(inner, text="Sign In", height=42, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"), command=self._handle_login,)
        self.login_button.grid(row=7, column=0, sticky="ew")

        # Bind enter key
        self.password_entry.bind("<Return>", lambda e: self._handle_login())
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())


    def _handle_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.show_error("Please fill in both fields")
            return

        connector: DBConnector
        with self.controller.connector as connector:
            connection_status = 0
            if connector.check_credentials():
                try:
                    connector.connect()
                    connection_status = connector.conn.status
                except Exception as e:
                    self.show_error(e)

            if connection_status == 1:
                self.controller.login()

    def show_error(self, message: str):
        self.error_label.configure(text=message)

    def get(self):
        try:
            return {"database": self.database_name, "user": self.username, "password": self.password, "host": self.host, "port": self.port}
        except ValueError:
            return None