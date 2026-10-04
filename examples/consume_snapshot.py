#!/usr/bin/env python3
"""Reference consumer of a ner-evidence snapshot, using ONLY the published contract.

Imports nothing from ner_evidence and reads nothing outside the snapshot directory.
Usage: python consume_snapshot.py <snapshot-dir> [--expect-id ID]
Implements docs/snapshot-and-consumer-contract.md: verification steps 1-5, then
iterates fixtures joined to cases and prints a per-slice inventory (no scoring).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def fail(msg):
    print("REJECTED:", msg)
    sys.exit(1)


def main():
    snap = Path(sys.argv[1])
    expect = sys.argv[sys.argv.index("--expect-id") + 1] if "--expect-id" in sys.argv else None
    m = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    if m["manifest_version"] != "0.1.0" or m["consumer_contract_version"] != "0.1.0":
        fail("unsupported contract version")
    listed = {f["path"]: f for f in m["files"]}
    on_disk = {p.relative_to(snap).as_posix() for p in snap.rglob("*") if p.is_file()} - {"manifest.json"}
    if on_disk != set(listed):
        fail(f"file set differs from manifest: {sorted(on_disk ^ set(listed))}")
    for path, f in listed.items():
        data = (snap / path).read_bytes()
        if len(data) != f["bytes"] or hashlib.sha256(data).hexdigest() != f["sha256"]:
            fail(f"digest mismatch: {path}")
    h = hashlib.sha256(b"ner-evidence-snapshot-digest/1\n")
    for f in sorted(m["files"], key=lambda f: f["path"]):
        h.update(f"{f['sha256']}  {f['path']}\n".encode("utf-8"))
    if h.hexdigest() != m["content_digest"]:
        fail("content_digest mismatch")
    if m["snapshot_id"] != f"{m['scope']}-{m['release_label']}-{m['content_digest'][:12]}":
        fail("snapshot_id is not derived from content_digest")
    if expect and m["snapshot_id"] != expect:
        fail(f"pinned {expect} but found {m['snapshot_id']}")

    cases = {}
    for line in (snap / "cases.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        cases[c["id"]] = c
    n_fx, slices = 0, Counter()
    for line in (snap / "fixtures.jsonl").read_text(encoding="utf-8").splitlines():
        fx = json.loads(line)
        case = cases[fx["case_id"]]  # join by case_id
        text = fx["text"]
        for sp in fx["spans"]:
            assert text[sp["start"]:sp["end"]] == sp["surface"]
            assert text.encode("utf-8")[sp["utf8_start"]:sp["utf8_end"]].decode("utf-8") == sp["surface"]
            assert text.encode("utf-16-le")[2 * sp["utf16_start"]:2 * sp["utf16_end"]].decode("utf-16-le") == sp["surface"]
        n_fx += 1
        slices[(fx["language"], case["ambiguity"]["level"])] += 1
    if (len(cases), n_fx) != (m["counts"]["cases"], m["counts"]["fixtures"]):
        fail("counts differ from manifest")
    print(f"ACCEPTED {m['snapshot_id']} cases={len(cases)} fixtures={n_fx} redistribution={m['redistribution']}")
    for (lang, level), n in sorted(slices.items()):
        print(f"  {lang} {level}: {n} fixtures")


if __name__ == "__main__":
    main()
