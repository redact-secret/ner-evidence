import copy
import json
import os
import subprocess
import sys
import unicodedata
import unittest

import helpers  # noqa: F401
from helpers import good_case, load_repo
from ner_evidence import annotate, canonical, project

REPO = load_repo()
RULESET = REPO.ruleset
FIXTURE_SCHEMA = REPO.schema("fixture")


def case_from(markup, language="en", **over):
    text, spans = annotate.annotate(markup)
    c = good_case(text=text, expectations=spans, language=language, focus_span=0)
    c["id"] = f"person/{language}/common-name/probe"
    c["dimensions"].update(over.get("dimensions", {}))
    c.update({k: v for k, v in over.items() if k != "dimensions"})
    return c


class Projection(unittest.TestCase):
    def test_plain_is_identity(self):
        c = good_case()
        fx = {f["projection_id"]: f for f in project.project_case(c, RULESET)}
        self.assertEqual(fx["plain"]["text"], c["text"])
        self.assertEqual([(s["start"], s["end"]) for s in fx["plain"]["spans"]], [(18, 21), (26, 29)])

    def test_offsets_in_all_units_for_korean_and_astral(self):
        c = case_from("😀 [[p:김민수]]는 갔다", "ko")
        for fx in project.project_case(c, RULESET):
            t = fx["text"]
            for sp in fx["spans"]:
                self.assertEqual(t[sp["start"]:sp["end"]], sp["surface"])
                self.assertEqual(t.encode("utf-8")[sp["utf8_start"]:sp["utf8_end"]].decode("utf-8"), sp["surface"])
                self.assertEqual(t.encode("utf-16-le")[sp["utf16_start"] * 2:sp["utf16_end"] * 2].decode("utf-16-le"), sp["surface"])

    def test_json_string_escapes_and_parses(self):
        c = case_from('He said [[p:Maria]] "wins" \\ today')
        fx = next(f for f in project.project_case(c, RULESET) if f["projection_id"] == "json-string")
        self.assertEqual(json.loads(fx["text"])["message"], c["text"])
        sp = fx["spans"][0]
        self.assertEqual(fx["text"][sp["start"]:sp["end"]], "Maria")

    def test_nfd_only_when_it_changes_text(self):
        ascii_case = case_from("[[p:Maria]] came")
        self.assertNotIn("nfd-decomposed", {f["projection_id"] for f in project.project_case(ascii_case, RULESET)})
        ko = case_from("[[p:김민수]]는 갔다", "ko")
        nfd = next(f for f in project.project_case(ko, RULESET) if f["projection_id"] == "nfd-decomposed")
        self.assertEqual(nfd["text"], unicodedata.normalize("NFD", ko["text"]))
        self.assertGreater(nfd["spans"][0]["end"] - nfd["spans"][0]["start"], 3)  # jamo decomposition lengthens the span
        accented = case_from("[[p:José]] came")
        self.assertIn("nfd-decomposed", {f["projection_id"] for f in project.project_case(accented, RULESET)})

    def test_exclusion_is_honoured(self):
        c = good_case(projections_excluded=[{"projection_id": "quoted", "reason": "Quote marks would change what this case tests."}])
        self.assertNotIn("quoted", {f["projection_id"] for f in project.project_case(c, RULESET)})

    def test_expectations_are_copied_not_invented(self):
        c = good_case()
        for fx in project.project_case(c, RULESET):
            self.assertEqual([s["expect"] for s in fx["spans"]], [e["expect"] for e in c["expectations"]])

    def test_wrapper_neutrality_check(self):
        rs = copy.deepcopy(RULESET)
        rs["projections"][2]["prefix"] = "Message about maria: "
        c = case_from("[[p:Maria]] came")
        self.assertTrue(project.check_ruleset(rs, [c]))
        self.assertEqual(project.check_ruleset(RULESET, [c]), [])


class Determinism(unittest.TestCase):
    def test_order_independent_and_repeatable(self):
        cases = [case_from("[[p:김민수]]는 갔다", "ko"), good_case(), case_from("[[p:José]] came")]
        cases[0]["id"] = "person/ko/common-name/a"
        cases[2]["id"] = "person/en/common-name/b"
        a = canonical.jsonl_bytes(project.project_all(cases, RULESET))
        b = canonical.jsonl_bytes(project.project_all(list(reversed(cases)), RULESET))
        self.assertEqual(a, b)

    def test_stable_across_hash_seeds(self):
        code = (
            "import sys; sys.path.insert(0,'src');"
            "from ner_evidence import repo,project,canonical;"
            "r=repo.load(); import json;"
            "c={'id':'person/en/common-name/z','language':'en','text':'Maria came','expectations':[{'start':0,'end':5,'surface':'Maria','expect':'person'}]};"
            "print(canonical.sha256_hex(canonical.jsonl_bytes(project.project_all([c], r.ruleset))))"
        )
        outs = set()
        for seed in ("0", "1", "12345"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            outs.add(subprocess.run([sys.executable, "-c", code], cwd=str(helpers_root()), env=env, capture_output=True, text=True, check=True).stdout)
        self.assertEqual(len(outs), 1)


def helpers_root():
    import _bootstrap
    return _bootstrap.ROOT


class LineageVerification(unittest.TestCase):
    def setUp(self):
        self.case = good_case()
        self.cases = {self.case["id"]: self.case}
        self.fx = project.project_case(self.case, RULESET)[1]

    def errs(self, fx, cases=None):
        return project.verify_fixture(fx, cases if cases is not None else self.cases, RULESET, FIXTURE_SCHEMA)

    def test_valid_fixture(self):
        self.assertEqual(self.errs(self.fx), [])

    def test_stale_case_digest_rejected(self):
        changed = copy.deepcopy(self.case)
        changed["title"] = "A different title after the fixture was generated"
        self.assertTrue(any("stale" in e for e in self.errs(self.fx, {changed["id"]: changed})))

    def test_invented_expectation_rejected(self):
        fx = copy.deepcopy(self.fx)
        fx["spans"][0]["expect"] = "person"
        self.assertTrue(any("expectation" in e for e in self.errs(fx)))

    def test_extra_span_rejected(self):
        fx = copy.deepcopy(self.fx)
        fx["spans"].append({**fx["spans"][0], "case_span_index": 2})
        self.assertTrue(self.errs(fx))

    def test_missing_case_rejected(self):
        self.assertTrue(any("does not exist" in e for e in self.errs(self.fx, {})))

    def test_tampered_text_rejected(self):
        fx = copy.deepcopy(self.fx)
        fx["text"] = fx["text"].replace("meeting", "meetings")
        self.assertTrue(self.errs(fx))

    def test_missing_and_extra_fixtures_detected(self):
        fixtures = project.project_case(self.case, RULESET)
        probs = project.verify_all(fixtures[:-1], [self.case], RULESET, FIXTURE_SCHEMA)
        self.assertTrue(any("missing" in p.message for p in probs))
        ghost = copy.deepcopy(fixtures[0])
        ghost["fixture_id"] = "person/en/common-name/ghost@plain"
        probs = project.verify_all(fixtures + [ghost], [self.case], RULESET, FIXTURE_SCHEMA)
        self.assertTrue(probs)

    def test_malformed_fixture_rejected(self):
        self.assertTrue(self.errs({"fixture_id": "x"}))


if __name__ == "__main__":
    unittest.main()
