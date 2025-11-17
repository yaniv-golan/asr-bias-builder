#!/usr/bin/env python3
"""Extract final Claude result from streaming JSON events."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional


def parse_stream(path: Path) -> dict:
    final_result = None
    metadata = {}
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(obj)
            if obj.get("type") == "result":
                final_result = obj.get("result")
                for key in ("session_id", "model", "usage", "cost", "duration_ms"):
                    if key in obj:
                        metadata[key] = obj[key]
    if final_result is None:
        raise RuntimeError("No result event found in stream")
    payload = {"result": final_result, "event_count": len(events)}
    if metadata:
        payload["metadata"] = metadata
    return payload


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize Claude stream output")
    parser.add_argument("stream_jsonl", type=Path, help="Path to claude_stream.jsonl")
    parser.add_argument("--output", type=Path, help="Write normalized JSON to this path instead of stdout")
    args = parser.parse_args(argv)

    payload = parse_stream(args.stream_jsonl)
    output_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
    else:
        print(output_text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
