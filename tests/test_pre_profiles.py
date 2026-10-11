import unittest
from src.pre_profiles import build, summarize_team

class PreProfileTests(unittest.TestCase):
    def test_chronological_history_excludes_target_and_future(self):
        def match(n, day):
            return {"match_id": n, "match_date": f"2020-01-{day:02d}", "kick_off": "12:00:00", "home_team": {"home_team_id": 1}, "away_team": {"away_team_id": 2}}
        import src.pre_profiles as mod
        original = mod.fetch_json
        try:
            mod.fetch_json = lambda *args, **kwargs: []
            rows = build([match(i, i) for i in range(1, 8)], limit=1, prior=5)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["prior_matches"], 5)
            self.assertEqual(rows[0]["prior_match_ids"], "[2, 3, 4, 5, 6]")
            self.assertEqual(rows[0]["complete_history"], 1)
        finally:
            mod.fetch_json = original

    def test_unshot_possession_is_counted(self):
        events = [{"index": 1, "possession": 1, "possession_team": {"id": 4}, "team": {"id": 4}, "type": {"name": "Pass"}}]
        result = summarize_team(events, 4)
        self.assertEqual(result["for_possessions"], 1)
        self.assertEqual(sum(v for k,v in result.items() if k.startswith("for_shots")), 0)

if __name__ == "__main__":
    unittest.main()
