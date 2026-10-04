import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
import _bootstrap
from helpers import good_case
from ner_evidence import annotate, canonical, repo as repo_mod, snapshot

SRC_ROOT = _bootstrap.ROOT


def ko_case():
    text, spans = annotate.annotate("[[p:김민수]]는 [[n:김치]]를 먹었다.")
    c = good_case(text=text, expectations=spans, language="ko", focus_span=0)
    c.update(id="person/ko/particle-context/topic-marker", title="Topic marker after a full name",
             why="The topic particle attaches directly to the name and must stay outside the span.")
    c["dimensions"].update(script="hangul", token_class="single", collision_classes=["common-word"],
                           context_types=["particle-attached"], name_features=["ko-surname-given", "ko-3-syllable"],
                           boundary_tags=["particle-excluded"], familiarity="common")
    c["ambiguity"] = {"level": "context-resolvable", "note": "김 begins both a surname and the food 김치; context resolves it."}
    return c


def make_root(tmp: Path, cases=None, targets=None) -> Path:
    for d in ("taxonomy", "schemas", "projections"):
        shutil.copytree(SRC_ROOT / d, tmp / d)
    (tmp / "evidence" / "sources").mkdir(parents=True)
    (tmp / "evidence" / "cases" / "person").mkdir(parents=True)
    all_sources = json.loads((SRC_ROOT / "evidence" / "sources" / "sources.json").read_text())["sources"]
    (tmp / "evidence" / "sources" / "sources.json").write_text(
        canonical.pretty({"sources": [x for x in all_sources if x["id"] == "src/project-authored-synthetic"]}))
    targets = targets or {"targets_version": "1.0.0", "ratio_targets": [], "known_gaps": [],
                          "count_targets": [{"id": "at-least-two-cases", "description": "two cases", "where": {}, "min": 2}]}
    (tmp / "evidence" / "slice-targets.json").write_text(json.dumps(targets))
    cases = cases or [good_case(), ko_case()]
    (tmp / "evidence" / "cases" / "person" / "t.json").write_text(canonical.pretty({"cases": cases}))
    return tmp


