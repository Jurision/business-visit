import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "trip-plan-sync.py"
SPEC = importlib.util.spec_from_file_location("trip_plan_sync", MODULE_PATH)
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


class TripPlanValidationTests(unittest.TestCase):
    def setUp(self):
        self.original_store = SYNC.STORE
        self.tempdir = tempfile.TemporaryDirectory()
        SYNC.STORE = str(pathlib.Path(self.tempdir.name) / "plan.json")

    def tearDown(self):
        SYNC.STORE = self.original_store
        self.tempdir.cleanup()

    def test_complete_plan_is_valid(self):
        plan = [["us", "hongtai"], ["zhigong", "machines"], ["bright"], ["tube"], ["junshuo"]]
        self.assertTrue(SYNC.valid_plan(plan))

    def test_plan_rejects_missing_duplicate_and_unknown_visits(self):
        self.assertFalse(SYNC.valid_plan([["us"], ["zhigong"], ["bright"], ["tube"], ["junshuo"]]))
        self.assertFalse(SYNC.valid_plan([["us", "us"], ["zhigong"], ["bright"], ["tube"], ["junshuo"]]))
        self.assertFalse(SYNC.valid_plan([["us", "hongtai"], ["zhigong", "machines"], ["bright"], ["tube", "other"], ["junshuo"]]))

    def test_checklist_is_allow_listed(self):
        self.assertTrue(SYNC.valid_check({"c1": True, "c7": False}))
        self.assertFalse(SYNC.valid_check({"c8": True}))
        self.assertFalse(SYNC.valid_check({"c1": 1}))

    def test_write_is_atomic_and_load_round_trips(self):
        document = {
            "plan": [["us", "hongtai"], ["zhigong", "machines"], ["bright"], ["tube"], ["junshuo"]],
            "check": {"c1": True},
            "rev": 4,
        }
        SYNC.write(document)
        self.assertEqual(SYNC.load(), document)
        self.assertFalse(pathlib.Path(SYNC.STORE + ".tmp").exists())
        self.assertEqual(json.loads(pathlib.Path(SYNC.STORE).read_text()), document)

    def test_legacy_plan_is_migrated_without_reordering_existing_visits(self):
        legacy = {
            "plan": [["us", "hongtai"], ["zhigong", "machines"], ["bright"], ["tube"], []],
            "check": {"c1": True},
            "rev": 34,
        }
        pathlib.Path(SYNC.STORE).write_text(json.dumps(legacy), encoding="utf-8")

        migrated = SYNC.load()

        self.assertEqual(
            migrated["plan"],
            [["us", "hongtai"], ["zhigong", "machines"], ["bright"], ["tube"], ["junshuo"]],
        )
        self.assertEqual(migrated["rev"], 35)
        self.assertEqual(json.loads(pathlib.Path(SYNC.STORE).read_text()), migrated)


if __name__ == "__main__":
    unittest.main()
