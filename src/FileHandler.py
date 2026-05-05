import csv
import pandas as pd
import numpy as np
from Report import Report
from DBConnection import *
from DataCache import DataCache
from decimal import Decimal
from pathlib import Path
import psycopg2.extras

# List of fields a report must contain
REPORT_FIELD_LIST = ["customername", "city", "state", "stockcode", "productfam", "productdesc", "quantity", "saledate",
                     "amount", "transfer"]

# List of fields an alias mapping list must contain
MAPPING_FIELD_LIST = ["alias", "parent"]

# Status codes for individual mappings
MAPPING_CODES = {"valid": 0, "duplicate alias": 2, "unknown customer": 1}

class FileHandler:

    def __init__(self, dao_factory: DAOFactory, data_cache: DataCache):
        self.dao = dao_factory
        self.cache = data_cache

    def insert_report(self, report: Report) -> None:
        # dict to store row information
        # column index for row matches line_data, i.e. line_data["customer"] = row[0]
        line_data = {"customername": '', "city": '', "state": '', "stockcode": '', "productfamily": '', "productdesc": '',
                     "quantity": 0, "saledate": None, "amount": 0.0, "transfer": ''}

        # Use report manufacturer name to get manufacturer DAO
        manufacturer = self.dao.manufacturers.get_by_name(report.manufacturerName)
            
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
            customer_id = self.cache.customer_aliases[line_data["customername"]]

            # insert location
            if (line_data["city"], line_data["state"]) in self.cache.locations:
                location_id = self.cache.locations[(line_data["city"], line_data["state"])]
            else:
                location_id = self.dao.locations.create(Location(location_id = None, city = line_data["city"], state = line_data["state"])).location_id
                self.cache.locations[(line_data["city"], line_data["state"])] = location_id

            # save each customer location to a list of CustomerLocation
            customer_location = CustomerLocation(customer_id = customer_id, location_id = location_id)
            customer_location_list.append(customer_location)

            # save each sale customer to a list of SaleCustomer
            sale_customer = SaleCustomer(customer_id = customer_id, location_id = location_id, report_id = sales_report.report_id)
            sale_customer_list.append(sale_customer)

            # insert item
            if line_data["stockcode"] in self.cache.items:
                item_id = self.cache.items[line_data["stockcode"]]
            else:
                item_id = self.dao.items.create(Item(item_id = None, stockcode = line_data["stockcode"], product_family = line_data["productfamily"], product_description = line_data["productdesc"])).item_id
                self.cache.items[line_data["stockcode"]] = item_id

            # save each line of report to a list of ReportLine
            line = ReportLine(report_line_id = None, report_id = sales_report.report_id, customer_alias= line_data["customername"], customer_id = customer_id, item_id = item_id, location_id = location_id, quantity = line_data["quantity"],
                              transfer = line_data["transfer"], amt = Decimal(line_data["amount"]), sale_date = line_data["saledate"] )
            report_line_list.append(line)

        # insert data from lists
        self.dao.customer_locations.create_bulk(customer_location_list)
        self.dao.sale_customers.create_bulk(sale_customer_list)
        self.dao.report_lines.create_bulk(report_line_list)

    # TODO look into changing to use dataframes header row instead of reading file a second time
    def trim_report(self, dataframe, file_path) -> pd.DataFrame:
        fields_to_keep = []
        with open(file_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            header = next(csv_reader)

        #Check column numbers for each desired field
        for field in REPORT_FIELD_LIST:
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
        for field in REPORT_FIELD_LIST:
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
        dataframe.columns = REPORT_FIELD_LIST
        dataframe = dataframe.map(lambda s: s.lower() if isinstance(s, str) else s)
        #Change instances of nan to proper datatypes in each col
        dataframe["quantity"] = dataframe["quantity"].fillna(0).astype(str).str.replace(r'[$,)#]', '', regex=True).str.strip().astype(float).astype(int)
        dataframe["saledate"] = dataframe["saledate"].fillna(None)
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
    
    def standardize_report(self, report: Report) -> Report:
        report.dataframe = self.fill_empty(self.trim_report(report.dataframe, report.filePath))
        return report

    #------------------------------------------------------------------
    # check_report - check validity of report being entered
    #------------------------------------------------------------------

    def check_report(self, report: Report) -> tuple[tuple[bool, bool], dict[str, int]]:
        unknown_list = {}
        valid_manufacturer = False
        already_present = False
        manufacturer_id = self.cache.manufacturers[report.manufacturerName] | None

        # check if manufacturer on report exists in database
        # if exists then check if a report already exists for that manufacturer during the report period
        if manufacturer_id is not None:
            valid_manufacturer = True
            already_present = self.dao.sales_reports.check_exists(manufacturer_id, report.year,report.month)

        # Add each unique unknown name to the unknown_list
        for name in report.dataframe["customername"]:
            if name not in self.cache.customer_aliases:
                unknown_list[name] = 0

        return (valid_manufacturer, already_present), unknown_list
    
    def read_mappings(self, file_path: str) -> pd.DataFrame:
        file_path = Path(file_path)
        mappings = pd.read_csv(file_path, encoding='latin-1').astype(str)
        return mappings
    
    def check_mappings(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        
        valid_columns = False
        column_list = list(map(lambda x: x.lower(), dataframe.columns.tolist()))
        print(column_list)
        
        fields_to_keep = []

        #Check column numbers for each desired field
        for field in MAPPING_FIELD_LIST:
            for idx, col in enumerate(column_list):
                if field in col.lower():
                    fields_to_keep.append(idx)
                    break

        #Trim DF to only contain desired columns
        dataframe = dataframe.iloc[:, fields_to_keep]
        dataframe.columns = MAPPING_FIELD_LIST
        column_list = list(map(lambda x: x.lower(), dataframe.columns.tolist()))

        if MAPPING_FIELD_LIST[0] in column_list and MAPPING_FIELD_LIST[1] in column_list:
            valid_columns = True
            self.cache.refresh()
            # TODO change np.where to row by row check for status
            dataframe.insert(loc=len(dataframe.columns), column="status", value=np.nan)
            dataframe["status"] = np.where(dataframe["parent"] in self.cache.customer_aliases, MAPPING_CODES["valid"], MAPPING_CODES["unknown customer"])
            dataframe["status"] = np.where(dataframe["alias"] in self.cache.customer_aliases, MAPPING_CODES["duplicate alias"], MAPPING_CODES["valid"])
        
        return (dataframe, valid_columns)
    
    def insert_alias_mappings(self, dataframe: pd.DataFrame) -> bool:
        mappings_to_insert = []
        for row in dataframe.itertuples(index=False):
            customer_id = self.cache.customer_aliases[row[1]]
            alias = row[0]
            mapping = CustomerAlias(alias=alias, customer_id=customer_id)
            mappings_to_insert.append(mapping)
        
        success = self.dao.customer_aliases.create_bulk(mappings_to_insert)
        
        return success
        
        
        

