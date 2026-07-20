"""To be finished later."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import psycopg2.extras

from src.db_connection import DBConnector

# Column names must match database column names
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
    "team_name",
    "representative_name",
]

_REPORT_QUERY = """
            select
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
                rl.transfer,
                rt.team_name,
                rep.representative_name
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
            left join rep_team_customer_locations rtcl
                on rtcl.customer_id = rl.customer_id
                and rtcl.location_id = rl.location_id
            left join representative_teams rt
                on rt.team_id = rtcl.team_id
            left join team_members tm
                on tm.team_id = rtcl.team_id
                and tm.rep_classification = m.manufacturer_classification
            left join representatives rep
                on rep.representative_id = tm.representative_id
            where rl.report_id = %s
            order by
                c.customer_name,
                l.city,
                i.stockcode;
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
            cursor.execute(_REPORT_QUERY, (report_id,))
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
            cur.execute(_REPORT_QUERY, (report_id,))
            buffer: list[dict] = []
            for row in cur:
                buffer.append(dict(row))
                if len(buffer) >= chunk_size:
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
