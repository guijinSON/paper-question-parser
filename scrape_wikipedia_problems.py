#!/usr/bin/env python3
"""Scrape open/solved science problems from Wikipedia 'List of unsolved problems in X' pages."""

import json
import re
import subprocess
import time
from pathlib import Path

from bs4 import BeautifulSoup, Tag

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
OUT_JSONL = Path("outputs/wikipedia_problems.jsonl")

PAGES = [
    (
        "mathematics",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_mathematics",
    ),
    ("physics", "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_physics"),
    ("biology", "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_biology"),
    (
        "chemistry",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_chemistry",
    ),
    (
        "neuroscience",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_neuroscience",
    ),
    (
        "geoscience",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_geoscience",
    ),
    (
        "astronomy",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_astronomy",
    ),
    (
        "statistics",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_statistics",
    ),
    (
        "fair_division",
        "https://en.wikipedia.org/wiki/List_of_unsolved_problems_in_fair_division",
    ),
]

# Section headings that mean we should stop collecting problems
SKIP_SECTION_RE = re.compile(
    r"^(see also|references|notes|further reading|external links|"
    r"books discussing|bibliography|footnotes|citations|"
    r"notable lists|notebooks|recently solved|"
    r"books discussing problems solved)",
    re.I,
)

# Section headings that indicate the problems listed are already solved
SOLVED_SECTION_RE = re.compile(
    r"(solved since|solved in the past|recently solved|problems solved|rapidly solved)",
    re.I,
)

# Inline text signals that a specific problem was solved
INLINE_SOLVED_RE = re.compile(
    r"\b(solved by|proved by|proven by|resolved by|disproved by|"
    r"was solved|was proved|was proven|was resolved|was disproved|"
    r"has been solved|has been proved|has been proven)\b",
    re.I,
)

CITATION_RE = re.compile(r"\[\s*\d+\s*\]")
WHITESPACE_RE = re.compile(r"\s+")


def fetch(url: str) -> str:
    result = subprocess.run(
        ["curl", "-s", "-L", "-A", UA, url],
        capture_output=True,
        text=True,
    )
    return result.stdout


def clean_text(text: str) -> str:
    text = CITATION_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def heading_text(elem: Tag) -> str:
    """Return heading text with [edit] spans removed."""
    for span in elem.find_all("span", class_="mw-editsection"):
        span.decompose()
    return elem.get_text(" ", strip=True)


def parse_page(html: str, field: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return []

    problems: list[dict] = []
    current_category: str | None = None
    section_solved = False
    h2_solved = False  # tracks whether the enclosing h2 section is a solved section
    skip = False

    for elem in content.find_all(["h2", "h3", "ul", "ol"]):
        if not isinstance(elem, Tag):
            continue

        if elem.name in ("h2", "h3"):
            text = heading_text(elem)

            if SKIP_SECTION_RE.search(text):
                skip = True
                current_category = None
                if elem.name == "h2":
                    h2_solved = False
                continue

            skip = False

            if elem.name == "h2":
                h2_solved = bool(SOLVED_SECTION_RE.search(text))
                section_solved = h2_solved
            else:
                # h3: inherit h2 solved status unless the h3 itself signals solved
                section_solved = h2_solved or bool(SOLVED_SECTION_RE.search(text))

            current_category = text

        elif elem.name in ("ul", "ol") and not skip and current_category:
            # Only take direct <li> children to avoid double-counting nested lists
            for li in elem.find_all("li", recursive=False):
                # Skip nested list markers that are just blank or very short
                raw = clean_text(li.get_text(" ", strip=True))
                if len(raw) < 20:
                    continue

                # Inline solved signal overrides the section flag
                inline_solved = bool(INLINE_SOLVED_RE.search(raw))

                problems.append(
                    {
                        "problem": raw,
                        "field": field,
                        "category": current_category,
                        "solved": section_solved or inline_solved,
                    }
                )

    return problems


def main() -> None:
    all_problems: list[dict] = []

    for field, url in PAGES:
        print(f"Fetching {field} ...", flush=True)
        html = fetch(url)
        print(f"  {len(html):,} bytes", flush=True)
        probs = parse_page(html, field)
        solved_n = sum(1 for p in probs if p["solved"])
        print(
            f"  {len(probs)} problems ({solved_n} solved, {len(probs)-solved_n} unsolved)",
            flush=True,
        )
        all_problems.extend(probs)
        time.sleep(0.5)

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for p in all_problems:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    total_solved = sum(1 for p in all_problems if p["solved"])
    print(
        f"\nTotal: {len(all_problems)} problems "
        f"({total_solved} solved, {len(all_problems)-total_solved} unsolved)"
    )
    print(f"Saved to {OUT_JSONL}")


if __name__ == "__main__":
    main()
