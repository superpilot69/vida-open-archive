#!/usr/bin/env python3

import argparse
import base64
import json
import re
from pathlib import Path


PAGE_SPLIT_RE = re.compile(r"(.*?)(?:\[第\s*(\d+)\s*页结束\])", re.S)
ARTICLE_START_RE = re.compile(r"第\s*(\d+)\s*篇\s*:(https?://\S+)")
META_RE = re.compile(
    r"赞同数\s*:\s*\((\d+)\s*赞同\s*\)\s*创建时间\s*:\s*\((\d{4}-\d{2}-\d{2})\)"
)
PAGE_SECTION_RE = re.compile(r"^## 第\s*(\d+)\s*页\n", re.M)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
LAYOUT_MARKER_RE = re.compile(r"^第篇*(\d+)篇*:(https?://\S+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a typed article dataset for the Vida exhibition artifact."
    )
    parser.add_argument("--txt", type=Path, required=True, help="Clean transcription TXT path.")
    parser.add_argument(
        "--layout-md",
        type=Path,
        required=True,
        help="Markdown extracted from the PDF with inline image references.",
    )
    parser.add_argument(
        "--output-ts",
        type=Path,
        required=True,
        help="Target TypeScript module path for the prepared dataset.",
    )
    return parser.parse_args()


def is_page_number(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return len(stripped) <= 6 and all(
        char.isdigit() or char in "０１２３４５６７８９" for char in stripped
    )


def normalize_block(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    cleaned = []
    previous_blank = False

    for line in lines:
        if line.strip():
            cleaned.append(line)
            previous_blank = False
        elif not previous_blank:
            cleaned.append("")
            previous_blank = True

    return "\n".join(cleaned).strip()


def clean_page_text(page_text: str) -> str:
    lines = [line.rstrip() for line in page_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]

    while lines and not lines[-1].strip():
        lines.pop()

    if lines and is_page_number(lines[-1]):
        lines.pop()

    return "\n".join(lines).strip("\n")


def clean_title(raw_title: str) -> str:
    title_lines = [line.strip() for line in normalize_block(raw_title).splitlines() if line.strip()]
    if not title_lines:
        return ""

    title = "".join(title_lines)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff0-9])", "", title)
    title = re.sub(r"(?<=[0-9%％])\s+(?=[\u4e00-\u9fff])", "", title)
    title = re.sub(r"(?<=[（(])\s+", "", title)
    title = re.sub(r"\s+(?=[）)])", "", title)

    if len(title_lines) >= 2 and title_lines[-1].isdigit() and not title.startswith(title_lines[-1]):
        title = title_lines[-1] + title

    return title.strip()


def infer_article_type(url: str) -> str:
    if "/zhuanlan.zhihu.com/" in url:
        return "专栏"
    if "/pin/" in url:
        return "想法"
    return "回答"


def parse_articles(txt_path: Path) -> dict[str, dict]:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    articles: dict[str, dict] = {}
    current_article_id: str | None = None

    for page_content, page_number in PAGE_SPLIT_RE.findall(text):
        page_number_int = int(page_number)
        cleaned_page = clean_page_text(page_content)
        article_matches = list(ARTICLE_START_RE.finditer(cleaned_page))

        if not article_matches:
            if current_article_id is not None:
                articles[current_article_id]["raw_parts"].append(cleaned_page)
                articles[current_article_id]["pages"].append(page_number_int)
            continue

        prefix = cleaned_page[: article_matches[0].start()].strip()
        if prefix and current_article_id is not None:
            articles[current_article_id]["raw_parts"].append(prefix)
            articles[current_article_id]["pages"].append(page_number_int)

        for index, match in enumerate(article_matches):
            article_id, url = match.groups()
            current_article_id = article_id
            article = articles.setdefault(
                article_id,
                {
                    "id": int(article_id),
                    "url": url,
                    "pages": [],
                    "raw_parts": [],
                },
            )

            segment_start = match.end()
            segment_end = (
                article_matches[index + 1].start()
                if index + 1 < len(article_matches)
                else len(cleaned_page)
            )
            segment = cleaned_page[segment_start:segment_end].strip()
            if segment:
                article["raw_parts"].append(segment)

            if not article["pages"] or article["pages"][-1] != page_number_int:
                article["pages"].append(page_number_int)

    prepared: dict[str, dict] = {}
    for article_id, article in articles.items():
        raw_text = normalize_block("\n\n".join(part for part in article["raw_parts"] if part.strip()))
        meta_match = META_RE.search(raw_text)
        if not meta_match:
            raise RuntimeError(f"Missing likes/date metadata for article {article_id}")

        likes = int(meta_match.group(1))
        date = meta_match.group(2)
        title = clean_title(raw_text[: meta_match.start()])
        content = normalize_block(raw_text[meta_match.end() :])

        prepared[article_id] = {
            "id": article["id"],
            "title": title,
            "likes": likes,
            "date": date,
            "url": article["url"],
            "type": infer_article_type(article["url"]),
            "content": content,
            "pages": article["pages"],
            "images": [],
        }

    return prepared


