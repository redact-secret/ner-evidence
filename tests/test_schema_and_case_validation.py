import unittest

import helpers  # noqa: F401  (also bootstraps sys.path)
from helpers import good_case, load_repo
from ner_evidence import annotate, jsonschema_lite, validate


class SchemaLite(unittest.TestCase):
    def test_unsupported_keyword_fails_loudly(self):
        with self.assertRaises(jsonschema_lite.SchemaError):
            jsonschema_lite.validate({}, {"type": "object", "dependentRequired": {}})

    def test_basic_keywords(self):
        s = {"type": "object", "required": ["a"], "additionalProperties": False,
             "properties": {"a": {"type": "integer", "minimum": 1}}}
        self.assertEqual(jsonschema_lite.validate({"a": 1}, s), [])
        self.assertTrue(jsonschema_lite.validate({}, s))
        self.assertTrue(jsonschema_lite.validate({"a": 0}, s))
        self.assertTrue(jsonschema_lite.validate({"a": True}, s))  # bool is not an integer
        self.assertTrue(jsonschema_lite.validate({"a": 1, "b": 2}, s))


class CaseValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def codes(self, case):
        return {p.code for p in validate.check_case(case, self.repo)}

    def test_good_case_passes(self):
        self.assertEqual(validate.check_case(good_case(), self.repo), [])

    def test_surface_must_match_offsets(self):
        c = good_case()
        c["expectations"][1]["surface"] = "Mat"
        self.assertIn("SPAN", self.codes(c))

    def test_offsets_outside_text(self):
        c = good_case()
        c["expectations"][1].update(start=40, end=99)
        self.assertIn("SPAN", self.codes(c))

    def test_overlapping_or_unsorted_spans(self):
        c = good_case()
        c["expectations"].reverse()
        c["focus_span"] = 0
        self.assertIn("SPAN", self.codes(c))

    def test_non_nfc_text_rejected(self):
        c = good_case(text="Café is open and May will attend.")
        c["expectations"] = [{"start": 22, "end": 25, "surface": "May", "expect": "person"}]
        c["focus_span"] = 0
        self.assertIn("TEXT", self.codes(c))

    def test_missing_why_rejected(self):
        c = good_case()
        del c["why"]
        self.assertIn("SCHEMA", self.codes(c))

    def test_short_why_rejected(self):
        self.assertIn("SCHEMA", self.codes(good_case(why="Because.")))

    def test_unknown_vocabulary_rejected(self):
        c = good_case()
        c["dimensions"]["collision_classes"] = ["spaceship"]
        self.assertIn("VOCAB", self.codes(c))

    def test_derived_dimensions_must_match_surface(self):
        c = good_case()
        c["dimensions"]["token_class"] = "multi"
        self.assertIn("DERIVED", self.codes(c))
        c = good_case()
        c["dimensions"]["script"] = "hangul"
        self.assertIn("DERIVED", self.codes(c))

    def test_collision_cannot_be_unambiguous(self):
        c = good_case()
        c["ambiguity"] = {"level": "unambiguous"}
        self.assertIn("AMBIGUITY", self.codes(c))

    def test_either_iff_genuinely_ambiguous(self):
        c = good_case()
        c["ambiguity"]["level"] = "genuinely-ambiguous"
        self.assertIn("AMBIGUITY", self.codes(c))
        c = good_case()
        c["expectations"][1]["expect"] = "either"
        self.assertIn("AMBIGUITY", self.codes(c))

    def test_no_person_context_consistency(self):
        c = good_case()
        c["dimensions"]["context_types"] = ["no-person"]
        self.assertIn("CONTEXT", self.codes(c))

    def test_model_terms_in_metadata_rejected(self):
        c = good_case(why="Lowers the threshold at which FastNER fires, because the month reading is common here.")
        self.assertIn("MODEL_TERM", self.codes(c))

    def test_model_terms_allowed_in_case_text(self):
        # A name such as "Presidio" in the text itself is not metadata.
        text = "Presidio and May talked."
        c = good_case(text=text)
        c["expectations"] = [{"start": 0, "end": 8, "surface": "Presidio", "expect": "person"},
                             {"start": 13, "end": 16, "surface": "May", "expect": "person"}]
        c["focus_span"] = 1
        self.assertNotIn("MODEL_TERM", self.codes(c))

    def test_identity_rules(self):
        self.assertIn("ID", self.codes(good_case(id="person/en/common-word-collision/issue-12")))
        self.assertIn("ID", self.codes(good_case(id="person/ko/common-word-collision/may-month")))  # language mismatch
        self.assertIn("SCHEMA", self.codes(good_case(id="May/month")))

    def test_unknown_extra_property_rejected(self):
        c = good_case()
        c["support_status"] = "supported"
        self.assertIn("SCHEMA", self.codes(c))

    def test_plain_projection_cannot_be_excluded(self):
        c = good_case(projections_excluded=[{"projection_id": "plain", "reason": "this must never be allowed to happen"}])
        self.assertIn("PROJECTION", self.codes(c))


