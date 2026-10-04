import copy
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401
from helpers import good_case, load_repo
from ner_evidence import privacy, provenance


def corpus_source(**over):
    src = {
        "id": "src/example-corpus", "kind": "public-corpus", "title": "Example public corpus",
        "description": "A public corpus used only in tests of the provenance rules.",
        "version": "2024-01", "as_of": "2024-01-01", "use": "text-incorporated",
        "policy": {"text_redistribution": "allowed", "attribution_required": True, "attribution": "Example Corpus (2024), CC BY 4.0.",
                   "share_alike": False, "max_excerpt_chars": 120, "names_in_cases": "replaced-with-synthetic"},
        "origin": {"type": "url", "locator": "https://example.org/corpus", "artifact_sha256": "0" * 64, "retrieved_on": "2024-01-02"},
        "license": {"spdx": "CC-BY-4.0", "redistribution": "allowed", "terms_note": "Attribution required."},
        "personal_data": {"contains_personal_data": False, "name_origin": "synthetic", "notes": "Synthetic names only."},
        "transformations": ["none"], "known_bias": ["Test-only corpus with no coverage claims."],
        "review": {"provenance": "independently-reviewed", "legal": "independently-reviewed"},
    }
    for k, v in over.items():
        src[k] = v
    return src


def reference_source(**over):
    ref = corpus_source(id="src/ref-test", kind="reference", use="cited-rule",
                        license={"spdx": "CC-BY-4.0", "redistribution": "cite-only", "terms_note": "Cited by section, not copied."},
                        policy={"text_redistribution": "prohibited", "attribution_required": False, "share_alike": False, "names_in_cases": "not-applicable"},
                        review={"provenance": "author-only", "legal": "pending"})
    del ref["origin"]["artifact_sha256"], ref["origin"]["retrieved_on"]
    ref.update(over)
    return ref


class ImportPolicy(unittest.TestCase):
    def setUp(self):
        self.repo = load_repo()

    def codes(self, src):
        self.repo.sources = [src]
        return {p.code for p in provenance.check_sources(self.repo)}

    def test_good_corpus_and_good_reference_pass(self):
        self.assertEqual(self.codes(corpus_source()), set())
        self.assertEqual(self.codes(reference_source()), set())

    def test_non_authored_source_needs_a_policy(self):
        src = corpus_source()
        del src["policy"]
        self.assertIn("POLICY", self.codes(src))

    def test_redistribution_must_agree_with_policy(self):
        src = corpus_source()
        src["policy"]["text_redistribution"] = "prohibited"
        self.assertIn("POLICY", self.codes(src))

    def test_attribution_text_required_when_attribution_is_required(self):
        src = corpus_source()
        del src["policy"]["attribution"]
        self.assertIn("POLICY", self.codes(src))

    def test_incorporated_text_needs_an_excerpt_cap_and_a_name_plan(self):
        src = corpus_source()
        del src["policy"]["max_excerpt_chars"]
        self.assertIn("POLICY", self.codes(src))
        src = corpus_source()
        src["policy"]["names_in_cases"] = "not-applicable"
        self.assertIn("POLICY", self.codes(src))

    def test_natural_names_must_be_replaced_before_entering_cases(self):
        src = corpus_source(personal_data={"contains_personal_data": False, "name_origin": "naturally-occurring", "notes": "Names occur naturally in the corpus."})
        src["policy"]["names_in_cases"] = "as-found-non-personal"
        self.assertIn("POLICY", self.codes(src))
        src["policy"]["names_in_cases"] = "replaced-with-synthetic"
        self.assertNotIn("POLICY", self.codes(src))

    def test_share_alike_needs_a_share_alike_license(self):
        src = corpus_source()
        src["policy"]["share_alike"] = True
        self.assertIn("POLICY", self.codes(src))
        src["license"]["spdx"] = "CC-BY-SA-4.0"
        self.assertNotIn("POLICY", self.codes(src))

    def test_a_cited_rule_source_stores_no_text(self):
        src = reference_source()
        src["policy"]["names_in_cases"] = "replaced-with-synthetic"
        self.assertIn("POLICY", self.codes(src))

    def test_use_must_fit_kind(self):
        self.assertIn("POLICY", self.codes(corpus_source(use="cited-rule")))

    def test_excerpt_cap_is_enforced_on_cases(self):
        src = corpus_source()
        src["policy"]["max_excerpt_chars"] = 10
        self.repo.sources = [src]
        case = good_case(source_ids=["src/example-corpus"], evidence_class="corpus-backed")
        self.repo.cases = [case]
        probs = provenance.check_case_provenance(self.repo)
        self.assertIn("POLICY", {p.code for p in probs})
        src["policy"]["max_excerpt_chars"] = 200
        self.assertNotIn("POLICY", {p.code for p in provenance.check_case_provenance(self.repo)})

    def test_reference_backed_case_must_cite_a_rule(self):
        self.repo.sources = [reference_source(), load_repo().sources[0]]
        case = good_case(source_ids=["src/project-authored-synthetic", "src/ref-test"], evidence_class="reference-backed")
        self.repo.cases = [case]
        self.assertIn("PROVENANCE", {p.code for p in provenance.check_case_provenance(self.repo)})
        case["citations"] = [{"source_id": "src/ref-test", "locator": "Article 48"}]
        self.assertEqual([str(p) for p in provenance.check_case_provenance(self.repo)], [])

    def test_citations_are_only_for_reference_backed_cases_and_must_be_listed_sources(self):
        self.repo.sources = [reference_source(), load_repo().sources[0]]
        case = good_case(source_ids=["src/project-authored-synthetic"], citations=[{"source_id": "src/ref-test", "locator": "Article 48"}])
        self.repo.cases = [case]
        self.assertTrue(provenance.check_case_provenance(self.repo))

    def test_committed_sources_all_declare_use_and_policy(self):
        for s in load_repo().sources:
            self.assertIn("use", s)
            self.assertEqual("policy" in s, s["kind"] != "project-authored", s["id"])

    def test_synthetic_reference_and_corpus_evidence_are_separately_countable(self):
        from ner_evidence import slices
        repo = load_repo()
        counts = {b: slices.count(repo.cases, {"provenance_basis": b}) for b in ("synthetic-authored", "reference-backed", "corpus-backed")}
        self.assertGreater(counts["synthetic-authored"], 0)
        self.assertGreaterEqual(counts["reference-backed"], 25)
        self.assertEqual(counts["corpus-backed"], 0)  # honest: no corpus is imported at Beta 1
        self.assertEqual(sum(counts.values()), len(repo.cases))