def attach_images(articles: dict[str, dict], layout_md_path: Path) -> None:
    markdown = layout_md_path.read_text(encoding="utf-8")
    positions = list(PAGE_SECTION_RE.finditer(markdown))
    current_article_id: str | None = None

    for index, match in enumerate(positions):
        section_start = match.end()
        section_end = positions[index + 1].start() if index + 1 < len(positions) else len(markdown)
        section = markdown[section_start:section_end]
        lines = section.splitlines()
        line_index = 0

        while line_index < len(lines):
            stripped = lines[line_index].strip()

            if not stripped or stripped == "---":
                line_index += 1
                continue

            image_match = IMAGE_RE.search(stripped)
            if image_match:
                if current_article_id is not None:
                    articles[current_article_id]["images"].append(image_match.group(1))
                line_index += 1
                continue

            normalized = re.sub(r"\s+", "", stripped)
            next_normalized = (
                normalized + re.sub(r"\s+", "", lines[line_index + 1].strip())
                if line_index + 1 < len(lines)
                else normalized
            )

            match_single = LAYOUT_MARKER_RE.match(normalized)
            match_double = LAYOUT_MARKER_RE.match(next_normalized)
            if match_single:
                current_article_id = match_single.group(1)
                line_index += 1
                continue
            if match_double:
                current_article_id = match_double.group(1)
                line_index += 2
                continue

            line_index += 1


def image_to_data_url(base_dir: Path, relative_path: str) -> str:
    image_path = (base_dir / relative_path).resolve()
    suffix = image_path.suffix.lower()
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_module(articles: dict[str, dict], layout_md_path: Path) -> str:
    base_dir = layout_md_path.parent
    sorted_articles = sorted(articles.values(), key=lambda article: article["id"])

    for article in sorted_articles:
        article["imageCount"] = len(article["images"])
        article["images"] = [
            image_to_data_url(base_dir, relative_path) for relative_path in article["images"]
        ]
        article["excerpt"] = article["content"][:220].replace("\n", " ").strip()
        article["wordCount"] = len(article["content"].replace("\n", ""))

    stats = {
        "articleCount": len(sorted_articles),
        "totalLikes": sum(article["likes"] for article in sorted_articles),
        "imageArticleCount": sum(1 for article in sorted_articles if article["imageCount"] > 0),
        "dateRange": {
            "earliest": min(article["date"] for article in sorted_articles),
            "latest": max(article["date"] for article in sorted_articles),
        },
    }

    articles_json = json.dumps(sorted_articles, ensure_ascii=False, indent=2)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    return (
        "// This file is generated by scripts/prepare_vida_artifact_data.py\n"
        f"export const archiveStats = {stats_json};\n\n"
        f"export const articlesData = {articles_json};\n"
    )


def main() -> int:
    args = parse_args()
    articles = parse_articles(args.txt.resolve())
    attach_images(articles, args.layout_md.resolve())

    output_path = args.output_ts.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_module(articles, args.layout_md.resolve()), encoding="utf-8")

    total_images = sum(article["imageCount"] if "imageCount" in article else len(article["images"]) for article in articles.values())
    print(f"articles={len(articles)}")
    print(f"assigned_images={total_images}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
