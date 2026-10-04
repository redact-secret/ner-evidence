"""Derived name-frequency bands from registered public reference tables.

The raw tables are not committed (policy: no raw corpora, tables or dumps). A reviewer who downloads the exact
registered artifacts can re-derive ``evidence/references/name-frequency-bands.json`` with
``python -m ner_evidence references verify``; the repository gates only check that the committed bands are
consistent with the cases that cite them.
"""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

from . import canonical
from .repo import Problem, Repo

EN_SOURCE = "src/ref-us-census-2010-surnames"
KO_SOURCE = "src/ref-ko-surname-population-2015"
EN_COMMON_MAX_RANK = 1000
KO_COMMON_MIN_SHARE = 0.005
RULES = {
    EN_SOURCE: {
        "common": "The normalized surname has rank 1000 or better in the 2010 Census surname table (the published Top 1,000).",
        "rare": "The normalized surname is in the table (100 or more occurrences) but ranks below 1000.",
        "novel": "The normalized surname is absent from the table (fewer than 100 occurrences in the 2010 Census).",
        "normalization": "Unicode NFKD, combining marks removed, lowercase, only the letters a-z kept (so O'Brien and Al-Rashid become obrien and alrashid, as in the table).",
    },
    KO_SOURCE: {
        "common": "The surname is listed and held by at least 0.5% of the 2015 South Korean population (49,705,663 in the table note).",
        "rare": "The surname is listed with a population share below 0.5%.",
        "novel": "Not derivable: the transcription lists only part of the surnames in use, so absence from it proves nothing; no Korean case uses this band.",
        "normalization": "The Hangul surname string exactly as listed (one or two syllables); no normalization.",
    },
}


def normalize_en(s: str) -> str:
    folded = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in folded if not unicodedata.combining(c)).lower())


def load_census(zip_path: Path) -> dict[str, int]:
    """Read Names_2010Census.csv from the registered names.zip."""
    ranks: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as z:
        text = io.TextIOWrapper(z.open("Names_2010Census.csv"), encoding="utf-8", newline="")
        for row in csv.DictReader(text):
            if row["name"] == "ALL OTHER NAMES" or not row["rank"].isdigit():
                continue
            ranks[row["name"].lower()] = int(row["rank"])
    return ranks


def load_kosis_wikitext(path: Path) -> tuple[dict[str, int], int]:
    text = path.read_text(encoding="utf-8")
    total = int(re.search(r"total population was ([\d,]+)", text).group(1).replace(",", ""))
    start = text.find('{| class="wikitable')
    table = text[start:text.find("\n|}", start)]
    out: dict[str, int] = {}
    for row in table.split("\n|-")[1:]:
        cells = [c.strip() for c in row.strip().lstrip("|").split(" || ")]
        if len(cells) < 6:
            continue
        m = re.search(r"\{\{lang\|ko\|([^}]+)\}\}", cells[0])
        pop = re.sub(r"[^0-9]", "", cells[5].split("{{")[0])
        if m and pop:
            out[m.group(1)] = int(pop)
    return out, total


def band_en(component: str, ranks: dict[str, int]) -> str:
    rank = ranks.get(normalize_en(component))
    if rank is None:
        return "novel"
    return "common" if rank <= EN_COMMON_MAX_RANK else "rare"


def band_ko(component: str, pops: dict[str, int], total: int) -> str | None:
    if component not in pops:
        return None
    return "common" if pops[component] / total >= KO_COMMON_MIN_SHARE else "rare"


def cited_components(repo: Repo) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for c in repo.cases:
        ref = c["dimensions"].get("familiarity_reference")
        if ref:
            out.setdefault(ref["source_id"], set()).add(ref["component"])
    return out


def check_artifact(repo: Repo, source_id: str, path: Path) -> list[Problem]:
    src = next((s for s in repo.sources if s["id"] == source_id), None)
    if src is None:
        return [Problem("REFERENCE", source_id, "source is not registered")]
    want = src["origin"].get("artifact_sha256")
    got = canonical.sha256_hex(path.read_bytes())
    return [] if got == want else [Problem("REFERENCE", source_id, f"{path} sha256 {got} != registered {want}")]


def derive(repo: Repo, census_zip: Path, kosis_wikitext: Path) -> tuple[dict, list[Problem]]:
    probs = check_artifact(repo, EN_SOURCE, census_zip) + check_artifact(repo, KO_SOURCE, kosis_wikitext)
    ranks = load_census(census_zip)
    pops, total = load_kosis_wikitext(kosis_wikitext)
    cited = cited_components(repo)
    refs = []
    for sid, lang in ((EN_SOURCE, "en"), (KO_SOURCE, "ko")):
        entries = {}
        for comp in sorted(cited.get(sid, ())):
            b = band_en(comp, ranks) if lang == "en" else band_ko(comp, pops, total)
            if b is None:
                probs.append(Problem("REFERENCE", sid, f"{comp!r} is not derivable from the reference"))
            else:
                entries[comp] = b
        refs.append({"source_id": sid, "language": lang, "component_type": "surname", "rules": RULES[sid], "entries": entries})
    return {"bands_version": "1.0.0", "references": refs}, probs