class StructuredAmbiguity(unittest.TestCase):
    """Machine-readable ambiguity semantics (schema 1.1.0)."""

    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def codes(self, case):
        return {p.code for p in validate.check_case(case, self.repo)}

    def structured(self, **amb):
        c = good_case()
        c["ambiguity"].update(kind="lexical-homograph", alternative_reading="temporal-term",
                              resolved_by=["predicate-or-argument"], **amb)
        return c

    def test_complete_structure_passes(self):
        self.assertEqual(validate.check_case(self.structured(), self.repo), [])

    def test_partial_structure_rejected(self):
        c = good_case()
        c["ambiguity"]["kind"] = "lexical-homograph"
        self.assertIn("AMBIGUITY", self.codes(c))

    def test_unknown_vocabulary_rejected(self):
        c = self.structured()
        c["ambiguity"]["kind"] = "made-up-kind"
        c["ambiguity"]["resolved_by"] = ["tea-leaves"]
        self.assertEqual(sum(1 for p in validate.check_case(c, self.repo) if p.code == "VOCAB"), 2)

    def test_nothing_iff_genuinely_ambiguous(self):
        c = self.structured()
        c["ambiguity"]["resolved_by"] = ["nothing"]
        self.assertIn("AMBIGUITY", self.codes(c))

    def test_genuine_case_needs_both_outcomes(self):
        c = good_case()
        c["expectations"][1]["expect"] = "either"
        c["ambiguity"].update(level="genuinely-ambiguous", kind="lexical-homograph",
                              alternative_reading="temporal-term", resolved_by=["nothing"])
        self.assertIn("AMBIGUITY", self.codes(c))  # acceptable_outcomes missing
        c["ambiguity"]["acceptable_outcomes"] = ["person", "not-person"]
        self.assertEqual(validate.check_case(c, self.repo), [])

    def test_unambiguous_case_cannot_carry_structure(self):
        c = good_case()
        c["dimensions"]["collision_classes"] = []
        c["ambiguity"] = {"level": "unambiguous", "kind": "lexical-homograph"}
        self.assertIn("AMBIGUITY", self.codes(c))

    def test_context_ambiguity_cases_are_all_structured(self):
        for case in self.repo.cases:
            if case["id"].split("/")[2] == "context-ambiguity":
                self.assertIn("kind", case["ambiguity"], case["id"])

    def test_minimal_pairs_exist_in_both_languages(self):
        by_lang = {"en": 0, "ko": 0}
        for case in self.repo.cases:
            if case["id"].split("/")[2] == "context-ambiguity" and case["ambiguity"]["level"] == "genuinely-ambiguous":
                by_lang[case["language"]] += 1
        self.assertGreaterEqual(by_lang["en"], 4)
        self.assertGreaterEqual(by_lang["ko"], 2)


