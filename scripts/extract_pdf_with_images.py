#!/usr/bin/env python3

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract page-ordered text and images from a PDF into Markdown."
    )
    parser.add_argument("pdf", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where the Markdown, manifest, and images will be written.",
    )
    return parser.parse_args()


def is_footer_page_number(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    full_width_digits = "０１２３４５６７８９"
    return all(char.isdigit() or char in full_width_digits for char in stripped) and len(stripped) <= 3


def normalize_inline_text(text: str) -> str:
    cleaned = text.replace("\xa0", " ").replace("\u3000", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def should_insert_space(previous_text: str, next_text: str, gap: int) -> bool:
    if gap < 8 or not previous_text or not next_text:
        return False

    prev_char = previous_text[-1]
    next_char = next_text[0]
    return prev_char.isascii() and next_char.isascii()


def is_footer_number_node(
    text: str,
    top: int,
    left: int,
    width: int,
    page_height: int,
    page_width: int,
) -> bool:
    normalized = normalize_inline_text(text)
    if not is_footer_page_number(normalized):
        return False

    if top < max(page_height - 80, 0):
        return False

    node_center = left + (width / 2)
    return page_width * 0.4 <= node_center <= page_width * 0.6


def build_text_lines(text_nodes: list[dict], page_height: int) -> list[dict]:
    if not text_nodes:
        return []

    sorted_nodes = sorted(text_nodes, key=lambda node: (node["top"], node["left"]))
    lines: list[dict] = []
    current_nodes: list[dict] = []
    current_bottom = None

    def flush_line(nodes: list[dict]) -> None:
        if not nodes:
            return

        parts = []
        left = min(node["left"] for node in nodes)
        top = min(node["top"] for node in nodes)
        right = max(node["left"] + node["width"] for node in nodes)
        previous_right = None
        previous_text = ""
        previous_left = None
        previous_width = None

        for node in sorted(nodes, key=lambda item: item["left"]):
            node_text = normalize_inline_text(node["text"])
            if not node_text:
                continue

            if (
                previous_left is not None
                and node_text == previous_text
                and abs(node["left"] - previous_left) <= 3
                and previous_width is not None
                and abs(node["width"] - previous_width) <= 3
            ):
                continue

            if previous_right is not None and should_insert_space(
                previous_text, node_text, node["left"] - previous_right
            ):
                parts.append(" ")

            parts.append(node_text)
            previous_right = node["left"] + node["width"]
            previous_text = node_text
            previous_left = node["left"]
            previous_width = node["width"]

        line_text = "".join(parts).strip()
        if not line_text:
            return

        if top >= max(page_height - 80, 0) and is_footer_page_number(line_text):
            return

        lines.append(
            {
                "kind": "text",
                "top": top,
                "left": left,
                "right": right,
                "text": line_text,
            }
        )

    for node in sorted_nodes:
        node_bottom = node["top"] + node["height"]
        if current_bottom is None or node["top"] <= current_bottom - 2:
            current_nodes.append(node)
            current_bottom = node_bottom if current_bottom is None else max(current_bottom, node_bottom)
        else:
            flush_line(current_nodes)
            current_nodes = [node]
            current_bottom = node_bottom

    flush_line(current_nodes)
    return lines


def run_pdftohtml(pdf_path: Path, work_dir: Path) -> Path:
    prefix = work_dir / "layout"
    subprocess.run(
        ["pdftohtml", "-xml", "-nodrm", str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
    )
    xml_path = work_dir / "layout.xml"
    if not xml_path.exists():
        raise RuntimeError(f"pdftohtml did not create XML output: {xml_path}")
    return xml_path


def extract_layout(pdf_path: Path, images_dir: Path) -> tuple[list[dict], int]:
    pages: list[dict] = []
    total_images = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        xml_path = run_pdftohtml(pdf_path, Path(temp_dir))
        root = ET.parse(xml_path).getroot()

        for page_element in root.findall("page"):
            page_number = int(page_element.attrib["number"])
            page_height = int(page_element.attrib.get("height", "0"))
            page_width = int(page_element.attrib.get("width", "0"))
            page_items: list[dict] = []

            seen_text_nodes = set()
            text_nodes = []
            for text_element in page_element.findall("text"):
                text = "".join(text_element.itertext())
                top = int(text_element.attrib.get("top", "0"))
                left = int(text_element.attrib.get("left", "0"))
                width = int(text_element.attrib.get("width", "0"))
                height = int(text_element.attrib.get("height", "0"))
                if is_footer_number_node(text, top, left, width, page_height, page_width):
                    continue
                key = (top, left, width, height, text)
                if key in seen_text_nodes:
                    continue
                seen_text_nodes.add(key)
                text_nodes.append(
                    {
                        "top": top,
                        "left": left,
                        "width": width,
                        "height": height,
                        "text": text,
                    }
                )

            page_items.extend(build_text_lines(text_nodes, page_height))

            for image_index, image_element in enumerate(page_element.findall("image"), start=1):
                src_path = Path(image_element.attrib["src"])
                suffix = src_path.suffix.lower() or ".bin"
                filename = f"page_{page_number:03d}_img_{image_index:02d}{suffix}"
                destination = images_dir / filename
                shutil.copy2(src_path, destination)
                page_items.append(
                    {
                        "kind": "image",
                        "top": int(image_element.attrib.get("top", "0")),
                        "left": int(image_element.attrib.get("left", "0")),
                        "index": image_index,
                        "filename": filename,
                        "relative_path": f"images/{filename}",
                    }
                )
                total_images += 1

            page_items.sort(key=lambda item: (item["top"], item["left"], item["kind"] != "text"))
            pages.append(
                {
                    "number": page_number,
                    "height": page_height,
                    "items": page_items,
                    "image_count": sum(1 for item in page_items if item["kind"] == "image"),
                }
            )

    return pages, total_images


def render_page_items(page: dict) -> list[str]:
    rendered = []
    previous_top = None

    for item in page["items"]:
        if item["kind"] == "image":
            if rendered and rendered[-1] != "":
                rendered.append("")
            rendered.append(
                f"![第{page['number']}页图片{item['index']}]({item['relative_path']})"
            )
            rendered.append("")
            previous_top = item["top"]
            continue

        if previous_top is not None and item["top"] - previous_top > 26:
            if rendered and rendered[-1] != "":
                rendered.append("")

        rendered.append(item["text"])
        previous_top = item["top"]

    while rendered and rendered[-1] == "":
        rendered.pop()

    return rendered


def build_markdown(
    pdf_name: str,
    pages: list[dict],
    total_images: int,
) -> str:
    lines = [
        f"# {pdf_name} 图文提取",
        "",
        f"- 源文件: `{pdf_name}`",
        f"- 页数: `{len(pages)}`",
        f"- 提取图片数: `{total_images}`",
        "",
        "> 说明: 按 PDF 原始页序输出，并根据页面坐标把图片插回正文流附近，便于核对是否漏图。",
        "",
    ]

    for page in pages:
        page_number = page["number"]
        lines.append(f"## 第 {page_number} 页")
        lines.append("")
        rendered_page = render_page_items(page)
        if rendered_page:
            lines.extend(rendered_page)
        else:
            lines.append("_本页无可提取文本_")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.resolve()
    output_dir = args.output_dir.resolve()
    images_dir = output_dir / "images"

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    pages, total_images = extract_layout(pdf_path, images_dir)
    markdown = build_markdown(pdf_path.name, pages, total_images)
    markdown_path = output_dir / "extracted.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    manifest = {
        "pdf": pdf_path.name,
        "pages": len(pages),
        "images": total_images,
        "page_image_counts": [page["image_count"] for page in pages],
        "markdown": markdown_path.name,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"markdown={markdown_path}")
    print(f"manifest={manifest_path}")
    print(f"pages={manifest['pages']}")
    print(f"images={manifest['images']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
