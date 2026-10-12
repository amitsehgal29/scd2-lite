import unittest

from scd2_lite import OPEN_END, apply_snapshot

DIM = [
    {"id": "1", "city": "X", "valid_from": "2026-01-01", "valid_to": "2026-05-01", "is_current": "false"},
    {"id": "1", "city": "Y", "valid_from": "2026-05-01", "valid_to": OPEN_END, "is_current": "true"},
    {"id": "2", "city": "P", "valid_from": "2026-02-01", "valid_to": OPEN_END, "is_current": "true"},
    {"id": "3", "city": "Q", "valid_from": "2026-03-01", "valid_to": OPEN_END, "is_current": "true"},
]
SNAP = [{"id": "1", "city": "Y"}, {"id": "2", "city": "R"}, {"id": "4", "city": "S"}]
AS_OF = "2026-10-12"


def by(rows, k):
    return [r for r in rows if r["id"] == k]


class Scd2Tests(unittest.TestCase):
    def setUp(self):
        self.rows, self.stats = apply_snapshot(DIM, SNAP, "id", ["city"], AS_OF)

    def test_stats(self):
        self.assertEqual(self.stats, {"unchanged": 1, "changed": 1, "inserted": 1, "deleted": 1})

    def test_unchanged_row_and_history_untouched(self):
        rows = by(self.rows, "1")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["is_current"], "false")
        self.assertEqual(rows[1], DIM[1])

    def test_changed_key_is_closed_and_reopened(self):
        old, new = by(self.rows, "2")
        self.assertEqual((old["city"], old["valid_to"], old["is_current"]), ("P", AS_OF, "false"))
        self.assertEqual((new["city"], new["valid_from"], new["valid_to"], new["is_current"]),
                         ("R", AS_OF, OPEN_END, "true"))

    def test_deleted_key_is_closed(self):
        (row,) = by(self.rows, "3")
        self.assertEqual((row["valid_to"], row["is_current"]), (AS_OF, "false"))

    def test_new_key_is_inserted(self):
        (row,) = by(self.rows, "4")
        self.assertEqual((row["city"], row["valid_from"], row["is_current"]), ("S", AS_OF, "true"))

    def test_keep_deleted_leaves_key_open(self):
        rows, stats = apply_snapshot(DIM, SNAP, "id", ["city"], AS_OF, keep_deleted=True)
        (row,) = by(rows, "3")
        self.assertEqual(row["is_current"], "true")
        self.assertEqual(stats["deleted"], 0)

    def test_exactly_one_current_row_per_key(self):
        for k in ("1", "2", "4"):
            self.assertEqual(sum(r["is_current"] == "true" for r in by(self.rows, k)), 1)

    def test_empty_dimension_inserts_everything(self):
        rows, stats = apply_snapshot([], SNAP, "id", ["city"], AS_OF)
        self.assertEqual(stats["inserted"], 3)
        self.assertEqual(len(rows), 3)

    def test_rerun_is_idempotent(self):
        again, stats = apply_snapshot(self.rows, SNAP, "id", ["city"], AS_OF, keep_deleted=False)
        self.assertEqual(stats, {"unchanged": 3, "changed": 0, "inserted": 0, "deleted": 0})
        self.assertEqual(again, self.rows)

    def test_duplicate_snapshot_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            apply_snapshot(DIM, SNAP + [{"id": "4", "city": "T"}], "id", ["city"], AS_OF)

    def test_two_current_rows_rejected(self):
        bad = DIM + [{"id": "2", "city": "Z", "valid_from": "x", "valid_to": OPEN_END, "is_current": "true"}]
        with self.assertRaisesRegex(ValueError, "two current rows"):
            apply_snapshot(bad, SNAP, "id", ["city"], AS_OF)


if __name__ == "__main__":
    unittest.main()
