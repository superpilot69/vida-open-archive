#!/usr/bin/env python3

import argparse
import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Optional


PAGE_HEADER_RE = re.compile(r"^## 第\s+(\d+)\s+页\s*$", re.M)
ARTICLE_ID_LINE_RE = re.compile(r"^(\d+)\s*:\s*(https?://\S+)\s*$")
ARTICLE_HEADER_RE = re.compile(r"^第\s*(\d+)\s*篇\s*:\s*(https?://\S+)\s*$")
META_RE = re.compile(r"赞同数\s*:\s*\((\d+)赞同\)\s*创建时间\s*:\s*\((\d{4}-\d{2}-\d{2})\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a structured JSON dataset from the extracted Vida Markdown."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output/vida_articles_extract/extracted.md"),
        help="Path to the extracted Markdown source.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write the JSON dataset.",
    )
    return parser.parse_args()


def normalize_line(line: str) -> str:
    cleaned = line.replace("\u00a0", " ").replace("\u3000", " ").strip()
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def clean_title(title_lines: list[str]) -> str:
    pieces = [normalize_line(line) for line in title_lines if normalize_line(line)]
    return "".join(pieces)


def source_type(url: str) -> str:
    if "zhuanlan.zhihu.com" in url:
        return "专栏"
    if "/pin/" in url:
        return "想法"
    if "/answer/" in url:
        return "回答"
    return "其他"


def image_to_data_url(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(image_path.name)
    mime_type = mime_type or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def split_pages(markdown: str) -> list[dict]:
    start = markdown.find("## 第 1 页")
    if start == -1:
        raise RuntimeError("Could not find the first page marker in extracted Markdown.")

    body = markdown[start:]
    parts = PAGE_HEADER_RE.split(body)
    pages = []

    for index in range(1, len(parts), 2):
        page_number = int(parts[index])
        section = parts[index + 1]
        section = section.split("\n---", 1)[0]
        lines = [line.rstrip() for line in section.splitlines()]
        pages.append({"page": page_number, "lines": lines})

    return pages


def finalize_article(article: Optional[dict], articles: list[dict]) -> None:
    if article is None:
        return

    flush_paragraph(article)
    article["content"] = "\n\n".join(
        block["text"] for block in article["blocks"] if block["type"] == "text"
    ).strip()
    article["excerpt"] = next(
        (block["text"] for block in article["blocks"] if block["type"] == "text"),
        "",
    )[:180]
    article["imageCount"] = sum(1 for block in article["blocks"] if block["type"] == "image")
    article["hasImages"] = article["imageCount"] > 0
    articles.append(article)


def flush_paragraph(article: dict) -> None:
    lines = article.get("_paragraph_lines")
    if not lines:
        return

    text = "\n".join(lines).strip()
    if text:
        article["blocks"].append({"type": "text", "text": text})
    article["_paragraph_lines"] = []


def start_article(article_id: int, url: str, page_number: int) -> dict:
    return {
        "id": article_id,
        "url": url,
        "sourceType": source_type(url),
        "pageStart": page_number,
        "title": "",
        "likes": None,
        "date": "",
        "blocks": [],
        "_paragraph_lines": [],
        "_title_lines": [],
    }


def parse_articles(markdown_path: Path) -> list[dict]:
    markdown = markdown_path.read_text(encoding="utf-8")
    image_root = markdown_path.parent
    pages = split_pages(markdown)
    articles: list[dict] = []
    current_article: Optional[dict] = None

    for page in pages:
        lines = page["lines"]
        line_index = 0

        while line_index < len(lines):
            line = normalize_line(lines[line_index])
            if not line:
                if current_article is not None:
                    flush_paragraph(current_article)
                line_index += 1
                continue

            header_match = ARTICLE_HEADER_RE.match(line)
            if header_match is not None:
                finalize_article(current_article, articles)
                article_id = int(header_match.group(1))
                url = header_match.group(2)
                current_article = start_article(article_id, url, page["page"])
                line_index += 1
                continue

            if "第篇" in line:
                next_line = normalize_line(lines[line_index + 1]) if line_index + 1 < len(lines) else ""
                match = ARTICLE_ID_LINE_RE.match(next_line)
                if match is not None:
                    finalize_article(current_article, articles)
                    article_id = int(match.group(1))
                    url = match.group(2)
                    current_article = start_article(article_id, url, page["page"])
                    line_index += 2
                    continue

            if current_article is None:
                line_index += 1
                continue

            if current_article["likes"] is None:
                meta_match = META_RE.search(line)
                if meta_match is not None:
                    current_article["likes"] = int(meta_match.group(1))
                    current_article["date"] = meta_match.group(2)
                    current_article["title"] = clean_title(current_article["_title_lines"])
                    line_index += 1
                    continue

                current_article["_title_lines"].append(line)
                line_index += 1
                continue

            image_match = IMAGE_RE.search(line)
            if image_match is not None:
                flush_paragraph(current_article)
                image_relative_path = image_match.group(1)
                image_path = (image_root / image_relative_path).resolve()
                current_article["blocks"].append(
                    {
                        "type": "image",
                        "alt": line[line.find("[") + 1 : line.find("]")] or current_article["title"],
                        "src": image_to_data_url(image_path),
                    }
                )
                line_index += 1
                continue

            current_article["_paragraph_lines"].append(line)
            line_index += 1

    finalize_article(current_article, articles)

    for article in articles:
        article.pop("_paragraph_lines", None)
        article.pop("_title_lines", None)
        if article["likes"] is None:
            article["likes"] = 0

    return articles


def main() -> int:
    args = parse_args()
    articles = parse_articles(args.input.resolve())
    articles.sort(key=lambda article: (-article["likes"], article["id"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "totalArticles": len(articles),
        "totalImages": sum(article["imageCount"] for article in articles),
        "articles": articles,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"articles={payload['totalArticles']}")
    print(f"images={payload['totalImages']}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
