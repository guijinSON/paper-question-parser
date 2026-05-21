"""Keyword counters for reasoning traces.

This module intentionally does not score or classify hallucinations. It only
extracts answer-like candidates and counts keyword groups that may be useful
for downstream analysis in a notebook.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


MISSING_INFO_TERMS = (
    "not enough information",
    "insufficient information",
    "lack of information",
    "without knowing",
    "without specific",
    "without the specific",
    "without actual",
    "not provided",
    "cannot compute",
    "can't compute",
    "cannot determine",
    "impossible to know",
    "impossible to determine",
)

GUESS_TERMS = (
    "i will go with",
    "i'll go with",
    "i will choose",
    "i'll choose",
    "let's guess",
    "i will assume",
    "i'll assume",
    "more likely intended",
    "likely intended",
    "most likely",
    "stick with",
    "robust choice",
    "standard fit",
)

HEDGING_TERMS = (
    "maybe",
    "perhaps",
    "probably",
    "likely",
    "seems",
    "not sure",
    "unsure",
    "unclear",
    "i think",
    "i suspect",
    "i guess",
)

SELF_CORRECTION_TERMS = (
    "wait",
    "hold on",
    "actually",
    "recheck",
    "re-check",
    "re-evaluate",
    "re-evaluating",
    "let me check again",
    "double check",
    "that can't be",
    "that cannot be",
    "doesn't make sense",
    "does not make sense",
)

GIVE_UP_TERMS = (
    "lack of progress",
    "given the time",
    "time constraints",
    "too complex",
    "not practical manually",
    "i'm stuck",
    "i am stuck",
    "dead end",
    "can't solve",
    "cannot solve",
    "without progress",
    "hazard a guess",
    "educated guess",
)

UNPROVEN_CLAIM_TERMS = (
    "it can be shown",
    "one can show",
    "it is easy to see",
    "clearly",
    "obviously",
    "intuitively",
    "by symmetry",
    "must be",
    "should be",
)

INCOMPLETE_DERIVATION_TERMS = (
    "skip",
    "omit",
    "not derive",
    "without deriving",
    "i won't derive",
    "leave it",
    "not going to compute",
    "too long to compute",
)

FORMULA_MEMORY_TERMS = (
    "i don't remember",
    "i do not remember",
    "don't remember the exact",
    "do not remember the exact",
    "remember the exact",
    "recall a formula",
    "from memory",
    "not sure of the formula",
    "not sure about the formula",
)

SOURCE_REFERENCE_TERMS = (
    "paper",
    "book",
    "article",
    "textbook",
    "monograph",
    "survey",
    "journal",
    "proceedings",
    "publication",
    "arxiv",
    "doi",
    "wikipedia",
    "mathworld",
    "oeis",
    "stackexchange",
    "aops",
    "art of problem solving",
    "website",
    "webpage",
    "online source",
)

UNSUPPORTED_TERMS = (
    "known result",
    "standard result",
    "i remember",
    "similar problem online",
    "look it up mentally",
    "the problem implies",
    "strongly suggests",
    "well-known",
    "it is known",
    "i recall",
)

FINAL_PHRASE_RE = re.compile(
    r"(?im)^\s*(?:[*_`#>\-\d.)\s]*)?"
    r"(?:final answer|answer|final decision|therefore,?\s+the answer is|"
    r"so,?\s+the answer is|the answer is|i will (?:choose|go with|stick with))"
    r"\s*[:\-]?\s*(?P<value>.{1,180})$"
)

BOX_RE = re.compile(r"\\boxed\{(?P<value>[^{}]{1,180})\}")


def _clean_candidate(value: str) -> str:
    value = re.sub(r"\\boxed\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\(?:textbf|text|mathrm)\{([^{}]*)\}", r"\1", value)
    value = value.strip()
    value = value.split("\n", 1)[0]
    value = re.sub(r"^[\s:=$`*_\-]+|[\s`*_]+$", "", value)
    value = value.strip(". ")

    # Keep only the answer-like prefix if the line continues into prose.
    stop_match = re.search(r"\s+(?:because|since|where|which|so the|as the)\b", value, re.I)
    if stop_match:
        value = value[: stop_match.start()].strip()

    value = re.sub(r"\s+", " ", value)
    return value[:180]


def _norm_candidate(value: str) -> str:
    value = _clean_candidate(value).lower()
    value = re.sub(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"\1/\2", value)
    value = re.sub(r"[{}$\\]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _ground_truth_answer(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    source_row = row.get("source_row") or {}
    nested_metadata = metadata.get("metadata") or {}
    for value in (
        metadata.get("answer"),
        metadata.get("Answer"),
        nested_metadata.get("answer"),
        source_row.get("answer"),
    ):
        if value not in (None, ""):
            return str(value)
    return ""


def _answer_fingerprint(value: str) -> str:
    value = _norm_candidate(value)
    value = value.replace("left", "").replace("right", "")
    value = re.sub(r"\\(?:frac|dfrac)\s*([^{}\s]+)\s*([^{}\s]+)", r"\1/\2", value)
    value = re.sub(r"[^a-z0-9./+\-\[\],()]", "", value)
    return value


def _rough_answer_match(candidate: str, truth: str) -> bool:
    candidate_fp = _answer_fingerprint(candidate)
    truth_fp = _answer_fingerprint(truth)
    if not candidate_fp or not truth_fp:
        return False
    if candidate_fp == truth_fp:
        return True
    # For very short answers, substring matching is too permissive: "1" would
    # match "194". For longer exact expressions, formatting wrappers vary.
    if len(truth_fp) >= 5 and truth_fp in candidate_fp:
        return True
    if len(candidate_fp) >= 5 and candidate_fp in truth_fp:
        return True
    return False


def extract_answer_candidates(reasoning: str, tail_chars: int = 16000) -> list[str]:
    """Extract answer-like candidates from the tail of a reasoning trace."""

    tail = reasoning[-tail_chars:]
    candidates: list[str] = []

    for match in BOX_RE.finditer(tail):
        candidate = _norm_candidate(match.group("value"))
        if candidate:
            candidates.append(candidate)

    for match in FINAL_PHRASE_RE.finditer(tail):
        candidate = _norm_candidate(match.group("value"))
        if not candidate:
            continue
        if len(candidate) > 120:
            continue
        # Avoid lines like "answer is not directly computable".
        if re.search(r"\b(problem asks|not directly|unknown|unclear)\b", candidate):
            continue
        candidates.append(candidate)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _count_terms(text_lower: str, terms: tuple[str, ...]) -> int:
    return sum(text_lower.count(term) for term in terms)


def _term_counts(text_lower: str, terms: tuple[str, ...]) -> dict[str, int]:
    return {term: count for term in terms if (count := text_lower.count(term))}


def _count_numbered_result_references(text_lower: str) -> int:
    return len(re.findall(r"\b(?:theorem|lemma|proposition|corollary)\s+\d", text_lower))


INT_PATTERN = r"(?<![\d.])(?<!\d,)[-+]?\d+(?!\d|[.,]\d)"
SUM_INT_PATTERN = r"(?<![A-Za-z\d.^*/_{])(?<!\d,)-?\d+(?!\d|[.,]\d)"
M_ASSIGN_RE = re.compile(rf"\bm\s*=\s*(?P<value>{INT_PATTERN})\b", re.I)
N_ASSIGN_RE = re.compile(rf"\bn\s*=\s*(?P<value>{INT_PATTERN})\b", re.I)
M_PLUS_N_CLAIM_RE = re.compile(
    rf"\bm\s*\+\s*n\s*=\s*"
    rf"(?:{INT_PATTERN}\s*\+\s*{INT_PATTERN}\s*=\s*)?"
    rf"(?:\\boxed\s*\{{)?(?P<claimed>{INT_PATTERN})(?:\}})?"
    rf"(?!\s*[/+*^=]|\s*[A-Za-z_(])",
    re.I,
)
DIRECT_SUM_RE = re.compile(
    rf"(?<![A-Za-z+\-\d.,^*/_{{])(?P<a>{SUM_INT_PATTERN})\s*\+\s*(?P<b>{SUM_INT_PATTERN})\s*=\s*(?P<claimed>{SUM_INT_PATTERN})\b"
)
M_PLUS_N_CONTEXT_RE = re.compile(r"\bm\s*\+\s*n\b", re.I)
FRACTION_RE = re.compile(
    rf"\\d?frac\s*\{{(?P<numerator>{INT_PATTERN})\}}\s*\{{(?P<denominator>{INT_PATTERN})\}}"
)
PLAIN_FRACTION_RE = re.compile(
    rf"(?<![\d.])(?<!\d,)(?P<numerator>-?\d+)\s*/\s*(?P<denominator>-?\d+)(?!\d|[.,]\d)"
)
REPETITION_TOKEN_RE = re.compile(r"[a-z0-9_\\]+")


def _snippet(text: str, start: int, end: int, padding: int = 80) -> str:
    left = max(0, start - padding)
    right = min(len(text), end + padding)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def _assignment_matches(pattern: re.Pattern[str], text: str) -> list[re.Match[str]]:
    """Return assignments, excluding the n=... substring inside m+n=...."""

    matches = []
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 12) : match.start()]
        if re.search(r"\+\s*$", prefix):
            continue
        matches.append(match)
    return matches


def _find_bad_arithmetic_sums(text: str) -> list[dict[str, Any]]:
    """Find simple bad final-sum arithmetic such as m=100, n=13, m+n=114."""

    issues: list[dict[str, Any]] = []

    for match in M_PLUS_N_CLAIM_RE.finditer(text):
        prefix = text[max(0, match.start() - 1000) : match.start()]
        m_matches = _assignment_matches(M_ASSIGN_RE, prefix)
        n_matches = _assignment_matches(N_ASSIGN_RE, prefix)
        if not m_matches or not n_matches:
            continue
        assignment_start = min(m_matches[-1].start(), n_matches[-1].start())
        if M_PLUS_N_CLAIM_RE.search(prefix[assignment_start:]):
            continue
        m_value = int(m_matches[-1].group("value"))
        n_value = int(n_matches[-1].group("value"))
        claimed = int(match.group("claimed"))
        local_context = text[max(0, match.start() - 220) : match.end() + 220].lower()
        if any(term in local_context for term in ("impossible", "suppose", "matrix")):
            continue
        expected = m_value + n_value
        if expected != claimed:
            issues.append(
                {
                    "type": "m_plus_n",
                    "m": m_value,
                    "n": n_value,
                    "claimed": claimed,
                    "expected": expected,
                    "snippet": _snippet(text, match.start(), match.end()),
                }
            )

    for match in DIRECT_SUM_RE.finditer(text):
        # Avoid double-counting the numeric side of "m+n = a+b = c".
        nearby_prefix = text[max(0, match.start() - 20) : match.start()]
        # Avoid treating the last two terms of a longer sum as a standalone
        # two-term equality, e.g. "90 + 24 + 1 = 115".
        if re.search(r"[+\-\u2212]\s*$", nearby_prefix):
            continue
        if re.search(r"(?:\\(?:cdot|times)|[* /^]|\u00b7)\s*$", nearby_prefix):
            continue
        previous_nonspace = re.search(r"\S\s*$", nearby_prefix)
        if previous_nonspace and not previous_nonspace.group(0).strip().isascii():
            continue
        if previous_nonspace and previous_nonspace.group(0).strip() in ("\u221a", "\u00b7"):
            continue
        if previous_nonspace and previous_nonspace.group(0).strip() in "0123456789)]}":
            continue
        nearby_suffix = text[match.end() : match.end() + 20]
        if re.match(r"\s*(?:[+\-*/^=()]|[A-Za-z_\\])", nearby_suffix):
            continue
        if re.search(r"\bm\s*\+\s*n\s*=\s*$", nearby_prefix, re.I):
            continue
        a_value = int(match.group("a"))
        b_value = int(match.group("b"))
        claimed = int(match.group("claimed"))
        local_context = text[max(0, match.start() - 220) : match.end() + 220].lower()
        if any(term in local_context for term in ("\\equiv", " mod ", "modulo", "congruent")):
            continue
        if any(term in local_context for term in ("would need", "we'd need", "contradiction", "impossible", "if i say")):
            continue
        if any(
            term in local_context
            for term in (
                "pattern",
                "operation",
                "equation",
                "matches",
                "second:",
                "third:",
                "fourth:",
                "eq ",
                "case",
                "hypothesis",
                "attempt",
                "digits",
                "outputs",
                "puzzle",
                "rule",
                "specific",
                "offset",
                "first number",
                "formula",
                "expression:",
                "look at",
                "notice",
                "where does",
                "target",
                "product",
                "cubes",
                "concatenate",
                "q(",
                "for instance",
                "proof says",
                "\\in",
                "\\frac",
                "\u2208",
            )
        ):
            continue
        if max(abs(a_value), abs(b_value), abs(claimed)) <= 2:
            continue
        expected = a_value + b_value
        if expected != claimed:
            issues.append(
                {
                    "type": "direct_sum",
                    "a": a_value,
                    "b": b_value,
                    "claimed": claimed,
                    "expected": expected,
                    "snippet": _snippet(text, match.start(), match.end()),
                }
            )

    return issues


def _find_bad_fraction_sums(text: str, context_text: str) -> list[dict[str, Any]]:
    """Find final fraction a/b paired with a bad m+n claim."""

    issues: list[dict[str, Any]] = []
    if not M_PLUS_N_CONTEXT_RE.search(context_text):
        return issues

    for claim_match in M_PLUS_N_CLAIM_RE.finditer(text):
        prefix = text[max(0, claim_match.start() - 600) : claim_match.start()]
        m_matches = _assignment_matches(M_ASSIGN_RE, prefix)
        n_matches = _assignment_matches(N_ASSIGN_RE, prefix)
        if not m_matches or not n_matches:
            continue
        m_value = int(m_matches[-1].group("value"))
        n_value = int(n_matches[-1].group("value"))
        assignment_start = min(m_matches[-1].start(), n_matches[-1].start())
        fraction_prefix = prefix[:assignment_start]
        fraction_candidates: list[tuple[int, int, int, int]] = []
        for frac_match in FRACTION_RE.finditer(fraction_prefix):
            fraction_candidates.append(
                (
                    frac_match.start(),
                    frac_match.end(),
                    int(frac_match.group("numerator")),
                    int(frac_match.group("denominator")),
                )
            )
        for frac_match in PLAIN_FRACTION_RE.finditer(fraction_prefix):
            fraction_candidates.append(
                (
                    frac_match.start(),
                    frac_match.end(),
                    int(frac_match.group("numerator")),
                    int(frac_match.group("denominator")),
                )
            )
        if not fraction_candidates:
            continue
        frac_start, frac_end, numerator, denominator = max(fraction_candidates, key=lambda item: item[1])
        if denominator == 0 or numerator < 0 or denominator < 0:
            continue
        if assignment_start - frac_end > 220:
            continue
        if numerator != m_value or denominator != n_value:
            continue
        if M_PLUS_N_CLAIM_RE.search(prefix[assignment_start:]):
            continue
        claimed = int(claim_match.group("claimed"))
        expected = numerator + denominator
        if expected != claimed:
            start = max(0, claim_match.start() - 600) + frac_start
            issues.append(
                {
                    "numerator": numerator,
                    "denominator": denominator,
                    "claimed": claimed,
                    "expected": expected,
                    "snippet": _snippet(text, start, claim_match.end()),
                }
            )

    return issues


def _norm_repetition_unit(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _repetition_units(text: str, *, min_chars: int, line_mode: bool) -> list[str]:
    if line_mode:
        raw_units = text.splitlines()
    else:
        raw_units = re.split(r"(?<=[.!?])\s+|\n+", text)
    units = [_norm_repetition_unit(unit) for unit in raw_units]
    return [unit for unit in units if len(unit) >= min_chars]


def _top_repeated(counter: Counter[str]) -> tuple[str, int]:
    repeated = [(unit, count) for unit, count in counter.items() if count > 1]
    if not repeated:
        return "", 0
    return max(repeated, key=lambda item: (item[1], len(item[0])))


def _max_same_token_run(tokens: list[str]) -> tuple[str, int]:
    best_token = ""
    best_count = 0
    previous = None
    current_count = 0
    for token in tokens:
        if token == previous:
            current_count += 1
        else:
            previous = token
            current_count = 1
        if current_count > best_count:
            best_token = token
            best_count = current_count
    return best_token, best_count


def _tail_chunk_repeat_max(text: str) -> tuple[int, int]:
    tail = _norm_repetition_unit(text[-4000:])
    best_size = 0
    best_count = 0
    for size in (40, 80, 160, 320):
        chunks = [
            tail[index : index + size]
            for index in range(0, max(0, len(tail) - size + 1), size)
        ]
        if not chunks:
            continue
        count = max(Counter(chunks).values(), default=0)
        if count > best_count:
            best_size = size
            best_count = count
    return best_size, best_count


def count_repetition_metrics(reasoning: str, *, tail_chars: int = 24000) -> dict[str, Any]:
    """Return simple repetition metrics for one analyzed reasoning trace."""

    tail = reasoning[-tail_chars:]
    sentence_counts = Counter(_repetition_units(tail, min_chars=35, line_mode=False))
    line_counts = Counter(_repetition_units(tail, min_chars=20, line_mode=True))
    top_sentence, max_repeated_sentence_count = _top_repeated(sentence_counts)
    top_line, max_repeated_line_count = _top_repeated(line_counts)

    tokens = REPETITION_TOKEN_RE.findall(tail.lower())
    ngrams = [
        " ".join(tokens[index : index + 8])
        for index in range(max(0, len(tokens) - 7))
    ]
    ngram_counts = Counter(ngrams)
    top_ngram, max_repeated_8gram_count = _top_repeated(ngram_counts)
    same_token, max_same_token_run = _max_same_token_run(tokens)
    tail_chunk_size, tail_chunk_repeat_max = _tail_chunk_repeat_max(tail)
    unique_token_ratio = len(set(tokens)) / len(tokens) if tokens else 1.0

    repeated_sentence_count = sum(count - 1 for count in sentence_counts.values() if count > 1)
    repeated_line_count = sum(count - 1 for count in line_counts.values() if count > 1)
    low_unique_token_ratio = int(len(tokens) >= 300 and unique_token_ratio < 0.08)
    repeated_sentence_loop = int(repeated_sentence_count >= 20 or max_repeated_sentence_count >= 5)
    repeated_line_loop = int(repeated_line_count >= 20 or max_repeated_line_count >= 5)
    repeated_8gram_loop = int(max_repeated_8gram_count >= 50)
    same_token_loop = int(max_same_token_run >= 40)
    tail_chunk_loop = int(tail_chunk_repeat_max >= 5)
    any_repetition_loop = int(
        repeated_sentence_loop
        or repeated_line_loop
        or repeated_8gram_loop
        or same_token_loop
        or low_unique_token_ratio
        or tail_chunk_loop
    )

    repetition_counts = {
        "repeated_sentence_count": repeated_sentence_count,
        "max_repeated_sentence_count": max_repeated_sentence_count,
        "repeated_line_count": repeated_line_count,
        "max_repeated_line_count": max_repeated_line_count,
        "max_repeated_8gram_count": max_repeated_8gram_count,
        "max_same_token_run": max_same_token_run,
        "tail_chunk_repeat_max": tail_chunk_repeat_max,
        "low_unique_token_ratio": low_unique_token_ratio,
        "repeated_sentence_loop": repeated_sentence_loop,
        "repeated_line_loop": repeated_line_loop,
        "repeated_8gram_loop": repeated_8gram_loop,
        "same_token_loop": same_token_loop,
        "tail_chunk_loop": tail_chunk_loop,
        "any_repetition_loop": any_repetition_loop,
    }
    repetition_details = {
        "token_count": len(tokens),
        "unique_token_ratio": unique_token_ratio,
        "top_repeated_sentence": top_sentence[:220],
        "top_repeated_line": top_line[:220],
        "top_repeated_8gram": top_ngram[:220],
        "same_token": same_token,
        "tail_chunk_size": tail_chunk_size,
    }
    return {
        "repetition_counts": repetition_counts,
        "repetition_details": repetition_details,
    }


def count_reasoning_keywords(
    row_or_reasoning: dict[str, Any] | str,
    *,
    tail_chars: int = 24000,
) -> dict[str, Any]:
    """Return keyword counts for one JSONL row or reasoning string."""

    if isinstance(row_or_reasoning, str):
        row: dict[str, Any] = {}
        reasoning = row_or_reasoning
    else:
        row = row_or_reasoning
        reasoning = row.get("reasoning") or ""

    answer = row.get("answer")
    answer_text = "" if answer is None else str(answer)
    ground_truth = _ground_truth_answer(row)
    finish_reason = row.get("finish_reason")
    truncated = bool(row.get("truncated_by_max_tokens")) or finish_reason == "length"
    # In these JSONL files the top-level answer field is sometimes the whole
    # generated response, not a compact final answer. Treat prose-like answers
    # as additional trace text so repeated/contradictory finalization is caught.
    analysis_text = reasoning
    if len(answer_text) > 300:
        analysis_text = reasoning + "\n" + answer_text

    tail_lower = analysis_text[-tail_chars:].lower()

    candidates = extract_answer_candidates(analysis_text)
    compact_answer_candidates = list(candidates)
    if 0 < len(answer_text) <= 300:
        compact_answer_candidates.append(answer_text)

    keyword_groups = {
        "hedging": HEDGING_TERMS,
        "self_correction": SELF_CORRECTION_TERMS,
        "give_up": GIVE_UP_TERMS,
        "unproven_claim": UNPROVEN_CLAIM_TERMS,
        "incomplete_derivation": INCOMPLETE_DERIVATION_TERMS,
        "formula_memory": FORMULA_MEMORY_TERMS,
        "source_reference": SOURCE_REFERENCE_TERMS,
        "unsupported": UNSUPPORTED_TERMS,
    }
    group_counts = {
        group: _count_terms(tail_lower, terms)
        for group, terms in keyword_groups.items()
    }
    matched_terms = {
        group: _term_counts(tail_lower, terms)
        for group, terms in keyword_groups.items()
    }
    matched_terms = {group: counts for group, counts in matched_terms.items() if counts}
    numbered_result_reference_count = _count_numbered_result_references(tail_lower)
    answer_matches_metadata = None
    if ground_truth and compact_answer_candidates:
        answer_matches_metadata = any(
            _rough_answer_match(candidate, ground_truth)
            for candidate in compact_answer_candidates
        )
    check_tail = analysis_text
    problem_text = str(row.get("problem") or "")
    check_context = problem_text + "\n" + analysis_text
    bad_arithmetic_sums = _find_bad_arithmetic_sums(check_tail)
    bad_fraction_sums = _find_bad_fraction_sums(check_tail, check_context)
    deterministic_check_counts = {
        "truncated_no_answer": int(truncated and not candidates),
        "arithmetic_final_sum_check": len(bad_arithmetic_sums),
        "fraction_sum_check": len(bad_fraction_sums),
    }
    deterministic_check_details = {
        "arithmetic_final_sum_check": bad_arithmetic_sums[:8],
        "fraction_sum_check": bad_fraction_sums[:8],
    }
    repetition = count_repetition_metrics(analysis_text, tail_chars=tail_chars)

    return {
        "keyword_counts": group_counts,
        "matched_terms": matched_terms,
        "deterministic_check_counts": deterministic_check_counts,
        "deterministic_check_details": deterministic_check_details,
        "repetition_counts": repetition["repetition_counts"],
        "repetition_details": repetition["repetition_details"],
        "numbered_result_reference_count": numbered_result_reference_count,
        "answer_candidates": candidates[:8],
        "candidate_count": len(candidates),
        "ground_truth_answer": ground_truth,
        "answer_matches_metadata": answer_matches_metadata,
        "truncated": truncated,
        "finish_reason": finish_reason,
        "answer_len": len(answer_text),
        "reasoning_len": len(reasoning),
        "analysis_len": len(analysis_text),
        "tail_chars": tail_chars,
    }


def detect_reasoning_hallucination(
    row_or_reasoning: dict[str, Any] | str,
    *,
    tail_chars: int = 24000,
) -> dict[str, Any]:
    """Backward-compatible alias for ``count_reasoning_keywords``.

    This no longer returns a hallucination score or suspect label.
    """

    return count_reasoning_keywords(row_or_reasoning, tail_chars=tail_chars)
