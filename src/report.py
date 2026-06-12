"""Module provides the Report class for reading and storing .csv format reports."""

import csv
import re
from pathlib import Path

import pandas as pd


class Report:
    """Class for reading and storing report data.

    Attributes
    ----------
    filePath (str):
        File path of the report.
    reportName (str):
        Full file name of report file excluding .csv.
    manufacturerName (str):
        Name of manufacturer of the report. Pulled from reportName.
    month (str):
        Month of the report. Pulled from reportName.
    year (str):
        Year of the report. Pulled from reportName.
    dataframe (DataFrame):
        Data read from the report .csv file.

    """

    def __init__(self) -> None:
        """Initialize all report class variables to default values."""
        self.filePath = ""
        self.reportName = ""
        self.manufacturerName = ""
        self.month = ""
        self.year = ""
        self.dataframe: pd.DataFrame = None

    def set_info(self, file_path: str) -> None:
        """Read report information from file path.

        Args:
            file_path (str): File path of the report to be entered

        """
        self.filePath = Path(file_path)

        # Use csv.DictReader to properly handle multiline quoted values
        with Path.open(self.filePath, encoding="latin-1") as f:
            reader = csv.DictReader(f)
            # Get fieldnames to preserve column order
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Create DataFrame with explicit column order, filtering out None columns
        valid_fields = [f for f in fieldnames if f is not None]
        self.dataframe = pd.DataFrame(
            [{k: row.get(k) for k in valid_fields} for row in rows],
        ).astype(str)

        self.reportName = self.filePath.name
        self.manufacturerName = self.reportName.split()[0].lower()

        # Get report date from filename
        match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)",  # noqa: E501
                          self.reportName)
        if match is not None:
            self.month = self.reportName[match.start(): match.end()].lower()
            self.year = self.reportName[match.end() + 1: match.end() + 5]

    def clear_info(self) -> None:
        """Reset all class variables to default empty values."""
        self.filePath = ""
        self.reportName = ""
        self.manufacturerName = ""
        self.month = ""
        self.year = ""
        self.dataframe: pd.DataFrame = None
