from typing import Union
from src.pages.LoginPage import LoginPage
from src.pages.HomePage import HomePage
from src.pages.ReportPage import ReportPage

from DBConnection import DBConnector
import traceback

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self, connector: DBConnector):
        super().__init__()

        self.connector = connector
        self.connection_status = 0
        self.current = None
        self.screen_width = int(self.winfo_screenwidth()/2)
        self.screen_height = int(self.winfo_screenheight()/2)
        self.minsize(800, 550)
        self._resize_job = None
        self.current_user = None

        self.geometry(f"{self.screen_width}x{self.screen_height}")
        self.title("Edos Database Connector")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for PageClass in (LoginPage, HomePage, ReportPage):
            frame = PageClass(parent=self.main_container, controller=self)
            self.frames[PageClass] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        if connector.check_credentials():
            print("Credentials found, attempting connection...")
            try:
                connector.connect()
                self.connection_status = connector.conn.status
            except Exception as e:
                self.show_frame(LoginPage)
                self.frames[LoginPage].show_error(str(e))

            if self.connection_status == 1:
                self.current_user = connector.get_credentials()["user"]
                self.show_frame(HomePage, user=self.current_user)
        else:
            self.show_frame(LoginPage)

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(50, self._do_resize)

    def _do_resize(self):
        self._resize_job = None

    def show_frame(self, page_class, **kwargs):
        frame = self.frames[page_class]
        frame.tkraise()

        if hasattr(frame, "on_show"):
            frame.on_show(**kwargs)

    def login(self):
        self.show_frame(HomePage, user=self.current_user)
    
    def logout(self):
        self.connector.conn.close()
        self.current_user = None
        self.show_frame(LoginPage)