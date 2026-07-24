#!/usr/bin/env python3
"""Build a searchable JSON API reference from the vendored cavalry-types .d.ts files.

Reads:  vendor/cavalry-types/namespaces/*.d.ts
Writes: src/cavalry_mcp/data/api_reference.json

The .d.ts files are written in a uniform style: a JSDoc block (/** ... */)
directly above each `function`, `const` or `class` declaration inside a
`declare namespace <name> { ... }` block. This parser is intentionally simple
and line-based; if cavalry-types changes format, adjust here.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT / "vendor" / "cavalry-types" / "namespaces"
OUTPUT = ROOT / "src" / "cavalry_mcp" / "data" / "api_reference.json"

DECL_RE = re.compile(r"^\s*(function|const|class)\s+(\w+)")


def clean_doc(raw_lines: list[str]) -> str:
    """Turn raw JSDoc interior lines into plain text."""
    cleaned = []
    for line in raw_lines:
        line = re.sub(r"^\s*\* ?", "", line)
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


def parse_namespace(path: Path) -> list[dict]:
    namespace = path.name.removesuffix(".d.ts")
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("/**"):
            doc_lines: list[str] = []
            i += 1
            while i < len(lines) and "*/" not in lines[i]:
                doc_lines.append(lines[i])
                i += 1
            i += 1  # skip the */ line
            if i >= len(lines):
                break
            decl_match = DECL_RE.match(lines[i])
            if not decl_match:
                continue  # docblock not attached to a declaration we care about
            kind, name = decl_match.group(1), decl_match.group(2)
            if kind == "class":
                # Accumulate until the closing brace at namespace-member indent (2 spaces).
                sig_lines = [lines[i]]
                i += 1
                while i < len(lines) and not re.match(r"^  \}", lines[i]):
                    sig_lines.append(lines[i])
                    i += 1
                sig_lines.append("  }")
            else:
                # function/const: accumulate until the terminating semicolon.
                sig_lines = [lines[i]]
                while ";" not in sig_lines[-1] and i + 1 < len(lines):
                    i += 1
                    sig_lines.append(lines[i])
                i += 1
            signature = " ".join(part.strip() for part in sig_lines)
            signature = re.sub(r"\s+", " ", signature).strip()
            entries.append(
                {
                    "namespace": namespace,
                    "kind": "class" if kind == "class" else kind,
                    "name": name,
                    "signature": signature,
                    "doc": clean_doc(doc_lines),
                }
            )
        else:
            i += 1
    return entries


def main() -> int:
    files = sorted(VENDOR_DIR.glob("*.d.ts"))
    if not files:
        print(f"No .d.ts files found in {VENDOR_DIR}", file=sys.stderr)
        return 1
    entries: list[dict] = []
    for path in files:
        parsed = parse_namespace(path)
        entries.extend(parsed)
        print(f"{path.name}: {len(parsed)} entries")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "https://github.com/scenery-io/cavalry-types",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": len(entries),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"Wrote {len(entries)} entries -> {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
