import psycopg2

from ReportStandardizer import ReportStandardizer
from DBConnection import DBConnector
import pandas as pd
import glob

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

connector = DBConnector()
connectionStatus = 0
queryDict = {"manufacturerInsert": """insert into manufacturers(manufacturer_name) values (%s) returning manufacturer_id;""",
             "salesReportInsert": """insert into sales_report(manufacturer_id, report_year, report_month) values (%s, %s, %s) returning report_id;""",
             "customerInsert": """insert into customers(customer_name) values (%s) returning customer_id;""",
             "locationInsert": """insert into locations(city, state) values (%s, %s) returning location_id;""",
             "customerLocationInsert": """insert into customer_locations(customer_id, location_id) values (%s, %s);""",
             "saleCustomerInsert": """insert into sale_customer(report_id, customer_id, location_id) values (%s, %s, %s);""",
             "itemInsert": """insert into item(item_name, item_family, item_description) values (%s, %s, %s) returning item_id;""",
             "reportLineInsert": """insert into report_line(report_id, customer_id, item_id, location_id, amt, sale_date, quantity, transfer) values (%s, %s, %s, %s, %s, %s, %s, %s);""",
             "checkCustomer": """select c.customer_name from customers c where c.customer_name = %s;""",
             "checkLocation" : """select l.city, l.state from locations l where l.city = %s and l.state = %s;""",
             "checkCustomerLocation": """select cl.customer_id, cl.location_id from customer_locations cl where cl.customer_id = %s and cl.location_id = %s;""",
             "checkSaleCustomer": """select sc.customer_id, sc.report_id, sc.location_id from sale_customer sc where sc.customer_id = %s and sc.report_id = %s and sc.location_id = %s;""",
             "checkItem": """select i.item_name from item i where i.item_name = %s;"""}

def get_user_credentials():
    credentials = []
    print("Please enter database name")
    credentials.append(input())
    print("Please enter username")
    credentials.append(input())
    print("Please enter password")
    credentials.append(input())
    print("Please enter host")
    credentials.append(input())
    print("Please enter port")
    credentials.append(input())

    connector.set_credentials(credentials[0], credentials[1], credentials[2], credentials[3], credentials[4])

print("Connecting to database...")

if not connector.check_credentials():
        get_user_credentials()

while connectionStatus == 0:
    try:
        connector.direct_connect()
        conn = connector.conn
        connectionStatus = conn.status
    except psycopg2.Error as e:
        print("Connection to database failed. Please reenter credentials")
        #get_user_credentials()

print("Connection to database successful")

def get_manufacturer_id(manufacturer_name):
    cursor = conn.cursor()
    id_query = """select m.manufacturer_id
                 from manufacturers m 
                 where m.manufacturer_name = %s;"""
    cursor.execute(id_query, (manufacturer_name,))
    if cursor.rowcount != 0:
        return cursor.fetchone()[0]
    return None

def get_location_id(city, state):
    cursor = conn.cursor()
    id_query = """select l.location_id
                 from locations l
                 where l.city = %s and l.state = %s;"""
    cursor.execute(id_query, (city, state,))
    if cursor.rowcount != 0:
        return cursor.fetchone()[0]
    return None

def get_customer_id(customer_name):
    cursor = conn.cursor()
    id_query = """select c.customer_id
                 from customers c
                 where c.customer_name = %s;"""
    cursor.execute(id_query, (customer_name,))
    if cursor.rowcount != 0:
        return cursor.fetchone()[0]
    return None

def get_report_id(manufacturer_id, report_year, report_month):
    cursor = conn.cursor()
    id_query = """select r.report_id
                 from sales_report r
                 where r.manufacturer_id = %s and r.report_year = %s and r.report_month = %s;"""
    cursor.execute(id_query, (manufacturer_id, report_year, report_month,))
    if cursor.rowcount != 0:
        return cursor.fetchone()[0]
    return None

def get_item_id(item_name):
    cursor = conn.cursor()
    id_query = """select i.item_id
                 from item i
                 where i.item_name = %s;"""
    cursor.execute(id_query, (item_name,))
    if cursor.rowcount != 0:
        return cursor.fetchone()[0]
    return None

