"""Invariants of the committed evidence itself (not of the tooling)."""

import unittest

import helpers  # noqa: F401
from helpers import load_repo
from ner_evidence import project, provenance, slices, validate


class CommittedEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def test_everything_validates(self):
        self.assertEqual([str(p) for p in validate.check_all(self.repo)], [])
        self.assertEqual([str(p) for p in provenance.check_sources(self.repo) + provenance.check_case_provenance(self.repo)], [])

    def test_fixtures_reproduce_with_lineage(self):
        fixtures = project.project_all(self.repo.cases, self.repo.ruleset)
        self.assertEqual(project.verify_all(fixtures, self.repo.cases, self.repo.ruleset, self.repo.schema("fixture")), [])
        self.assertEqual(project.check_ruleset(self.repo.ruleset, self.repo.cases), [])

    def test_targets_met_or_explicitly_waived(self):
        report = slices.compute(self.repo.cases, project.project_all(self.repo.cases, self.repo.ruleset), self.repo.targets)
        self.assertEqual(report["unmet_targets"], [])
        for w in report["waived_targets"]:
            self.assertGreater(len(w["waiver"]), 40)

    def test_both_languages_and_required_groups_present(self):
        langs = {c["language"] for c in self.repo.cases}
        self.assertEqual(langs, {"en", "ko"})
        for g in self.repo.taxonomy["case_groups"]:
            for lang in g["languages"]:
                n = sum(1 for c in self.repo.cases if c["language"] == lang and c["id"].split("/")[2] == g["id"])
                self.assertGreater(n, 0, f"case group {g['id']} has no {lang} cases")

    def test_every_case_explains_itself_and_ambiguity_is_honest(self):
        for c in self.repo.cases:
            self.assertGreaterEqual(len(c["why"]), 40, c["id"])
        either = [c for c in self.repo.cases if any(e["expect"] == "either" for e in c["expectations"])]
        self.assertGreaterEqual(len(either), 20)

    def test_minimal_pairs_exist(self):
        ids = {c["id"] for c in self.repo.cases}
        for a, b in [("person/en/sentence-initial-trap/will-modal-question", "person/en/sentence-initial-trap/will-given-name"),
                     ("person/ko/common-word-collision/bada-name-and-sea", "person/ko/common-word-collision/bada-noun-sea-view")]:
            self.assertTrue(a in ids and b in ids, (a, b))

    def test_no_model_specific_state_anywhere_in_authored_data(self):
        import json
        banned = ("support_status", "threshold", "fastner", "gliner", "model_score")
        blob = json.dumps(self.repo.cases + self.repo.sources).lower()
        for term in banned:
            if term in ("threshold",):
                continue  # may appear in plain English sentences; metadata is checked by the validator
            self.assertNotIn(term, blob)


if __name__ == "__main__":
    unittest.main()
