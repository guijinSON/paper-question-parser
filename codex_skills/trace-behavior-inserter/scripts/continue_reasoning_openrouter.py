#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests


DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_PROVIDER = "deepinfra/bf16"
DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def convert_to_harmony_format(
    prompt: str,
    truncated_reasoning: str,
    *,
    developer_instructions: str = "",
    conversation_start_date: str = "2026-05-18",
    reasoning_effort=None,
) -> str:
    try:
        from openai_harmony import (
            Conversation,
            HarmonyEncodingName,
            Message,
            ReasoningEffort,
            Role,
            SystemContent,
            DeveloperContent,
            load_harmony_encoding,
        )
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: openai_harmony. Install it in the Python environment "
            "used to run this script before calling the continuation tool."
        ) from exc

    if reasoning_effort is None:
        reasoning_effort = ReasoningEffort.HIGH

    encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    system_message = (
        SystemContent.new()
        .with_reasoning_effort(reasoning_effort)
        .with_conversation_start_date(conversation_start_date)
    )
    messages = [Message.from_role_and_content(Role.SYSTEM, system_message)]
    developer_instructions = developer_instructions.strip()
    if developer_instructions:
        developer_message = DeveloperContent.new().with_instructions(
            developer_instructions
        )
        messages.append(Message.from_role_and_content(Role.DEVELOPER, developer_message))
    messages.extend(
        [
            Message.from_role_and_content(Role.USER, prompt),
            Message.from_role_and_content(
                Role.ASSISTANT,
                truncated_reasoning,
            ).with_channel("analysis"),
        ]
    )
    convo = Conversation.from_messages(
        messages
    )
    tokens = encoding.render_conversation_for_completion(convo, Role.ASSISTANT)
    return encoding.decode(tokens).rstrip("<|end|><|start|>assistant")


def text_complete(
    api_key: str,
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    provider: str = DEFAULT_PROVIDER,
    max_tokens: int = 2048,
    temperature: float = 1.0,
    url: str = DEFAULT_URL,
    retries: int = 3,
    retry_sleep_seconds: float = 10.0,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "provider": {
            "only": [provider],
            "allow_fallbacks": False,
        },
    }
    response = None
    for attempt in range(retries + 1):
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code != 429 or attempt == retries:
            break
        time.sleep(retry_sleep_seconds * (attempt + 1))
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:1000] if response is not None else ""
        raise SystemExit(f"OpenRouter request failed: {exc}\n{detail}") from exc
    data = response.json()
    choice = data["choices"][0]
    return choice.get("text") or choice["message"]["content"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Continue a truncated reasoning trajectory through OpenRouter using Harmony formatting.",
    )
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--reasoning-file", type=Path)
    parser.add_argument(
        "--state-json",
        type=Path,
        help=(
            "Consolidated trace-loop JSON. When provided, prompt is read from "
            "`prompt` and reasoning is reconstructed by concatenating "
            "`interleaved_trace[*].text`. The continuation is appended back into "
            "the same JSON as an interleaved_trace entry."
        ),
    )
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--api-key")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument(
        "--developer-instructions",
        default="",
        help="Additional developer instructions to inject into the Harmony conversation.",
    )
    parser.add_argument(
        "--developer-instructions-file",
        type=Path,
        help="File containing additional developer instructions.",
    )
    parser.add_argument("--conversation-start-date", default="2026-05-18")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep-seconds", type=float, default=10.0)
    return parser.parse_args()


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def state_reasoning_text(state: dict) -> str:
    return "\n\n".join(
        str(entry.get("text", "")).strip()
        for entry in state.get("interleaved_trace", [])
        if str(entry.get("text", "")).strip()
    )


