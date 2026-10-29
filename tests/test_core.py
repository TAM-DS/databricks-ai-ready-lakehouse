import csv
import tempfile
import unittest
from pathlib import Path
from quality_portal.core import read_snapshot, SnapshotError, GOLD_COLUMNS, REASONS_COLUMNS


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.gold = ["Gulf Coast", "Transformer", "80", "800", "400000.00", "20", "25.00", "2026-10-01", "2026-10-28"]
        write_csv(self.folder/"gold.csv", GOLD_COLUMNS, [self.gold])
        write_csv(self.folder/"quarantine_reasons.csv", REASONS_COLUMNS, [["duplicate_shipment", "5"], ["invalid_quantity", "5"]])

    def test_derives_metrics_from_export(self):
        s = read_snapshot(self.folder)
        self.assertEqual(s.totals["accepted_rows"], 80)
        self.assertEqual(s.totals["quarantined_rows"], 10)
        self.assertEqual(s.totals["source_rows"], 90)
        self.assertEqual(s.totals["gold_segments"], 1)
        self.assertEqual(s.totals["declared_rule_pass_pct"], 88.89)
        self.assertEqual(s.totals["modeled_inventory_value_usd"], 400000)

    def test_absent_export_fails_closed(self):
        (self.folder/"gold.csv").unlink()
        with self.assertRaises(SnapshotError):
            read_snapshot(self.folder)

    def test_rejects_inconsistent_percent(self):
        self.gold[6] = "10.00"
        write_csv(self.folder/"gold.csv", GOLD_COLUMNS, [self.gold])
        with self.assertRaises(SnapshotError):
            read_snapshot(self.folder)

    def test_rejects_duplicate_gold_groups(self):
        write_csv(self.folder/"gold.csv", GOLD_COLUMNS, [self.gold, self.gold])
        with self.assertRaises(SnapshotError):
            read_snapshot(self.folder)

    def test_rejects_negative_quarantine_count(self):
        write_csv(self.folder/"quarantine_reasons.csv", REASONS_COLUMNS, [["duplicate_shipment", "-5"]])
        with self.assertRaises(SnapshotError):
            read_snapshot(self.folder)

    def test_rejects_wrong_headers(self):
        write_csv(self.folder/"gold.csv", ["region", "total"], [["Gulf Coast", "1"]])
        with self.assertRaises(SnapshotError):
            read_snapshot(self.folder)


if __name__ == "__main__":
    unittest.main()
