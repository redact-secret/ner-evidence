"""Machine check that authored Korean sentences use the right particle allomorph after each name span.

Korean particles alternate by whether the preceding syllable ends in a consonant
(batchim). Authoring such text by hand is error-prone and a wrong allomorph
makes the expectation unnatural, so the rule is verified mechanically.
"""

import re
import unittest

import helpers  # noqa: F401
from helpers import load_repo

# particle -> required batchim state of the preceding syllable ("C" consonant-final, "V" vowel-final)
RULES = {"은": "C", "는": "V", "이": "C", "가": "V", "을": "C", "를": "V", "과": "C", "와": "V",
         "이랑": "C", "랑": "V", "이라고": "C", "라고": "V", "이야": "C", "아": "C", "야": "V", "이나": "C",
         "이었": "C", "였": "V", "이든": "C", "든": "V", "이며": "C", "며": "V"}
# 으로/로: ㄹ-final syllables take 로 like vowel-final ones.
HANGUL = re.compile(r"[가-힣]")


def batchim(ch: str) -> int:
    return (ord(ch) - 0xAC00) % 28


class Particles(unittest.TestCase):
    def test_allomorphs(self):
        repo = load_repo()
        problems = []
        checked = 0
        for case in repo.cases:
            if case["language"] != "ko":
                continue
            text = case["text"]
            for e in case["expectations"]:
                if e["expect"] == "not-person":
                    continue
                last = text[e["end"] - 1]
                rest = text[e["end"]:]
                if not HANGUL.match(last) or not rest:
                    continue
                state = "C" if batchim(last) else "V"
                m = re.match(r"(이랑|이라고|이었|이든|이야|이나|이며|으로|[은는이가을를과와랑라고야아였든며로])", rest)
                if not m:
                    continue
                p = m.group(1)
                if p in ("으로", "로"):
                    want = "V" if (state == "V" or batchim(last) == 8) else "C"
                    ok = (p == "로") == (want == "V")
                    checked += 1
                    if not ok:
                        problems.append(f"{case['id']}: {e['surface']}+{p}")
                    continue
                if p in ("라고", "고"):
                    continue
                if p in RULES:
                    checked += 1
                    if RULES[p] != state:
                        problems.append(f"{case['id']}: {e['surface']}+{p} (name ends {'with' if state == 'C' else 'without'} a final consonant)")
        self.assertGreater(checked, 100)
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