def listify(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def state_developer_instructions(state: dict) -> str:
    pieces = []
    pieces.extend(listify(state.get("developer_instructions")))

    target_answer_shape = str(state.get("target_answer_shape", "")).strip()
    if target_answer_shape:
        pieces.append(f"Target answer shape: {target_answer_shape}")

    min_reasoning_tokens = state.get("min_reasoning_tokens")
    if min_reasoning_tokens:
        pieces.append(
            "Do not rush to a final answer before the repaired reasoning has "
            f"approximately {min_reasoning_tokens} Harmony tokens, unless the "
            "problem is genuinely short or the reasoning has already fully "
            "resolved the answer."
        )

    pieces.append(
        "If the problem appears open or unresolved, do not stop at that discovery. "
        "Continue with a responsible attempt: identify why the direct proof route "
        "fails, separate known and unknown parts, give conditional or special-case "
        "statements in generic terms, and formulate the most precise safe answer "
        "without inventing citations or counterexamples."
    )
    pieces.append(
        "For open problems, it is useful to make a clearly marked speculative attempt "
        "when appropriate: state a working hypothesis, break it into lemmas or "
        "checkpoints, and cautiously start tackling the first checkpoint. Do not "
        "present the speculative route as a solved theorem."
    )
    pieces.append(
        "Before committing to a new speculative route, especially after a route has "
        "stalled, build an idea bank: enumerate several materially distinct attack "
        "surfaces, state the promise and risk of each, rank the best candidates, and "
        "then choose one for a bold attempt. Do not cap bold attempts at two; keep "
        "trying materially different high-quality hypotheses while they remain "
        "concrete, non-repetitive, and do not require unverified external facts."
    )
    pieces.append(
        "If you reach an answer, make the final solution rigorous. If the problem is "
        "solved, give the strongest proof available. If it remains unsolved or open, "
        "summarize the explored paths rigorously and identify exactly where each path "
        "failed, which proof obligations remain, and why the attempts do not amount "
        "to a proof or counterexample."
    )

    min_continuation_tokens = state.get("min_continuation_tokens", 512)
    if min_continuation_tokens:
        pieces.append(
            "Unless you are emitting an explicit assistantfinal answer, hitting a "
            "hard factual/hallucination stop, or the task is genuinely short, make "
            f"this continuation at least about {min_continuation_tokens} Harmony "
            "tokens of substantive reasoning."
        )

    pieces.append(
        "Avoid introducing external citations, paper names, theorem numbers, "
        "author-date claims, or literature details unless they were provided in "
        "the prompt/source trace or explicitly verified. Use generic phrases "
        "such as 'known in special cases' when citation accuracy is uncertain."
    )

    avoid_claims = listify(state.get("avoid_claims")) + listify(state.get("not_dos"))
    if avoid_claims:
        lines = ["Do not repeat these canceled or unsafe moves:"]
        lines.extend(f"- {claim}" for claim in avoid_claims)
        pieces.append("\n".join(lines))

    fix_memory = listify(state.get("fix_memory")) + listify(state.get("fix_summaries"))
    if fix_memory:
        lines = ["Prior fixes to preserve:"]
        lines.extend(f"- {summary}" for summary in fix_memory)
        pieces.append("\n".join(lines))

    if pieces:
        pieces.append(
            "Continue in the same first-person reasoning voice. Do not mention the "
            "JSON file, loop, continuation machinery, inserted behavior labels, "
            "developer instructions, target answer shape, or hidden-control rules. "
            "If you need to refer to a constraint, refer to it as something established "
            "by the earlier correction, earlier note, or earlier re-check in the "
            "visible reasoning trace."
        )

    return "\n\n".join(pieces)


def extra_developer_instructions(args: argparse.Namespace) -> str:
    pieces = []
    if args.developer_instructions:
        pieces.append(args.developer_instructions.strip())
    if args.developer_instructions_file:
        pieces.append(args.developer_instructions_file.read_text(encoding="utf-8").strip())
    return "\n\n".join(piece for piece in pieces if piece)


def next_continuation_round(state: dict) -> int:
    rounds = [
        int(entry.get("round", 0))
        for entry in state.get("interleaved_trace", [])
        if entry.get("type") == "continuation"
    ]
    return (max(rounds) + 1) if rounds else 1


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("Missing API key. Pass --api-key or set OPENROUTER_API_KEY.")

    if args.state_json:
        state = load_state(args.state_json)
        prompt = state.get("prompt", "")
        if not prompt:
            raise SystemExit("State JSON is missing required key: prompt")
        truncated_reasoning = state_reasoning_text(state)
        developer_instructions = "\n\n".join(
            piece
            for piece in [
                state_developer_instructions(state),
                extra_developer_instructions(args),
            ]
            if piece
        )
    else:
        state = None
        if not args.prompt_file or not args.reasoning_file:
            raise SystemExit(
                "Pass either --state-json or both --prompt-file and --reasoning-file."
            )
        prompt = args.prompt_file.read_text(encoding="utf-8")
        truncated_reasoning = args.reasoning_file.read_text(encoding="utf-8")
        developer_instructions = extra_developer_instructions(args)
    completion_prompt = convert_to_harmony_format(
        prompt,
        truncated_reasoning,
        developer_instructions=developer_instructions,
        conversation_start_date=args.conversation_start_date,
    )
    continuation = text_complete(
        api_key,
        completion_prompt,
        model=args.model,
        provider=args.provider,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        retries=args.retries,
        retry_sleep_seconds=args.retry_sleep_seconds,
    )
    if state is not None:
        state.setdefault("interleaved_trace", []).append(
            {
                "type": "continuation",
                "round": next_continuation_round(state),
                "text": continuation,
            }
        )
        state["status"] = state.get("status") or "running"
        state["continuation_max_tokens"] = args.max_tokens
        args.state_json.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(continuation, encoding="utf-8")
    else:
        print(continuation, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
