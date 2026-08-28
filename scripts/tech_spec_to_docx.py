#!/usr/bin/env python3
"""Business OS — client-friendly Word document generator.

Reads the tech-spec module docs (docs/tech-spec/modules/*.md) and the
scanner data (docs/tech-spec/_scan/pages.json) and produces a single
.docx written in plain business language — no API/endpoint jargon —
so a client can understand what the system does, module by module,
button by button.

Usage:
    python scripts/tech_spec_to_docx.py [--out docs/Business-OS-აღწერა.docx]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "docs" / "tech-spec" / "modules"
BUTTONS_DIR = ROOT / "docs" / "tech-spec" / "buttons"
SCAN_DIR = ROOT / "docs" / "tech-spec" / "_scan"

BRAND = RGBColor(0x10, 0x5F, 0x7D)   # brand teal
DARK = RGBColor(0x1F, 0x29, 0x37)
GRAY = RGBColor(0x6B, 0x72, 0x80)


def parse_md(path: Path) -> dict:
    """Extract title, purpose, button tables, business logic from a module doc."""
    text = path.read_text(encoding="utf-8")
    title = ""
    m = re.search(r"^# (.*)$", text, re.M)
    if m:
        title = m.group(1).strip()
        title = title.replace("მოდული: ", "")
        # keep only the Georgian name in parentheses if present:
        # "AccountingControls (ბუღალტრული კონტროლები)" -> "ბუღალტრული კონტროლები"
        pm = re.search(r"\(([^()]*[ა-ჰ][^()]*)\)", title)
        if pm:
            title = pm.group(1).strip()

    purpose = ""
    m = re.search(r"^## მიზანი\s*\n\n(.*?)(?=\n## |\Z)", text, re.S)
    if m:
        purpose = " ".join(m.group(1).split())

    # button tables: markdown tables whose header contains "ღილაკი" or "ელემენტი"
    buttons: list[tuple[str, str]] = []
    for tm in re.finditer(r"\|([^\n]+)\|\n\|[-| ]+\|\n((?:\|[^\n]+\|\n)+)", text):
        header = tm.group(1)
        if "ღილაკი" not in header and "ელემენტი" not in header:
            continue
        cols = [c.strip() for c in header.split("|") if c.strip()]
        for row in tm.group(2).strip().splitlines():
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) >= 2:
                buttons.append((cells[0], cells[1]))

    logic = ""
    m = re.search(r"^## ბიზნეს ლოგიკა\s*\n\n(.*?)(?=\n## |\Z)", text, re.S)
    if m:
        logic = " ".join(m.group(1).split())

    return {"title": title, "purpose": purpose, "buttons": buttons, "logic": logic}


def add_heading(doc, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = BRAND if level <= 2 else DARK
        run.font.name = "Arial"
    return h


def add_para(doc, text: str, size: float = 11, bold: bool = False, color=None) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Arial"
    if color:
        run.font.color.rgb = color
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "Business-OS-სისტემის-აღწერა.docx"))
    args = ap.parse_args()
    out = Path(args.out)

    doc = Document()
    # page setup
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(22)
    section.bottom_margin = Mm(22)
    section.left_margin = Mm(20)
    section.right_margin = Mm(20)

    # default font
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    # ── Cover ─────────────────────────────────────────────────────────────
    for _ in range(6):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("Business OS")
    r.font.size = Pt(40)
    r.font.bold = True
    r.font.color.rgb = BRAND
    r.font.name = "Arial"

    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = st.add_run("სისტემის სრული აღწერა")
    r.font.size = Pt(20)
    r.font.color.rgb = DARK
    r.font.name = "Arial"

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("რას აკეთებს სისტემა, მოდული მოდულზე — მარტივი ენით")
    r.font.size = Pt(12)
    r.font.italic = True
    r.font.color.rgb = GRAY
    r.font.name = "Arial"

    doc.add_page_break()

    # ── Intro ─────────────────────────────────────────────────────────────
    add_heading(doc, "შესავალი", 1)
    add_para(doc, (
        "Business OS არის ერთიანი პროგრამა, რომელიც აერთიანებს კომპანიის "
        "მთელ საქმიანობას ერთ ადგილზე: კლიენტები, გაყიდვები, შესყიდვები, "
        "საწყობი, ფინანსები, ბუღალტერია, თანამშრომლები და სხვა. "
        "ყველა მონაცემი ინახება ერთ ბაზაში, ამიტომ ინფორმაცია არ იკარგება "
        "და ყოველთვის განახლებულია."
    ))
    add_para(doc, (
        "ეს დოკუმენტი განმარტავს, რას აკეთებს სისტემის თითოეული ნაწილი "
        "და თითოეული ღილაკი — ისე, რომ ტექნიკური ცოდნა არ იყოს საჭირო."
    ))

    # ── Module index table ────────────────────────────────────────────────
    add_heading(doc, "სისტემის ნაწილები (მოდულები)", 1)
    add_para(doc, "სისტემა შედგება შემდეგი ნაწილებისგან:")

    files = sorted(MODULES_DIR.glob("*.md"))
    table = doc.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(["#", "ნაწილი", "რას აკეთებს"]):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)

    for idx, f in enumerate(files, 1):
        data = parse_md(f)
        row = table.add_row().cells
        row[0].text = str(idx)
        row[1].text = data["title"]
        purpose = data["purpose"]
        row[2].text = purpose[:160] + ("…" if len(purpose) > 160 else "")
        for c in row:
            for p in c.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)

    doc.add_page_break()

    # ── Per-module detail ─────────────────────────────────────────────────
    add_heading(doc, "დეტალური აღწერა", 1)
    add_para(doc, "თითოეული ნაწილის აღწერა: რისთვის არის, რა ღილაკებს ხედავთ და რას აკეთებენ ისინი.")

    for f in files:
        data = parse_md(f)
        title = data["title"]
        add_heading(doc, title, 2)

        if data["purpose"]:
            add_para(doc, data["purpose"])

        if data["buttons"]:
            add_para(doc, "ძირითადი ღილაკები და მათი დანიშნულება:", bold=True, size=10)
            bt = doc.add_table(rows=1, cols=2)
            bt.style = "Light Grid Accent 1"
            h = bt.rows[0].cells
            h[0].text = "ღილაკი / ელემენტი"
            h[1].text = "რას აკეთებს"
            for c in h:
                for p in c.paragraphs:
                    for run in p.runs:
                        run.font.bold = True
                        run.font.size = Pt(9)
            seen = set()
            for label, desc in data["buttons"]:
                key = (label, desc)
                if key in seen or len(label) > 60:
                    continue
                seen.add(key)
                row = bt.add_row().cells
                row[0].text = label
                row[1].text = desc
                for c in row:
                    for p in c.paragraphs:
                        for run in p.runs:
                            run.font.size = Pt(9)

        # ── Detailed button descriptions (client language) ────────────────
        # Look for a buttons/<module-code>.json file with full per-button
        # descriptions: usage / when / action / result.
        btn_file = BUTTONS_DIR / f"{f.stem}.json"
        if btn_file.exists():
            try:
                btn_data = json.loads(btn_file.read_text(encoding="utf-8"))
                # structure: {"invoices": {"module": ..., "buttons": {...}}}
                btns = {}
                for v in btn_data.values():
                    if isinstance(v, dict) and "buttons" in v:
                        btns = v["buttons"]
                        break
                if not btns and isinstance(btn_data, dict) and "buttons" in btn_data:
                    btns = btn_data["buttons"]
                if btns:
                    add_para(doc, "თითოეული ღილაკის დეტალური აღწერა:", bold=True, size=10)
                    for label, info in btns.items():
                        p = doc.add_paragraph()
                        r = p.add_run(f"▸ {label}")
                        r.font.bold = True
                        r.font.size = Pt(10)
                        r.font.color.rgb = BRAND
                        for field, field_label in (
                            ("usage", "რისთვის გამოიყენება"),
                            ("when", "როდის ჩნდება"),
                            ("action", "რას აკეთებს დაჭერისას"),
                            ("result", "რა ხდება შემდეგ"),
                        ):
                            if info.get(field):
                                fp = doc.add_paragraph()
                                fp.paragraph_format.left_indent = Mm(8)
                                fr = fp.add_run(f"{field_label}: ")
                                fr.font.bold = True
                                fr.font.size = Pt(9.5)
                                fr2 = fp.add_run(info[field])
                                fr2.font.size = Pt(9.5)
            except Exception as e:  # noqa: BLE001
                print(f"⚠ buttons file {btn_file.name}: {e}", file=sys.stderr)

        if data["logic"]:
            add_para(doc, "როგორ მუშაობს:", bold=True, size=10)
            add_para(doc, data["logic"], size=10)

    # footer with page numbers
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run("Business OS — სისტემის აღწერა")
    run.font.size = Pt(8)
    run.font.color.rgb = GRAY

    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    print(f"✅ Saved: {out} ({len(files)} modules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
