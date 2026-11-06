"""Deterministic text cleanup shared by adapters and normalizers."""

from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

# UTF-8 text that was decoded as Latin-1/cp1252 upstream shows up as a lead char
# (U+00C2-U+00F4) followed by 1-3 "continuation" chars: U+0080-U+00BF, or the cp1252
# characters that stand in for bytes 0x80-0x9F.
_CP1252_HIGH = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"  # noqa: RUF001
_CONT = f"[\u0080-¿{_CP1252_HIGH}]"
_MOJIBAKE = re.compile(f"[Â-ô]{_CONT}{{1,3}}")
_WS = re.compile(r"\s+")
_COMPANY_SUFFIX = re.compile(
    r"[\s,]+(?:inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|gmbh|ag|sa|sas|"
    r"bv|b\.v|pty|plc|oy|ab|srl|s\.r\.l|pte|kk)\.?$",
    re.IGNORECASE,
)


def _to_byte(ch: str) -> int:
    code = ord(ch)
    return code if code < 0x100 else ch.encode("cp1252")[0]


def _repair_sequence(match: re.Match[str]) -> str:
    seq = match.group(0)
    lead = ord(seq[0])
    need = 1 if lead < 0xE0 else 2 if lead < 0xF0 else 3
    head, tail = seq[: need + 1], seq[need + 1 :]
    if len(head) != need + 1:
        return seq
    try:
        return bytes(_to_byte(c) for c in head).decode("utf-8") + tail
    except (UnicodeDecodeError, UnicodeEncodeError):
        return seq


def fix_mojibake(text: str) -> str:
    """Undo UTF-8-read-as-Latin-1/cp1252, sequence by sequence.

    Only byte sequences that decode as valid UTF-8 are replaced, so correct text (and
    correct characters mixed into a broken line) is left alone.
    """
    return _MOJIBAKE.sub(_repair_sequence, text)


def clean_text(text: str | None) -> str | None:
    """Unescape HTML entities, repair mojibake, NFC-normalize, collapse whitespace."""
    if text is None:
        return None
    out = html.unescape(fix_mojibake(text))
    out = unicodedata.normalize("NFC", out)
    out = _WS.sub(" ", out).strip()
    return out or None


_BLOCK_TAGS = (
    "p", "div", "li", "ul", "ol", "tr", "table", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
)  # fmt: skip


def html_to_text(html_fragment: str | None) -> str | None:
    """HTML fragment -> plain text: block elements and <br> become line breaks, inline
    elements (<b>, <a>, <span>, ...) join their neighbours with no break."""
    if not html_fragment:
        return None
    soup = BeautifulSoup(html_fragment, "lxml")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(_BLOCK_TAGS):
        block.insert_before("\n")
        block.insert_after("\n")
    lines = (clean_text(line) for line in soup.get_text().splitlines())
    text = "\n".join(line for line in lines if line)
    return text or None


def normalize_title(title: str) -> str:
    """Lowercase, punctuation-light form used for fingerprints and fuzzy matching."""
    t = (clean_text(title) or "").lower()
    t = re.sub(r"[^\w+#./ ]+", " ", t)  # keep c++, c#, node.js, ci/cd
    return _WS.sub(" ", t).strip()


def normalize_company(name: str) -> str:
    """Stable key for companies.normalized_name: case-folded, no legal suffix."""
    n = (clean_text(name) or "").casefold()
    for _ in range(2):  # "Foo Pty Ltd"
        n = _COMPANY_SUFFIX.sub("", n).strip()
    n = re.sub(r"[^\w]+", " ", n)
    return _WS.sub(" ", n).strip()
