import unittest
from datetime import datetime, timedelta

from event_definition import EventDefinition, EventInstance, EventPhase


class EventDefinitionTests(unittest.TestCase):
    def test_empty_draft_can_be_configured_incrementally(self):
        event = EventDefinition()
        self.assertFalse(event.is_configured)

        event.update(title="  Test event  ")
        self.assertEqual(event.title, "Test event")
        self.assertFalse(event.is_configured)

        starts_at = datetime(2026, 10, 7, 12, 0)
        event.update(starts_at=starts_at, recruitment_text="Let's join")
        self.assertTrue(event.is_configured)
        self.assertEqual(event.recruitment_text, "Let's join")

    def test_phase_boundaries_preserve_existing_schedule(self):
        starts_at = datetime(2026, 10, 7, 12, 0)
        expected = {
            -30: EventPhase.RECRUITING,
            -15: EventPhase.REMINDER,
            -10: EventPhase.FORMATION,
            0: EventPhase.START,
            60: EventPhase.FINISH,
        }
        for minute_offset, phase in expected.items():
            with self.subTest(minute_offset=minute_offset):
                now = starts_at + timedelta(minutes=minute_offset)
                self.assertIs(EventPhase.at(now, starts_at), phase)
        self.assertIsNone(EventPhase.at(starts_at + timedelta(minutes=1), starts_at))

    def test_event_instances_keep_independent_runtime_state(self):
        first = EventInstance(EventDefinition(title="first", starts_at=datetime(2026, 10, 7, 12)))
        second = EventInstance(EventDefinition(title="second", starts_at=datetime(2026, 10, 7, 13)))
        first.recruiting_members.append("alice")
        first.parties = ["party"]
        first.recruiting_message = "message"

        self.assertEqual(second.recruiting_members, [])
        self.assertIsNone(second.parties)
        self.assertIsNone(second.recruiting_message)
        self.assertTrue(first.claim_phase(EventPhase.RECRUITING))
        self.assertFalse(first.claim_phase(EventPhase.RECRUITING))
        self.assertTrue(second.claim_phase(EventPhase.RECRUITING))


if __name__ == "__main__":
    unittest.main()
