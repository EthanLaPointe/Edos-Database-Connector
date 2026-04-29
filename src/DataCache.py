from DBConnection import *

class DataCache:
    def __init__(self, factory: DAOFactory):
        self._factory = factory
        self.locations: dict = {}
        self.customer_aliases: dict = {}
        self.items: dict = {}
        self.manufacturers: dict = {}
        self.refresh()
        
    def refresh(self):
        self.locations = self._factory.locations.get_all_as_dict()
        self.customer_aliases = (self._factory.customer_aliases.get_all_as_dict() | self._dao.customers.get_all_as_dict())
        self.items = self._factory.items.get_all_as_dict()
        self.manufacturers = self._factory.manufacturers.get_all_as_dict()