"""Module containing FileHandler class implementation.

Used for the cleaning, validation, and insertion, of report files into the database.
Also used for the reading, cleaning, validation, and insertion, of alias mapping files.
""" # noqa: CPY001

import re
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from report import Report
from src.data_cache import DataCache
from src.db_connection import (
    Classification,
    Customer,
    CustomerAlias,
    CustomerLocation,
    DAOFactory,
    Item,
    Location,
    ReportLine,
    Representative,
    RepresentativeTeam,
    RepTeamCustomerLocation,
    SalesReport,
    TeamMember,
)

# List of fields a report must contain
REPORT_FIELD_LIST = [
    "customername",
    "city",
    "state",
    "stockcode",
    "productfam",
    "productdesc",
    "quantity",
    "saledate",
    "amount",
    "transfer",
]

# List of state codes to ignore
STATE_LIST = [
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "MD",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NJ",
    "NM",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
]

# List of fields an alias mapping list must contain
MAPPING_FIELD_LIST = [
    "alias",
    "parent",
]

_MAPPING_FIELD_ALIAS = [
    "customer_name",
    "parent",
]

REP_MAPPING_FIELD_LIST = [
    "name",
    "superparent",
    "city",
    "state",
    "new team",
    "heating",
    "plumbing",
]

# Status codes for individual mappings
MAPPING_CODES = {"valid": 0, "duplicate alias": 1, "unknown customer": 2}

CITY_TRANSLATIONS = {
    "n": "north",
    "s": "south",
    "so": "south",
    "e": "east",
    "w": "west",
    "st": "saint",
    "ft": "fort",
}

