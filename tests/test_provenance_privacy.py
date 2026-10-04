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
        "version": "2024-01", "as_of": "2024-01-01",
        "origin": {"type": "url", "locator": "https://example.org/corpus", "artifact_sha256": "0" * 64, "retrieved_on": "2024-01-02"},
        "license": {"spdx": "CC-BY-4.0", "redistribution": "allowed", "terms_note": "Attribution required."},
        "personal_data": {"contains_personal_data": False, "name_origin": "synthetic", "notes": "Synthetic names only."},
        "transformations": ["none"], "known_bias": ["Test-only corpus with no coverage claims."],
        "review": {"provenance": "independently-reviewed", "legal": "independently-reviewed"},
    }
    for k, v in over.items():
        src[k] = v
    return src


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

    def test_authored_cannot_use_real_names(self):
        s = copy.deepcopy(self.repo.sources[0])
        s["personal_data"]["name_origin"] = "public-figure"
        self.assertIn("PRIVACY", self.codes(s))

    def test_malformed_source_rejected(self):
        self.assertIn("SCHEMA", self.codes({"id": "src/x", "kind": "project-authored"}))

    def test_case_provenance(self):
        self.repo.sources = load_repo().sources
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
