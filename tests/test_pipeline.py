import unittest
from src.pipeline import summarize_match

class PipelineTests(unittest.TestCase):
    def test_includes_possessions_without_shots(self):
        events = [
            {"id":"a","index":1,"possession":1,"possession_team":{"id":7},"type":{"name":"Pass"}},
            {"id":"b","index":2,"possession":2,"possession_team":{"id":8},"team":{"id":8},"type":{"name":"Shot"},"shot":{"outcome":{"name":"Goal"},"statsbomb_xg":0.2}},
        ]
        p, s = summarize_match(10, events)
        self.assertEqual(len(p), 2)
        self.assertEqual(sum(x["has_shot"] == 0 for x in p), 1)
        self.assertEqual(s[0]["goal"], 1)

if __name__ == "__main__":
    unittest.main()
