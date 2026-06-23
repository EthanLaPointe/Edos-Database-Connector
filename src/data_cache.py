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
        self._factory: DAOFactory = factory
        self.locations: dict = {}
        self.customer_locations: set = {}
        self.customer_aliases: dict = {}
        self.customers: dict = {}
        self.items: dict = {}
        self.manufacturers: dict = {}
        self.representatives: dict = {}
        self.refresh_all()

    def refresh_all(self) -> None:
        """Refresh all dicts of DB data."""
        self.locations = self._factory.locations.get_all_as_dict()
        self.customer_aliases = (
            self._factory.customer_aliases.get_all_as_dict()
            | self._factory.customers.get_all_as_dict()
        )
        self.customers = self._factory.customers.get_all_as_dict()
        self.items = self._factory.items.get_all_as_dict()
        self.manufacturers = self._factory.manufacturers.get_all_as_dict()
        self.customer_locations = self._factory.customer_locations.get_all_as_dict()
        self.representatives = self._factory.representatives.get_all_as_dict()

    def refresh_locations(self) -> None:
        """Refresh location dict."""
        self.locations = self._factory.locations.get_all_as_dict()

    def refresh_customer_aliases(self) -> None:
        """Refresh both customer and alias dicts."""
        self.customers = self._factory.customers.get_all_as_dict()
        self.customer_aliases = (
            self._factory.customer_aliases.get_all_as_dict()
            | self.customers
        )

    def refresh_customers(self) -> None:
        """Refresh customer dict."""
        self.customers = self._factory.customers.get_all_as_dict()

    def refresh_items(self) -> None:
        """Refresh item dict."""
        self.items = self._factory.items.get_all_as_dict()

    def refresh_manufacturers(self) -> None:
        """Refresh manufacturer dict."""
        self.manufacturers = self._factory.manufacturers.get_all_as_dict()

    def refresh_customer_locations(self) -> None:
        """Refresh customer location set."""
        self.customer_locations = self._factory.customer_locations.get_all_as_set()

    def refresh_representatives(self) -> None:
        """Refresh representative dict."""
        self.representatives = self._factory.representatives.get_all_as_dict()
