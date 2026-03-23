import json
import tempfile
import unittest

from simulator import DeterministicCivilizationSimulator


class SimulatorTests(unittest.TestCase):
    def test_same_seed_same_digest(self):
        a = DeterministicCivilizationSimulator(seed=12345, initial_agents=100)
        b = DeterministicCivilizationSimulator(seed=12345, initial_agents=100)
        a.run(5)
        b.run(5)
        self.assertEqual(a.digest(), b.digest())

    def test_save_load_replay_exact(self):
        sim = DeterministicCivilizationSimulator(seed=12345, initial_agents=80)
        sim.run(5)
        with tempfile.NamedTemporaryFile(suffix='.json') as tmp:
            sim.save(tmp.name)
            loaded = DeterministicCivilizationSimulator.load(tmp.name)
            self.assertEqual(sim.digest(), loaded.digest())
            sim.run(5)
            loaded.run(5)
            self.assertEqual(sim.digest(), loaded.digest())

    def test_supports_large_population(self):
        sim = DeterministicCivilizationSimulator(seed=12345, initial_agents=1000, width=56, height=40)
        result = sim.run(1)
        self.assertGreaterEqual(result['alive'], 900)
        self.assertIn('food', result['market'])


if __name__ == '__main__':
    unittest.main()
