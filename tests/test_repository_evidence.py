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

    def test_contrast_tagged_cases_keep_expectation_lineage_in_every_projection(self):
        tagged = {c["id"]: c for c in self.repo.cases if c["dimensions"].get("contrast_classes")}
        self.assertGreater(len(tagged), 100)
        fixtures = [f for f in project.project_all(self.repo.cases, self.repo.ruleset) if f["case_id"] in tagged]
        self.assertEqual(project.verify_all(fixtures, list(tagged.values()), self.repo.ruleset, self.repo.schema("fixture")), [])
        seen = set()
        for f in fixtures:
            case = tagged[f["case_id"]]
            seen.add(f["case_id"])
            self.assertEqual([e["expect"] for e in f["spans"]], [e["expect"] for e in case["expectations"]], f["fixture_id"])
            self.assertEqual([e["case_span_index"] for e in f["spans"]], list(range(len(case["expectations"]))), f["fixture_id"])
        self.assertEqual(seen, set(tagged))

    def test_no_model_relative_seen_unseen_vocabulary_remains(self):
        from ner_evidence import slices
        self.assertNotIn("seen", slices.fields(self.repo.cases[0]))
        self.assertIn("name_commonness", slices.fields(self.repo.cases[0]))
        for t in self.repo.targets["count_targets"] + self.repo.targets["ratio_targets"]:
            self.assertNotIn("unseen", t["id"])
        for case in self.repo.cases:
            self.assertNotIn("unseen", case["id"])

    def test_reference_bands_are_minimal_and_consistent(self):
        from ner_evidence import references
        self.assertEqual([str(p) for p in references.check_bands(self.repo)], [])
        for ref in self.repo.bands["references"]:
            for band in ref["entries"].values():
                self.assertIn(band, {"common", "rare", "novel"})

    def test_uncommon_name_coverage_grew_over_alpha(self):
        from ner_evidence import slices
        self.assertGreaterEqual(slices.count(self.repo.cases, {"language": "en", "name_commonness": "uncommon"}), 100)
        self.assertGreaterEqual(slices.count(self.repo.cases, {"language": "ko", "name_commonness": "uncommon"}), 90)

    def test_collision_slices_are_balanced_and_reported_separately(self):
        ids = {t["id"] for t in self.repo.targets["count_targets"]}
        for lang in ("en", "ko"):
            for cls in ("organization", "location", "product-brand"):
                for kind in ("person", "not-person", "either"):
                    self.assertIn(f"{lang}-collision-{cls}-{kind}", ids)

    def test_every_collision_pair_partner_exists(self):
        ids = {c["id"] for c in self.repo.cases}
        import re
        for c in self.repo.cases:
            m = re.search(r"Partner of ([a-z0-9-]+):", c["why"])
            if m:
                partner = "/".join(c["id"].split("/")[:2]) + "/" + m.group(1)
                self.assertTrue(any(i.endswith("/" + m.group(1)) and i.startswith(c["id"].rsplit("/", 2)[0]) for i in ids), (c["id"], partner))

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
