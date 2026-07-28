import random
import unittest

from autoclicker.timing import next_interval


class NextIntervalTests(unittest.TestCase):
    def test_no_variation_returns_base_interval(self):
        self.assertEqual(next_interval(0.5, 0), 0.5)

    def test_interval_stays_in_requested_range(self):
        rng = random.Random(42)
        values = [next_interval(1, 25, rng) for _ in range(1000)]
        self.assertTrue(all(0.75 <= value <= 1.25 for value in values))
        self.assertGreater(len(set(values)), 900)

    def test_rejects_invalid_base_interval(self):
        for value in (0, -1, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                next_interval(value, 10)

    def test_rejects_invalid_variation(self):
        for value in (-1, 101, float("inf"), float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                next_interval(1, value)


if __name__ == "__main__":
    unittest.main()
