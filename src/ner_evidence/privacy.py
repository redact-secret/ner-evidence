"""Privacy and safe-data lint.

Scans committed evidence for patterns that indicate real personal data or
secrets, and rejects file types that suggest a raw corpus dump. Findings never
echo the matched value, only the rule and location, so the lint itself cannot
spread what it finds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SCAN_DIRS = ("evidence", "projections", "taxonomy", "snapshots")
ALLOWED_SUFFIXES = {".json", ".jsonl", ".md"}
MAX_FILE_BYTES = 4 * 1024 * 1024

SAFE_EMAIL_DOMAINS = re.compile(r"(^|\.)(example\.(com|org|net)|[a-z0-9-]+\.(invalid|test|example|localhost))$", re.I)
SAFE_URL_HOSTS = SAFE_EMAIL_DOMAINS

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
URL = re.compile(r"https?://([^/\s\"'<>\\]+)", re.I)
PHONE = re.compile(r"(?<![\w.])\+?\d[\d ().-]{7,}\d(?![\w])")
KR_RRN = re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)")
US_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
SECRETS = {
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "slack-token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "api-key-like": re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
}
PROVENANCE_MARKERS = re.compile(r"(?i)\b(customer (list|export|data)|employee roster|internal use only|do not distribute|patient (record|name))\b")


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str

    def __str__(self) -> str:
        return f"[PRIVACY:{self.rule}] {self.where}"


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - (9 if d * 2 > 9 else 0)
        total += d
        alt = not alt
    return total % 10 == 0


def _public_ipv4(addr: str) -> bool:
    parts = [int(p) for p in addr.split(".")]
    if any(p > 255 for p in parts):
        return False
    a, b = parts[0], parts[1]
    if a in (10, 127, 0) or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31):
        return False
    if (a, b, parts[2]) in {(192, 0, 2), (198, 51, 100), (203, 0, 113)}:
        return False
    return True


def scan_text(text: str) -> list[str]:
    """Return rule names triggered by ``text`` (no matched values)."""
    rules: list[str] = []
    for m in EMAIL.finditer(text):
        if not SAFE_EMAIL_DOMAINS.search(m.group(1)):
            rules.append("email-address")
    for m in URL.finditer(text):
        host = m.group(1).split(":")[0]
        if not SAFE_URL_HOSTS.search(host):
            rules.append("non-reserved-url")
    for m in PHONE.finditer(text):
        if sum(ch.isdigit() for ch in m.group(0)) >= 9:
            rules.append("phone-like-number")
    if KR_RRN.search(text):
        rules.append("korean-resident-registration-number")
    if US_SSN.search(text):
        rules.append("us-ssn-like")
    for m in CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            rules.append("payment-card-number")
    for m in IPV4.finditer(text):
        if _public_ipv4(m.group(1)):
            rules.append("public-ip-address")
    for name, rx in SECRETS.items():
        if rx.search(text):
            rules.append(name)
    if PROVENANCE_MARKERS.search(text):
        rules.append("private-data-marker")
    return sorted(set(rules))


def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for d in SCAN_DIRS:
        base = root / d
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                findings.append(Finding("disallowed-file-type", rel))
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                findings.append(Finding("oversized-file", rel))
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for rule in scan_text(line):
                    findings.append(Finding(rule, f"{rel}:{lineno}"))
    return findings
