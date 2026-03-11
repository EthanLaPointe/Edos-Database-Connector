import csv
import pandas as pd
import numpy as np
from pathlib import Path
import re

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

class ReportStandardizer:

    reportPath = ""
    df = []
    reportName = ""
    manufacturerName = ""
    month = ""
    year = ""

    fieldList = ["customername", "city", "state", "stockcode", "itemfamily", "itemdesc", "quantity", "saledate", "amount", "transfer"]

    def set_report_path(self, report_path):
        self.reportPath = Path(report_path)
        self.df = pd.read_csv(self.reportPath).astype(str)
        self.reportName = self.reportPath.name
        self.manufacturerName = self.reportName.split()[0]

        #Get report date from filename
        match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", self.reportName)
        if match is not None:
            self.month = self.reportName[match.start(): match.end()]
            self.year = self.reportName[match.end() + 1: match.end() + 5]
        else:
            print("Date not found")

    def trim_report(self):
        fields_to_keep = []
        with open(self.reportPath) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            header = next(csv_reader)

        #Check column numbers for each desired field
        for field in self.fieldList:
            for idx, col in enumerate(header):
                if field in col.lower():
                    fields_to_keep.append(idx)
                    break

        #Trim DF to only contain desired columns
        trimmed_df = self.df.iloc[:, fields_to_keep]
        return trimmed_df

    def fill_empty(self, trimmed_df):
        #Loop through desired fields
        header_locations = []
        for field in self.fieldList:
            field_found = False
            #Check if field is present in header row
            for idx, col in enumerate(trimmed_df.columns):
                #If present add fields location to location list
                if field in col.lower():
                    #print("found: ", field)
                    header_locations.append(idx)
                    field_found = True
                    break
            #If desired field is not found insert it next to the most recently found field
            if not field_found:
                #print("inserting: ", field)
                trimmed_df.insert(loc=header_locations[-1] + 1, column=field, value=np.nan)
        #Update column names to match field list
        trimmed_df.columns = self.fieldList
        #Change instances of nan to proper datatypes in each col
        trimmed_df["quantity"] = trimmed_df["quantity"].fillna(0).astype(int)
        trimmed_df["saledate"] = trimmed_df["saledate"].fillna(None)
        #Remove any $ from amount column
        trimmed_df["amount"] = trimmed_df["amount"].fillna(0.0)
        trimmed_df["amount"] = trimmed_df["amount"].str.replace('[$,()]', '', regex=True).astype(float)
        #Fill any leftover empty cells with None
        trimmed_df = trimmed_df.replace({np.nan: None})

        return trimmed_df

    def standardize(self, report_path):
        self.set_report_path(report_path)
        standardized_report = self.fill_empty(self.trim_report())
        return standardized_report

    def get_field_list(self):
        return self.fieldList
    def get_manufacturer_name(self):
        return self.manufacturerName
    def get_report_month(self):
        return self.month
    def get_report_year(self):
        return self.year