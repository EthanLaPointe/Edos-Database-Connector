import psycopg2
import json
import os
from ReportStandardizer import ReportStandardizer

class DBConnector:

    def __init__(self):
        self.conn = None
        self.queryDict = {"manufacturerInsert": """insert into manufacturers(manufacturer_name) values (%s) returning manufacturer_id;""",
                 "salesReportInsert": """insert into sales_report(manufacturer_id, report_year, report_month) values (%s, %s, %s) returning report_id;""",
                 "customerInsert": """insert into customers(customer_name) values (%s) returning customer_id;""",
                 "locationInsert": """insert into locations(city, state) values (%s, %s) returning location_id;""",
                 "customerLocationInsert": """insert into customer_locations(customer_id, location_id) values (%s, %s);""",
                 "saleCustomerInsert": """insert into sale_customer(report_id, customer_id, location_id) values (%s, %s, %s);""",
                 "itemInsert": """insert into item(stockcode, product_family, product_description) values (%s, %s, %s) returning item_id;""",
                 "reportLineInsert": """insert into report_line(report_id, customer_id, item_id, location_id, amt, sale_date, quantity, transfer) values (%s, %s, %s, %s, %s, %s, %s, %s);""",
                 "checkCustomer": """select c.customer_name from customers c where c.customer_name = %s;""",
                 "checkLocation" : """select l.city, l.state from locations l where l.city = %s and l.state = %s;""",
                 "checkCustomerLocation": """select cl.customer_id, cl.location_id from customer_locations cl where cl.customer_id = %s and cl.location_id = %s;""",
                 "checkSaleCustomer": """select sc.customer_id, sc.report_id, sc.location_id from sale_customer sc where sc.customer_id = %s and sc.report_id = %s and sc.location_id = %s;""",
                 "checkItem": """select i.stockcode from item i where i.stockcode = %s;"""}

    def connect(self):
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
    def set_credentials(database_name, username, password, host, port):
        data = {
            "database": database_name,
            "user": username,
            "host": host,
            "password": password,
            "port": port
        }

        file_path = 'credentials.json'
        with open(file_path, 'w') as f:
            json.dump(data, f)

    @staticmethod
    def check_credentials():
        return os.path.isfile('credentials.json')

    @staticmethod
    def get_credentials():
        with open('credentials.json', 'r') as f:
            credentials = json.load(f)
        return credentials

    def get_customer_list(self):
        cursor = self.conn.cursor()
        query = """select customer_name, customer_id from customers;"""
        cursor.execute(query)
        if cursor.rowcount != 0:
            return cursor.fetchall()
        return None

    def get_manufacturer_id(self, manufacturer_name):
        cursor = self.conn.cursor()
        id_query = """select m.manufacturer_id
                     from manufacturers m 
                     where m.manufacturer_name = %s;"""
        cursor.execute(id_query, (manufacturer_name,))
        if cursor.rowcount != 0:
            return cursor.fetchone()[0]
        return None

    def get_location_id(self, city, state):
        cursor = self.conn.cursor()
        id_query = """select l.location_id
                     from locations l
                     where l.city = %s and l.state = %s;"""
        cursor.execute(id_query, (city, state,))
        if cursor.rowcount != 0:
            return cursor.fetchone()[0]
        return None

    def get_customer_id(self, customer_name):
        cursor = self.conn.cursor()
        id_query = """select c.customer_id
                     from customers c
                     where c.customer_name = %s;"""
        cursor.execute(id_query, (customer_name,))
        if cursor.rowcount != 0:
            return cursor.fetchone()[0]
        return None

    def get_report_id(self, manufacturer_id, report_year, report_month):
        cursor = self.conn.cursor()
        id_query = """select r.report_id
                     from sales_report r
                     where r.manufacturer_id = %s and r.report_year = %s and r.report_month = %s;"""
        cursor.execute(id_query, (manufacturer_id, report_year, report_month,))
        if cursor.rowcount != 0:
            return cursor.fetchone()[0]
        return None

    def get_item_id(self, item_name):
        cursor = self.conn.cursor()
        id_query = """select i.item_id
                     from item i
                     where i.stockcode = %s;"""
        cursor.execute(id_query, (item_name,))
        if cursor.rowcount != 0:
            return cursor.fetchone()[0]
        return None

    def insert_report(self, report):
        cursor = self.conn.cursor()

        #dict to store row information
        #column index for row matches line_data, i.e. line_data["customer"] = row[0]
        line_data = {"customername": '', "city": '', "state": '', "stockcode": '', "productfamily": '', "productdesc": '',"quantity": 0, "saledate": None, "amount": 0.0, "transfer": ''}

        inserted_customers = {}
        inserted_items = {}
        inserted_locations = {}

        #insert manufacturer name and check if present already
        manufacturer_id = self.get_manufacturer_id(report.manufacturerName)
        if not manufacturer_id:
            cursor.execute(self.queryDict["manufacturerInsert"], (report.manufacturerName,))
            manufacturer_id = cursor.fetchone()[0]

        try:
            cursor.execute(self.queryDict["salesReportInsert"], (manufacturer_id, report.year, report.month))
            report_id = cursor.fetchone()[0]
        except psycopg2.Error as insert_exception:
            print("Failed to insert sales report. Error: ", insert_exception)
            self.conn.rollback()
            return

        for row in report.dataframe.itertuples(index=False):
            #fill line_data dict with information from current row
            line_data["customername"] = row[0]
            if line_data["customername"]:
                line_data["customername"] = line_data["customername"].lower()
            line_data["city"] = row[1]
            if line_data["city"]:
                line_data["city"] = line_data["city"].lower()
            line_data["state"] = row[2]
            if line_data["state"]:
                line_data["state"] = line_data["state"].lower()
            line_data["stockcode"] = row[3]
            line_data["productfamily"] = row[4]
            line_data["productdesc"] = row[5]
            line_data["quantity"] = row[6]
            line_data["saledate"] = row[7]
            line_data["amount"] = row[8]
            if line_data["amount"] >= 0 and line_data["quantity"] == 0:
                line_data["quantity"] = None
            line_data["transfer"] = row[9]

            #insert customer
            if line_data["customername"] not in inserted_customers:
                customer_id = self.get_customer_id(line_data["customername"])
                if not customer_id:
                    cursor.execute(self.queryDict["customerInsert"], (line_data["customername"],))
                    customer_id = cursor.fetchone()[0]
                    inserted_customers[line_data["customername"]] = customer_id
            else:
                customer_id = inserted_customers[line_data["customername"]]
            #insert location
            if (line_data["city"], line_data["state"]) not in inserted_locations:
                location_id = self.get_location_id(line_data["city"], line_data["state"])
                if not location_id:
                    cursor.execute(self.queryDict["locationInsert"], (line_data["city"], line_data["state"]))
                    location_id = cursor.fetchone()[0]
                    inserted_locations[(line_data["city"], line_data["state"])] = location_id
            else:
                location_id = inserted_locations[(line_data["city"], line_data["state"])]
            #insert customer location
            cursor.execute(self.queryDict["checkCustomerLocation"], (customer_id, location_id))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(self.queryDict["customerLocationInsert"], (customer_id, location_id))
            #insert sale customer
            cursor.execute(self.queryDict["checkSaleCustomer"], (customer_id, report_id, location_id))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute(self.queryDict["saleCustomerInsert"], (report_id, customer_id, location_id))
            #insert item
            if line_data["stockcode"] not in inserted_items:
                item_id = self.get_item_id(line_data["stockcode"])
                if not item_id:
                    cursor.execute(self.queryDict["itemInsert"], (line_data["stockcode"], line_data["productfamily"], line_data["productdesc"]))
                    item_id = cursor.fetchone()[0]
                    inserted_items[line_data["stockcode"]] = item_id
            else:
                item_id = inserted_items[line_data["stockcode"]]
            #insert report_line
            cursor.execute(self.queryDict["reportLineInsert"], (report_id, customer_id, item_id, location_id, float(line_data["amount"]), line_data["saledate"], line_data["quantity"], line_data["transfer"]))

        self.conn.commit()


    def select_report_by_id(self, _id):
        report_id = _id
        cursor = self.conn.cursor()
        query = """select m.manufacturer_name, \
                          sr.report_year, \
                          sr.report_month, \
                          c.customer_name, \
                          l.city, \
                          l.state, \
                          i.stockcode, \
                          rl.amt, \
                          rl.quantity, \
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
    
                   order by c.customer_name, \
                            l.city, \
                            i.item_name;"""

        cursor.execute(query, (report_id,))
        rows = cursor.fetchall()

        for row in rows:
            print(row)