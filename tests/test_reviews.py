import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from helpers import good_case, load_repo
from ner_evidence import canonical, repo as repo_mod, reviews, snapshot
from test_snapshot import make_root

DATE = "2026-01-02"


def reviewer(rid="rev/en-one", languages=("en",), facets=("linguistic", "factual"), independent=True, status="active"):
    return {"id": rid, "languages": list(languages), "facets": list(facets), "independent_of_authors": independent,
            "qualification": "Test reviewer with relevant qualifications for the facet.", "status": status, "registered_on": DATE}


def verdict(case, rid="rev/en-one", v="agree", facet="linguistic", comment="The expectation follows from the sentence and the span conventions."):
    return reviews.with_id({"event_type": "verdict", "case_id": case["id"], "subject_digest": reviews.subject_digest(case), "facet": facet,
                            "recorded_on": DATE, "reviewer_id": rid, "verdict": v, "comment": comment})


def request(case, role="en-annotator", facet="linguistic"):
    return reviews.with_id({"event_type": "request", "case_id": case["id"], "subject_digest": reviews.subject_digest(case), "facet": facet,
                            "recorded_on": DATE, "requested_role": role})


class Derivation(unittest.TestCase):
    def setUp(self):
        self.repo = load_repo()
        self.case = good_case()
        self.repo.cases = [self.case]
        self.repo.reviewers = {"reviewers": [reviewer(), reviewer("rev/self", independent=False), reviewer("rev/ko-one", languages=("ko",))]}
        self.repo.ledger = []

    def codes(self):
        return {p.code for p in reviews.check_reviews(self.repo)}

    def status(self, facet="linguistic"):
        return reviews.derived_status(self.repo, self.case, facet)

    def test_no_ledger_is_author_only_and_consistent(self):
        self.assertEqual(self.status(), "author-only")
        self.assertEqual(reviews.check_reviews(self.repo), [])

    def test_independent_agreement_derives_reviewed_and_status_cannot_be_hand_set(self):
        self.repo.ledger = [verdict(self.case)]
        self.assertEqual(self.status(), "independently-reviewed")
        self.assertIn("REVIEW_STATUS", self.codes())  # case still says author-only
        self.case["review"]["linguistic"] = "independently-reviewed"
        self.assertEqual(reviews.check_reviews(self.repo), [])

    def test_hand_set_status_without_a_ledger_is_rejected(self):
        self.case["review"]["linguistic"] = "independently-reviewed"
        self.assertIn("REVIEW_STATUS", self.codes())

    def test_disagreement_is_disputed_and_listed(self):
        self.repo.reviewers["reviewers"].append(reviewer("rev/en-two"))
        self.repo.ledger = [verdict(self.case), verdict(self.case, "rev/en-two", "disagree", comment="The span should include the honorific here.")]
        self.assertEqual(self.status(), "disputed")
        self.assertEqual(reviews.summary(self.repo)["disputed"], [{"case_id": self.case["id"], "facet": "linguistic"}])

    def test_reviewer_can_withdraw_by_a_later_verdict(self):
        self.repo.ledger = [verdict(self.case, v="disagree", comment="Initially I thought the span was too long."), verdict(self.case)]
        self.assertEqual(self.status(), "independently-reviewed")

    def test_any_content_change_makes_the_verdict_stale(self):
        self.repo.ledger = [verdict(self.case)]
        for field, value in (("why", "A different rationale that is long enough to pass the schema checks."), ("evidence_class", "authored-baseline"),
                             ("source_ids", ["src/project-authored-synthetic", "src/other"]), ("title", "A different title for the case")):
            changed = copy.deepcopy(self.case)
            changed[field] = value
            self.assertEqual(reviews.derived_status(self.repo, changed, "linguistic"), "author-only", field)
        self.repo.cases = [self.case]
        self.assertEqual(reviews.summary(self.repo)["stale_events"], 0)
        self.case["why"] = "A different rationale that is long enough to pass the schema checks."
        self.assertEqual(reviews.summary(self.repo)["stale_events"], 1)

    def test_changing_only_the_review_block_does_not_invalidate(self):
        self.repo.ledger = [verdict(self.case)]
        self.case["review"]["linguistic"] = "independently-reviewed"
        self.assertEqual(self.status(), "independently-reviewed")

    def test_non_independent_and_wrong_language_reviewers_do_not_count(self):
        self.repo.ledger = [verdict(self.case, "rev/self"), verdict(self.case, "rev/ko-one")]
        self.assertEqual(self.status(), "author-only")
        self.assertEqual(reviews.summary(self.repo)["uncounted_verdicts"], 1)

    def test_retired_reviewer_does_not_count(self):
        self.repo.reviewers["reviewers"][0]["status"] = "retired"
        self.repo.ledger = [verdict(self.case)]
        self.assertEqual(self.status(), "author-only")

    def test_unregistered_reviewer_rejected(self):
        self.repo.ledger = [verdict(self.case, "rev/nobody")]
        self.assertIn("REVIEW", self.codes())

    def test_tampered_event_rejected(self):
        ev = verdict(self.case)
        ev["verdict"] = "disagree"
        self.repo.ledger = [ev]
        self.assertIn("REVIEW", self.codes())

    def test_duplicate_and_unknown_case_rejected(self):
        ev = verdict(self.case)
        self.repo.ledger = [ev, copy.deepcopy(ev)]
        self.assertIn("REVIEW", self.codes())
        ghost = copy.deepcopy(self.case)
        ghost["id"] = "person/en/common-word-collision/ghost"
        self.repo.ledger = [verdict(ghost)]
        self.assertIn("REVIEW", self.codes())

    def test_model_terms_in_comments_rejected(self):
        self.repo.ledger = [verdict(self.case, comment="This matches what the FastNER output shows for it.")]
        self.assertIn("MODEL_TERM", self.codes())

    def test_request_role_must_fit_case_and_facet(self):
        self.repo.ledger = [request(self.case, role="ko-native-linguist")]
        self.assertIn("REVIEW", self.codes())
        self.repo.ledger = [request(self.case)]
        self.assertEqual(reviews.check_reviews(self.repo), [])
        self.assertEqual(reviews.summary(self.repo)["open_requests"]["linguistic"]["en"], 1)

    def test_verdict_event_cannot_carry_a_case_edit(self):
        ev = verdict(self.case)
        ev["proposed_change"] = "Extend the span to include the title."
        ev = reviews.with_id({k: v for k, v in ev.items() if k != "event_id"})
        self.repo.ledger = [ev]
        self.case["review"]["linguistic"] = "independently-reviewed"
        self.assertEqual(reviews.check_reviews(self.repo), [])  # a proposal is allowed, but only as text in the event
        self.case["review"]["linguistic"] = "author-only"
        extra = copy.deepcopy(verdict(self.case))
        extra["expectations"] = []
        self.repo.ledger = [extra]
        self.assertIn("SCHEMA", self.codes())