class Sources(unittest.TestCase):
    def setUp(self):
        self.repo = load_repo()
        self.repo.cases = [good_case()]

    def codes(self, *sources):
        self.repo.sources = list(sources)
        return {p.code for p in provenance.check_sources(self.repo)}

    def test_repository_sources_are_valid(self):
        self.assertEqual(provenance.check_sources(load_repo()), [])

    def test_good_import_passes(self):
        self.assertEqual(self.codes(corpus_source()), set())

    def test_personal_data_rejected(self):
        s = corpus_source()
        s["personal_data"]["contains_personal_data"] = True
        self.assertIn("PRIVACY", self.codes(s))

    def test_import_needs_checksum_and_retrieval_date(self):
        s = corpus_source()
        del s["origin"]["artifact_sha256"]
        self.assertIn("PROVENANCE", self.codes(s))

    def test_import_needs_legal_review(self):
        s = corpus_source()
        s["review"]["legal"] = "pending"
        self.assertIn("LICENSE", self.codes(s))

    def test_pending_license_cannot_be_redistributable(self):
        s = corpus_source()
        s["license"] = {"spdx": "LicenseRef-x-pending", "redistribution": "allowed", "terms_note": "Pending decision."}
        self.assertIn("LICENSE", self.codes(s))

    def test_natural_names_need_legal_review(self):
        s = corpus_source()
        s["personal_data"]["name_origin"] = "naturally-occurring"
        s["review"]["legal"] = "pending"
        self.assertIn("PRIVACY", self.codes(s))

    def test_derived_labels_only_reference_may_cite_natural_names_but_incorporated_text_may_not(self):
        ref = reference_source(use="derived-labels-only",
                               personal_data={"contains_personal_data": False, "name_origin": "naturally-occurring", "notes": "Aggregate counts, labels only."})
        self.assertEqual(self.codes(ref), set())
        ref["use"] = "text-incorporated"
        ref["policy"].update(names_in_cases="replaced-with-synthetic", max_excerpt_chars=50, text_redistribution="allowed")
        ref["license"]["redistribution"] = "allowed"
        self.assertIn("PRIVACY", self.codes(ref))

    def test_derived_labels_only_sources_do_not_restrict_redistribution(self):
        ref = reference_source(id="src/ref-test", use="derived-labels-only")
        authored = copy.deepcopy(load_repo().sources[0])
        authored["license"]["redistribution"] = "allowed"
        authored["license"]["spdx"] = "CC0-1.0"
        self.repo.sources = [authored, ref]
        self.repo.cases = [good_case(source_ids=[authored["id"], "src/ref-test"])]
        self.assertEqual(provenance.redistribution_level(self.repo), "allowed")

    def test_authored_cannot_use_real_names(self):
        s = copy.deepcopy(self.repo.sources[0])
        s["personal_data"]["name_origin"] = "public-figure"
        self.assertIn("PRIVACY", self.codes(s))

    def test_malformed_source_rejected(self):
        self.assertIn("SCHEMA", self.codes({"id": "src/x", "kind": "project-authored"}))

    def test_case_provenance(self):
        self.repo.sources = [x for x in load_repo().sources if x["id"] == "src/project-authored-synthetic"]
        self.assertEqual(provenance.check_case_provenance(self.repo), [])
        self.repo.cases = [good_case(source_ids=["src/missing"])]
        codes = {p.code for p in provenance.check_case_provenance(self.repo)}
        self.assertEqual(codes, {"PROVENANCE"})

    def test_evidence_class_must_match_source_kind(self):
        self.repo.sources = [corpus_source()]
        self.repo.cases = [good_case(source_ids=["src/example-corpus"])]  # authored-adversarial vs corpus
        self.assertTrue(provenance.check_case_provenance(self.repo))

    def test_unused_source_flagged(self):
        self.repo.cases = []
        self.assertTrue(provenance.check_case_provenance(self.repo))

    def test_public_gate_fails_while_internal_only(self):
        self.assertTrue(provenance.public_release_problems(load_repo()))
        self.assertEqual(provenance.public_release_problems(self._open_repo()), [])

    def _open_repo(self):
        r = load_repo()
        r.sources = [corpus_source()]
        return r


