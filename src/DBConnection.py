import psycopg2
import json
import os

class DBConnector:

    conn = None

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

    def set_credentials(self, database_name, username, password, host, port):
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

    def check_credentials(self):
        return os.path.isfile('credentials.json')

    def get_credentials(self):
        with open('credentials.json', 'r') as f:
            credentials = json.load(f)
        return credentials
