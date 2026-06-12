"""To be finished later."""
import contextlib
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

import psycopg2
import psycopg2.extras

T = TypeVar("T")

class DBConnector:
    """Class for logging in and connecting to the database.

    Contains methods for connection and reading/writing database credtials.
    """

    def __init__(self) -> None:
        """Initialize class attributes to default values."""
        self.conn = None
        self.customer_list = {}
        self.alias_list = {}
        self.location_list = {}
        self.item_list = {}

    @contextlib.contextmanager
    def cursor(self) -> Iterator[psycopg2.extensions.cursor]:
        """Provide a cursor for executing database operations.

        Opens a new cursor from the active connection and yields it
        to the caller. Automatically commits on success, or rolls back
        and raises and exception on failure. Cursor is automatically closed
        upon exit.

        Yields:
            Iterator[psycopg2.extensions.cursor]:
                A cursor object that internally handles all
                commits and rollbacks as needed.

        Raises:
            Exception: Any exception raised inside the 'with' block.

        """
        with self.conn.cursor() as cursor:
            try:
                yield cursor
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def close(self) -> None:
        """Close the currently active connection."""
        self.conn.close()

    def connect(self) -> None:
        """Check if credentials file exists and attempt connection."""
        if self.check_credentials():
            credentials = self.get_credentials()
            self.conn = psycopg2.connect(
                database=credentials["database"],
                user=credentials["user"],
                host=credentials["host"],
                password=credentials["password"],
                port=credentials["port"],
            )
        else:
            return

    def _credentials_path(self) -> Path:
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        return base_dir / "credentials.json"

    def set_credentials(
        self,
        database_name: str,
        username: str,
        password: str,
        host: str,
        port: str,
    ) -> None:
        """Write database credentials to a credentials.json file.

        Args:
            database_name (_type_):
                Name of database to connect to.
            username (_type_):
                Username of account connecting to database.
            password (_type_):
                Password of account connecting to database.
            host (_type_):
                IP address where database is located.
            port (_type_):
                Port the database is running on.

        """
        data = {
            "database": database_name,
            "user": username,
            "host": host,
            "password": password,
            "port": port,
        }

        file_path = self._credentials_path()
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def check_credentials(self) -> bool:
        """Check if credentials file exists."""
        file_path = self._credentials_path()
        return file_path.is_file()

    def get_credentials(self) -> dict[str, str]:
        """Read credentials file and load into dict.

        Returns:
            dict[str, str]:
                dict containing the saved login info.

        """
        credentials_path = self._credentials_path()
        with credentials_path.open("r", encoding="utf-8") as f:
            return json.load(f)

#------------------------------------------------------------------
# Dataclasses representing each table in database
#------------------------------------------------------------------

@dataclass
class Customer:
    """Dataclass to hold customer information from database."""

    customer_id: int | None
    customer_name: str

@dataclass
class  CustomerAlias:
    """Dataclass to hold customer alias information from database."""

    alias: str
    customer_id: int

@dataclass
class Location:
    """Dataclass to hold location information from database."""

    location_id: int | None
    city: str
    state: str

@dataclass
class CustomerLocation:
    """Dataclass to hold customer location information from database."""

    customer_id: int
    location_id: int

@dataclass
class Manufacturer:
    """Dataclass to hold manufacturer information from database."""

    manufacturer_id: int | None
    manufacturer_name: str

@dataclass
class Item:
    """Dataclass to hold item information from database."""

    item_id: int | None
    stockcode: str
    product_family: str
    product_description: str

@dataclass
class SalesReport:
    """Dataclass to hold sales report information from database."""

    report_id: int | None
    manufacturer_id: int
    report_year: str
    report_month: str

@dataclass
class SalesReportSummary:
    """Dataclass for report list display."""

    report_id: int
    manufacturer_name: str
    report_month: str
    report_year: str

@dataclass
class SaleCustomer:
    """Dataclass to hold sale customer information from database."""

    report_id: int
    customer_id: int
    location_id: int

@dataclass
class ReportLine:
    """Dataclass to hold report line information from database."""

    report_line_id: int | None
    report_id: int
    customer_alias: str
    customer_id: int
    location_id: int
    item_id: int
    quantity: int
    amt: Decimal
    transfer: str
    sale_date: str

#------------------------------------------------------------------
# DAO Classes
#------------------------------------------------------------------

