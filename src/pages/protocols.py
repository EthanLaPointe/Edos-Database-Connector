"""Protocol definitions for type annotations."""
from typing import Protocol


class AppController(Protocol):
    """Protocol describing the interface page classes and sidebar require from App."""

    current_user: str | None
    cache_updated: object # PySide6 Signal

    def show_home(self) -> None: ...  # noqa: D102
    def show_report(self) -> None: ...  # noqa: D102
    def show_alias(self) -> None: ...  # noqa: D102
    def show_rep(self) -> None: ... # noqa: D102
    def logout(self) -> None: ...  # noqa: D102
