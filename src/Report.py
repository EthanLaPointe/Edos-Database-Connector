import pandas as pd
from pathlib import Path
import re

class Report:

    def __init__(self):
        self.filePath = ""
        self.reportName = ""
        self.manufacturerName = ""
        self.month = ""
        self.year = ""
        self.dataframe = None

    def set_info(self, file_path):
        self.filePath = Path(file_path)
        self.dataframe = pd.read_csv(self.filePath, encoding='latin-1').astype(str)
        self.reportName = self.filePath.name
        self.manufacturerName = self.reportName.split()[0]

        # Get report date from filename
        match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)",
                          self.reportName)
        if match is not None:
            self.month = self.reportName[match.start(): match.end()]
            self.year = self.reportName[match.end() + 1: match.end() + 5]
        else:
            print("Date not found")

