"""verify_mec.py must reject tampered traces. Needs a traced run: python scripts/test_verify_mec.py RUN_DIR"""
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(path, fn):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())
    fn(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def first(rows, pred):
    return next(r for r in rows if pred(r))


def scale(r, key, factor):
    r[key] = str(float(r[key]) * factor)


TAMPERS = {
    "link rate": ("links.csv", lambda rs: scale(first(rs, lambda r: r["direction"] == "UP"), "rate_bps", 1.01)),
    "link sharing": ("links.csv", lambda rs: first(rs, lambda r: True).__setitem__("sharing", "7")),
    "cpu segment length": ("cpu.csv", lambda rs: scale(first(rs, lambda r: True), "end", 1.001)),
    "uav cpu energy": ("energy.csv", lambda rs: scale(first(rs, lambda r: r["node"] == "-1"), "cpu_j", 1.01)),
    "device idle energy": ("energy.csv", lambda rs: scale(first(rs, lambda r: r["node"] == "0"), "idle_j", 0.99)),
    "done after deadline": ("tasks.csv", lambda rs: first(rs, lambda r: r["status"] == "DONE").__setitem__(
        "deadline", str(float(first(rs, lambda r: r["status"] == "DONE")["resolved"]) - 0.5))),
    "dropped counted as done": ("tasks.csv", lambda rs: first(rs, lambda r: r["status"] == "DROP_DEADLINE").__setitem__("status", "DONE")),
    "metric dvr": ("metrics.csv", lambda rs: first(rs, lambda r: r["metric"] == "dvr").__setitem__("value", "0.123")),
}


def verify(run):
    return subprocess.run([sys.executable, str(ROOT / "scripts/verify_mec.py"), str(run)], capture_output=True, text=True).returncode


def main():
    source = Path(sys.argv[1]).resolve()
    if verify(source) != 0:
        raise SystemExit("baseline run must PASS first")
    # one episode that offloads and drops something, so every tamper has a target
    episodes = sorted((source / "traces").glob("*/L*/S*/DEADLINE_ENERGY__LLF__DROP_INFEASIBLE"))
    failures = []
    for name, (file, fn) in TAMPERS.items():
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            run.mkdir()
            for f in ("episodes.csv", "manifest.json", "config.json"):
                shutil.copy(source / f, run / f)
            shutil.copytree(source / "models", run / "models")
            target = None
            for ep in episodes:
                rel = ep.relative_to(source)
                shutil.copytree(ep, run / rel)
                if target is None:
                    try:
                        edit(run / rel / file, fn)
                        target = rel
                    except StopIteration:
                        shutil.rmtree(run / rel)
                        shutil.copytree(ep, run / rel)
            code = verify(run) if target else None
            print(f"{name:26s} -> {'rejected' if code == 1 else 'NOT REJECTED' if code == 0 else 'no target'}")
            if code != 1:
                failures.append(name)
    if failures:
        raise SystemExit(f"verifier missed: {failures}")
    print("OK: every tampered trace was rejected")


if __name__ == "__main__":
    main()