class ContrastClasses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def codes(self, case):
        return {p.code for p in validate.check_case(case, self.repo)}

    def test_unknown_class_rejected(self):
        c = good_case()
        c["dimensions"]["contrast_classes"] = ["en-placeholder"]
        self.assertIn("VOCAB", self.codes(c))  # unknown id

    def test_class_must_match_case_language(self):
        c = good_case()
        c["dimensions"]["contrast_classes"] = ["ko-particle-allomorph"]
        self.assertIn("VOCAB", self.codes(c))

    def test_every_class_has_a_floor_and_a_rationale(self):
        ids = {t["id"] for t in self.repo.targets["count_targets"]}
        for entry in self.repo.taxonomy["dimensions"]["contrast_class"]:
            self.assertIn("contrast-" + entry["id"], ids)
            self.assertIn("Why:", entry["definition"], entry["id"])


class FamiliarityBasis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = load_repo()

    def codes(self, case):
        return {p.code for p in validate.check_case(case, self.repo)}

    def with_basis(self, basis, familiarity="rare", ref=None):
        c = good_case()
        c["dimensions"]["familiarity"] = familiarity
        c["dimensions"]["familiarity_basis"] = basis
        if ref:
            c["dimensions"]["familiarity_reference"] = ref
        return c

    def test_basis_is_required_when_a_label_applies(self):
        c = good_case()
        del c["dimensions"]["familiarity_basis"]
        self.assertIn("FAMILIARITY", self.codes(c))

    def test_author_judgment_needs_no_reference(self):
        self.assertEqual(validate.check_case(self.with_basis("author-judgment"), self.repo), [])

    def test_not_applicable_forbids_a_basis(self):
        self.assertIn("FAMILIARITY", self.codes(self.with_basis("author-judgment", "not-applicable")))

    def test_constructed_only_supports_novel(self):
        self.assertIn("FAMILIARITY", self.codes(self.with_basis("constructed", "rare")))
        self.assertEqual(validate.check_case(self.with_basis("constructed", "novel"), self.repo), [])

    def test_reference_frequency_requires_a_reference(self):
        self.assertIn("FAMILIARITY", self.codes(self.with_basis("reference-frequency")))

    def test_reference_must_match_the_committed_band(self):
        ref = {"source_id": "src/ref-us-census-2010-surnames", "component": "Whitlow"}
        c = self.with_basis("reference-frequency", "rare", ref)
        c["expectations"][1].update(start=26, end=29)
        c["text"] = "The meeting is in May and Whitlow will attend."
        c["expectations"] = [{"start": 18, "end": 21, "surface": "May", "expect": "not-person"},
                             {"start": 26, "end": 33, "surface": "Whitlow", "expect": "person"}]
        c["source_ids"] = ["src/project-authored-synthetic", "src/ref-us-census-2010-surnames"]
        self.assertEqual(validate.check_case(c, self.repo), [])
        c["dimensions"]["familiarity"] = "common"  # the band is rare
        self.assertIn("FAMILIARITY", self.codes(c))
        c["dimensions"]["familiarity"] = "rare"
        c["dimensions"]["familiarity_reference"]["component"] = "Smithwick"  # no derived band
        self.assertIn("FAMILIARITY", self.codes(c))

    def test_reference_source_must_be_listed_on_the_case(self):
        ref = {"source_id": "src/ref-us-census-2010-surnames", "component": "May"}
        self.assertIn("PROVENANCE", self.codes(self.with_basis("reference-frequency", "rare", ref)))

    def test_every_labelled_committed_case_has_a_basis(self):
        for case in self.repo.cases:
            fam = case["dimensions"]["familiarity"]
            self.assertEqual("familiarity_basis" in case["dimensions"], fam != "not-applicable", case["id"])


class Annotate(unittest.TestCase):
    def test_offsets(self):
        text, spans = annotate.annotate("Dr. [[p:Reyes]] saw [[n:May]].")
        self.assertEqual(text, "Dr. Reyes saw May.")
        for s in spans:
            self.assertEqual(text[s["start"]:s["end"]], s["surface"])

    def test_korean_offsets_are_code_points(self):
        text, spans = annotate.annotate("[[p:김민수]]는 갔다")
        self.assertEqual((spans[0]["start"], spans[0]["end"]), (0, 3))


if __name__ == "__main__":
    unittest.main()
