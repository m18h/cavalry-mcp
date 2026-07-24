#!/usr/bin/env python3
"""Build the cavalry-mcp semantic knowledge base from the official Cavalry docs.

Pipeline: sitemap → fetch pages (with on-disk cache) → extract article →
markdown → chunk (heading-aware, code-fence-safe) → embed with fastembed →
write src/cavalry_mcp/data/knowledge_chunks.json + knowledge_vectors.npz.

Requires the optional `kb` extra:  uv sync --extra kb
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "docs_html"
DATA_DIR = ROOT / "src" / "cavalry_mcp" / "data"

SITEMAP_URL = "https://docs.cavalry.scenegroup.co/sitemap.xml"
MODEL = "BAAI/bge-small-en-v1.5"
MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 80
FETCH_WORKERS = 6

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
ZERO_WIDTH_RE = re.compile(r"[​‌‍﻿]")


def clean_heading(text: str) -> str:
    """Remove Docusaurus anchor-link residue from heading text."""
    text = MD_LINK_RE.sub(r"\1", text)
    text = ZERO_WIDTH_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def sitemap_urls() -> list[str]:
    import httpx

    resp = httpx.get(SITEMAP_URL, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
    return [
        url
        for url in urls
        if "/docs/" in url and not url.rstrip("/").endswith("/docs/search")
    ]


def fetch_page(url: str, *, use_cache: bool = True) -> tuple[str, str]:
    """Return (url, html). Caches raw HTML under .cache/docs_html/."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{hashlib.sha1(url.encode()).hexdigest()}.html"
    if use_cache and cache_file.exists():
        return url, cache_file.read_text(encoding="utf-8")
    import httpx

    for attempt in (1, 2):
        try:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            cache_file.write_text(resp.text, encoding="utf-8")
            return url, resp.text
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.0)
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Extraction & chunking
# ---------------------------------------------------------------------------


def extract_markdown(html: str) -> tuple[str, str]:
    """Extract (title, markdown) from a Docusaurus page."""
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup.find("main") or soup.body or soup
    title_tag = article.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"
    title = title.removesuffix(" | Cavalry").strip()
    md = markdownify(str(article), heading_style="ATX", strip=["img"])
    # Collapse 3+ blank lines; drop Docusaurus nav residue.
    md = re.sub(r"\n{3,}", "\n\n", md)
    return title, md.strip()


def split_blocks(md: str) -> list[str]:
    """Split markdown into blocks: paragraphs or atomic fenced code blocks."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current.append(line)
            continue
        if not in_fence and not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def chunk_page(title: str, url: str, md: str) -> list[dict]:
    chunks: list[dict] = []
    breadcrumb: list[tuple[int, str]] = []
    buf = ""

    def breadcrumb_text() -> str:
        return " > ".join([title] + [text for _, text in breadcrumb])

    def flush() -> None:
        nonlocal buf
        text = buf.strip()
        buf = ""
        if len(text) < MIN_CHUNK_CHARS:
            return
        chunks.append(
            {"title": title, "url": url, "heading": breadcrumb_text(), "text": text}
        )

    for block in split_blocks(md):
        lines = block.splitlines()
        heading = HEADING_RE.match(lines[0]) if len(lines) == 1 else None
        if heading:
            flush()
            level = len(heading.group(1))
            while breadcrumb and breadcrumb[-1][0] >= level:
                breadcrumb.pop()
            breadcrumb.append((level, clean_heading(heading.group(2))))
            continue
        if len(block) > MAX_CHUNK_CHARS:
            flush()
            for i in range(0, len(block), MAX_CHUNK_CHARS):
                buf = block[i : i + MAX_CHUNK_CHARS]
                flush()
            continue
        if buf and len(buf) + len(block) + 2 > MAX_CHUNK_CHARS:
            flush()
        buf = f"{buf}\n\n{block}" if buf else block
    flush()
    return chunks


# ---------------------------------------------------------------------------
# Embedding & persistence
# ---------------------------------------------------------------------------


def embed_chunks(chunks: list[dict]):
    import numpy as np
    from fastembed import TextEmbedding

    model = TextEmbedding(MODEL)
    # Heading breadcrumb is part of the embedded text for better retrieval.
    texts = [f"{c['heading']}\n\n{c['text']}" for c in chunks]
    vectors = list(model.passage_embed(texts, batch_size=64))
    return np.array(vectors, dtype=np.float32)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-cache", action="store_true", help="refetch all pages")
    parser.add_argument("--limit", type=int, default=0, help="only fetch N pages (testing)")
    args = parser.parse_args()

    print("Fetching sitemap…")
    urls = sitemap_urls()
    if args.limit:
        urls = urls[: args.limit]
    print(f"{len(urls)} doc pages")

    pages: dict[str, str] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {
            pool.submit(fetch_page, url, use_cache=not args.no_cache): url
            for url in urls
        }
        for i, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            try:
                got_url, html = future.result()
                pages[got_url] = html
            except Exception as exc:
                failures.append(url)
                print(f"  FAILED {url}: {exc}", file=sys.stderr)
            if i % 50 == 0 or i == len(urls):
                print(f"  fetched {i}/{len(urls)}")

    print("Extracting & chunking…")
    chunks: list[dict] = []
    for url in urls:  # keep sitemap order for determinism
        if url not in pages:
            continue
        try:
            title, md = extract_markdown(pages[url])
            chunks.extend(chunk_page(title, url, md))
        except Exception as exc:
            failures.append(url)
            print(f"  FAILED parse {url}: {exc}", file=sys.stderr)
    print(f"{len(chunks)} chunks from {len(pages)} pages ({len(failures)} failures)")

    print(f"Embedding with {MODEL} (first run downloads the model)…")
    vectors = embed_chunks(chunks)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    chunks_path = DATA_DIR / "knowledge_chunks.json"
    vectors_path = DATA_DIR / "knowledge_vectors.npz"

    import numpy as np

    payload = {
        "model": MODEL,
        "source": SITEMAP_URL,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": len(chunks),
        "chunks": chunks,
    }
    chunks_path.write_text(json.dumps(payload), encoding="utf-8")
    np.savez_compressed(vectors_path, vectors=vectors)

    print(f"Wrote {chunks_path} ({chunks_path.stat().st_size // 1024} KB)")
    print(f"Wrote {vectors_path} ({vectors_path.stat().st_size // 1024} KB)")
    if failures:
        print(f"{len(failures)} pages failed (re-run to retry)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
