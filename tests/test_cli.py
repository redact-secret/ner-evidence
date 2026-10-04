import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
import _bootstrap
from ner_evidence import cli
from test_snapshot import make_root


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class Cli(unittest.TestCase):
    def test_annotate_outputs_exact_spans(self):
        code, out = run("annotate", "Dr. [[p:Reyes]] saw [[n:May]].")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["text"], "Dr. Reyes saw May.")
        self.assertEqual([e["expect"] for e in data["expectations"]], ["person", "not-person"])

    def test_check_passes_on_committed_repository(self):
        code, out = run("--root", str(_bootstrap.ROOT), "check")
        self.assertEqual(code, 0, out)
        self.assertIn("all gates passed", out)

    def test_check_fails_on_corrupt_case_and_names_the_case(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            f = root / "evidence" / "cases" / "person" / "t.json"
            data = json.loads(f.read_text())
            data["cases"][0]["expectations"][0]["surface"] = "Mat"
            f.write_text(json.dumps(data))
            code, out = run("--root", str(root), "validate")
            self.assertEqual(code, 1)
            self.assertIn("person/en/common-word-collision/may-month", out)

    def test_malformed_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            (root / "evidence" / "cases" / "person" / "broken.json").write_text("{not json")
            code, out = run("--root", str(root), "validate")
            self.assertEqual(code, 1)
            self.assertIn("PARSE", out)

    def test_duplicate_case_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            src = root / "evidence" / "cases" / "person" / "t.json"
            (root / "evidence" / "cases" / "person" / "dup.json").write_text(src.read_text())
            code, out = run("--root", str(root), "validate")
            self.assertEqual(code, 1)
            self.assertIn("DUPLICATE_ID", out)

    def test_fmt_check_flags_unformatted_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            f = root / "evidence" / "cases" / "person" / "t.json"
            f.write_text(json.dumps(json.loads(f.read_text())))  # compact, not canonical
            code, out = run("--root", str(root), "fmt", "--check")
            self.assertEqual(code, 1)
            code, _ = run("--root", str(root), "fmt")
            self.assertEqual(code, 0)
            self.assertEqual(run("--root", str(root), "fmt", "--check")[0], 0)

    def test_snapshot_build_requires_label_and_builds_when_given(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            self.assertEqual(run("--root", str(root), "snapshot", "build")[0], 2)
            code, out = run("--root", str(root), "snapshot", "build", "--label", "alpha.1")
            self.assertEqual(code, 0, out)
            self.assertEqual(run("--root", str(root), "snapshot", "verify")[0], 0)


if __name__ == "__main__":
    unittest.main()