class PrivacyLint(unittest.TestCase):
    def test_event_ids_and_digests_are_not_card_numbers(self):
        self.assertEqual(privacy.scan_text('{"event_id":"ev-' + "4111111111111111" + '"}'), [])

    # Values are assembled at runtime so this file never contains a live-looking secret.
    def test_flags(self):
        cases = {
            "email-address": "contact " + "jane.doe" + "@" + "mailhost.com" + " now",
            "non-reserved-url": "see https://" + "intranet.corp.net/people.csv",
            "phone-like-number": "call " + "010-" + "1234-" + "5678" + " today",
            "korean-resident-registration-number": "id " + "900101" + "-" + "1234567",
            "us-ssn-like": "ssn " + "123-45-" + "6789",
            "payment-card-number": "card " + "4111 1111 " + "1111 1111",
            "public-ip-address": "host " + "8.8." + "8.8",
            "aws-access-key": "key " + "AKIA" + "ABCDEFGHIJKLMNOP",
            "private-key-block": "-----BEGIN " + "RSA PRIVATE KEY-----",
            "private-data-marker": "from the " + "customer export " + "file",
        }
        for rule, text in cases.items():
            self.assertIn(rule, privacy.scan_text(text), rule)

    def test_safe_values_pass(self):
        for text in [
            "noreply@example.invalid", "https://example.org/x", "ts=2026-01-01T00:00:00Z level=info",
            "192.0.2.10", "10.0.0.1", "Kim Min-su visited Seoul in May.", "김민수는 서울에 갔다.",
            "version 0.1.0 digest " + "a" * 64,
        ]:
            self.assertEqual(privacy.scan_text(text), [], text)

    def test_sha256_digests_are_not_flagged_but_digit_runs_still_are(self):
        digest = "1234567890123" + "a" * 51  # 64 hex chars containing a 13-digit run
        self.assertEqual(len(digest), 64)
        self.assertEqual(privacy.scan_text('{"case_digest": "%s"}' % digest), [])
        self.assertIn("phone-like-number", privacy.scan_text("call " + "010-1234-" + "5678"))

    def test_tree_rejects_dump_file_types_and_size(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "evidence").mkdir()
            (root / "evidence" / "names.csv").write_text("a,b\n")
            (root / "evidence" / "ok.json").write_text('{"a": "fine"}')
            rules = {f.rule for f in privacy.scan_tree(root)}
            self.assertEqual(rules, {"disallowed-file-type"})
            (root / "evidence" / "names.csv").unlink()
            (root / "evidence" / "big.json").write_text(" " * (privacy.MAX_FILE_BYTES + 1))
            self.assertEqual({f.rule for f in privacy.scan_tree(root)}, {"oversized-file"})

    def test_findings_do_not_echo_values(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "evidence").mkdir()
            secret = "AKIA" + "ABCDEFGHIJKLMNOP"
            (root / "evidence" / "x.json").write_text('{"a": "%s"}' % secret)
            out = "\n".join(str(f) for f in privacy.scan_tree(root))
            self.assertNotIn(secret, out)
            self.assertIn("x.json:1", out)

    def test_repository_is_clean(self):
        self.assertEqual(privacy.scan_tree(Path(__file__).resolve().parents[1]), [])


if __name__ == "__main__":
    unittest.main()
