import unittest

from pipeline import derive


def game(**kw):
    g = {"gid": "BAL202405010", "date": "2024-05-01", "num": 0, "type": "regular", "season": 2024, "team": "BAL",
         "home": True, "opp": "NYA", "opp_name": "New York Yankees", "rs": 0, "ra": 0, "line_us": [], "line_them": [],
         "innings": 9, "site": "BAL12", "tp": 0, "p_h": 5, "p_bfp": 30, "p_outs": 27, "link": "x", "src": "test"}
    g.update(kw)
    return g


class WalkOff(unittest.TestCase):
    def test_bottom_ninth_comeback(self):
        g = game(rs=4, ra=3, line_us=[0, 0, 1, 0, 0, 2, 0, 0, 1], line_them=[1, 0, 0, 0, 2, 0, 0, 0, 0])
        self.assertTrue(derive.is_walkoff(g))

    def test_home_led_and_did_not_bat_in_ninth(self):
        g = game(rs=4, ra=3, line_us=[0, 0, 4, 0, 0, 0, 0, 0], line_them=[1, 0, 0, 0, 2, 0, 0, 0, 0])
        self.assertFalse(derive.is_walkoff(g))

    def test_home_already_ahead_entering_last_inning(self):
        g = game(rs=6, ra=3, line_us=[0, 0, 4, 0, 0, 0, 0, 0, 2], line_them=[1, 0, 0, 0, 2, 0, 0, 0, 0])
        self.assertFalse(derive.is_walkoff(g))

    def test_extra_innings(self):
        g = game(rs=3, ra=2, innings=11, line_us=[1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
                 line_them=[0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertTrue(derive.is_walkoff(g))

    def test_road_win_is_never_a_walkoff(self):
        g = game(home=False, rs=4, ra=3, line_us=[0] * 8 + [4], line_them=[3] + [0] * 8)
        self.assertFalse(derive.is_walkoff(g))


class Clinch(unittest.TestCase):
    # Three teams, four games each against the others.
    def test_clinches_when_rival_cannot_catch_up(self):
        results = [
            ("2024-09-01", 0, "BOS", "BAL", 1, 2),
            ("2024-09-02", 0, "NYA", "BAL", 1, 2),
            ("2024-09-03", 0, "BOS", "NYA", 1, 2),
            ("2024-09-04", 0, "BOS", "BAL", 1, 2),
            ("2024-09-05", 0, "NYA", "BAL", 3, 2),
            ("2024-09-06", 0, "BOS", "NYA", 2, 1),
        ]
        # After 9/4: BAL 3 wins; NYA 1 win + 2 left = 3 (could tie), BOS 0 + 1 = 1.
        # After 9/5: BAL 3; NYA 2 + 1 left = 3. Still tied at best.
        # After 9/6: NYA finishes 2. BAL clinches.
        self.assertEqual(derive.clinch_date(results, "BAL", ["BAL", "BOS", "NYA"]), "2024-09-06")

    def test_head_to_head_breaks_ties_from_2022(self):
        results = [
            ("2024-09-01", 0, "NYA", "BAL", 1, 2),
            ("2024-09-02", 0, "NYA", "BAL", 1, 2),
            ("2024-09-03", 0, "NYA", "BOS", 2, 1),
            ("2024-09-04", 0, "BOS", "NYA", 1, 2),
            ("2024-09-05", 0, "BOS", "BAL", 2, 1),
        ]
        teams = ["BAL", "BOS", "NYA"]
        # After 9/2 BAL has 2 wins and has beaten NYA twice in two games.
        # NYA can still reach 2 wins, but BAL owns the season series.
        self.assertEqual(derive.clinch_date(results, "BAL", teams, tiebreak_h2h=True), "2024-09-04")
        self.assertIsNone(derive.clinch_date(results, "BAL", teams))


class Records(unittest.TestCase):
    def test_regular_and_postseason_counted_separately(self):
        games = [game(date="1966-10-09", season=1966, rs=1, ra=0, type="worldseries"),
                 game(date="1966-10-09", season=1966, rs=1, ra=2, num=1),
                 game(date="1970-10-09", season=1970, rs=3, ra=3)]
        self.assertEqual(derive.records(games), {"10-09": [[1966, 0, 1, 0, 1, 0], [1970, 0, 0, 1, 0, 0]]})


class Career(unittest.TestCase):
    def test_crossing_found_in_the_right_game(self):
        lines = [("1996-09-05", "g1", 0), ("1996-09-06", "g2", 1), ("1996-09-07", "g3", 1)]
        self.assertEqual(derive.career_crossings(lines, 499, "homeRuns", [300, 400, 500]), [("1996-09-06", "g2", 500)])


class PlayerGames(unittest.TestCase):
    def test_cycle_and_three_homers(self):
        g = game()
        bats = [{"gid": g["gid"], "date": g["date"], "pid": "a", "h": 4, "d": 1, "t": 1, "hr": 1},
                {"gid": g["gid"], "date": g["date"], "pid": "b", "h": 3, "d": 0, "t": 0, "hr": 3}]
        ev = derive.player_game_events([g], bats, [], lambda pid: pid.upper())
        self.assertEqual(sorted((e["t"], e["title"]) for e in ev),
                         [("cycle", "A hits for the cycle"), ("three_homer_game", "B hits three home runs")])


if __name__ == "__main__":
    unittest.main()
