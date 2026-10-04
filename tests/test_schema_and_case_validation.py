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
