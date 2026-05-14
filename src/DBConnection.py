import contextlib
import json
import os
import sys
from collections.abc import Iterator
from ctypes.wintypes import HCURSOR
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce
from typing import Any, Optional, TypeVar

import psycopg2
import psycopg2.extras

T = TypeVar("T")

class DBConnector:

    def __init__(self):
        self.conn = None
        self.customer_list = {}
        self.alias_list = {}
        self.location_list = {}
        self.item_list = {}

    @contextlib.contextmanager
    def cursor(self) -> Iterator[psycopg2.extensions.cursor]:
        with self.conn.cursor() as cursor:
            try:
                yield cursor
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def close(self):
        self.conn.cursor().close()
        self.conn.close()

    def connect(self) -> None:
        if self.check_credentials():
            credentials = self.get_credentials()
            self.conn = psycopg2.connect(
                database=credentials['database'],
                user=credentials['user'],
                host=credentials['host'],
                password=credentials['password'],
                port=credentials['port']
            )
        else:
            print("Database credentials not found")

    def direct_connect(self):
        #fill with credentials manually
        self.conn = psycopg2.connect(
            database="",
            user="",
            password="",
            host="",
            port=""
        )

    @staticmethod
    def _credentials_path():
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(__file__)
        return os.path.join(base_dir, 'credentials.json')

    @staticmethod
    def set_credentials(database_name, username, password, host, port):
        data = {
            "database": database_name,
            "user": username,
            "host": host,
            "password": password,
            "port": port
        }

        file_path = DBConnector._credentials_path()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def check_credentials():
        return os.path.isfile(DBConnector._credentials_path())

    @staticmethod
    def get_credentials():
        with open(DBConnector._credentials_path(), 'r', encoding='utf-8') as f:
            credentials = json.load(f)
        return credentials

    def select_report_by_id(self, _id):
        report_id = _id
        cursor = self.conn.cursor()
        query = """select m.manufacturer_name,
                          sr.report_year,
                          sr.report_month,
                          c.customer_name,
                          l.city,
                          l.state,
                          i.stockcode,
                          rl.amt,x
                          rl.quantity,
                          rl.transfer
                   from report_line rl
    
                            join sales_report sr
                                 on rl.report_id = sr.report_id
    
                            join manufacturers m
                                 on sr.manufacturer_id = m.manufacturer_id
    
                            join customers c
                                 on rl.customer_id = c.customer_id
    
                            join locations l
                                 on rl.location_id = l.location_id
    
                            join item i
                                 on rl.item_id = i.item_id
    
                   where rl.report_id = %s
    
                   order by c.customer_name,
                            l.city,
                            i.item_name;"""

        cursor.execute(query, (report_id,))
        rows = cursor.fetchall()

        for row in rows:
            print(row)

#------------------------------------------------------------------
# Dataclasses representing each table in database
#------------------------------------------------------------------

@dataclass
class Customer:
    customer_id: Optional[int]
    customer_name: str

@dataclass
class  CustomerAlias:
    alias: str
    customer_id: int

@dataclass
class Location:
    location_id: Optional[int]
    city: str
    state: str

@dataclass
class CustomerLocation:
    customer_id: int
    location_id: int

@dataclass
class Manufacturer:
    manufacturer_id: Optional[int]
    manufacturer_name: str

@dataclass
class Item:
    item_id: Optional[int]
    stockcode: str
    product_family: str
    product_description: str

@dataclass
class SalesReport:
    report_id: Optional[int]
    manufacturer_id: int
    report_year: str
    report_month: str

@dataclass
class SaleCustomer:
    report_id: int
    customer_id: int
    location_id: int