class DAO:
    """Parent DAO class all subclasses inherit from.

    Subclasses must define:
        _table      :str         - table name
        _pk         :str         - primary key column name
        _select     :str         - full SELECT ... FROM <table> fragment
        _from_row   :classmethod - converts a ReadDictRow to the model
    """

    _table: str
    _pk: str
    _select: str

    def __init__(self, connector: DBConnector) -> None:
        """Initialize internal DBConnector.

        Args:
            connector (DBConnector):
                The DBConnector to be used by the DAO class for all functions.

        """
        self.connector = connector

    def _from_row(self, row: tuple[Any, ...]) -> T:
        raise NotImplementedError

    def get_all(self, limit: int = 10_000) -> list[T]:
        """Retrieve all entries within associated table.

        Utilizes internal select statement and primary key to select and order
        data from the associated table.

        Args:
            limit(int):
                The line limit the function should not exceed.

        Raises:
            RuntimeError:
                Raise RuntimeError if query exceeds specified limit.

        Note:
            Should only be used for small, slow growing tables.
            Use get_all_as_dict() or get_page() for larger tables.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            rows = cursor.fetchall()
        if len(rows) > limit:
            msg = f"{self._table}.get_all() exceeded {limit} rows."
            raise RuntimeError(msg)
        return [self._from_row(row) for row in rows]

    def get_all_as_dict(self, limit: int = 15_000) -> dict[T, T]:
        """Retrieve all entries within associated table as a dictionary.

        Utilizes internal select statement and primary key to select and order
        data from the associated table. Returns dictionary for use in joining
        reference tables or viewing large tables.

        Args:
            limit(int):
                The line limit the function should not exceed.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            return {x[0]: x[1] for x in cursor.fetchall()}

    def get_page(self, page_size: int = 100, page_number: int | None = None) -> list[T]:
        """Split table into pages based on page size.

        Args:
            page_size (int, optional):
                The number of entries that should be included per page. Defaults to 100.
            page_number (int | None, optional):
                The specific page number to retrieve. Defaults to None.

        Returns:
            list[T]: A list of the table associated dataclass.

        """
        with self.connector.cursor() as cursor:
            if page_number is None:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} LIMIT %s", (page_size,),
                )
            else:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s",
                    ((page_size * page_number), page_size),
                )
            return [self._from_row(row) for row in cursor.fetchall()]

    def get_page_as_dict(
        self,
        page_size: int = 100,
        page_number: int | None = None,
    ) -> dict[T, T]:
        """Split table into pages based on page size.

        Args:
            page_size (int, optional):
                The number of entries that should be included per page. Defaults to 100.
            page_number (int | None, optional):
                The specific page number to retrieve. Defaults to None.

        Returns:
            dict[T, T]: A dict of table information

        """
        with self.connector.cursor() as cursor:
            if page_number is None:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} LIMIT %s", (page_size,),
                )
            else:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s",
                    ((page_size * page_number), page_size),
                )
            return {getattr(row, self._pk): row for row in cursor.fetchall()}

#------------------------------------------------------------------
# Concrete implementations of DAO class
#------------------------------------------------------------------

