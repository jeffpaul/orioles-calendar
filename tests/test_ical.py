import unittest

from pipeline import ical

PLAYERS = [
    {"id": "ripkc001", "n": "Cal Ripken Jr.", "b": "1960-08-24", "y": [1981, 2001], "g": 3001, "w": [95.9, 95.9],
     "hof": True, "a": [{"d": "1978-06-06", "how": "Da", "from": ""}]},
    {"id": "scrub001", "n": "Joe Scrub", "b": "1970-02-29", "y": [1995], "g": 3, "w": [-0.1, -0.1], "a": []},
    {"id": "brown001", "n": "Old Brownie", "b": "1890-02-29", "y": [1920], "g": 900, "w": [20.0, 20.0], "a": []},
]
EVENTS = [
    {"d": "1995-09-06", "t": "callout", "c": 1, "title": "Cal Ripken Jr. plays his 2,131st consecutive game",
     "ids": ["ripkc001"]},
    {"d": "1996-09-06", "t": "walk_off", "title": "Someone hits a walk-off single", "ids": []},
    {"d": "1995-04-02", "t": "debut", "title": "Joe Scrub plays his first game for the Orioles", "ids": ["scrub001"]},
    {"d": "1944-10-01", "t": "pennant", "title": "Browns clinch the 1944 American League pennant", "ids": []},
]


class Feed(unittest.TestCase):
    def setUp(self):
        self.text = ical.feed(PLAYERS, EVENTS, "https://example.org/", "20260925T000000Z", "Test")

    def test_lines_are_crlf_and_folded(self):
        raw = self.text.encode("utf-8")
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertTrue(all(len(line) <= 75 for line in raw.split(b"\r\n")))

    def test_best_story_leads_and_text_is_escaped(self):
        self.assertIn("SUMMARY:Cal Ripken Jr. plays his 2\\,131st consecutive game (1995)", self.text.replace("\r\n ", ""))
        self.assertIn("DTSTART;VALUE=DATE:20000906\r\nRRULE:FREQ=YEARLY", self.text)

    def test_routine_debuts_and_minor_birthdays_are_left_out(self):
        self.assertNotIn("Joe Scrub", self.text)

    def test_feb_29_folds_into_feb_28(self):
        self.assertIn("DTSTART;VALUE=DATE:20000228", self.text)
        self.assertNotIn("20000229", self.text)

    def test_orioles_only_feed_drops_earlier_eras(self):
        text = ical.feed(PLAYERS, EVENTS, "https://example.org/", "20260925T000000Z", "Test", first_year=1954)
        self.assertNotIn("Browns clinch", text)
        self.assertNotIn("Old Brownie", text)
        self.assertIn("Orioles acquire Cal Ripken Jr. in the amateur draft", text.replace("\r\n ", ""))


class Managers(unittest.TestCase):
    PEOPLE = [
        {"id": "weave801", "n": "Earl Weaver", "b": "1930-08-14", "x": "2013-01-19", "y": [], "g": 0, "a": [],
         "hof": True, "m": {"y": [1968, 1986], "g": 2541, "w": 1480, "l": 1060}},
        {"id": "fill801", "n": "Short Interim", "b": "1950-03-03", "y": [], "g": 0, "a": [],
         "m": {"y": [1985], "g": 1, "w": 1, "l": 0}},
    ]
    EVENTS = [
        {"d": "1968-07-11", "t": "mgr_first", "title": "Earl Weaver manages his first game for the Orioles",
         "ids": ["weave801"], "n": 2289},
        {"d": "1985-06-13", "t": "mgr_first", "title": "Short Interim manages his first game for the Orioles",
         "ids": ["fill801"], "n": 1},
    ]

    def test_long_tenures_birthdays_and_deaths_are_in_interim_spells_are_not(self):
        text = ical.feed(self.PEOPLE, self.EVENTS, "https://example.org/", "20260925T000000Z", "Test").replace("\r\n ", "")
        self.assertIn("Earl Weaver manages his first game for the Orioles", text)
        self.assertIn("Earl Weaver is born", text)
        self.assertIn("Earl Weaver dies", text)
        self.assertNotIn("Short Interim", text)


class Fold(unittest.TestCase):
    def test_never_splits_a_multibyte_character(self):
        line = "SUMMARY:" + "Miñoso " * 20
        folded = ical.fold(line)
        self.assertEqual(folded.replace("\r\n ", ""), line)
        for part in folded.split("\r\n"):
            part.encode("utf-8").decode("utf-8")
            self.assertLessEqual(len(part.encode("utf-8")), 75)


if __name__ == "__main__":
    unittest.main()
