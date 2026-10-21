import json
import unittest
from pathlib import Path

from pipeline import checks

try:
    from pipeline import cards
except ImportError:  # Pillow isn't installed
    cards = None

ITEMS = [(80, 1995, "Cal Ripken Jr. plays his 2,131st consecutive game, passing Lou Gehrig"),
         (70, 1996, "Eddie Murray hits his 500th career home run")]


@unittest.skipIf(cards is None, "Pillow not installed")
class Cards(unittest.TestCase):
    def test_page_points_previews_at_the_card_and_forwards_to_the_date(self):
        html = cards.page("09-06", ITEMS, [[1995, 1, 0, 0, 0, 0]])
        self.assertIn('<meta property="og:image" content="https://jeffpaul.github.io/orioles-calendar/day/09-06.png">', html)
        self.assertIn('content="1995: Cal Ripken Jr. plays his 2,131st consecutive game, passing Lou Gehrig. Plus 1 more."', html)
        self.assertIn('location.replace("../#09-06")', html)

    def test_card_is_preview_sized(self):
        self.assertEqual(cards.card("09-06", ITEMS, []).size, (1200, 630))
        self.assertEqual(cards.card("02-29", [], []).size, (1200, 630))


class Callouts(unittest.TestCase):
    def test_every_callout_has_a_chip_and_a_check(self):
        path = Path(__file__).resolve().parent.parent / "pipeline" / "callouts.json"
        callouts = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len({c["d"] for c in callouts}), len(callouts))
        for c in callouts:
            self.assertIn(c["check"], ("appeared", "absent"), c["title"])
            self.assertTrue(0 < len(c["chip"]) <= 40, c["chip"])


class Schedule(unittest.TestCase):
    GAME = {"d": "2027-02-19", "t": "S", "home": True, "opp": "Atlanta Braves", "abbr": "ATL",
            "time": "1:05 PM", "venue": "Ed Smith Stadium", "status": "Scheduled", "pk": 868576}

    def test_well_formed_schedule_passes(self):
        self.assertEqual(checks.schedule([self.GAME]), [])

    def test_duplicates_and_missing_fields_fail(self):
        self.assertTrue(checks.schedule([self.GAME, self.GAME]))
        self.assertTrue(checks.schedule([{**self.GAME, "d": "2027-02"}]))


if __name__ == "__main__":
    unittest.main()
