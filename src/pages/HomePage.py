from collections.abc import Callable
from src.LabeledEntry import LabeledEntry
from src.pages.ReportPage import ReportPage

import customtkinter as ctk

class HomePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._build_ui()
        self.user_label = None
        self.welcome_label = None
        
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(8, weight=1)
        
        # Logo / app name
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(28, 24), sticky="w")
        ctk.CTkLabel(logo_frame, text="⬡  Edos Database", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),).pack()
        
        ctk.CTkLabel(sidebar, text="Navigation", font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50").grid(row=1, column=0, padx=24, pady=(0, 6), sticky="w")
        
        # Navigation buttons
        nav_items = [("Home", HomePage, True), ("New Report", ReportPage, False)]
        for i, (label, page, active) in enumerate(nav_items):
            btn = ctk.CTkButton(
                sidebar, 
                text=label, 
                anchor="w", 
                height=40, 
                corner_radius=8, 
                fg_color=("gray75", "gray25") if active else "transparent", 
                text_color=("gray10", "gray90"), 
                hover_color=("gray70", "gray30"),
                font=ctk.CTkFont(size=13),
                command=lambda p=page: self.controller.show_frame(p)
                )
            btn.grid(row=i+2, column=0, padx=12, pady=3, sticky="ew")
            
        # Spacer
        spacer = ctk.CTkFrame(sidebar, height=1, fg_color="gray30")
        spacer.grid(row=8, column=0, padx=20, pady=16, sticky="ew")
        
        # User info / logout
        self.user_label = ctk.CTkLabel(sidebar, text="", font=ctk.CTkFont(size=12), text_color="gray60")
        self.user_label.grid(row=9, column=0, padx=24, pady=(0, 6), sticky="w")
        
        ctk.CTkButton(
            sidebar,
            text="Logout",
            anchor="w",
            height=36,
            corner_radius=8,
            fg_color="transparent",
            text_color=("#CC3333", "#FF6B6B"),
            hover_color=("gray70", "gray30"),
            font=ctk.CTkFont(size=13),
            command=self.controller.logout,
        ).grid(row=10, column=0, padx=12, pady=(0, 20), sticky="ew")
        
    # Main content
    def _build_content(self):
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=32, pady=28)
        content.grid_columnconfigure((0, 1, 2), weight=1)
        content.grid_rowconfigure(2, weight=1)
        
        # Header
        ctk.CTkLabel(content, text="Dashboard", font=ctk.CTkFont(size=26, weight="bold"), anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        
        self.welcome_label = ctk.CTkLabel(content, text="Welcome back!", font=ctk.CTkFont(size=13), text_color="gray60", anchor="w")
        self.welcome_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 24))
        
        # Recent reports
        table_frame = ctk.CTkFrame(content, corner_radius=12)
        table_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(24, 0))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(3, weight=1)
        
        ctk.CTkLabel(table_frame, text="Recently Entered Reports", font=ctk.CTkFont(size=15, weight="bold"), anchor="w",).grid(row=0, column=0, padx=20, pady=(16,12), sticky="w")
        
        headers = ["Report ID", "Manufacturer", "Month", "Year"]
        placeholder_data = [
            "1", "Legend", "January", "2026",
            "2", "Bocchi", "February", "2026",
            "3", "Halo", "February", "2026",
        ]
        
        # Header row
        header_frame = ctk.CTkFrame(table_frame, fg_color=("gray85", "gray20"), corner_radius=6)
        header_frame.grid(row=1, column=0, padx=16, sticky="ew")
        for c, h, in enumerate(headers):
            header_frame.grid_columnconfigure(c, weight=1)
            ctk.CTkLabel(header_frame, text=h, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray60").grid(row=0, column=c, padx=12, pady=8, sticky="w")
            
        # Data rows
        for r, row in enumerate(placeholder_data):
            row_frame = ctk.CTkFrame(table_frame, fg_color="transparent")
            row_frame.grid(row=r+2, column=0, padx=16, sticky="ew")
            for c, cell in enumerate(row):
                row_frame.grid_columnconfigure(c, weight=1)
                ctk.CTkLabel(row_frame, text=cell, font=ctk.CTkFont(size=12),).grid(row=0, column=c, padx=12, pady=10, sticky="w")
                
        def on_show(self):
            user = self.controller.current_user or "User"
            self.welcome_label.configure(text=f"Welcome back, {user}!")
            self.user_label.configure(text=f"Logged in as {user}")