class FileHandler:
    """To be finished later."""

    def __init__(self, dao_factory: DAOFactory, data_cache: DataCache) -> None:
        """Initialize a FileHandler instance.

        Args:
            dao_factory (DAOFactory):
                The DAOFactory the handler should use.
            data_cache (DataCache):
                The DataCache of the main app.

        """
        self.dao = dao_factory
        self.cache = data_cache

    def insert_report(self, report: Report) -> None:
        """Insert a sales report into the database.

        Args:
            report (Report):
                The Report object containing the sales report information.

        """
        self.cache.refresh_all()
        line_data = {
            "customername": "",
            "city": "",
            "state": "",
            "stockcode": "",
            "productfamily": "",
            "productdesc": "",
            "quantity": 0,
            "saledate": None,
            "amount": 0.0,
            "transfer": "",
        }

        # Use report manufacturer name to get manufacturer from dao
        manufacturer = self.dao.manufacturers.get_by_name(report.manufacturerName)

        try:
            sales_report = SalesReport(
                report_id=None,
                manufacturer_id=manufacturer.manufacturer_id,
                report_year=report.year,
                report_month=report.month,
            )
            sales_report = self.dao.sales_reports.create(sales_report)

        except Exception: # noqa: BLE001
            return

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
                location_id = self.cache.locations[(
                    line_data["city"],
                    line_data["state"],
                )]
            else:
                location_id = self.dao.locations.create(
                    Location(
                        location_id=None,
                        city=line_data["city"],
                        state=line_data["state"],
                    ),
                ).location_id
                self.cache.locations[(line_data["city"], line_data["state"])] \
                = location_id

            customer_location = CustomerLocation(
                customer_id=customer_id,
                location_id=location_id,
            )

            if customer_location not in self.cache.customer_locations:
                self.dao.customer_locations.create(customer_location)
                customer_location_list.append(customer_location)

            rep_team_id = self.cache.rtcl.get(customer_location)

            # insert item
            if line_data["stockcode"] in self.cache.items:
                item_id = self.cache.items[line_data["stockcode"]]
            else:
                item_id = self.dao.items.create(
                    Item(
                        item_id=None,
                        stockcode=line_data["stockcode"],
                        product_family=line_data["productfamily"],
                        product_description=line_data["productdesc"],
                    ),
                ).item_id
                self.cache.items[line_data["stockcode"]] = item_id

            # save each line of report to a list of ReportLine
            line = ReportLine(
                report_line_id=None,
                report_id=sales_report.report_id,
                customer_alias=line_data["customername"],
                customer_id=customer_id,
                item_id=item_id,
                location_id=location_id,
                quantity=line_data["quantity"],
                transfer = line_data["transfer"],
                amt = Decimal(line_data["amount"]),
                sale_date = line_data["saledate"],
                rep_team = rep_team_id,
            )
            report_line_list.append(line)

        # insert data from lists
        self.dao.report_lines.create_bulk(report_line_list)

    def trim_report(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Trim a report to contain only desired fields.

        Args:
            dataframe (Pandas.DataFrame):
                The dataframe of the report to trim.

        """
        header = [col.lower() for col in dataframe.columns]
        fields_to_keep = []

        # Check column numbers for each desired field
        for field in REPORT_FIELD_LIST:
            for idx, col in enumerate(header):
                if field in col:
                    fields_to_keep.append(idx)
                    break

        # Trim DF to only contain desired columns
        return dataframe.iloc[:, fields_to_keep]

    def _expand_city_abbreviations(self, series: pd.Series) -> pd.Series:
        if not CITY_TRANSLATIONS:
            return series

        # Build regex pattern
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(k) for k in CITY_TRANSLATIONS) + r")\b",
        )

        # Process unique cities only, link abbreviated city to its translation
        unique_cities = series.unique()
        lookup: dict[str, str] = {
            val: pattern.sub(lambda m: CITY_TRANSLATIONS[m.group(0)], val)
            for val in unique_cities
            if isinstance(val, str)
        }

        return series.map(lookup)

    def fill_empty(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Fill empty rows and add any missing dataframe columns."""
        normalized_columns = []
        pattern = re.compile("|".join(re.escape(x) for x in STATE_LIST))

        for field in REPORT_FIELD_LIST:
            match = next(
                (
                    col
                    for col in dataframe.columns
                    if field in str(col).lower()
                ),
                None,
            )
            if match is None:
                dataframe[field] = np.nan
                normalized_columns.append(field)
            else:
                normalized_columns.append(match)

        dataframe = dataframe[normalized_columns]
        dataframe.columns = REPORT_FIELD_LIST

        # Lowercase only string columns (avoid applymap to be robust)
        dataframe = dataframe.apply(
            lambda col: col.str.lower()
            if pd.api.types.is_string_dtype(col) else col,
        )
        # Change instances of nan to proper datatypes in each col
        # For quantity: remove special chars, convert to numeric, fill NaN with 0
        dataframe["quantity"] = (
            dataframe["quantity"]
            .astype(str)
            .str.replace(r"[$,)#\*]", "", regex=True)
            .str.strip()
        )
        dataframe["quantity"] = (
            pd.to_numeric(dataframe["quantity"], errors="coerce").fillna(0).astype(int)
        )
        dataframe["saledate"] = dataframe["saledate"].fillna(None)
        dataframe["saledate"] = dataframe["saledate"].replace({"": None})
        # Remove special characters and strip whitespace from cities
        dataframe["city"] = dataframe["city"].replace({np.nan: ""})
        dataframe["city"] = (
            dataframe["city"]
            .astype(str)
            .str.replace(r"[.]", "", regex=True)
            .str.strip()
            .str.split(",", n=1).str[0]
            .str.strip()
        )
        dataframe["city"] = dataframe["city"].replace({"": None})
        # Expand all abbreviations in city column
        dataframe["city"] = self._expand_city_abbreviations(dataframe["city"])
        # Strip whitespace from state
        dataframe["state"] = dataframe["state"].replace({np.nan: ""})
        dataframe = dataframe[~dataframe["state"].str.contains(pattern, regex=True)]
        dataframe["state"] = dataframe["state"].astype(str).str.strip()
        dataframe["state"] = dataframe["state"].replace({"": None})
        # Remove any $ from amount column
        dataframe["amount"] = (
            dataframe["amount"]
            .astype(str)
            .str.replace(r"[$,)#]", "", regex=True)
            .str.strip()
            # Replace empty-string values
            .replace("", "0.0", regex=False)
            .str.replace(r"[-(]", "-0", regex=True)
            .fillna(0.0)
            .astype(float)
        )
        # Remove any text inside parenthesis and special characters
        dataframe["customername"] = (
            dataframe["customername"]
            .astype(str)
            .str.replace(r"\(.*?\)", "", regex=True)
            .str.replace(r"[.(),-_#]", " ", regex=True)
            .str.replace(r" +", " ", regex=True)
            .str.strip()
        )
        dataframe = dataframe[~dataframe["customername"]
                              .str.contains(r"\bedos\b", regex=True, na=False)
                    ]
        #Fill any leftover empty cells with None
        dataframe = dataframe.replace({np.nan: None})
        #Remove any row where amount is 0
        #And set quantity to null if it = 0 where amount is > 0
        dataframe = dataframe[dataframe["amount"] != 0.0]
        dataframe["quantity"] = np.where(
            (dataframe["amount"] > 0) & (dataframe["quantity"] == 0),
            None,
            dataframe["quantity"],
        )
        return dataframe

    def standardize_report(self, report: Report) -> Report:
        """Trim and clean a Report object.

        Args:
            report (Report):
                The report object containing the sales report information.

        Returns:
            Report:
                A Report object with the standardized dataframe.

        """
        report.dataframe = self.fill_empty(
            self.trim_report(report.dataframe),
        )
        return report

    #------------------------------------------------------------------
    # check_report - check validity of report being entered
    #------------------------------------------------------------------

    def check_report(self, report: Report) -> tuple[tuple[bool, bool], dict[str, int]]:
        """Check if a report is valid to be inserted.

        Args:
            report (Report):
                The report to check validity of.

        Returns:
            tuple[tuple[bool, bool], dict[str, int]]:
                A tuple containing a pair of bools(valid_manufacturer, already_present)
                and a dictionary containing all unknown customer aliases in the report.

        """
        unknown_list = {}
        valid_manufacturer = False
        already_present = False
        manufacturer_id = self.cache.manufacturers.get(report.manufacturerName, None)

        # check if manufacturer on report exists in database
        # if exists then check if a report already exists
        # for that manufacturer during the report period
        if manufacturer_id is not None:
            valid_manufacturer = True
            already_present = self.dao.sales_reports.check_exists(
                SalesReport(
                    report_id=None,
                    manufacturer_id=manufacturer_id,
                    report_year=report.year,
                    report_month=report.month,
                ),
            )

        # Add each unique unknown name to the unknown_list
        for name in report.dataframe["customername"]:
            if name not in self.cache.customer_aliases:
                unknown_list[name] = 0

        return (valid_manufacturer, already_present), unknown_list

    def read_mappings(self, file_path: str) -> pd.DataFrame:
        """Read a .csv file of mappings (Aliases or representatives).

        Args:
            file_path (str):
                The file path of the mapping file.

        Returns:
            Pandas.DataFrame:

        """
        file_path = Path(file_path)
        return pd.read_csv(file_path, encoding="latin-1").astype(str)

    def check_alias_mappings(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[pd.DataFrame, bool]:
        """Check the validity of a customer alias mapping.

        Args:
            dataframe (Pandas.DataFrame):
                The dataframe read from the mapping file.

        Returns:
            tuple[Pandas.DataFrame, bool]:
                A tuple containing the trimmed dataframe and True or False
                depending on the validity of the mappings.

        """
        valid_columns = False
        column_list = [x.lower() for x in dataframe.columns.tolist()]

        fields_to_keep = []

        #Check column numbers for each desired field
        _found_alias = False

        for idx, col in enumerate(column_list):
            if not _found_alias and col.__contains__(MAPPING_FIELD_LIST[0]):
                fields_to_keep.append(idx)
                _found_alias = True
            elif (
                _found_alias
                and (
                    col.__contains__(_MAPPING_FIELD_ALIAS[0])
                    or col.__contains__(_MAPPING_FIELD_ALIAS[1])
                )
            ):
                fields_to_keep.append(idx)
                valid_columns = True
                break

        #Trim DF to only contain desired columns
        dataframe = dataframe.iloc[:, fields_to_keep]
        dataframe = dataframe.dropna()
        column_list = [x.lower() for x in dataframe.columns.tolist()]
        dataframe.columns = MAPPING_FIELD_LIST

        # Refresh cache before status check to ensure customer list is current
        self.cache.refresh_customers()

        dataframe.insert(loc=len(dataframe.columns), column="status", value=np.nan)

        # Filter names in alias and parent columns to match report filtering
        dataframe = dataframe.apply(
            lambda col: col.str.lower()
            if pd.api.types.is_string_dtype(col) else col,
        )
        dataframe["parent"] = dataframe["parent"].astype(str).str.replace(
            r"[.'(),-]",
            "",
            regex=True,
        ).str.replace(
            r" +",
            " ",
            regex=True,
        ).str.strip()
        dataframe["alias"] = dataframe["alias"].astype(str).str.replace(
            r"[.'(),-]",
            "",
            regex=True,
        ).str.replace(
            r" +",
            " ",
            regex=True,
        ).str.strip()

        # Set row status
        dataframe["status"] = np.where(
            dataframe["alias"].isin(self.cache.customer_aliases),
            MAPPING_CODES["duplicate alias"],
            MAPPING_CODES["valid"],
        )
        # Skip any rows that already have a non-valid status
        dataframe["status"] = np.where(
            dataframe["status"] == MAPPING_CODES["duplicate alias"],
            dataframe["status"],
            np.where(
                dataframe["parent"].isin(self.cache.customer_aliases),
                MAPPING_CODES["valid"],
                MAPPING_CODES["unknown customer"],
            ),
        )

        return (dataframe, valid_columns)

    def insert_alias_mappings(self, dataframe: pd.DataFrame) -> bool:
        """Insert customer alias mappings into database.

        Args:
            dataframe (Pandas.DataFrame):
                The dataframe of customer alias mappings.

        Returns:
            bool:
                True or False depending on insertion success.

        """
        mappings_to_insert = []
        for row in dataframe.itertuples(index=False):
            customer_id = self.cache.customer_aliases[row[1]]
            alias = row[0]
            mapping = CustomerAlias(alias=alias, customer_id=customer_id)
            mappings_to_insert.append(mapping)

        return self.dao.customer_aliases.create_bulk(mappings_to_insert)

    def check_rep_mappings(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        """Check the validity of a representative mapping file and clean it.

        Args:
            dataframe (Pandas.DataFrame):
                The dataframe of the representative mappings.

        Returns:
            tuple[Pandas.DataFrame, bool]:
                The cleaned dataframe and a bool for whether it is a valid
                representative mapping or not.

        """
        valid_columns = False
        column_list = [x.lower() for x in dataframe.columns.tolist()]

        fields_to_keep = []


        # Locate desired columns
        for field in REP_MAPPING_FIELD_LIST:
            for idx, col in enumerate(column_list):
                if col == field:
                    fields_to_keep.append(idx)
                    break

        # Trim DF to only contain desired columns
        dataframe = dataframe.iloc[:, fields_to_keep]
        dataframe = dataframe.dropna()
        column_list = [x.lower() for x in dataframe.columns.tolist()]

        if column_list == REP_MAPPING_FIELD_LIST:
            valid_columns = True
        else:
            valid_columns = False
            return (dataframe, valid_columns)

        # Filter names in name and superparent columns to match report filtering
        dataframe = dataframe.apply(
            lambda col: col.str.lower()
            if pd.api.types.is_string_dtype(col) else col,
        )
        dataframe.columns = REP_MAPPING_FIELD_LIST
        dataframe["superparent"] = dataframe["superparent"].astype(str).str.replace(
            r"[.'(),-]",
            "",
            regex=True,
        ).str.replace(
            r" +",
            " ",
            regex=True,
        ).str.strip()
        dataframe["name"] = dataframe["name"].astype(str).str.replace(
            r"[.'(),-]",
            "",
            regex=True,
        ).str.replace(
            r" +",
            " ",
            regex=True,
        ).str.strip()

        return (dataframe, valid_columns)

    def insert_rep_mappings(self, dataframe: pd.DataFrame) -> bool:
        """Insert representative teams into the database.

        Args:
            dataframe (Pandas.DataFrame):
                The validated dataframe containing representative relationships.

        Returns:
            bool:
                True if insert was successful or False if it failed.

        """
        # Insert all teams
        # Add team members to each team
        # Link customer locations and teams

        # Get all customers and insert them.
        customer_list = [
            Customer(customer_id=None, customer_name=name)
            for name in dataframe["superparent"]
        ]
        self.dao.customers.create_bulk(customer_list)
        self.cache.refresh_customer_aliases()

        # Get all aliases and locations and insert them
        alias_list = []
        location_list = []
        rep_teams = set()

        for row in dataframe.itertuples(index=False):
            alias_list.append(
                CustomerAlias(alias=row[0], customer_id=self.cache.customers[row[1]]),
            )
            location_list.append(Location(location_id=None, city=row[2], state=row[3]))
            rep_teams.add(RepresentativeTeam(team_id=None, team_name=row[4]))

        self.dao.customer_aliases.create_bulk(alias_list)
        self.dao.locations.create_bulk(location_list)
        self.dao.rep_teams.create_bulk(rep_teams)

        self.cache.refresh_locations()
        self.cache.refresh_customer_aliases()
        self.cache.refresh_rep_teams()

        # Get all customer locations and insert them
        cl_list = [
            CustomerLocation(
                customer_id=self.cache.customers[row[1]],
                location_id=self.cache.locations[(row[2], row[3])],
            )
            for row in dataframe.itertuples(index=False)
        ]

        self.dao.customer_locations.create_bulk(cl_list)
        self.cache.refresh_customer_locations()

        # Get all rep team locations, representatives, and team members
        rtcl_list = []
        reps = []
        tmp_members = []

        for row in dataframe.itertuples(index=False):
            customer_id = self.cache.customers[row[1]]
            location_id = self.cache.locations[(row[2], row[3])]
            cl = CustomerLocation(customer_id, location_id)
            team_id = self.cache.rep_teams[row[4]]
            rtcl = RepTeamCustomerLocation(
                team_id=team_id,
                customer_location=cl,
            )
            rtcl_list.append(rtcl)
            if row[5]:
                reps.append(Representative(
                    representative_id=None,
                    representative_name=row[5],
                    ),
                )
                tmp_members.append((row[5], team_id, Classification.HEATING))
            if row[6]:
                reps.append(Representative(
                    representative_id=None,
                    representative_name=row[6],
                    ),
                )
                tmp_members.append((row[6], team_id, Classification.PLUMBING))

        # Insert rep team locations and representatives
        self.dao.rtcl.create_bulk(rtcl_list)
        self.dao.representatives.create_bulk(reps)

        self.cache.refresh_representatives()

        team_members = []

        # Pull rep IDs by name to create team_member list for insertion
        for member in tmp_members:
            rep_name = member[0]
            team_id = member[1]
            rep_class = member[2]
            rep_id = self.cache.representatives[rep_name]

            team_members.append(
                TeamMember(
                    team_id=team_id,
                    representative_id=rep_id,
                    rep_classification=rep_class,
                ),
            )

        self.dao.team_members.create_bulk(team_members)
        return True



