"""Adversarial checks for the independent auditor; use an already generated run."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("offloading_audit", Path(__file__).with_name("verify-uav-offloading.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(sys.argv[1])
        cls.manifest = json.loads((cls.root/"manifest.json").read_text())
        cls.scenario = next(iter(cls.manifest["configs"]))
        cls.directory = cls.root/cls.scenario/f'seed-{cls.manifest["first_seed"]}'
        cls.name = "DEADLINE_ENERGY__EDF"
        cls.jobs = {int(j["id"]): j for j in audit.read(cls.directory/"workload.csv")}
        cls.outcomes = {int(o["id"]): o for o in audit.read(cls.directory/(cls.name+"-tasks.csv"))}
        cls.energies = audit.read(cls.directory/(cls.name+"-energy.csv"))
        cls.decisions = audit.read(cls.directory/(cls.name+"-decisions.csv"))

    def setUp(self):
        self.o = copy.deepcopy(self.outcomes)
        self.e = copy.deepcopy(self.energies)
        self.d = copy.deepcopy(self.decisions)

    def instance(self, jobs=None):
        return audit.Audit(self.jobs if jobs is None else jobs, self.o, self.e,
                           self.manifest["configs"][self.scenario], "EDF", self.manifest["protocol"]["agingFraction"])

    def test_original_trace_passes(self):
        self.instance().verify(self.d, "DEADLINE_ENERGY")

    def test_changed_work_is_rejected(self):
        row = next(iter(self.o.values()))
        row["executed_mi"] = str(float(row["executed_mi"])+1)
        with self.assertRaisesRegex(AssertionError, "Work conservation"):
            self.instance().verify(self.d, "DEADLINE_ENERGY")

    def test_changed_energy_is_rejected(self):
        self.e[0]["compute_j"] = str(float(self.e[0]["compute_j"])+1)
        with self.assertRaisesRegex(AssertionError, "compute_j"):
            self.instance().verify(self.d, "DEADLINE_ENERGY")

    def test_changed_forecast_is_rejected(self):
        self.d[0]["local_finish_s"] = str(float(self.d[0]["local_finish_s"])+1)
        with self.assertRaisesRegex(AssertionError, "forecast finish"):
            self.instance().verify(self.d, "DEADLINE_ENERGY")

    def test_changed_destination_is_rejected(self):
        self.d[0]["destination"] = "UAV" if self.d[0]["destination"] == "LOCAL" else "LOCAL"
        with self.assertRaisesRegex(AssertionError, "Offloading policy/trace mismatch"):
            self.instance().verify(self.d, "DEADLINE_ENERGY")

    def test_forecast_cannot_see_future_or_actual_mi(self):
        first = min(self.d, key=lambda d: (float(d["at_s"]), int(d["id"])))
        tid, now = int(first["id"]), float(first["at_s"])
        changed = copy.deepcopy(self.jobs)
        future = 0
        for index, j in changed.items():
            j["actual_mi"] = str(float(j["actual_mi"])*100)
            if float(j["arrival_s"]) > now:
                j["estimated_mi"] = str(float(j["estimated_mi"])*100)
                j["priority"] = "999"
                future += 1
        self.assertGreater(future, 0)
        for air in (False, True):
            self.assertEqual(self.instance().projection(tid, now, air), self.instance(changed).projection(tid, now, air))

    def test_edf_and_spt_select_different_hand_computed_jobs(self):
        tasks = [(0, "RESCUENET", 0, 0, 20, 2, 10), (1, "ALIBABA", 0, 0, 30, 1, 1)]
        self.assertEqual(0, audit.select(tasks, 0, 10000, 1, 1, 1, 40, "EDF", .75))
        self.assertEqual(1, audit.select(tasks, 0, 10000, 1, 1, 1, 40, "SPT", .75))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/test-uav-offloading-verifier.py RUN_DIR")
    unittest.main(argv=[sys.argv[0]], verbosity=2)