def audit(repo: Repo, census_zip: Path, kosis_wikitext: Path) -> dict:
    """Informational: compare author-judged labels with the surname band. Disagreement is not an error."""
    ranks = load_census(census_zip)
    pops, total = load_kosis_wikitext(kosis_wikitext)
    out = {"en": {}, "ko": {}, "skipped": 0}
    for c in repo.cases:
        d = c["dimensions"]
        focus = c["expectations"][c["focus_span"]]
        if d["familiarity"] == "not-applicable" or focus["expect"] == "not-person" or d.get("familiarity_basis") == "reference-frequency":
            continue
        if c["language"] == "en":
            toks = [t for t in re.sub(r"[.,]", " ", focus["surface"]).split() if t.lower() not in {"jr", "sr", "ii", "iii", "dr", "mr", "ms", "mrs", "prof"}]
            if len(toks) < 2:
                out["skipped"] += 1
                continue
            band = band_en(toks[-1], ranks)
        else:
            hangul = re.match(r"[가-힣]+", focus["surface"])
            if not hangul or "ko-given-only" in d["name_features"]:
                out["skipped"] += 1
                continue
            word = hangul.group(0)
            band = band_ko(word[:2] if len(word) >= 4 and word[:2] in pops else word[:1], pops, total)
            if band is None:
                out["skipped"] += 1
                continue
        key = f"{d['familiarity']} labelled / {band} by reference"
        out[c["language"]][key] = out[c["language"]].get(key, 0) + 1
    return out


def check_bands(repo: Repo) -> list[Problem]:
    """Gate: committed bands are well-formed, and every entry is cited by a case (minimization)."""
    probs: list[Problem] = []
    if not repo.bands:
        return [Problem("REFERENCE", "name-frequency-bands", "evidence/references/name-frequency-bands.json is missing")]
    registered = {s["id"]: s for s in repo.sources}
    cited = cited_components(repo)
    for ref in repo.bands.get("references", []):
        sid = ref["source_id"]
        src = registered.get(sid)
        if src is None or src["kind"] != "reference":
            probs.append(Problem("REFERENCE", sid, "band table must belong to a registered source of kind 'reference'"))
        for comp in ref["entries"]:
            if comp not in cited.get(sid, set()):
                probs.append(Problem("REFERENCE", sid, f"entry {comp!r} is cited by no case; remove it (bands are minimized to what cases use)"))
    return probs


def register(sub) -> None:
    p = sub.add_parser("references", help="derive / verify / audit name-frequency bands from the registered reference artifacts")
    p.add_argument("action", choices=["derive", "verify", "audit", "check"])
    p.add_argument("--census-zip", help="the registered Census names.zip (verified by sha256)")
    p.add_argument("--kosis-wikitext", help="raw wikitext of the registered Wikipedia revision")
    p.add_argument("--write", action="store_true", help="derive: write evidence/references/name-frequency-bands.json")
    p.set_defaults(fn=cmd_references)


def cmd_references(args) -> int:
    from . import repo as repo_mod
    repo = repo_mod.load(Path(args.root) if args.root else None)
    if args.action == "check":
        probs = check_bands(repo)
        for p in probs:
            print(p)
        print(f"references: {sum(len(r['entries']) for r in repo.bands.get('references', []))} derived bands, {len(probs)} problems")
        return 1 if probs else 0
    if not (args.census_zip and args.kosis_wikitext):
        print("this action needs --census-zip and --kosis-wikitext (the registered artifacts; see the source records)")
        return 2
    if args.action == "audit":
        print(json.dumps(audit(repo, Path(args.census_zip), Path(args.kosis_wikitext)), indent=2, ensure_ascii=False))
        return 0
    bands, probs = derive(repo, Path(args.census_zip), Path(args.kosis_wikitext))
    for p in probs:
        print(p)
    path = repo.root / "evidence" / "references" / "name-frequency-bands.json"
    text = canonical.pretty(bands)
    if args.action == "derive" and args.write and not probs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(repo.root)}")
        return 0
    if args.action == "verify":
        same = path.exists() and path.read_text(encoding="utf-8") == text
        if not same:
            print("[REFERENCE] committed bands differ from the bands derived from the registered artifacts")
        print(f"references verify: {len(probs)} problems, {'identical' if same else 'DIFFERENT'}")
        return 0 if (same and not probs) else 1
    print(text, end="")
    return 1 if probs else 0