class CustomerDAO(DAO):
    """To be finished later."""

    _table = "customers"
    _pk = "customer_id"
    _select = "SELECT customer_name, customer_id FROM customers"

    def _from_row(self, row: tuple[Any, ...]) -> Customer:
        return Customer(customer_name = row[0], customer_id = row[1])

    def get_by_id(self, customer_id: int) -> Customer | None:
        """Retrieve customer from database based on ID.

        Args:
            customer_id (int):
                The ID of the customer to be retrieved.

        Returns:
            Customer | None:
                The customer associated with the ID or none
                if it does not exist within the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def get_by_name(self, customer_name: str) -> Customer | None:
        """Retrieve customer from database based on name.

        Args:
            customer_name (int):
                The name of the customer to be retrieved.

        Returns:
            Customer | None:
                The customer associated with the ID or none
                if it does not exist within the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_name = %s", (customer_name,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def create(self, customer: Customer) -> Customer:
        """Add customer to the database.

        Args:
            customer (Customer):
                The customer to be inserted into the customer table.

        Returns:
            Customer:
                The customer that was inserted with its id assigned upon insertion.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO customers (customer_name) VALUES (%s) "
                "ON CONFLICT DO NOTHING RETURNING customer_id",
                (customer.customer_name,),
            )
            customer.customer_id = cursor.fetchone()[0]
        return customer

    def create_bulk(self, lines: list[Customer]) -> None:
        """Insert a list of customers into the database.

        Args:
            lines (list[Customer]):
                The list of customers to be inserted.

        """
        if not lines:
            return

        values = [(ln.customer_name,) for ln in lines]

        with self.connector.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO customers (customer_name) "
                "VALUES %s ON CONFLICT DO NOTHING",
                values,
                page_size=500,
            )

    def update(self, customer: Customer) -> None:
        """Update a customer name in the database.

        Args:
            customer (Customer):
                The customer to update.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "UPDATE customers SET customer_name = %s WHERE customer_id = %s",
                (customer.customer_name, customer.customer_id),
            )

    def delete(self, customer_id: int) -> None:
        """Delete a customer from the database.

        Args:
            customer_id (int):
                The ID of the customer to delete.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM customers WHERE customer_id = %s",
                (customer_id,),
            )

class CustomerAliasDAO(DAO):
    """To be finished later."""

    _table = "customer_alias"
    _pk = "customer_id"
    _select = "SELECT alias, customer_id FROM customer_alias"

    def _from_row(self, row: tuple[Any, ...]) -> CustomerAlias:
        return CustomerAlias(row[0], row[1])

    def get_by_customer(self, customer_id: int) -> list[CustomerAlias]:
        """Retrieve all aliases associated with a customers ID.

        Args:
            customer_id (int):
                ID of the customer to retrieve aliases for.

        Returns:
            list[CustomerAlias]:
                A list of all aliases associated with the custoemr ID.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            return [CustomerAlias(**row) for row in cursor.fetchall()]

    def create(self, alias: CustomerAlias) -> None:
        """Insert a new customer alias into the database.

        Args:
            alias (CustomerAlias):
                The alias to be inserted into the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO customer_alias (alias, customer_id) VALUES (%s, %s)",
                (alias.alias, alias.customer_id),
            )

    def create_bulk(self, lines: list[CustomerAlias]) -> bool:
        """Insert list of CustomerAliases into database.

        Args:
            lines (list[CustomerAlias]):
                The list of aliases to be inserted into the database.

        Returns:
            bool:
                True if the insert was successful, False if the list was empty.

        """
        if not lines:
            return False

        values = [(ln.alias, ln.customer_id) for ln in lines]

        with self.connector.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO customer_alias (alias, customer_id) "
                "VALUES %s ON CONFLICT DO NOTHING",
                values,
                page_size=500,
            )
            return True


    def delete(self, alias: str) -> None:
        """Delete a customer alias from the database.

        Args:
            alias (str):
                The alias to be deleted.

        """
        with self.connector.cursor() as cursor:
            cursor.execute("DELETE FROM customer_alias WHERE alias = %s", (alias,))

class LocationDAO(DAO):
    """To be finished later."""

    _table = "locations"
    _pk = "location_id"
    _select = "SELECT location_id, city, state FROM locations"

    def _from_row(self, row: tuple[Any, ...]) -> Location:
        return Location(location_id=row[0], city=row[1], state=row[2])

    def get_all_as_dict(self) -> dict[tuple[str, str], int]:
        """Retrieve all locations in the database as a dictionary.

        Returns:
            dict[tuple[str, str], int]:
                A dictionary with a tuple of (city, state)
                as the key and location ID as the value.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk}")
            return {(x[1], x[2]): x[0] for x in cursor.fetchall()}

    def get_page_as_dict(
        self,
        page_size: int = 100,
        page_number: int | None = None,
    ) -> dict[tuple[str, str], int]:
        """Retrieve all locations of a page as a dictionary.

        Args:
            page_size (int, optional):
                The max number of entries a page should have. Defaults to 100.
            page_number (int | None, optional):
                The page number to start from. Defaults to None.

        Returns:
            dict[tuple[str, str], int]:
                A dictionary with a tuple of (city, state)
                as the key and location ID as the value.

        """
        with self.connector.cursor() as cursor:
            if page_number is None:
                cursor.execute(
                    f"{self._select} ORDER BY state, city LIMIT %s",
                    (page_size,),
                )
            else:
                cursor.execute(
                    f"{self._select} ORDER BY state, city OFFSET %s LIMIT %s",
                    ((page_size * page_number), page_size),
                )
            return {(x[1], x[2]): x[0] for x in cursor.fetchall()}

    def get_by_id(self, location_id: int) -> Location | None:
        """Retrieve a location based on its ID.

        Args:
            location_id (int):
                The ID of the location to retrieve.

        Returns:
            Location | None:
                The location associated with the ID or None if it
                is not present in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE location_id = %s", (location_id,))
            row = cursor.fetchone()
        return Location(**row) if row else None

    def get_by_name(self, city: str, state: str) -> Location | None:
        """Retrieve a location based on its city and state.

        Args:
            city (str):
                The city of the location to retrieve.
            state (str):
                The state of the location to retrieve.

        Returns:
            Location | None:
                The location associated with the city and state or None if it
                is not present in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE city = %s AND state = %s",
                (city, state),
            )
            row = cursor.fetchone()
        return Location(**row) if row else None

    def create(self, location: Location) -> Location:
        """Insert a location into the database.

        Args:
            location (Location):
                The location to be inserted into the database.

        Returns:
            Location:
                A new location object containing the ID
                assigned to the inserted location.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO locations (city, state) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING RETURNING location_id ",
                (location.city, location.state),
            )
            location.location_id = cursor.fetchone()[0]
        return location

    def update(self, location: Location) -> None:
        """Update a location's city and state in the database.

        Args:
            location (Location):
                The location information to be updated on the associated location ID.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "UPDATE locations SET city = %s, state = %s WHERE location_id = %s",
                (location.city, location.state, location.location_id),
            )

    def delete(self, location_id: int) -> None:
        """Delete a location from the database.

        Args:
            location_id (int):
                The ID of the location to delete.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM locations WHERE location_id = %s",
                (location_id,),
            )

class CustomerLocationDAO(DAO):
    """To be finished later."""

    _table = "customer_locations"
    _pk = "customer_id"
    _select = "SELECT customer_id, location_id FROM customer_locations"

    def _from_row(self, row: tuple[Any, ...]) -> CustomerLocation:
        return CustomerLocation(**row)

    def get(self, customer_id: int, location_id: int) -> CustomerLocation | None:
        """Retrieve a customer location link based on the customer and location IDs.

        Args:
            customer_id (int):
                The ID of the customer in the link.
            location_id (int):
                The ID of the location in the link.

        Returns:
            CustomerLocation | None:
                The customer location link if it exists or None if not.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE customer_id = %s AND location_id = %s",
                (customer_id, location_id),
            )
            row = cursor.fetchone()
            return CustomerLocation(
                customer_id = row[0],
                location_id = row[1],
            ) if row else None

    def get_locations_for_customer(self, customer_id: int) -> list[CustomerLocation]:
        """Retrieve a list of all customer locations associated with a customer ID.

        Args:
            customer_id (int):
                The ID of the customer.

        Returns:
            list[CustomerLocation]:
                A list of all customer locations associated with the customer ID.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            return [CustomerLocation(**row) for row in cursor.fetchall()]

    def get_customers_for_location(self, location_id: int) -> list[CustomerLocation]:
        """Retrieve a list of all customers associated with a location ID.

        Args:
            location_id (int):
                The ID of the location.

        Returns:
            list[CustomerLocation]:
                A list of all customer locations associated with the location ID.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE location_id = %s", (location_id,))
            return [CustomerLocation(**row) for row in cursor.fetchall()]

    def create(self, link: CustomerLocation) -> None:
        """Insert a customer location link into the database.

        Args:
            link (CustomerLocation):
                The link to be inserted.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO customer_locations (customer_id, location_id) "
                "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (link.customer_id, link.location_id),
                )

    def create_bulk(self, lines: list[CustomerLocation]) -> None:
        """Insert a list of customer location links into the database.

        Args:
            lines (list[CustomerLocation]):
                The list of customer locations to be inserted.

        """
        if not lines:
            return lines

        values = [(ln.customer_id, ln.location_id) for ln in lines]

        with self.connector.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO customer_locations (customer_id, location_id) "
                "VALUES %s ON CONFLICT DO NOTHING",
                values,
                page_size=500,
            )
            return None

    def delete(self, customer_id: int, location_id: int) -> None:
        """Delete a customer location link from the database.

        Args:
            customer_id (int):
                The ID of the customer in the link.
            location_id (int):
                The ID of the location in the link.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM customer_locations "
                "WHERE customer_id = %s AND location_id = %s",
                (customer_id, location_id),
            )

