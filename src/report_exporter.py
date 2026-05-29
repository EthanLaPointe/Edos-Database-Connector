"""To be finished later."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import psycopg2.extras

from src.db_connection import DBConnector

EXPORT_COLUMNS = [
    "manufacturer_name",
    "report_year",
    "report_month",
    "customer_alias",
    "customer_name",
    "city",
    "state",
    "stockcode",
    "product_family",
    "product_description",
    "amt",
    "quantity",
    "transfer",
]

_REPORT_QUERY = """
    SELECT
        m.manufacturer_name,
        sr.report_year,
        sr.report_month,
        rl.customer_alias,
        c.customer_name,
        l.city,
        l.state,
        i.stockcode,
        i.product_family,
        i.product_description,
        rl.amt,
        rl.quantity,
        rl.transfer
    FROM report_line rl
    JOIN sales_report sr  ON rl.report_id      = sr.report_id
    JOIN manufacturers m  ON sr.manufacturer_id = m.manufacturer_id
    JOIN customers c      ON rl.customer_id     = c.customer_id
    JOIN locations l      ON rl.location_id     = l.location_id
    JOIN item i           ON rl.item_id         = i.item_id
    WHERE rl.report_id = %s
    ORDER BY c.customer_name, l.city, i.stockcode
"""


class ReportExporter:
    """Fetches full report data from the database and optionally writes it to a CSV.

    Uses the DBConnector's existing cursor context-manager so commits/rollbacks
    are handled consistently with the rest of the codebase.

    Args:
        connector (DBConnector):
            An open DBConnector instance. The caller is responsible for
            opening and closing the connection.

    """

    def __init__(self, connector: DBConnector) -> None:
        """Store the active connector."""
        self.connector = connector

    def fetch_dataframe(self, report_id: int) -> pd.DataFrame:
        """Return the full report as a DataFrame.

        Args:
            report_id (int):
                ID of the sales_report to retrieve.

        Returns:
            pd.DataFrame:
                Columns match EXPORT_COLUMNS.
                Empty DataFrame when no rows are found.

        """
        with self.connector.cursor() as cursor:
            cursor.execute(_REPORT_QUERY, (report_id))
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame(columns=EXPORT_COLUMNS)

        return pd.DataFrame(rows, columns=EXPORT_COLUMNS)

    def stream_dataframe(
        self,
        report_id: int,
        chunk_size: int = 500,
    ) -> Iterator[pd.DataFrame]:
        """Yield the report in chunks to avoid loading large reports into memory.

        Uses a named server-side cursor so only ''chunk_size'' rows are
        transferred per round-trip. Must NOT go through the commit/rollback wrapper.

        Args:
            report_id (int):
                ID of the sales_report row to retrieve.
            chunk_size (int):
                Rows per chunk. Defaults to 500.

        Yields:
            pd.DataFrame:
                Each chunk as a DataFrame with EXPORT_COLUMNS columns.

        """
        conn = self.connector.conn
        with conn.cursor(
            name="report_export_stream",
            cursor_factory=psycopg2.extras.RealDictCursor,
        ) as cur:
            cur.itersize = chunk_size
            cur.execute(_REPORT_QUERY, (report_id))
            buffer: list[dict] = []
            for row in cur:
                buffer.append(dict(row))
                if len(buffer >= chunk_size):
                    yield pd.DataFrame(buffer, columns=EXPORT_COLUMNS)
                    buffer.clear()
            if buffer:
                yield pd.DataFrame(buffer, columns=EXPORT_COLUMNS)

    def export_to_csv(self, report_id: int, path: str) -> int:
        """Fetch a report and write it to a CSV file.

        Uses stream_dataframe internally so large reports do not
        fill memory - first chunk writes the header, subsequent chunks
        are appended.

        Args:
            report_id (int):
                ID of the report to export.
            path (str):
                Destination file path (will be created or overwritten).

        Returns:
            int:
                Number of data rows written (excludes the header row).

        """
        out_path = Path(path)
        total_rows = 0
        first_chunk = True

        for chunk in self.stream_dataframe(report_id):
            chunk.to_csv(
                out_path,
                index=False,
                encoding="utf-8",
                mode="w" if first_chunk else "a",
                header=first_chunk,
            )
            total_rows += len(chunk)
            first_chunk = False

        # If no rows were found create and empty file with headers
        if first_chunk:
            pd.DataFrame(columns=EXPORT_COLUMNS).to_csv(
                out_path, index=False, encoding="utf-8",
            )

        return total_rows
