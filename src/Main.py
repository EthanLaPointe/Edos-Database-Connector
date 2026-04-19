from app import App
from DBConnection import DBConnector
 
if __name__ == "__main__":
    connector = DBConnector()
    app = App(connector)
    app.mainloop()