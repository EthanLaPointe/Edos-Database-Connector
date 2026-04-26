import csv
import pandas as pd
import numpy as np
from Report import Report
from DBConnection import *
from decimal import Decimal
import psycopg2.extras

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

class ReportHandler:

    def __init__(self, db_connector: DBConnector, dao_factory: DAOFactory):
        self.db = db_connector
        self.dao = dao_factory
        self.location_list = self.dao.locations.get_all_as_dict()
        self.customer_alias_list = self.dao.customer_aliases.get_all_as_dict() | self.dao.customers.get_all_as_dict()
        self.item_list = self.dao.items.get_all_as_dict()
        self.manufacturer_list = self.dao.manufacturers.get_all_as_dict()
        # List of fields the report must contain
        self.fieldList = ["customername", "city", "state", "stockcode", "productfam", "productdesc", "quantity", "date",
                     "amount", "transfer"]

    def update_lists(self):
        self.location_list = self.dao.locations.get_all_as_dict()
        self.customer_alias_list = self.dao.customer_aliases.get_all_as_dict() | self.dao.customers.get_all_as_dict()
        self.item_list = self.dao.items.get_all_as_dict()
        self.manufacturer_list = self.dao.manufacturers.get_all_as_dict()

    def insert_report(self, report) -> None:
        # dict to store row information
        # column index for row matches line_data, i.e. line_data["customer"] = row[0]
        line_data = {"customername": '', "city": '', "state": '', "stockcode": '', "productfamily": '', "productdesc": '',
                     "quantity": 0, "saledate": None, "amount": 0.0, "transfer": ''}

        # insert manufacturer name and check if present already
        manufacturer = self.dao.manufacturers.get_by_name(report.manufacturerName)
        if not manufacturer:
            manufacturer = self.dao.manufacturers.create(Manufacturer(manufacturer_id = None, manufacturer_name = report.manufacturerName))

        try:
            sales_report = SalesReport(report_id= None, manufacturer_id= manufacturer.manufacturer_id, report_year= report.year, report_month= report.month)
            sales_report = self.dao.sales_reports.create(sales_report)

        except psycopg2.Error as insert_exception:
            print("Failed to insert sales report. Error: ", insert_exception)
            return

        sale_customer_list = []
        customer_location_list = []
        report_line_list = []

        for row in report.dataframe.itertuples(index=False):
            # fill line_data dict with information from current row
            line_data["customername"] = row[0]
            line_data["city"] = row[1]
            line_data["state"] = row[2]
            line_data["stockcode"] = row[3]
            line_data["productfamily"] = row[4]
            line_data["productdesc"] = row[5]
            line_data["quantity"] = row[6]
            line_data["saledate"] = row[7]
            line_data["amount"] = row[8]
            if line_data["amount"] >= 0 and line_data["quantity"] == 0:
                line_data["quantity"] = None
            line_data["transfer"] = row[9]

            # retrieve customer_id from list
            customer_id = self.customer_alias_list[line_data["customername"]]

            # insert location
            if (line_data["city"], line_data["state"]) in self.location_list:
                location_id = self.location_list[(line_data["city"], line_data["state"])]
            else:
                location_id = self.dao.locations.create(Location(location_id = None, city = line_data["city"], state = line_data["state"])).location_id
                self.location_list[(line_data["city"], line_data["state"])] = location_id

            # save each customer location to a list of CustomerLocation
            customer_location = CustomerLocation(customer_id = customer_id, location_id = location_id)
            customer_location_list.append(customer_location)

            # save each sale customer to a list of SaleCustomer
            sale_customer = SaleCustomer(customer_id = customer_id, location_id = location_id, report_id = sales_report.report_id)
            sale_customer_list.append(sale_customer)

            # insert item
            if line_data["stockcode"] in self.item_list:
                item_id = self.item_list[line_data["stockcode"]]
            else:
                item_id = self.dao.items.create(Item(item_id = None, stockcode = line_data["stockcode"], product_family = line_data["productfamily"], product_description = line_data["productdesc"])).item_id
                self.item_list[line_data["stockcode"]] = item_id

            # save each line of report to a list of ReportLine
            line = ReportLine(report_line_id = None, report_id = sales_report.report_id, customer_alias= line_data["customername"], customer_id = customer_id, item_id = item_id, location_id = location_id, quantity = line_data["quantity"],
                              transfer = line_data["transfer"], amt = Decimal(line_data["amount"]), sale_date = line_data["saledate"] )
            report_line_list.append(line)

        # insert data from lists
        self.dao.customer_locations.create_bulk(customer_location_list)
        self.dao.sale_customers.create_bulk(sale_customer_list)
        self.dao.report_lines.create_bulk(report_line_list)

    def trim_report(self, dataframe, file_path) -> pd.DataFrame:
        fields_to_keep = []
        with open(file_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            header = next(csv_reader)

        #Check column numbers for each desired field
        for field in self.fieldList:
            for idx, col in enumerate(header):
                if field in col.lower():
                    fields_to_keep.append(idx)
                    break

        #Trim DF to only contain desired columns
        dataframe = dataframe.iloc[:, fields_to_keep]
        return dataframe

    def fill_empty(self, dataframe) -> pd.DataFrame:
        #Loop through desired fields
        header_locations = []
        for field in self.fieldList:
            field_found = False
            #Check if field is present in header row
            for idx, col in enumerate(dataframe.columns):
                #If present add fields location to location list
                if field in col.lower():
                    #print("found: ", field)
                    header_locations.append(idx)
                    field_found = True
                    break
            #If desired field is not found insert it next to the most recently found field
            if not field_found:
                #print("inserting: ", field)
                dataframe.insert(loc=header_locations[-1] + 1, column=field, value=np.nan)
        #Update column names to match field list
        dataframe.columns = self.fieldList
        dataframe = dataframe.map(lambda s: s.lower() if isinstance(s, str) else s)
        #Change instances of nan to proper datatypes in each col
        dataframe["quantity"] = dataframe["quantity"].fillna(0).astype(float).astype(int)
        #trimmed_df["quantity"] = np.where((trimmed_df["quantity"] == np.nan) & trimmed_df["amount"] <= 0, 0, trimmed_df["quantity"])
        dataframe["date"] = dataframe["date"].fillna(None)
        #Strip whitespace from city, state
        dataframe["city"] = dataframe["city"].astype(str).str.strip()
        dataframe["state"] = dataframe["state"].astype(str).str.strip()
        #Remove any $ from amount column
        dataframe["amount"] = dataframe["amount"].astype(str).str.replace(r'[$,)#]', '', regex=True).str.strip().replace('', '0.0').replace(r'[-(]', '-0', regex=True).fillna(0.0).astype(float)
        #Remove special characters from customer name
        dataframe["customername"] = dataframe["customername"].astype(str).str.replace(r"[.'(),-]", '', regex=True).str.replace(r' +', ' ', regex=True).str.strip()
        #Fill any leftover empty cells with None
        dataframe = dataframe.replace({np.nan: None})
        #Remove any rows where amount is 0 & set quantity to null if it = 0 where amount is > 0
        dataframe = dataframe[dataframe["amount"] != 0.0]
        dataframe["quantity"] = np.where((dataframe["amount"] > 0) & (dataframe["quantity"] == 0), None, dataframe["quantity"])

        return dataframe
    
    def standardize(self, report: Report) -> Report:
        report.dataframe = self.fill_empty(self.trim_report(report.dataframe, report.filePath))
        return report

    #------------------------------------------------------------------
    # check_report - check validity of report being entered
    #------------------------------------------------------------------

    def check_report(self, report: Report) -> tuple[tuple[bool, bool], dict[str, int]]:
        unknown_list = {}
        valid_manufacturer = False
        already_present = False
        manufacturer = None

        # check if manufacturer on report exists in database
        # if exists then check if a report already exists for that manufacturer during the report period
        if report.manufacturerName in self.manufacturer_list:
            valid_manufacturer = True
            manufacturer = self.dao.manufacturers.get_by_name(report.manufacturerName)
            already_present = self.dao.sales_reports.check_exists(manufacturer.manufacturer_id, report.year,report.month)

        # Add each unique unknown name to the unknown_list
        for name in report.dataframe["customername"]:
            if name not in self.customer_alias_list:
                unknown_list[name] = 0

        return (valid_manufacturer, already_present), unknown_list

