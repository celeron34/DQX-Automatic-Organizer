import unittest

from datetime import datetime, timedelta

from dqx_ise import build_schedule_entries, get_file_names, get_force_ids


class FakeElement:
    def __init__(self, attributes):
        self.attributes = attributes

    def get_attribute(self, name):
        return self.attributes.get(name)


class FakeParent:
    def __init__(self, elements):
        self.elements = elements
        self.last_xpath = None

    def find_elements(self, by, xpath):
        self.last_xpath = (by, xpath)
        return self.elements


class GetFileNamesTests(unittest.TestCase):
    def test_extracts_names_from_arbitrary_xpath_and_attribute(self):
        parent = FakeParent([
            FakeElement({'href': 'https://example.test/assets/party%20one.png?size=large#view'}),
            FakeElement({'href': '/download/report.csv?token=abc'}),
            FakeElement({'href': None}),
            FakeElement({'href': '/download/'}),
        ])

        result = get_file_names(parent, './/a', 'href')

        self.assertEqual(result, ['party one.png', 'report.csv'])
        self.assertEqual(parent.last_xpath, ('xpath', './/a'))

    def test_keeps_document_order_and_duplicate_names(self):
        parent = FakeParent([
            FakeElement({'src': '/img/1234.png?v=1'}),
            FakeElement({'src': 'https://cdn.example.test/1234.png?v=2'}),
            FakeElement({'src': '/img/5678.png'}),
        ])

        self.assertEqual(
            get_file_names(parent, './/img'),
            ['1234.png', '1234.png', '5678.png'],
        )

    def test_force_ids_are_read_from_current_page_links(self):
        parent = FakeParent([
            FakeElement({'href': 'https://hiroba.dqx.jp/sc/tokoyami/?defense_force_num=2'}),
            FakeElement({'href': '/sc/tokoyami/?other=1&defense_force_num=23'}),
            FakeElement({'href': '/sc/tokoyami/?defense_force_num=invalid'}),
            FakeElement({'href': None}),
        ])

        self.assertEqual(get_force_ids(parent), {2, 23})
        self.assertEqual(parent.last_xpath[0], 'xpath')


    def test_schedule_entries_associate_datetime_with_force(self):
        start = datetime(2026, 10, 8, 6, 0)
        icons = [
            ['2.png', '3.png'],
            ['23.png', '2.png'],
        ]

        entries = build_schedule_entries(icons, start, {2, 3})

        self.assertEqual(
            [(entry.datetime, entry.force_id, entry.is_all_forces) for entry in entries],
            [
                (start, 2, False),
                (start + timedelta(hours=1), 23, True),
                (start + timedelta(days=1), 3, False),
                (start + timedelta(days=1, hours=1), 2, False),
            ],
        )


if __name__ == '__main__':
    unittest.main()
