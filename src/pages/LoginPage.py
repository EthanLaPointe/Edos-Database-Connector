from collections.abc import Callable
from numpy.f2py.auxfuncs import show
from src.DBConnection import DBConnector

import customtkinter as ctk

class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.login_button = None
        self.error_label = None
        self.password_entry = None
        self.username_entry = None
        self.controller = controller
        self._build_ui()

    def _build_ui(self):

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Centered card
        card = ctk.CTkFrame(self, width=550, height=700, corner_radius=20)
        card.grid(row=0, column=0)
        card.grid_propagate(False)

        card.grid_rowconfigure(0, weight=1)
        card.grid_rowconfigure(15, weight=1)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=1, column=0, rowspan=14, sticky="nsew", padx=36)
        inner.grid_columnconfigure(0, weight=1)

        # Logo / app name
        ctk.CTkLabel(inner, text="⬡  Edos Database Connector", font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),).grid(row=0, column=0, pady=(0, 4), sticky="ew")
        ctk.CTkLabel(inner, text="Sign in to continue", font=ctk.CTkFont(size=13), text_color="gray60",).grid(row=1, column=0, pady=(0,24), sticky="ew")

        # Database Name
        ctk.CTkLabel(inner, text="Database Name", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w")
        self.database_entry = ctk.CTkEntry(inner, placeholder_text="Enter Database Name", height=40, corner_radius=8)
        self.database_entry.grid(row=3, column=0, pady=(4, 12), sticky="ew")

        # Username
        ctk.CTkLabel(inner, text="Username", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=4, column=0, sticky="w")
        self.username_entry = ctk.CTkEntry(inner, placeholder_text="Enter Username", height=40, corner_radius=8)
        self.username_entry.grid(row=5, column=0, pady=(4, 12), sticky="ew")

        # Password
        ctk.CTkLabel(inner, text="Password", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=6, column=0, sticky="ew")
        self.password_entry = ctk.CTkEntry(inner, placeholder_text="Enter Password", show="*", height=40, corner_radius=8)
        self.password_entry.grid(row=7, column=0, pady=(4, 12), sticky="ew")
        
        # Host
        ctk.CTkLabel(inner, text="Host", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=8, column=0, sticky="w")
        self.host_entry = ctk.CTkEntry(inner, placeholder_text="Enter Host", height=40, corner_radius=8)
        self.host_entry.grid(row=9, column=0, pady=(4, 12), sticky="ew")
        
        # Port
        ctk.CTkLabel(inner, text="Port", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(row=10, column=0, sticky="w")
        self.port_entry = ctk.CTkEntry(inner, placeholder_text="Enter Port", height=40, corner_radius=8)
        self.port_entry.grid(row=11, column=0, pady=(4, 6), sticky="ew")

        # Error label
        self.error_label = ctk.CTkLabel(inner, text="", text_color="red", font=ctk.CTkFont(size=12), anchor="w", wraplength=480)
        self.error_label.grid(row=12, column=0, pady=(0, 12), sticky="ew")

        # Login button
        self.login_button = ctk.CTkButton(inner, text="Sign In", height=42, corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"), command=self._handle_login,)
        self.login_button.grid(row=13, column=0, sticky="ew")

        # Bind enter key
        self.password_entry.bind("<Return>", lambda e: self._handle_login())
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())


    def _handle_login(self):
        database_name = self.database_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()
        
        self.controller.connector.set_credentials(database_name, username, password, host, port)
        
        if not database_name or not username or not password or not host or not port:
            self.show_error("Please fill in all fields")
            return
        
        connection_status = 0
        if self.controller.connector.check_credentials():
            try:
                self.controller.connector.connect()
                connection_status = self.controller.connector.conn.status
            except Exception as e:
                self.show_error(e)

        if connection_status == 1:
            self.controller.current_user = self.controller.connector.get_credentials()["user"]
            self.controller.login()

    def show_error(self, message: str):
        self.error_label.configure(text=message)

    def get(self):
        try:
            return {"database": self.database_name, "user": self.username, "password": self.password, "host": self.host, "port": self.port}
        except ValueError:
            return None