from PySide6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from datetime import date
 
from pages.Sidebar import Sidebar
from src.ReportHandler import ReportHandler
from src.Report import Report
from src.DBConnection import *

class InsertWorker(QThread):
    # 0 - Success
    # 1 - Manufacturer Unknown
    # 2 - Unknown Aliases
    # 3 - Report Already Exists
    # 4 - Cancelled
    finished = Signal(int)
    
    def __init__(self, report: Report):
        super().__init__()
        connector = DBConnector()
        connector.connect()
        self.factory = DAOFactory(connector)
        self.report = report
        self.handler = ReportHandler(connector, self.factory)
        self.handler.update_lists()
        
    # TODO Figure out if run() should display validation windows or if insertion_status should
    # be passed to report page and handled there
    def run(self):
        # Assume insertion successful
        insertion_status = 0
        
        self.report = self.handler.standardize(self.report)
        
        valid = self.handler.check_report(self.report)
        unknown_list = valid[1]
        manufacturer_exists = valid[0][0]
        #print(manufacturer_exists)
        report_already_exists = valid[0][1]
        #print(report_already_exists)
        
        # TODO Update all prints to utilize status message on report page
        if (manufacturer_exists and report_already_exists == False) and len(unknown_list) == 0:
            #print("Inserting: " + self.report.filePath + "...")
            self.handler.insert_report(self.report)
        elif not manufacturer_exists:
            # TODO Change missing manufacturer message to be a pop-up asking to insert the missing manufacturer or cancel
            print("Manufacturer:", self.report.manufacturerName, "not present in database"
                "\n1. Add", self.report.manufacturerName, "to database."
                "\n2. Cancel insert.")
            # Change this choice to utilize the pop-up
            manuf_choice = int(input())
            if manuf_choice == 1:
                self.factory.manufacturers.create(Manufacturer(manufacturer_id= None, manufacturer_name = self.report.manufacturerName))
                self.handler.update_lists()
                self.run()
                insertion_status = 1

            elif manuf_choice == 2:
                insertion_status = 4
            
        # TODO Update unknown customers section to utilize a scrollable list of unknown customers with line edits
        # for entering the associated customer and a button for adding as a new customer
        # (future QOL) Add autofill in line edits for existing customer names / Use drop down instead(potential scalability problems)
        elif report_already_exists == False and len(unknown_list) > 0:
            aliases_to_add = []
            print("Unknown customers found")
            print("1. Resolve unknown customers.")
            print("2. Cancel insert.")
            check_choice = int(input())
            if check_choice == 1:
                # TODO Rework to use scrollable that contains all names within unknown list
                for name in unknown_list.keys():
                    print("\033[H\033[J", end="")
                    exists = False
                    while not exists:
                        print(name)
                        print("Enter customer this name should be associated with. Enter \"new\" to add as new customer.")
                        association = str(input()).lower()
                        if association != 'new':
                            customer_id = self.factory.customers.get_by_name(association).customer_id
                            if customer_id is not None:
                                aliases_to_add.append(CustomerAlias(alias=name, customer_id=customer_id))
                                exists = True
                            else:
                                print("Please enter existing customer.")
                        else:
                            self.factory.customers.create(Customer(customer_id=None, customer_name=name))
                            exists = True
                self.factory.customer_aliases.create_bulk(aliases_to_add)
                self.handler.update_lists()
                print("All customer aliases added.")
                insertion_status = 2
                self.run()
            elif check_choice == 2:
                insertion_status = 4
        elif report_already_exists:
            print("Report already exists for", self.report.manufacturerName, " during the period", self.report.month, ",", self.report.year)
            insertion_status = 3
        self.finished.emit(insertion_status)

class ReportPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        self._build_ui()
        
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # Sidebar
        self.sidebar = Sidebar(controller=self.controller, active_page="report")
        root.addWidget(self.sidebar)
        
        # Content Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root.addWidget(scroll)