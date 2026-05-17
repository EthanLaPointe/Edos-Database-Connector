"""To be finished later."""
from src.db_connection import DAOFactory


class DataCache:
    """Cache class for storing commonly accessed DB data."""

    def __init__(self, factory: DAOFactory) -> None:
        """Initialize attributes to default values and call refresh.

        Args:
            factory (DAOFactory):
                DAOFactory to be used for retrieval of DB data.

        """
        self._factory = factory
        self.locations: dict = {}
        self.customer_aliases: dict = {}
        self.items: dict = {}
        self.manufacturers: dict = {}
        self.refresh()

    def refresh(self) -> None:
        """Refresh all dicts of DB data."""
        self.locations = self._factory.locations.get_all_as_dict()
        self.customer_aliases = (
            self._factory.customer_aliases.get_all_as_dict()
            | self._factory.customers.get_all_as_dict()
        )
        self.customers = self._factory.customers.get_all_as_dict()
        self.items = self._factory.items.get_all_as_dict()
        self.manufacturers = self._factory.manufacturers.get_all_as_dict()
