import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from file_handler import FileHandler, REPORT_FIELD_LIST


class TestFileHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = FileHandler.__new__(FileHandler)
        self.handler.dao = None
        self.handler.cache = None

    def test_fill_empty_inserts_missing_saledate_in_correct_position(self) -> None:
        """Test that missing saledate column is inserted in the correct position."""
        dataframe = pd.DataFrame(
            {
                "CustomerName": ["Cust A"],
                "City": ["Testville"],
                "State": ["TS"],
                "Stockcode": ["SC123"],
                "ProductFam": ["Family"],
                "ProductDesc": ["Desc"],
                "QuantityOrd": [5],
                "Amount": [100.0],
                "TransferOrNot": ["N"],
            }
        )

        result = self.handler.fill_empty(dataframe)

        self.assertEqual(list(result.columns), REPORT_FIELD_LIST)
        self.assertEqual(result.columns.get_loc("saledate"), REPORT_FIELD_LIST.index("saledate"))
        self.assertEqual(result.columns.get_loc("amount"), REPORT_FIELD_LIST.index("amount"))
        self.assertTrue(result["saledate"].isnull().all())

    def test_quantity_handles_special_characters(self) -> None:
        """Test that quantity column handles special characters like '**' gracefully."""
        dataframe = pd.DataFrame(
            {
                "CustomerName": ["Cust A", "Cust B"],
                "City": ["City1", "City2"],
                "State": ["ST1", "ST2"],
                "Stockcode": ["SC1", "SC2"],
                "ProductFam": ["Fam1", "Fam2"],
                "ProductDesc": ["Desc1", "Desc2"],
                "QuantityOrd": ["**", "5"],
                "Amount": [100.0, 200.0],
                "TransferOrNot": ["N", "Y"],
            }
        )

        result = self.handler.fill_empty(dataframe)

        # '**' should be converted to 0, '5' should remain 5
        self.assertEqual(result.iloc[0]["quantity"], 0)
        self.assertEqual(result.iloc[1]["quantity"], 5)


if __name__ == "__main__":
    unittest.main()

