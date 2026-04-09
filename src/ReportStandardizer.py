import csv
import pandas as pd
import numpy as np
from Report import Report

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

class ReportStandardizer:

    #List of fields the report must contain
    fieldList = ["customername", "city", "state", "stockcode", "productfam", "productdesc", "quantity", "date", "amount", "transfer"]

    def trim_report(self, dataframe, file_path):
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

    def fill_empty(self, dataframe):
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
        #Remove any $ from amount column
        dataframe["amount"] = dataframe["amount"].astype(str).str.replace(r'[$,)#]', '', regex=True).str.strip().replace('', '0.0').replace(r'[-(]', '-0', regex=True).fillna(0.0).astype(float)
        #Remove special characters from customer name
        dataframe["customername"] = dataframe["customername"].astype(str).str.replace(r"[.'(),-]", '', regex=True).str.replace("  ", " ")
        #Fill any leftover empty cells with None
        dataframe = dataframe.replace({np.nan: None})
        #Remove any rows where amount is 0 & set quantity to null if it = 0 where amount is > 0
        dataframe = dataframe[dataframe["amount"] != 0.0]
        dataframe["quantity"] = np.where((dataframe["amount"] > 0) & (dataframe["quantity"] == 0), None, dataframe["quantity"])

        return dataframe

    def replace_alias(self, dataframe, alias_list, customer_list):
        print()


    def standardize(self, report_path):
        standardized_report = Report()
        standardized_report.set_info(report_path)
        standardized_report.dataframe = self.fill_empty(self.trim_report(standardized_report.dataframe, report_path))
        return standardized_report