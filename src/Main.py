import psycopg2
from pip._internal.resolution.resolvelib.factory import Factory

from ReportHandler import ReportHandler
from Report import Report
from DBConnection import *
import pandas as pd
import glob
import traceback
import sys

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

def print_report(rld: ReportLineDAO, _id: int):
    for line in rld.stream_by_report(report_id=4):
        print(line)

connector = DBConnector()
connectionStatus = 0
queryDict = {"manufacturerInsert": """insert into manufacturers(manufacturer_name) values (%s) returning manufacturer_id;""",
             "salesReportInsert": """insert into sales_report(manufacturer_id, report_year, report_month) values (%s, %s, %s) returning report_id;""",
             "customerInsert": """insert into customers(customer_name) values (%s) returning customer_id;""",
             "locationInsert": """insert into locations(city, state) values (%s, %s) returning location_id;""",
             "customerLocationInsert": """insert into customer_locations(customer_id, location_id) values (%s, %s);""",
             "saleCustomerInsert": """insert into sale_customer(report_id, customer_id, location_id) values (%s, %s, %s);""",
             "itemInsert": """insert into item(stockcode, product_family, product_description) values (%s, %s, %s) returning item_id;""",
             "reportLineInsert": """insert into report_line(report_id, customer_id, item_id, location_id, amt, sale_date, quantity, transfer) values (%s, %s, %s, %s, %s, %s, %s, %s);""",
             "checkCustomer": """select c.customer_name from customers c where c.customer_name = %s;""",
             "checkLocation" : """select l.city, l.state from locations l where l.city = %s and l.state = %s;""",
             "checkCustomerLocation": """select cl.customer_id, cl.location_id from customer_locations cl where cl.customer_id = %s and cl.location_id = %s;""",
             "checkSaleCustomer": """select sc.customer_id, sc.report_id, sc.location_id from sale_customer sc where sc.customer_id = %s and sc.report_id = %s and sc.location_id = %s;""",
             "checkItem": """select i.stockcode from item i where i.stockcode = %s;"""}

def get_user_credentials():
    credentials = []
    print("Please enter database name")
    credentials.append(input())
    print("Please enter username")
    credentials.append(input())
    print("Please enter password")
    credentials.append(input())
    print("Please enter host")
    credentials.append(input())
    print("Please enter port")
    credentials.append(input())

    connector.set_credentials(credentials[0], credentials[1], credentials[2], credentials[3], credentials[4])

print("Connecting to database...")

#if not connector.check_credentials():
#        get_user_credentials()
try:
    while connectionStatus == 0:
        try:
            connector.connect()
            connectionStatus = connector.conn.status
        except psycopg2.Error as e:
            print("Connection to database failed:\n(1.) Renter Credentials\n(2.) Exit Program\nEnter 1 or 2 for choice:")
            conn_failed_choice = int(input())
            if conn_failed_choice == 1:
                get_user_credentials()
            if conn_failed_choice == 2:
                sys.exit()
    print("Connection to database successful")
    dao = DAOFactory(connector)
    handler = ReportHandler(connector, dao)
    choice = 0

    while choice != 3:
        print("1. Enter single report"
              "\n2. Enter multiple reports from folder"
              "\n3. Exit program")
        choice = int(input())
        report = Report()

        if choice == 1:
            print("Enter file path of report:")
            reportPath = (input().replace('\\', '/'))
            if reportPath[0] == '"':
                reportPath = reportPath[1:-1]
            print("Standardizing: " + reportPath + "...")
            report = handler.standardize(reportPath)
            print("Checking: " + reportPath + "...")
            valid = handler.check_report(report)
            if valid[0] and len(valid[1]) == 0:
                print("Inserting: " + reportPath + "...")
                handler.insert_report(report)
            elif valid[0] and len(valid[1]) > 0:
                unknown_list = valid[1]
                aliases_to_add = []
                print("Unknown customers found")
                print("1. Resolve unknown customers.")
                print("2. Cancel insert.")
                check_choice = int(input())
                if check_choice == 1:
                    for name in unknown_list.keys():
                        print("\033[H\033[J", end="")
                        exists = False
                        while not exists:
                            print(name)
                            print("Enter customer this name should be associated with. Enter \"new\" to add as new customer.")
                            association = str(input()).lower()
                            if association != 'new':
                                customer_id = dao.customers.get_by_name(association).customer_id
                                if customer_id is not None:
                                    aliases_to_add.append(CustomerAlias(alias= name, customer_id= customer_id))
                                    exists = True
                                else:
                                    print("Please enter existing customer.")
                            else:
                                dao.customers.create(Customer(customer_id= None, customer_name= name))
                                exists = True
                    dao.customer_aliases.create_bulk(aliases_to_add)
                    handler.update_lists()
                    print("All customer aliases added.")
                    print("Inserting: " + reportPath + "...")
                    handler.insert_report(report)
            else:
                print("Report already exists for", report.manufacturerName, " during the period", report.month, ",", report.year)

        if choice == 2:
            print("Enter path to the folder:")
            folderPath = (input().replace('\\', '/'))
            if folderPath[0] == '"':
                folderPath = folderPath[1:-1]
            folderPath = folderPath + "/*.csv"
            csvList = []
            for file in glob.iglob(folderPath):
                    csvList.append(file)

            for csv_file in csvList:
                print("Inserting: " + csv_file + "...")
                report = handler.standardize(csv_file.replace('\\', '/'))
                handler.insert_report(report)

        if choice == 3:
            print("Exiting program...")
            sys.exit()

        if choice == 4:
            print("Enter file path of report:")
            reportPath = (input().replace('\\', '/'))
            if reportPath[0] == '"':
                reportPath = reportPath[1:-1]
            report = handler.standardize(reportPath)
            print("Standardized report:\n")
            print(report.dataframe)

        if choice == 5:
            aliasList = (connector.get_customer_alias_list())
            print(aliasList)

            testvalue = 'winnelson'
            if testvalue in aliasList.keys():
                print(aliasList[testvalue])
            else:
                print(testvalue + " not found")

        if choice == 7:
            rld = ReportLineDAO(connector)
            info = rld.get_all()
            print(info)

        if choice == 8:
            itemDAO = ItemDAO(connector)
            items = itemDAO.get_all()
            print(len(items))

        if choice == 9:
            cd = CustomerDAO(connector)
            customers = cd.get_all_as_dict()
            print(customers)

        if choice == 10:
            testtuple = (True, ["egg"])
            print(testtuple[1])

except Exception as e:
    traceback.print_exc()
    input()