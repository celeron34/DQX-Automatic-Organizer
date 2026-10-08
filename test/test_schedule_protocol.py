import unittest
from datetime import datetime

from dqx_ise import DefenseScheduleEntry
from schedule_protocol import deserialize_entries, serialize_entries


class ScheduleProtocolTests(unittest.TestCase):
    def test_serializes_and_parses_schedule_entries(self):
        entries = [
            DefenseScheduleEntry(datetime(2026, 10, 9, 8), 12, False),
            DefenseScheduleEntry(datetime(2026, 10, 9, 9), 99, True),
        ]
        self.assertEqual(deserialize_entries(serialize_entries(entries)), entries)

    def test_rejects_invalid_schedule_fields(self):
        with self.assertRaisesRegex(ValueError, "force_id must be an integer"):
            deserialize_entries({"entries": [{
                "datetime": "2026-10-09T08:00:00",
                "force_id": "12",
                "is_all_forces": False,
            }]})

    def test_rejects_missing_entries_array(self):
        with self.assertRaisesRegex(ValueError, "entries array"):
            deserialize_entries({})


if __name__ == "__main__":
    unittest.main()
