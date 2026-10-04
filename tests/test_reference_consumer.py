import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.ROOT
CONSUMER = ROOT / "examples" / "consume_snapshot.py"


def snapshots():
    idx = json.loads((ROOT / "snapshots" / "index.json").read_text())["snapshots"]
    return [ROOT / "snapshots" / e["path"] for e in idx]


def consume(path, *extra):
    return subprocess.run([sys.executable, str(CONSUMER), str(path), *extra], capture_output=True, text=True)


class ReferenceConsumer(unittest.TestCase):
    def test_accepts_every_released_snapshot_without_importing_the_package(self):
        import ast
        tree = ast.parse(CONSUMER.read_text())
        imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertNotIn("ner_evidence", imported)
        for s in snapshots():
            r = consume(s, "--expect-id", s.name)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("ACCEPTED", r.stdout)

    def test_rejects_wrong_pin_and_tampering(self):
        s = snapshots()[0]
        self.assertEqual(consume(s, "--expect-id", "person-en-ko-alpha.1-000000000000").returncode, 1)
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / s.name
            shutil.copytree(s, copy)
            p = copy / "fixtures.jsonl"
            p.write_bytes(p.read_bytes().replace(b"person", b"persoN", 1))
            r = consume(copy)
            self.assertEqual(r.returncode, 1)
            self.assertIn("digest mismatch", r.stdout)


if __name__ == "__main__":
    unittest.main()