@dataclass
class ReportLine:
    report_line_id: Optional[int]
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
    """
    Subclasses must define:
        _table      :str         - table name
        _pk         :str         - primary key column name
        _select     :str         - full SELECT ... FROM <table> fragment
        _from_row   :classmethod - converts a ReadDictRow to the model
    """

    _table: str
    _pk: str
    _select: str

    def __init__(self, db: DBConnector) -> None:
        self.db = db

    def _from_row(self, row) -> T:
        raise NotImplementedError

    #------------------------------------------------------------------
    # get_all - use for small, slow growing reference tables
    # Raises error if row count exceeds 'limit'
    #------------------------------------------------------------------

    def get_all(self, limit: int = 10_000) -> list[T]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            rows = cursor.fetchall()
        if len(rows) > limit:
            raise RuntimeError(f"{self._table}.get_all() exceeded {limit} rows.")
        return [self._from_row(row) for row in rows]

    #------------------------------------------------------------------
    # get_all_as_dict - same as get all but returns rows as a dict
    # Use for joining reference tables or viewing large tables
    # Raises error if row count exceeds 'limit'
    #------------------------------------------------------------------

    def get_all_as_dict(self, limit: int = 15_000) -> dict[T, T]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            return dict(map(lambda x: (x[0], x[1]), cursor.fetchall()))

    # ------------------------------------------------------------------
    # get_page - splits table into pages based on page size
    # Preferred to get_all() for large tables
    # ------------------------------------------------------------------

    def get_page(self, page_size: int = 100, page_number: Optional[int] = None,) -> list[T]:
        with self.db.cursor() as cursor:
            if page_number is None:
                cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (page_size,))
            else:
                cursor.execute(f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s", ((page_size * page_number), page_size))
            return [self._from_row(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # get_page_as_dict - same as get_page but returns a dict
    # ------------------------------------------------------------------

    def get_page_as_dict(self, page_size: int = 100, page_number: Optional[int] = None,) -> dict[T, T]:
        with self.db.cursor() as cursor:
            if page_number is None:
                cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (page_size,))
            else:
                cursor.execute(f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s",((page_size * page_number), page_size))
            return {getattr(row, self._pk): row for row in cursor.fetchall()}

#------------------------------------------------------------------
# Concrete implementations of DAO class
#------------------------------------------------------------------

class CustomerDAO(DAO):

    _table = "customers"
    _pk = "customer_id"
    _select = "SELECT customer_name, customer_id FROM customers"

    def _from_row(self, row) -> Customer:
        return Customer(customer_name = row[0], customer_id = row[1])

    def get_by_id(self, customer_id: int) -> Optional[Customer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def get_by_name(self, customer_name: str) -> Optional[Customer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_name = %s", (customer_name,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def create(self, customer: Customer) -> Customer:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO customers (customer_name) VALUES (%s) RETURNING customer_id ON CONFLICT DO NOTHING", (customer.customer_name,))
            customer.customer_id = cursor.fetchone()[0]
        return customer

    def create_bulk(self, lines: list[Customer]) -> None:
        if not lines:
            return None

        values = [(ln.customer_name,) for ln in lines]

        with self.db.cursor() as cursor:
            psycopg2.extras.execute_values(cursor,"INSERT INTO customers (customer_name) VALUES %s ON CONFLICT DO NOTHING", values, page_size=500)
            return None

    def update(self, customer: Customer) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("UPDATE customers SET customer_name = %s WHERE customer_id = %s", (customer.customer_name, customer.customer_id))

    def delete(self, customer_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))

class CustomerAliasDAO(DAO):

    _table = "customer_alias"
    _pk = "customer_id"
    _select = "SELECT alias, customer_id FROM customer_alias"

    def _from_row(self, row) -> CustomerAlias:
        return CustomerAlias(**row)

    def get_by_customer(self, customer_id: int) -> list[CustomerAlias]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            return [CustomerAlias(**row) for row in cursor.fetchall()]

    def create(self, alias: CustomerAlias) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO customer_alias (alias, customer_id) VALUES (%s, %s)", (alias.alias, alias.customer_id))

    def create_bulk(self, lines: list[CustomerAlias]) -> bool:
        if not lines:
            return False

        values = [(ln.alias, ln.customer_id) for ln in lines]

        with self.db.cursor() as cursor:
            psycopg2.extras.execute_values(cursor,"INSERT INTO customer_alias (alias, customer_id) VALUES %s ON CONFLICT DO NOTHING", values, page_size=500)
            return True


    def delete(self, alias: str) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM customer_alias WHERE alias = %s", (alias,))

class LocationDAO(DAO):

    _table = "locations"
    _pk = "location_id"
    _select = "SELECT location_id, city, state FROM locations"

    def _from_row(self, row) -> Location:
        return Location(**row)

    def get_all_as_dict(self) -> dict[tuple[str, str], int]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk}")
            return dict(map(lambda x: ((x[1], x[2]), x[0]), cursor.fetchall()))

    def get_page_as_dict(self, page_size: int = 100, page_number: Optional[int] = None,) -> dict[tuple[str, str], int]:
        with self.db.cursor() as cursor:
            if page_number is None:
                cursor.execute(f"{self._select} ORDER BY state, city LIMIT %s", (page_size,))
            else:
                cursor.execute(f"{self._select} ORDER BY state, city OFFSET %s LIMIT %s",
                               ((page_size * page_number), page_size))
            return dict(map(lambda x: ((x[1], x[2]), x[0]), cursor.fetchall()))

    def get_by_id(self, location_id: int) -> Optional[Location]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE location_id = %s", (location_id,))
            row = cursor.fetchone()
        return Location(**row) if row else None

    def get_by_name(self, city: str, state: str) -> Optional[Location]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE city = %s AND state = %s", (city, state))
            row = cursor.fetchone()
        return Location(**row) if row else None

    def create(self, location: Location) -> Location:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO locations (city, state) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING location_id ", (location.city, location.state))
            location.location_id = cursor.fetchone()[0]
        return location

    def update(self, location: Location) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("UPDATE locations SET city = %s, state = %s WHERE location_id = %s", (location.city, location.state, location.location_id))

    def delete(self, location_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM locations WHERE location_id = %s", (location_id,))

class CustomerLocationDAO(DAO):

    _table = "customer_locations"
    _pk = "customer_id"
    _select = "SELECT customer_id, location_id FROM customer_locations"

    def _from_row(self, row) -> CustomerLocation:
        return CustomerLocation(**row)

    def get(self, customer_id: int, location_id: int) -> Optional[CustomerLocation]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s AND location_id = %s", (customer_id, location_id))
            row = cursor.fetchone()
            return CustomerLocation(customer_id = row[0], location_id = row[1]) if row else None

    def get_locations_for_customer(self, customer_id: int) -> list[CustomerLocation]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s", (customer_id,))
            return [CustomerLocation(**row) for row in cursor.fetchall()]

    def get_customers_for_location(self, location_id: int) -> list[CustomerLocation]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE location_id = %s", (location_id,))
            return [CustomerLocation(**row) for row in cursor.fetchall()]

    def create(self, link: CustomerLocation) -> CustomerLocation:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO customer_locations (customer_id, location_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (link.customer_id, link.location_id))
        return link

    def create_bulk(self, lines: list[CustomerLocation]) -> None:
        if not lines:
            return lines

        values = [(ln.customer_id, ln.location_id) for ln in lines]

        with self.db.cursor() as cursor:
            psycopg2.extras.execute_values(cursor,"INSERT INTO customer_locations (customer_id, location_id) VALUES %s ON CONFLICT DO NOTHING", values, page_size=500)
            return None

    def delete(self, customer_id: int, location_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM customer_locations WHERE customer_id = %s and location_id = %s", (customer_id, location_id))

class ManufacturerDAO(DAO):

    _table = "manufacturers"
    _pk = "manufacturer_id"
    _select = "SELECT manufacturer_name, manufacturer_id FROM manufacturers"

    def _from_row(self, row) -> Manufacturer:
        return Manufacturer(row[1], row[0])

    def get_by_id(self, manufacturer_id: int) -> Optional[Manufacturer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE manufacturer_id = %s", (manufacturer_id,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def get_by_name(self, manufacturer_name: str) -> Optional[Manufacturer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE manufacturer_name = %s", (manufacturer_name,))
            row = cursor.fetchone()
        return self._from_row(row) if row else None

    def create(self, manufacturer: Manufacturer) -> Manufacturer:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO manufacturers (manufacturer_name) VALUES (%s) RETURNING manufacturer_id", (manufacturer.manufacturer_name,))
            manufacturer.manufacturer_id = cursor.fetchone()[0]
        return manufacturer

    def update(self, manufacturer: Manufacturer) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("UPDATE manufacturers SET manufacturer_name = %s WHERE manufacturer_id = %s", (manufacturer.manufacturer_id,))

    def delete(self, manufacturer_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM manufacturers WHERE manufacturer_id = %s", (manufacturer_id,))

class ItemDAO(DAO):

    _table = "items"
    _pk = "item_id"
    _select = "SELECT item_id, stockcode, product_family, product_description FROM item"

    def _from_row(self, row) -> Item:
        return Item(row[0], row[1], row[2], row[3])

    def get_all_as_dict(self, limit: int = 15_000) -> dict[str, int]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (limit,))
            return dict(map(lambda x: (x[1], x[0]), cursor.fetchall()))

    def get_page_as_dict(self, page_size: int = 100, page_number: Optional[int] = None,) -> dict[str, int]:
        with self.db.cursor() as cursor:
            if page_number is None:
                cursor.execute(f"{self._select} ORDER BY {self._pk} LIMIT %s", (page_size,))
            else:
                cursor.execute(f"{self._select} ORDER BY {self._pk} OFFSET %s LIMIT %s",((page_size * page_number), page_size))
            return dict(map(lambda x: (x[1], x[0]), cursor.fetchall()))

    def get_by_id(self, item_id: int) -> Optional[Item]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE item_id = %s", (item_id,))
            row = cursor.fetchone()
        return Item(**row) if row else None

    def get_by_stockcode(self, stockcode: str) -> Optional[Item]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE stockcode = %s", (stockcode,))
            row = cursor.fetchone()
        return Item(**row) if row else None

    def get_by_family(self, product_family: str) -> list[Item]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE product_family = %s ORDER BY stockcode", (product_family,))
        return [Item(**row) for row in cursor.fetchall()]

    def create(self, item: Item) -> Item:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO item (stockcode, product_family, product_description) VALUES (%s, %s, %s) RETURNING item_id", (item.stockcode, item.product_family, item.product_description))
            item.item_id = cursor.fetchone()[0]
        return item

    def update(self, item: Item) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("UPDATE item SET stockcode = %s, product_family = %s, product_description = %s WHERE item_id = %s", (item.stockcode, item.product_family, item.product_description, item.item_id))

    def delete(self, item_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM item WHERE item_id = %s", (item_id,))

class SalesReportDAO(DAO):

    _table = "sales_report"
    _pk = "sales_report_id"
    _select = "SELECT report_id, manufacturer_id, report_year, report_month FROM sales_report"

    def _from_row(self, row) -> SalesReport:
        return SalesReport(**row)

    def get_by_id(self, report_id: int) -> Optional[SalesReport]:
        with self.db.cursor() as cursor:
            cursor.execute("SELECT FROM sales_report WHERE report_id = %s", (report_id,))
            row = cursor.fetchone()
        return SalesReport(**row) if row else None

    def check_exists(self, manufacturer_id: int, year: str, month: str) -> bool:
        with self.db.cursor() as cursor:
            cursor.execute("SELECT 1 FROM sales_report WHERE manufacturer_id = %s AND report_year = %s AND report_month = %s LIMIT 1", (manufacturer_id, year, month))
            result = cursor.fetchone()
        return True if result else False

    def get_by_manufacturer(self, manufacturer_id: int) -> list[SalesReport]:
        with self.db.cursor() as cursor:
            cursor.execute("SELECT FROM sales_report WHERE manufacturer_id = %s", (manufacturer_id,))
            return [SalesReport(**row) for row in cursor.fetchall()]

    def get_by_period(self, year: str, month: str) -> list[SalesReport]:
        with self.db.cursor() as cursor:
            cursor.execute("SELECT FROM sales_report WHERE year = %s AND month = %s", (year, month))
            return [SalesReport(**row) for row in cursor.fetchall()]

    def create(self, report: SalesReport) -> SalesReport:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO sales_report (manufacturer_id, report_year, report_month) VALUES (%s, %s, %s) RETURNING report_id", (report.manufacturer_id, report.report_year, report.report_month))
            report.report_id = cursor.fetchone()[0]
        return report

    def delete(self, report_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM sales_report WHERE report_id = %s", (report_id,))

class SaleCustomerDAO(DAO):

    _table = "sale_customer"
    _pk = "report_id"
    _select = "SELECT report_id, customer_id, location_id FROM sale_customer"

    def _from_row(self, row) -> SaleCustomer:
        return SaleCustomer(**row)

    def get(self, report_id: int, customer_id: int, location_id: int) -> Optional[SaleCustomer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE report_id = %s AND customer_id = %s AND location_id = %s", (report_id, customer_id, location_id))
            row = cursor.fetchone()
            return SaleCustomer(report_id= row[0], customer_id= row[1], location_id= row[2]) if row else None

    def get_by_report(self, report_id: int) -> list[SaleCustomer]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE report_id = %s", (report_id,))
        return [SaleCustomer(**row) for row in cursor.fetchall()]

    def create(self, link: SaleCustomer) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO sale_customer (report_id, customer_id, location_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (link.report_id, link.customer_id, link.location_id))

    def delete(self, report_id: int, customer_id: int, location_id: int) -> None:
        with self.db.cursor() as cursor:
            cursor.execute("DELETE FROM sale_customer WHERE report_id = %s AND customer_id = %s AND location_id = %s", (report_id, customer_id, location_id))

    def create_bulk(self, lines: list[SaleCustomer]) -> None:
        if not lines:
            return lines

        values = [(ln.report_id, ln.customer_id, ln.location_id) for ln in lines]

        with self.db.cursor() as cursor:
            psycopg2.extras.execute_values(cursor,"INSERT INTO sale_customer (report_id, customer_id, location_id) VALUES %s ON CONFLICT DO NOTHING", values, page_size=500)
            return None

class ReportLineDAO(DAO):

    _table = "report_line"
    _pk = "report_line_id"
    _select = "SELECT report_line_id, report_id, customer_alias, customer_id, item_id, quantity, amt, transfer, location_id, sale_date FROM report_line"

    def _from_row(self, row) -> ReportLine:
        return ReportLine(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9])

    def get_by_id(self, report_line_id: int) -> Optional[ReportLine]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE report_line_id = %s", (report_line_id,))
            row = cursor.fetchone()
            return ReportLine(**row) if row else None

    def get_by_report(self, report_id: int) -> list[tuple[Any, ]]:
        with self.db.cursor() as cursor:
             cursor.execute(f"{self._select} WHERE report_id = %s ORDER BY report_line_id", (report_id,))
             return cursor.fetchall()

    def stream_by_report(self, report_id: int, chunk_size: int = 500) -> Iterator[ReportLine]:
        # Named cursors must NOT go through the commit/rollback wrapper —
        # they need their own connection transaction scope.
        conn = self.db.conn
        with conn.cursor(name="report_line_stream", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = chunk_size
            cur.execute(f"{self._select} WHERE report_id = %s ORDER BY report_line_id", (report_id,))
            for row in cur:  # psycopg2 fetches `itersize` rows per round-trip
                yield ReportLine(**row)

    def get_by_customer(self, customer_id: int) -> list[ReportLine]:
        with self.db.cursor() as cursor:
            cursor.execute(f"{self._select} WHERE customer_id = %s ORDER BY report_line_id", (customer_id,))
            return [ReportLine(**row) for row in cursor.fetchall()]

    def get_by_date_range(self):
        print()

    def create(self, line: ReportLine) -> None:
        with self.db.cursor() as cursor:
            #"reportLineInsert": """insert into report_line(report_id, customer_id, item_id, location_id, amt, sale_date, quantity, transfer) values (%s, %s, %s, %s, %s, %s, %s, %s);"""
            cursor.execute("INSERT INTO report_line  (report_id, customer_id, item_id, quantity, amt, transfer, location_id, sale_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (line.report_id, line.customer_id, line.item_id, line.quantity, line.amt, line.transfer, line.location_id, line.sale_date,))

    def direct_insert(self, report_id, customer_id, item_id, location_id, amount, saledate, quantity, transfer):
        with self.db.cursor() as cursor:
            cursor.execute("insert into report_line(report_id, customer_id, item_id, location_id, amt, sale_date, quantity, transfer) values (%s, %s, %s, %s, %s, %s, %s, %s);",
                           (report_id, customer_id, item_id, location_id, amount, saledate, quantity, transfer))

    def create_bulk(self, lines: list[ReportLine]) -> None:
        if not lines:
            return lines

        values = [(ln.report_id, ln.customer_alias, ln.customer_id, ln.item_id, ln.quantity, ln.amt, ln.transfer, ln.location_id, ln.sale_date,) for ln in lines]

        with self.db.cursor() as cursor:
            psycopg2.extras.execute_values(cursor,"INSERT INTO report_line (report_id, customer_alias, customer_id, item_id, quantity, amt, transfer, location_id, sale_date) VALUES %s", values, page_size=500)
            return None

class DAOFactory:

    def __init__(self, db: DBConnector):
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

    def close(self):
        self.db.close()