class Sync(unittest.TestCase):
    def test_sync_changes_only_review_status(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            repo = repo_mod.load(root)
            case = next(c for c in repo.cases if c["language"] == "en")
            (root / "evidence" / "reviews").mkdir()
            (root / "evidence" / "reviews" / "reviewers.json").write_text(canonical.pretty({"reviewers": [reviewer()]}))
            (root / "evidence" / "reviews" / "ledger.jsonl").write_text(canonical.dumps(verdict(case)) + "\n")
            repo = repo_mod.load(root)
            before = {c["id"]: copy.deepcopy(c) for c in repo.cases}
            self.assertTrue(reviews.sync(repo))
            after = repo_mod.load(root)
            for c in after.cases:
                b = copy.deepcopy(before[c["id"]])
                b["review"]["linguistic"] = c["review"]["linguistic"]
                self.assertEqual(c, b)
            self.assertEqual({c["id"]: c["review"]["linguistic"] for c in after.cases}[case["id"]], "independently-reviewed")
            self.assertEqual(reviews.check_reviews(after), [])


class LedgerImmutability(unittest.TestCase):
    def git(self, root, *args):
        subprocess.run(["git", "-C", str(root), "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args], check=True, capture_output=True)

    def test_only_appends_are_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "evidence" / "reviews").mkdir(parents=True)
            ledger = root / reviews.LEDGER_PATH
            c = good_case()
            lines = [canonical.dumps(request(c)), canonical.dumps(verdict(c))]
            ledger.write_text("\n".join(lines) + "\n")
            self.git(root, "init", "-q")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "base")
            self.assertEqual(reviews.check_ledger_immutability(root, "HEAD")[0], [])
            ledger.write_text("\n".join(lines + [canonical.dumps(verdict(c, v="abstain", comment="Cannot judge this case reliably."))]) + "\n")
            self.assertEqual(reviews.check_ledger_immutability(root, "HEAD")[0], [])
            ledger.write_text(lines[1] + "\n" + lines[0] + "\n")
            self.assertTrue(reviews.check_ledger_immutability(root, "HEAD")[0])
            ledger.write_text(lines[0] + "\n")
            self.assertTrue(reviews.check_ledger_immutability(root, "HEAD")[0])


class VerdictCommand(unittest.TestCase):
    def test_cli_records_a_verdict_that_derives_reviewed_status(self):
        from ner_evidence import cli
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            (root / "evidence" / "reviews").mkdir()
            (root / "evidence" / "reviews" / "reviewers.json").write_text(canonical.pretty({"reviewers": [reviewer()]}))
            (root / "evidence" / "reviews" / "ledger.jsonl").write_text("")
            case = next(c for c in repo_mod.load(root).cases if c["language"] == "en")
            args = ["--root", str(root), "review", "verdict", "--case", case["id"], "--facet", "linguistic", "--reviewer", "rev/en-one",
                    "--verdict", "agree", "--comment", "The span excludes nothing it should keep.", "--date", DATE]
            self.assertEqual(cli.main(args), 0)
            self.assertEqual(cli.main(["--root", str(root), "review", "sync"]), 0)
            self.assertEqual(cli.main(["--root", str(root), "review", "check"]), 0)
            self.assertEqual(repo_mod.load(root).cases[0]["review"]["linguistic"], "independently-reviewed" if repo_mod.load(root).cases[0]["id"] == case["id"] else "author-only")
            bad = args[:]
            bad[bad.index("rev/en-one")] = "rev/nobody"
            self.assertEqual(cli.main(bad), 2)


class Workflow(unittest.TestCase):
    def test_request_events_are_prioritised_and_not_duplicated(self):
        repo = load_repo()
        repo.ledger = []
        first = reviews.request_events(repo, "ko", "linguistic", "ko-native-linguist", 5, DATE)
        self.assertEqual(len(first), 5)
        by_id = {c["id"]: c for c in repo.cases}
        self.assertTrue(all(by_id[e["case_id"]]["ambiguity"]["level"] == "genuinely-ambiguous" for e in first))
        repo.ledger = first
        again = reviews.request_events(repo, "ko", "linguistic", "ko-native-linguist", 5, DATE)
        self.assertFalse({e["case_id"] for e in first} & {e["case_id"] for e in again})

    def test_blind_packet_hides_labels_and_rationale(self):
        repo = load_repo()
        text = reviews.render_packet(repo, "en", "linguistic", 3, blind=True)
        self.assertNotIn("expected **", text)
        self.assertNotIn("why:", text)
        self.assertIn("BLIND MODE", text)
        self.assertIn("expected **", reviews.render_packet(repo, "en", "linguistic", 3))

    def test_committed_ledger_is_consistent_and_honest_about_zero_independent_reviews(self):
        repo = load_repo()
        self.assertEqual(reviews.check_reviews(repo), [])
        s = reviews.summary(repo)
        if not repo.reviewers["reviewers"]:
            self.assertEqual(s["reviewed_cases"]["linguistic"], {"en": 0, "ko": 0})
            self.assertEqual(s["reviewed_cases"]["factual"], {"en": 0, "ko": 0})
        self.assertGreater(s["open_requests"]["linguistic"]["en"], 0)
        self.assertGreater(s["open_requests"]["linguistic"]["ko"], 0)

    def test_snapshot_carries_ledger_and_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_root(Path(d))
            repo = repo_mod.load(root)
            case = next(c for c in repo.cases if c["language"] == "en")
            (root / "evidence" / "reviews").mkdir()
            (root / "evidence" / "reviews" / "reviewers.json").write_text(canonical.pretty({"reviewers": [reviewer()]}))
            (root / "evidence" / "reviews" / "ledger.jsonl").write_text(canonical.dumps(verdict(case)) + "\n")
            reviews.sync(repo_mod.load(root))
            m = snapshot.build(repo_mod.load(root), root / "snapshots", "person-en-ko", "beta.1", "beta")
            snap = root / "snapshots" / m["snapshot_id"]
            self.assertEqual(snapshot.verify(snap), [])
            self.assertEqual(m["review_summary"]["linguistic"].get("independently-reviewed"), 1)
            report = json.loads((snap / "slice-report.json").read_text())
            self.assertEqual(report["review_ledger"]["reviewed_cases"]["linguistic"]["en"], 1)


if __name__ == "__main__":
    unittest.main()
