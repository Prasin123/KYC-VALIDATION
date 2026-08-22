"""
Layout inspection tool for born-digital (vector) bank form PDFs.

This is the tool used to seed configs/banks/siddhartha/personal_account_opening.json.
It is kept in the repo so the same approach can be reused for other banks
(NIC Asia, NMB, Global IME, etc.) instead of hand-typing ROI coordinates.

What it does, for each page of a PDF:
  1. Extracts every word with its bounding box (page.get_text("words")).
  2. Extracts every vector-drawn shape, and separates:
       - small circular "radio button" style checkboxes (drawn as a closed
         bezier curve) from
       - rectangular date/entry boxes (drawn as straight-line rectangles).
  3. Pairs each checkbox with the nearest text label to its right on the
     same line, which is how option labels ("Yes", "No", "Male", ...) are
     recovered automatically.

This only works for PDFs that still carry a real text/vector layer (i.e. not
a flattened scan). For scanned/flattened forms, render the page to an image
and use the interactive ROI editor in the app instead -- there is no vector
geometry to mine.

Usage:
    python tools/inspect_pdf_layout.py path/to/form.pdf --out layout.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from typing import Optional

import fitz  # PyMuPDF


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int = 0
    line: int = 0
    word_no: int = 0


@dataclass
class CheckboxOption:
    box: list  # [x0, y0, x1, y1]
    label: Optional[str]


def extract_words(page: "fitz.Page") -> list[Word]:
    return [
        Word(round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), text, block, line, word_no)
        for (x0, y0, x1, y1, text, block, line, word_no) in page.get_text("words")
    ]


def build_lines(words: list[Word]) -> list[list[Word]]:
    """Group words into printed lines using PyMuPDF's own (block, line) index."""
    groups: dict[tuple[int, int], list[Word]] = {}
    for w in words:
        groups.setdefault((w.block, w.line), []).append(w)
    lines = []
    for key in sorted(groups.keys()):
        line_words = sorted(groups[key], key=lambda w: w.word_no)
        lines.append(line_words)
    return lines


def find_phrase(words: list[Word], phrase: str, occurrence: int = 0) -> Optional[Word]:
    """
    Find a (possibly multi-word) phrase across the page's reconstructed lines
    and return a synthetic Word spanning it (x0 = phrase start, x1 = phrase
    end, y0/y1 = the line's vertical extent). Case-insensitive substring
    match against the whole line text, so partial phrases work too.
    """
    needle = phrase.lower()
    matches = []
    for line in build_lines(words):
        offset = 0
        spans = []  # (start_char, end_char, word)
        line_text_parts = []
        for w in line:
            start = offset
            line_text_parts.append(w.text)
            end = start + len(w.text)
            spans.append((start, end, w))
            offset = end + 1  # +1 for the joining space
        line_text = " ".join(line_text_parts).lower()
        idx = line_text.find(needle)
        if idx == -1:
            continue
        end_idx = idx + len(needle)
        covering = [w for (s, e, w) in spans if s < end_idx and e > idx]
        if not covering:
            continue
        x0 = min(w.x0 for w in covering)
        x1 = max(w.x1 for w in covering)
        y0 = min(w.y0 for w in covering)
        y1 = max(w.y1 for w in covering)
        matches.append(Word(x0, y0, x1, y1, phrase))
    if occurrence < len(matches):
        return matches[occurrence]
    return None


def extract_checkbox_circles(page: "fitz.Page") -> list[list[float]]:
    """Small circular radio-button shapes, isolated from rectangular boxes."""
    circles = []
    for d in page.get_drawings():
        r = d["rect"]
        w, h = round(r.width, 1), round(r.height, 1)
        types = {item[0] for item in d["items"]}
        if "c" in types and 10 <= w <= 16 and 10 <= h <= 16:
            circles.append([round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])
    return circles


def extract_date_entry_boxes(page: "fitz.Page") -> list[list[float]]:
    """The small single-character DDMMYYYY entry boxes drawn as rectangles."""
    boxes = []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] == "re":
                r = item[1]
                w, h = round(r.width, 1), round(r.height, 1)
                if 12 <= w <= 18 and 12 <= h <= 18:
                    boxes.append([round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)])
    return boxes


def pair_checkbox_labels(words: list[Word], circles: list[list[float]], max_gap: float = 80) -> list[CheckboxOption]:
    pairs = []
    for (x0, y0, x1, y1) in circles:
        cy = (y0 + y1) / 2
        best, best_dist = None, float("inf")
        for w in words:
            wcy = (w.y0 + w.y1) / 2
            if abs(wcy - cy) < 6 and w.x0 > x1 - 2 and (w.x0 - x1) < max_gap:
                dist = w.x0 - x1
                if dist < best_dist:
                    best_dist, best = dist, w.text
        pairs.append(CheckboxOption(box=[x0, y0, x1, y1], label=best))
    return pairs


# Back-compat alias: earlier drafts of this tool matched single words only.
# find_phrase (above) supersedes this -- it handles multi-word labels by
# reconstructing printed lines from PyMuPDF's (block, line) indices.
find_label = find_phrase


def inspect(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    report = {"page_count": doc.page_count, "pages": []}
    for i, page in enumerate(doc):
        words = extract_words(page)
        circles = extract_checkbox_circles(page)
        date_boxes = extract_date_entry_boxes(page)
        checkbox_pairs = pair_checkbox_labels(words, circles)
        report["pages"].append({
            "page_number": i + 1,
            "size": [round(page.rect.width, 1), round(page.rect.height, 1)],
            "word_count": len(words),
            "checkbox_count": len(circles),
            "date_entry_box_count": len(date_boxes),
            "checkboxes": [asdict(p) for p in checkbox_pairs],
        })
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("--out", default="layout.json")
    args = ap.parse_args()
    result = inspect(args.pdf_path)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Wrote {args.out}: {result['page_count']} pages")
