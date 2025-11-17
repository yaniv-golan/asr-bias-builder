#!/usr/bin/env python3
"""Split deck text into Claude-compatible streaming JSONL chunks."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

DEFAULT_CHUNK_SIZE = 50_000


def chunk_text(text: str, chunk_size: int) -> Iterable[str]:
    if not text:
        yield ""
        return
    for idx in range(0, len(text), chunk_size):
        yield text[idx : idx + chunk_size]


def encode_message(chunk: str, index: int, total: int) -> str:
    payload = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"[Chunk {index}/{total}]\n\n{chunk}",
                }
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def write_stream_file(deck_text: Path, output_jsonl: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> List[str]:
    """Write a JSONL stream file and return the encoded messages."""
    text = deck_text.read_text(encoding="utf-8")
    chunks = list(chunk_text(text, max(1, chunk_size)))
    total = max(1, len(chunks))
    payloads = [encode_message(chunk, idx, total) for idx, chunk in enumerate(chunks, start=1)]
    output_jsonl.write_text("\n".join(payloads), encoding="utf-8")
    return payloads


def run_claude(
    deck_text: Path,
    schema_file: Path,
    output_path: Path,
    model: str,
    permission_flags: Optional[List[str]] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    stream_threshold_bytes: int = 80_000,
) -> subprocess.CompletedProcess[str]:
    """Invoke the Claude CLI, switching to stream mode when needed."""
    text_content = deck_text.read_text(encoding="utf-8")
    payload = text_content
    base_cmd = [
        "claude",
        "--print",
        "--model",
        model,
        "--system-prompt-file",
        str(schema_file),
    ]
    if permission_flags:
        base_cmd.extend(permission_flags)
    else:
        base_cmd.append("--dangerously-skip-permissions")

    if len(text_content.encode("utf-8")) > stream_threshold_bytes:
        stream_file = output_path.parent / "deck_stream.jsonl"
        payloads = write_stream_file(deck_text, stream_file, chunk_size)
        cmd = base_cmd + [
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
        ]
        process = subprocess.run(
            cmd,
            input="\n".join(payloads),
            text=True,
            capture_output=True,
            check=False,
        )
    else:
        cmd = base_cmd + ["--output-format", "json"]
        process = subprocess.run(
            cmd,
            input=payload,
            text=True,
            capture_output=True,
            check=False,
        )
    if process.stdout:
        raw_path = output_path.parent / f"{output_path.stem}_raw.json"
        raw_path.write_text(process.stdout, encoding="utf-8")
        try:
            stripped = json.loads(process.stdout).get("result", "")
        except json.JSONDecodeError:
            stripped = process.stdout
        if stripped:
            output_path.write_text(stripped, encoding="utf-8")
        else:
            output_path.write_text(process.stdout, encoding="utf-8")
    return process


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create JSONL chunks for Claude stream input")
    parser.add_argument("deck_text", type=Path)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    args = parser.parse_args(argv)

    text = args.deck_text.read_text(encoding="utf-8")
    chunks = list(chunk_text(text, max(1, args.chunk_size)))
    total = max(1, len(chunks))
    for idx, chunk in enumerate(chunks, start=1):
        print(encode_message(chunk, idx, total))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