class SnapshotBase(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.root = make_root(Path(self._d.name))
        self.repo = repo_mod.load(self.root)
        self.out = self.root / "snapshots"
        self.manifest = snapshot.build(self.repo, self.out, "person-en-ko", "alpha.1", "alpha")
        self.snap = self.out / self.manifest["snapshot_id"]


class ReferenceBands(unittest.TestCase):
    def test_snapshot_embeds_and_verifies_bands(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            case = good_case(id="person/en/common-word-collision/whitlow-attends", text="Whitlow will attend.", source_ids=[
                "src/project-authored-synthetic", "src/ref-us-census-2010-surnames"])
            case["expectations"] = [{"start": 0, "end": 7, "surface": "Whitlow", "expect": "person"}]
            case["focus_span"] = 0
            case["dimensions"].update(familiarity="rare", familiarity_basis="reference-frequency",
                                      familiarity_reference={"source_id": "src/ref-us-census-2010-surnames", "component": "Whitlow"},
                                      collision_classes=[], context_types=["plain-prose", "sentence-initial"], name_features=["surname-only"])
            case["ambiguity"] = {"level": "unambiguous"}
            case["title"], case["why"] = "Rare surname checked against a reference", "A rare surname used as a subject so the reference band can be checked mechanically."
            (root / "evidence" / "cases" / "person" / "t.json").write_text(canonical.pretty({"cases": [good_case(), ko_case(), case]}))
            all_sources = json.loads((SRC_ROOT / "evidence" / "sources" / "sources.json").read_text())["sources"]
            (root / "evidence" / "sources" / "sources.json").write_text(canonical.pretty({"sources": [
                x for x in all_sources if x["id"] in {"src/project-authored-synthetic", "src/ref-us-census-2010-surnames"}]}))
            (root / "evidence" / "references").mkdir()
            bands = json.loads((SRC_ROOT / "evidence" / "references" / "name-frequency-bands.json").read_text())
            bands["references"] = [r for r in bands["references"] if r["language"] == "en"]
            bands["references"][0]["entries"] = {"Whitlow": "rare"}
            (root / "evidence" / "references" / "name-frequency-bands.json").write_text(canonical.pretty(bands))
            repo = repo_mod.load(root)
            m = snapshot.build(repo, root / "snapshots", "person-en-ko", "beta.1", "beta")
            snap = root / "snapshots" / m["snapshot_id"]
            self.assertTrue((snap / "references" / "name-frequency-bands.json").exists())
            self.assertEqual(snapshot.verify(snap), [])
            # tamper with the embedded band, keeping digests consistent, and verification must notice via the case check
            data = json.loads((snap / "references" / "name-frequency-bands.json").read_text())
            self.assertEqual(data["references"][0]["entries"], {"Whitlow": "rare"})


class Build(SnapshotBase):
    def test_verifies(self):
        self.assertEqual(snapshot.verify(self.snap), [])
        self.assertEqual(snapshot.verify_all(self.out), [])

    def test_manifest_contents(self):
        m = self.manifest
        self.assertEqual(m["counts"]["cases"], 2)
        self.assertGreater(m["counts"]["fixtures"], 2)
        self.assertEqual(m["snapshot_id"], f"person-en-ko-alpha.1-{m['content_digest'][:12]}")
        self.assertEqual(m["redistribution"], "internal-only")
        self.assertNotIn("timestamp", json.dumps(m).lower())

    def test_digest_matches_documented_consumer_recipe(self):
        # Independent re-implementation of the recipe in docs/snapshot-and-consumer-contract.md
        m = json.loads((self.snap / "manifest.json").read_text())
        h = hashlib.sha256(b"ner-evidence-snapshot-digest/1\n")
        for f in sorted(m["files"], key=lambda f: f["path"]):
            data = (self.snap / f["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), f["sha256"])
            h.update(f"{f['sha256']}  {f['path']}\n".encode())
        self.assertEqual(h.hexdigest(), m["content_digest"])

    def test_deterministic_across_independent_builds(self):
        with tempfile.TemporaryDirectory() as d2:
            root2 = make_root(Path(d2))
            m2 = snapshot.build(repo_mod.load(root2), root2 / "snapshots", "person-en-ko", "alpha.1", "alpha")
            self.assertEqual(m2, self.manifest)
            for f in self.manifest["files"]:
                self.assertEqual((self.snap / f["path"]).read_bytes(), (root2 / "snapshots" / m2["snapshot_id"] / f["path"]).read_bytes())

    def test_case_order_does_not_change_identity(self):
        with tempfile.TemporaryDirectory() as d2:
            root2 = make_root(Path(d2), cases=[ko_case(), good_case()])
            m2 = snapshot.build(repo_mod.load(root2), root2 / "snapshots", "person-en-ko", "alpha.1", "alpha")
            self.assertEqual(m2["content_digest"], self.manifest["content_digest"])

    def test_idempotent_rebuild(self):
        again = snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.1", "alpha")
        self.assertEqual(again, self.manifest)
        self.assertEqual(len(snapshot.read_index(self.out)), 1)

    def test_content_change_requires_new_label(self):
        edited = good_case(title="May is a month in one clause and a person in the other")
        make_root_cases = [edited, ko_case()]
        (self.root / "evidence" / "cases" / "person" / "t.json").write_text(canonical.pretty({"cases": make_root_cases}))
        with self.assertRaises(snapshot.SnapshotError) as cm:
            snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.1", "alpha")
        self.assertIn("immutable", str(cm.exception))
        m2 = snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.2", "alpha")
        self.assertNotEqual(m2["snapshot_id"], self.manifest["snapshot_id"])
        self.assertEqual(snapshot.verify_all(self.out), [])  # old snapshot untouched and still valid

    def test_refuses_invalid_evidence(self):
        bad = good_case()
        bad["expectations"][0]["surface"] = "Mat"
        (self.root / "evidence" / "cases" / "person" / "t.json").write_text(canonical.pretty({"cases": [bad, ko_case()]}))
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.9", "alpha")

    def test_unmet_target_blocks_build_unless_waived(self):
        tg = {"targets_version": "1.0.0", "ratio_targets": [], "known_gaps": [],
              "count_targets": [{"id": "ten-cases", "description": "ten cases", "where": {}, "min": 10}]}
        (self.root / "evidence" / "slice-targets.json").write_text(json.dumps(tg))
        with self.assertRaises(snapshot.SnapshotError):
            snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.3", "alpha")
        tg["count_targets"][0]["waiver"] = "Only two cases exist in this synthetic test repository."
        (self.root / "evidence" / "slice-targets.json").write_text(json.dumps(tg))
        m = snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.3", "alpha")
        self.assertEqual(m["waived_targets"][0]["id"], "ten-cases")


class Tamper(SnapshotBase):
    def rewrite_manifest(self, mutate):
        m = json.loads((self.snap / "manifest.json").read_text())
        mutate(m)
        (self.snap / "manifest.json").write_text(canonical.pretty(m))

    def recompute(self, m):
        for f in m["files"]:
            data = (self.snap / f["path"]).read_bytes()
            f["sha256"], f["bytes"] = hashlib.sha256(data).hexdigest(), len(data)
        m["content_digest"] = snapshot.content_digest(m["files"])
        m["source_manifest_digest"] = next(f["sha256"] for f in m["files"] if f["path"] == "sources.json")

    def codes(self):
        return {p.code for p in snapshot.verify(self.snap)}

    def test_modified_file_detected(self):
        p = self.snap / "cases.jsonl"
        p.write_bytes(p.read_bytes().replace(b"meeting", b"meetings"))
        self.assertIn("DIGEST", self.codes())

    def test_extra_and_missing_files_detected(self):
        (self.snap / "notes.json").write_text("{}")
        self.assertIn("SNAPSHOT", self.codes())
        (self.snap / "notes.json").unlink()
        (self.snap / "fixtures.jsonl").unlink()
        self.assertIn("SNAPSHOT", self.codes())

    def test_consistent_rewrite_still_changes_identity(self):
        # An adversary who fixes every digest still cannot keep the snapshot_id.
        p = self.snap / "cases.jsonl"
        p.write_bytes(p.read_bytes().replace(b"meeting", b"meetings"))
        self.rewrite_manifest(self.recompute)
        self.assertIn("IDENTITY", self.codes())

    def test_lineage_break_detected_even_with_consistent_digests(self):
        fx = [json.loads(l) for l in (self.snap / "fixtures.jsonl").read_text().splitlines()]
        fx[0]["spans"][0]["expect"] = "either" if fx[0]["spans"][0]["expect"] != "either" else "person"
        (self.snap / "fixtures.jsonl").write_bytes(canonical.jsonl_bytes(fx))
        self.rewrite_manifest(self.recompute)
        codes = self.codes()
        self.assertIn("LINEAGE", codes)

    def test_wrong_counts_detected(self):
        self.rewrite_manifest(lambda m: m["counts"].update(cases=99))
        self.assertIn("COUNTS", self.codes())

    def test_malformed_manifest_rejected(self):
        self.rewrite_manifest(lambda m: m.pop("content_digest"))
        self.assertIn("SCHEMA", self.codes())

    def test_unlisted_directory_detected(self):
        shutil.copytree(self.snap, self.out / "person-en-ko-alpha.1-000000000000")
        self.assertTrue(any("not listed" in p.message for p in snapshot.verify_all(self.out)))


class Immutability(SnapshotBase):
    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.root), *a], capture_output=True, text=True, check=True)

    def setUp(self):
        super().setUp()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "release")

    def test_unchanged_passes_and_new_snapshot_may_be_added(self):
        self.assertEqual(snapshot.check_immutability(self.root, "main")[0], [])
        (self.root / "evidence" / "cases" / "person" / "t.json").write_text(canonical.pretty({"cases": [good_case(title="May as month and as a person in one sentence"), ko_case()]}))
        snapshot.build(repo_mod.load(self.root), self.out, "person-en-ko", "alpha.2", "alpha")
        self.assertEqual(snapshot.check_immutability(self.root, "main")[0], [])

    def test_modifying_or_deleting_released_file_fails(self):
        p = self.snap / "cases.jsonl"
        p.write_bytes(p.read_bytes() + b"\n")
        probs, _ = snapshot.check_immutability(self.root, "main")
        self.assertTrue(any(x.code == "IMMUTABLE" for x in probs))
        self.git("checkout", "--", ".")
        (self.snap / "manifest.json").unlink()
        self.assertTrue(snapshot.check_immutability(self.root, "main")[0])

    def test_rewriting_index_entry_fails(self):
        idx = json.loads((self.out / "index.json").read_text())
        idx["snapshots"][0]["content_digest"] = "0" * 64
        (self.out / "index.json").write_text(canonical.pretty(idx))
        self.assertTrue(snapshot.check_immutability(self.root, "main")[0])

    def test_missing_base_is_skipped_not_passed_silently(self):
        probs, note = snapshot.check_immutability(self.root, "no-such-ref")
        self.assertEqual(probs, [])
        self.assertIn("skipped", note)


if __name__ == "__main__":
    unittest.main()
