import psycopg2

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

def insert_report(report_path: str) -> bool:
    inserted = False
    print("Standardizing: " + report_path + "...")
    report = handler.standardize(report_path)
    print("Checking: " + report_path + "...")
    valid = handler.check_report(report)
    unknown_list = valid[1]
    manufacturer_exists = valid[0][0]
    print(manufacturer_exists)
    report_already_exists = valid[0][1]
    print(report_already_exists)

    if (manufacturer_exists and report_already_exists == False) and len(unknown_list) == 0:
        print("Inserting: " + report_path + "...")
        handler.insert_report(report)
        inserted = True
    elif not manufacturer_exists:
        print("Manufacturer:", report.manufacturerName, "not present in database"
              "\n1. Add", report.manufacturerName, "to database."
              "\n2. Cancel insert.")
        manuf_choice = int(input())
        if manuf_choice == 1:
            dao.manufacturers.create(Manufacturer(manufacturer_id= None, manufacturer_name = report.manufacturerName))
            handler.update_lists()
            inserted = insert_report(report_path)

        elif manuf_choice == 2:
            return inserted

    elif report_already_exists == False and len(unknown_list) > 0:
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
                            aliases_to_add.append(CustomerAlias(alias=name, customer_id=customer_id))
                            exists = True
                        else:
                            print("Please enter existing customer.")
                    else:
                        dao.customers.create(Customer(customer_id=None, customer_name=name))
                        exists = True
            dao.customer_aliases.create_bulk(aliases_to_add)
            handler.update_lists()
            print("All customer aliases added.")
            print("Inserting: " + reportPath + "...")
            handler.insert_report(report)
            inserted = True
        elif check_choice == 2:
            return inserted
    elif report_already_exists:
        print("Report already exists for", report.manufacturerName, " during the period", report.month, ",", report.year)
    return inserted

connector = DBConnector()
connectionStatus = 0

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
              "\n3. Enter list of customer aliases"
              "\n3. Exit program")
        choice = int(input())
        report = Report()

        if choice == 1:
            print("Enter file path of report:")
            reportPath = (input().replace('\\', '/'))
            if reportPath[0] == '"':
                reportPath = reportPath[1:-1]
            report_inserted = insert_report(reportPath)
            if report_inserted:
                print("Report inserted successfully")
            else:
                print("Report failed to insert")

        if choice == 2:
            print("Enter path to the folder:")
            folderPath = (input().replace('\\', '/'))
            if folderPath[0] == '"':
                folderPath = folderPath[1:-1]
            folderPath = folderPath + "/*.csv"
            csvList = []
            for file in glob.iglob(folderPath):
                    csvList.append(file)

            if len(csvList) > 0:
                for csv_file in csvList:
                    report_inserted = insert_report(csv_file.replace('\\', '/'))
            else:
                print("Entered folder does not contain any .csv files")

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

except Exception as e:
    traceback.print_exc()
    input()