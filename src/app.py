from collections.abc import Callable
from typing import Union
from LoginPage import LoginPage
from HomePage import HomePage
from DBConnection import *
import traceback
from LabeledEntry import LabeledEntry

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class CheckboxFrame(ctk.CTkFrame):
    def __init__(self, master, values, title):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = title
        self.checkboxes = []

        self.title  = ctk.CTkLabel(self, text = self.title, fg_color = "gray30", corner_radius = 6)
        self.title.grid(row = 0, column = 0, padx = 10, pady = (10, 0), sticky = "ew")

        for i, value in enumerate(self.values):
            checkbox = ctk.CTkCheckBox(self, text = value)
            checkbox.grid(row = i + 1, column = 0, padx = 10, pady = (10, 0),  sticky = "w")
            self.checkboxes.append(checkbox)

    def get(self):
        checked_boxes = []
        for checkbox in self.checkboxes:
            if checkbox.get() == 1:
                checked_boxes.append(checkbox.cget("text"))
        return checked_boxes

class ScrollableCheckboxFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, values, title):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.checkboxes = []

        self.title = ctk.CTkLabel(self, text = title, fg_color = "gray30", corner_radius = 6)
        self.title.grid(row = 0, column = 0, padx = 10, pady = (10, 0), sticky = "ew")

        for i, value in enumerate(self.values):
            checkbox = ctk.CTkCheckBox(self, text = value)
            checkbox.grid(row = i + 1, column = 0, padx = 10, pady = (10, 0), sticky = "w")
            self.checkboxes.append(checkbox)

    def get(self):
        checked_boxes = []
        for checkbox in self.checkboxes:
            if checkbox.get() == 1:
                checked_boxes.append(checkbox.cget("text"))
        return checked_boxes

class RadioButtonFrame(ctk.CTkFrame):
    def __init__(self, master, values, title):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.values = values
        self.title = title
        self.radiobuttons = []
        self.variable = ctk.StringVar(value = "")

        self.title = ctk.CTkLabel(self, text = self.title, fg_color = "gray30", corner_radius = 6)
        self.title.grid(row = 0, column = 0, padx = 10, pady = (10, 0), sticky = "ew")

        for i, value in enumerate(self.values):
            radiobutton = ctk.CTkRadioButton(self, text = value, value = value, variable = self.variable)
            radiobutton.grid(row = i + 1, column = 0, padx = 10, pady = (10, 0), sticky = "w")
            self.radiobuttons.append(radiobutton)

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(value)

class FloatSpinbox(ctk.CTkFrame):
    def __init__(self, *args, width: int = 100, height: int = 32, step_size: Union[int, float] = 1, command: Callable = None, **kwargs):
        super().__init__(*args, width = width, height = height, **kwargs)

        self.step_size = step_size
        self.command = command

        self.configure(fg_color = ("gray78", "gray28"))
        self.grid_columnconfigure((0, 2), weight = 0)
        self.grid_columnconfigure(1, weight = 1)

        self.subtract_button = ctk.CTkButton(self, text = "-", width = height - 6, height = height-6, command = self.subtract_button_callback)
        self.subtract_button.grid(row = 0, column = 0, padx = (3, 0), pady = 3)

        self.entry = ctk.CTkEntry(self, width = width - (2 * height), height = height - 6, border_width = 0)
        self.entry.grid(row = 0, column = 1, padx = 3, pady = 3, sticky = "ew")

        self.add_button = ctk.CTkButton(self, text = "+", width = height -6, height = height - 6, command = self.add_button_callback)
        self.add_button.grid(row = 0, column = 2, padx = (0, 3), pady = 3)

        self.entry.insert(0, "0.0")

    def add_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = float(self.entry.get()) + self.step_size
            self.entry.delete(0, "end")
            self.entry.insert(0, value)
        except ValueError:
            return

    def subtract_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = float(self.entry.get()) - self.step_size
            self.entry.delete(0, "end")
            self.entry.insert(0, value)
        except ValueError:
            return

    def get(self) -> Union[float, None]:
        try:
            return float(self.entry.get())
        except ValueError:
            return None

    def set(self, value: float):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(float(value)))

class App(ctk.CTk):
    def __init__(self, connector: DBConnector):
        super().__init__()

        self.connector = connector
        self.connection_status = 0
        self.current = None
        self.screen_width = int(self.winfo_screenwidth()/2)
        self.screen_height = int(self.winfo_screenheight()/2)

        self.geometry(f"{self.screen_width}x{self.screen_height}")
        self.title("Edos Database Connector")

        self.main_container = ctk.CTkFrame(self, corner_radius = 6)
        self.main_container.pack(fill = ctk.BOTH, expand = True)

        if connector.check_credentials():
            try:
                self.connector.connect()
                self.connection_status = connector.conn.status

                if self.connection_status == 1:
                    self.current = HomePage(self, width=self.screen_width, height=self.screen_height, data_callback=self.login)
                    self.current.pack(in_=self.main_container, fill = ctk.BOTH, expand = True)
                else:
                    self.current = LoginPage(self, width=self.screen_width, data_callback=self.login, height=self.screen_height)
                    self.current.pack(in_=self.main_container, fill=ctk.BOTH, expand=True)
            except Exception as e:
                print(e)
                traceback.print_exc()
                self.current = LoginPage(self, width=self.screen_width, data_callback=self.login, height=self.screen_height)
                self.current.pack(in_=self.main_container, fill=ctk.BOTH, expand=True)
        else:
            self.current = LoginPage(self, width=self.screen_width, data_callback=self.login, height=self.screen_height)
            self.current.pack(in_=self.main_container, fill=ctk.BOTH, expand=True)

    def login(self, credentials):
        print(credentials)
        self.connector.set_credentials(credentials['database'], credentials['user'], credentials['password'], credentials['host'], credentials['port'])
        try:
            self.connector.connect()
            self.connection_status = self.connector.conn.status

            if self.connection_status == 1:
                self.current.pack_forget()
                self.current = HomePage(self, width=self.screen_width, height=self.screen_height, data_callback=self.login)
                self.current.pack(in_ = self.main_container, fill = ctk.BOTH, expand=True)
        except Exception as e:
            print(e)
            traceback.print_exc()



app = App(DBConnector())
app.mainloop()