class ManufacturerDAO(DAO):
    """To be finished later."""

    _table = "manufacturers"
    _pk = "manufacturer_id"
    _select = "SELECT manufacturer_name, manufacturer_id FROM manufacturers"

    def _from_row(self, row: tuple[Any, ...]) -> Manufacturer:
        return Manufacturer(row[1], row[0])

    def get_by_id(self, manufacturer_id: int) -> Manufacturer | None:
        """Retrieve a manufacturer based on its ID.

        Args:
            manufacturer_id (int):
                The ID of the manufacturer to retrieve.

        Returns:
            Manufacturer | None:
                The manufacturer associated with the ID
                or None if it does not exist in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE manufacturer_id = %s",
                (manufacturer_id,),
            )
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def get_by_name(self, manufacturer_name: str) -> Manufacturer | None:
        """Retrieve a manufacturer based on its name.

        Args:
            manufacturer_name (str):
                The name of the manufacturer to retrieve.

        Returns:
            Manufacturer | None:
                The manufacturer associated with the name
                or None if it does not exist in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE manufacturer_name = %s",
                (manufacturer_name,),
            )
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def create(self, manufacturer: Manufacturer) -> Manufacturer:
        """Insert a manufacturer into the database.

        Args:
            manufacturer (Manufacturer):
                The manufacturer to insert.

        Returns:
            Manufacturer:
                A new manufacturer object containing the id
                of the inserted manufacturer.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO manufacturers (manufacturer_name) "
                "VALUES (%s) RETURNING manufacturer_id",
                (manufacturer.manufacturer_name,),
            )
            manufacturer.manufacturer_id = cursor.fetchone()[0]
        return manufacturer

    def update(self, manufacturer: Manufacturer) -> None:
        """Update a manufacturer in the database.

        Args:
            manufacturer (Manufacturer):
                A manufacturer object containing the new name
                and the ID of the manufacturer being updated.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "UPDATE manufacturers SET manufacturer_name = %s "
                "WHERE manufacturer_id = %s",
                (manufacturer.manufacturer_id,),
            )

    def delete(self, manufacturer_id: int) -> None:
        """Delete a manufacturer from the database.

        Args:
            manufacturer_id (int):
                The ID of the manufacturer to delete.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM manufacturers WHERE manufacturer_id = %s",
                (manufacturer_id,),
            )

class ItemDAO(DAO):
    """To be finished later."""

    _table = "items"
    _pk = "item_id"
    _select = "SELECT item_id, stockcode, product_family, product_description FROM item"

    def _from_row(self, row: tuple[Any, ...]) -> Item:
        return Item(row[0], row[1], row[2], row[3])

    def get_all_as_dict(self, limit: int = 15_000) -> dict[str, int]:
        """Retreive all items in the database as a dict.

        Args:
            limit (int):
                The maximum number of entries to retrieve.

        Returns:
            dict[str, int]:
                A dictionary containing the item stockcode as the key
                and the item ID as the value.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            return {x[1]: x[0] for x in cursor.fetchall()}

    def get_page_as_dict(
        self,
        page_size: int = 100,
        page_number: int | None = None,
    ) -> dict[str, int]:
        """Retrieve a page of items as a dict.

        Args:
            page_size (int):
                The maximum number of entries each page should have. Defaults to 100.
            page_number (int | None):
                The number of the page to retrieve(should be based on page_size).
                Defaults to None.

        Returns:
            dict[str, int]:
                A dictionary containing the item stockcode as the key
                and the item ID as the value.

        """
        with self.connector.cursor() as cursor:
            if page_number is None:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} LIMIT %s",
                    (page_size,),
                )
            else:
                cursor.execute(
                    f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s",
                    ((page_size * page_number), page_size),
                )
            return {x[1]: x[0] for x in cursor.fetchall()}

    def get_by_id(self, item_id: int) -> Item | None:
        """Retrieve an item based on its ID.

        Args:
            item_id (int):
                The ID of the item to retrieve.

        Returns:
            Item | None:
                An Item object containing the item information associated with the ID
                or None if the item does not exist in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE item_id = %s", (item_id,))
            row = cursor.fetchone()
        return Item(**row) if row else None

    def get_by_stockcode(self, stockcode: str) -> Item | None:
        """Retrieve an item based on its stockcode.

        Args:
            stockcode (str):
                The stockcode of the item to retrieve.

        Returns:
            Item | None:
                An Item object containing the item information associated
                with the stockcode or None if the item does not exist in the database.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE stockcode = %s", (stockcode,))
            row = cursor.fetchone()
        return Item(**row) if row else None

    def get_by_family(self, product_family: str) -> list[Item]:
        """Retrieve all items within a specific product family.

        Args:
            product_family (str):
                The product family of the items to retrieve.

        Returns:
            list[Item]:
                A list containing all items associated with
                the specified product family.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE product_family = %s ORDER BY stockcode",
                (product_family,),
            )
        return [Item(**row) for row in cursor.fetchall()]

    def create(self, item: Item) -> Item:
        """Insert an item into the database.

        Args:
            item (Item):
                The item to be inserted.

        Returns:
            Item:
                An item object containing the ID of the inserted item.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO item (stockcode, product_family, product_description) "
                "VALUES (%s, %s, %s) RETURNING item_id",
                (item.stockcode, item.product_family, item.product_description),
            )
            item.item_id = cursor.fetchone()[0]
        return item

    def update(self, item: Item) -> None:
        """Update an item in the database.

        Args:
            item (Item):
                An Item object containing the ID of the item to update
                and the updated information.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "UPDATE item "
                "SET stockcode = %s, product_family = %s, product_description = %s "
                "WHERE item_id = %s",
                (
                    item.stockcode,
                    item.product_family,
                    item.product_description,
                    item.item_id,
                ),
            )

    def delete(self, item_id: int) -> None:
        """Delete an item from the database.

        Args:
            item_id (int):
                The ID of the item to delete.

        """
        with self.connector.cursor() as cursor:
            cursor.execute("DELETE FROM item WHERE item_id = %s", (item_id,))

class SalesReportDAO(DAO):
    """To be finished later."""

    _table = "sales_report"
    _pk = "sales_report_id"
    _select = (
        "SELECT report_id, manufacturer_id, report_year, report_month FROM sales_report"
    )

    def _from_row(self, row: tuple[Any, ...]) -> SalesReport:
        return SalesReport(**row)

    def get_by_id(self, report_id: int) -> SalesReport | None:
        """Retrieve a sales report by its ID.

        Args:
            report_id (int):
                The ID of the report to retrieve.

        Returns:
            SalesReport | None:
                The sales report associated with the ID if it exists
                or None if it does not.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "SELECT FROM sales_report WHERE report_id = %s",
                (report_id,),
            )
            row = cursor.fetchone()
        return SalesReport(**row) if row else None

    def check_exists(self, report: SalesReport) -> bool:
        """Check if a specific report is already present in the database.

        Args:
            report (SalesReport):
                The report to check. Must contain the manufacturer ID,
                report year, and report month.

        Returns:
            bool:
                True if the report exists within the database
                or false if it does not.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM sales_report "
                "WHERE manufacturer_id = %s AND report_year = %s AND report_month = %s "
                "LIMIT 1",
                (report.manufacturer_id, report.report_year, report.report_month),
            )
            result = cursor.fetchone()
        return bool(result)

    def get_by_manufacturer(self, manufacturer_id: int) -> list[SalesReport]:
        """Retrieve all sales reports of a specific manufacturer.

        Args:
            manufacturer_id (int):
                The ID of the manufacturer.

        Returns:
            list[SalesReport]:
                A list containing all sales reports associated
                with that manufacturer.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "SELECT FROM sales_report WHERE manufacturer_id = %s",
                (manufacturer_id,),
            )
            return [SalesReport(**row) for row in cursor.fetchall()]

    def get_by_period(self, year: str, month: str) -> list[SalesReport]:
        """Retrieve all sales reports within a specific period.

        Args:
            year (str):
                The year of the reports.
            month (str):
                The month of the reports.

        Returns:
            list[SalesReport]:
                A list of all sales reports within the specified period.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "SELECT FROM sales_report WHERE year = %s AND month = %s",
                (year, month),
            )
            return [SalesReport(**row) for row in cursor.fetchall()]

    def create(self, report: SalesReport) -> SalesReport:
        """Insert a new sales report into the database.

        Args:
            report (SalesReport):
                The sales report to insert.

        Returns:
            SalesReport:
                A SalesReport object containing the ID of the new report.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sales_report (manufacturer_id, report_year, report_month) "
                "VALUES (%s, %s, %s) RETURNING report_id",
                (report.manufacturer_id, report.report_year, report.report_month),
            )
            report.report_id = cursor.fetchone()[0]
        return report

    def delete(self, report_id: int) -> None:
        """Delete a sales report from the database.

        Args:
            report_id (int):
                The ID of the report to delete.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sales_report WHERE report_id = %s",
                (report_id,),
            )

    def list_summary(self, limit: int = 50) -> list["SalesReportSummary"]:
        """Return recent reports joined with manufacturer name for display.

        Args:
            limit (int):
                Maximum number of reports to return. Defaults to 50.

        Returns:
            list[SalesReportSummary]:
                Reports ordered by year DESC, month DESC so the most
                recent appears first.

        """
        query = (
            "SELECT sr.report_id, m.manufacturer_name, "
            "sr.report_month, sr.report_year "
            "FROM sales_report sr "
            "JOIN manufacturers m ON sr.manufacturer_id = m.manufacturer_id "
            "ORDER BY sr.report_id DESC "
            "LIMIT %s"
        )
        with self.connector.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        return [
            SalesReportSummary(
                report_id=row[0],
                manufacturer_name=row[1],
                report_month=row[2],
                report_year=row[3],
            )
            for row in rows
        ]

class SaleCustomerDAO(DAO):
    """To be finished later."""

    _table = "sale_customer"
    _pk = "report_id"
    _select = "SELECT report_id, customer_id, location_id FROM sale_customer"

    def _from_row(self, row: tuple[Any, ...]) -> SaleCustomer:
        return SaleCustomer(**row)

    def get(
        self,
        report_id: int,
        customer_id: int,
        location_id: int,
    ) -> SaleCustomer | None:
        """Retrieve a SaleCustomer from the database.

        Args:
            report_id (int):
                The ID of the report the customer is from.
            customer_id (int):
                The ID of the customer.
            location_id (int):
                The ID of the location of the customer.

        Returns;
            SaleCustomer | None:
                A SaleCustomer object if an associated sales customer exists
                or None if it does not.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE report_id = %s AND customer_id = %s "
                "AND location_id = %s",
                (report_id, customer_id, location_id),
            )
            row = cursor.fetchone()
            return SaleCustomer(report_id=row[0],
                                customer_id=row[1],
                                location_id=row[2],
                            ) if row else None

    def get_by_report(self, report_id: int) -> list[SaleCustomer]:
        """Retrieve all SaleCustomers of a report.

        Args:
            report_id (int):
                The ID of the report to pull customers from.

        Returns:
            list[SaleCustomer]:
                A list of all SaleCustomers within the specified report.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE report_id = %s", (report_id,))
        return [SaleCustomer(**row) for row in cursor.fetchall()]

    def create(self, link: SaleCustomer) -> None:
        """Insert a new SaleCustomer into the database.

        Args:
            link (SaleCustomer):
                The SaleCustomer link to be inserted.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sale_customer (report_id, customer_id, location_id) "
                "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (link.report_id, link.customer_id, link.location_id),
            )

    def delete(self, report_id: int, customer_id: int, location_id: int) -> None:
        """Delete a SaleCustomer link from the database.

        Args:
            report_id (int):
                The ID of the report the sale customer is from.
            customer_id (int):
                The ID of the customer.
            location_id (int):
                The ID of the location of the customer.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sale_customer "
                "WHERE report_id = %s AND customer_id = %s AND location_id = %s",
                (report_id, customer_id, location_id),
            )

    def create_bulk(self, lines: list[SaleCustomer]) -> None:
        """Insert a list of SaleCustomers into the database.

        Args:
            lines (list[SaleCustomer]):
                The list of SaleCustomers to be inserted.

        """
        if not lines:
            return lines

        values = [(ln.report_id, ln.customer_id, ln.location_id) for ln in lines]

        with self.connector.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO sale_customer (report_id, customer_id, location_id) "
                "VALUES %s ON CONFLICT DO NOTHING",
                values,
                page_size=500,
            )
            return None

class ReportLineDAO(DAO):
    """To be finished later."""

    _table = "report_line"
    _pk = "report_line_id"
    _select = ("SELECT report_line_id, "
               "report_id, "
               "customer_alias, "
               "customer_id, item_id, "
               "quantity, "
               "amt, "
               "transfer, "
               "location_id, "
               "sale_date "
               "FROM report_line"
            )

    def _from_row(self, row: tuple[Any, ...]) -> ReportLine:
        return ReportLine(
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
        )

    def get_by_id(self, report_line_id: int) -> ReportLine | None:
        """Retrieve a ReportLine based on its ID.

        Args:
            report_line_id (int):
                The ID of the ReportLine to retrieve.

        Returns:
            ReportLine | None:
                The ReportLine associated with the ID if it exists
                or None if it does not.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE report_line_id = %s",
                (report_line_id,),
            )
            row = cursor.fetchone()
            return ReportLine(**row) if row else None

    def get_by_report(self, report_id: int) -> list[ReportLine]:
        """Retrieve a list of all ReportLines within a report.

        Args:
            report_id (int):
                The ID of the report to retreive the lines from.

        Returns:
            list[ReportLine]:
                A list containing all ReportLines of the specified report.

        """
        with self.connector.cursor() as cursor:
             cursor.execute(
                 f"{self._select} WHERE report_id = %s ORDER BY report_line_id",
                 (report_id,),
                )
             return [self._from_row(x) for x in cursor.fetchall()]

    def stream_by_report(
        self, report_id: int,
        chunk_size: int = 500,
    ) -> Iterator[ReportLine]:
        """To be documented later."""
        # Named cursors must NOT go through the commit/rollback wrapper —
        # they need their own connection transaction scope.
        conn = self.connector.conn
        with conn.cursor(
            name="report_line_stream",
            cursor_factory=psycopg2.extras.RealDictCursor,
        ) as cur:
            cur.itersize = chunk_size
            cur.execute(
                f"{self._select} WHERE report_id = %s ORDER BY report_line_id",
                (report_id,),
            )
            for row in cur:  # psycopg2 fetches `itersize` rows per round-trip
                yield ReportLine(**row)

    def get_by_customer(self, customer_id: int) -> list[ReportLine]:
        """Retrieve all ReportLines containing a specific customer.

        Args:
            customer_id (int):
                The ID of the customer to search for.

        Returns:
            list[ReportLine]:
                A list of ReportLine containing all lines with the
                specified customer.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                f"{self._select} WHERE customer_id = %s ORDER BY report_line_id",
                (customer_id,),
            )
            return [ReportLine(**row) for row in cursor.fetchall()]

    def get_by_date_range(self) -> list[ReportLine]:
        """To be implemented later."""

    def create(self, line: ReportLine) -> None:
        """Insert a ReportLine into the database.

        Args:
            line (ReportLine):
                The ReportLine to be inserted.

        """
        with self.connector.cursor() as cursor:
            cursor.execute("INSERT INTO report_line "
                           "(report_id, "
                           "customer_id, "
                           "item_id, "
                           "quantity, "
                           "amt, "
                           "transfer, "
                           "location_id, "
                           "sale_date) "
                           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            line.report_id,
                            line.customer_id,
                            line.item_id,
                            line.quantity,
                            line.amt,
                            line.transfer,
                            line.location_id,
                            line.sale_date,
                        ),
            )

    def direct_insert(  # noqa: PLR0913
        self,
        report_id: int,
        customer_id: int,
        item_id: int,
        location_id: int,
        amount: float,
        saledate: str,
        quantity: int,
        transfer: str,
    ) -> None:
        """Insert a single report line using raw data.

        Args:
            report_id (int):
                ID of the parent report.
            customer_id (int):
                ID of the customer in the line.
            item_id (int):
                ID of the item in the line.
            location_id (int):
                ID of the location in the line.
            amount (float):
                The amount value of the line.
            saledate (str):
                The sale date of the line.
            quantity (int):
                The item quantity of the line.
            transfer (str):
                The transfer type of the line.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(
                "insert into report_line "
                "(report_id, "
                "customer_id, "
                "item_id, "
                "location_id, "
                "amt, "
                "sale_date, "
                "quantity, "
                "transfer) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s);",
                (
                    report_id,
                    customer_id,
                    item_id,
                    location_id,
                    amount,
                    saledate,
                    quantity,
                    transfer,
                ),
            )

    def create_bulk(self, lines: list[ReportLine]) -> None:
        """Insert a list of ReportLine.

        Args:
            lines (list[ReportLine]):
                The list of ReportLines to insert.

        """
        if not lines:
            return lines

        values = [
            (
                ln.report_id,
                ln.customer_alias,
                ln.customer_id,
                ln.item_id,
                ln.quantity,
                ln.amt,
                ln.transfer,
                ln.location_id,
                ln.sale_date,
            )
            for ln in lines
        ]

        with self.connector.cursor() as cursor:
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO report_line "
                "(report_id, "
                "customer_alias, "
                "customer_id, "
                "item_id, "
                "quantity, "
                "amt, "
                "transfer, "
                "location_id, "
                "sale_date) "
                "VALUES %s",
                values,
                page_size=500,
            )
            return None

class DAOFactory:
    """To be finished later."""

    def __init__(self, db: DBConnector) -> None:
        """Initialize a DAOFactory object and its internal DAO Classes."""
        self.db = db
        self.customers = CustomerDAO(db)
        self.customer_aliases = CustomerAliasDAO(db)
        self.locations = LocationDAO(db)
        self.customer_locations = CustomerLocationDAO(db)
        self.manufacturers = ManufacturerDAO(db)
        self.items = ItemDAO(db)
        self.sales_reports = SalesReportDAO(db)
        self.sale_customers = SaleCustomerDAO(db)
        self.report_lines = ReportLineDAO(db)

    def close(self) -> None:
        """Close the database connection of the factory."""
        self.db.close()