def insert_report(report_path):
    cursor = conn.cursor()

    standardizer = ReportStandardizer()
    df = standardizer.standardize(report_path)

    manufacturer_name = standardizer.get_manufacturer_name()
    line_data = {"customer": '', "city": '', "state": '', "stockcode": '', "itemfamily": '', "itemdesc": '', "quantity": 0,"saledate": None, "amount": 0.0, "transfer": ''}
    report_month = standardizer.get_report_month()
    report_year = standardizer.get_report_year()
    inserted_customers = {}
    inserted_items = {}
    inserted_locations = {}

    #insert manufacturer name and check if present already
    manufacturer_id = get_manufacturer_id(manufacturer_name)
    if not manufacturer_id:
        cursor.execute(queryDict["manufacturerInsert"], (manufacturer_name,))
        manufacturer_id = cursor.fetchone()[0]

    try:
        cursor.execute(queryDict["salesReportInsert"], (manufacturer_id, report_year, report_month))
        report_id = cursor.fetchone()[0]
    except psycopg2.Error as insert_exception:
        print("Failed to insert sales report. Error: ", insert_exception)
        conn.rollback()
        return

    for row in range(len(df.index)):
        #print("row:", row)
        line_data["customer"] = df.iloc[row, 0]
        if line_data["customer"]:
            line_data["customer"] = line_data["customer"].lower()
        line_data["city"] = df.iloc[row, 1]
        if line_data["city"]:
            line_data["city"] = line_data["city"].lower()
        line_data["state"] = df.iloc[row, 2]
        if line_data["state"]:
            line_data["state"] = line_data["state"].lower()
        line_data["stockcode"] = df.iloc[row, 3]
        line_data["itemfamily"] = df.iloc[row, 4]
        line_data["itemdesc"] = df.iloc[row, 5]
        line_data["quantity"] = df.iloc[row, 6]
        line_data["saledate"] = df.iloc[row, 7]
        line_data["amount"] = df.iloc[row, 8]
        line_data["transfer"] = df.iloc[row, 9]

        #insert customer
        if line_data["customer"] not in inserted_customers:
            customer_id = get_customer_id(line_data["customer"])
            if not customer_id:
                cursor.execute(queryDict["customerInsert"], (line_data["customer"],))
                customer_id = cursor.fetchone()[0]
                inserted_customers[line_data["customer"]] = customer_id
        else:
            customer_id = inserted_customers[line_data["customer"]]
        #insert location
        if (line_data["city"], line_data["state"]) not in inserted_locations:
            location_id = get_location_id(line_data["city"], line_data["state"])
            if not location_id:
                cursor.execute(queryDict["locationInsert"], (line_data["city"], line_data["state"]))
                location_id = cursor.fetchone()[0]
                inserted_locations[(line_data["city"], line_data["state"])] = location_id
        else:
            location_id = inserted_locations[(line_data["city"], line_data["state"])]
        #insert customer location
        cursor.execute(queryDict["checkCustomerLocation"], (customer_id, location_id))
        rows = cursor.fetchall()
        if not rows:
            cursor.execute(queryDict["customerLocationInsert"], (customer_id, location_id))
        #insert sale customer
        cursor.execute(queryDict["checkSaleCustomer"], (customer_id, report_id, location_id))
        rows = cursor.fetchall()
        if not rows:
            cursor.execute(queryDict["saleCustomerInsert"], (report_id, customer_id, location_id))
        #insert item
        if line_data["stockcode"] not in inserted_items:
            item_id = get_item_id(line_data["stockcode"])
            if not item_id:
                cursor.execute(queryDict["itemInsert"], (line_data["stockcode"], line_data["itemfamily"], line_data["itemdesc"]))
                item_id = cursor.fetchone()[0]
                inserted_items[line_data["stockcode"]] = item_id
        else:
            item_id = inserted_items[line_data["stockcode"]]
        #insert report_line
        cursor.execute(queryDict["reportLineInsert"], (report_id, customer_id, item_id, location_id, float(line_data["amount"]), line_data["saledate"], int(line_data["quantity"]), line_data["transfer"]))

    conn.commit()

choice = 0

while choice != 3:
    print("1. Enter single report"
          "\n2. Enter multiple reports from folder"
          "\n3. Exit program")
    choice = int(input())

    if choice == 1:
        print("Enter file path of report:")
        reportPath = (input().replace('\\', '/'))
        if reportPath[0] == '"':
            reportPath = reportPath[1:-1]
        print("Inserting: " + reportPath + "...")
        insert_report(reportPath)

    if choice == 2:
        print("Enter path to the folder:")
        folderPath = (input().replace('\\', '/'))
        if folderPath[0] == '"':
            folderPath = folderPath[1:-1]
        folderPath = folderPath + "/*.csv"
        csvList = []
        for file in glob.iglob(folderPath):
                csvList.append(file)

        for csv in csvList:
            print("Inserting: " + csv + "...")
            insert_report(csv.replace('\\', '/'))

    if choice == 3:
        print("Exiting program...")

def select_report_by_id(_id):
    report_id = _id
    cursor = conn.cursor()
    query = """select
                    m.manufacturer_name,
                    sr.report_year,
                    sr.report_month,
                    c.customer_name,
                    l.city,
                    l.state,
                    i.item_name,
                    rl.amt,
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
                
                order by
                    c.customer_name,
                    l.city,
                    i.item_name;"""

    cursor.execute(query, (report_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        print(row)

#select_report_by_id(1)

#print(select_report_by_id(1))

