from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall("main:si", NS):
        parts = []
        for t in si.findall(".//main:t", NS):
            if t.text:
                parts.append(t.text)
        out.append("".join(parts))
    return out


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    v = cell.find("main:v", NS)
    if v is None or v.text is None:
        inline_str = cell.find("main:is", NS)
        if inline_str is not None:
            return "".join(x.text or "" for x in inline_str.findall(".//main:t", NS))
        return ""
    if cell_type == "s":
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            return v.text
    return v.text


def _sheet_map(zf: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.get("Id"): r.get("Target") for r in rels if r.tag.endswith("Relationship")}
    out: dict[str, str] = {}
    for sheet in wb.findall("main:sheets/main:sheet", NS):
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rid_to_target.get(rid, "")
        path = "xl/" + target.replace("\\", "/") if target and not target.startswith("/") else target.lstrip("/")
        out[sheet.get("name")] = path
    return out


def read_budget_sheet(xlsx: Path | None, sheet_name: str) -> dict[int, dict[int, str]]:
    if not xlsx:
        return {}
    if not xlsx.exists():
        raise FileNotFoundError(f"파일 없음: {xlsx}")

    with zipfile.ZipFile(xlsx, "r") as zf:
        mapping = _sheet_map(zf)
        if sheet_name not in mapping:
            return {}

        shared = _load_shared_strings(zf)
        root = ET.fromstring(zf.read(mapping[sheet_name]))
        rows: dict[int, dict[int, str]] = {}

        for row in root.findall(".//main:sheetData/main:row", NS):
            rnum = int(row.get("r", "0"))
            cur: dict[int, str] = {}
            for cell in row.findall("main:c", NS):
                ref = cell.get("r")
                if not ref:
                    continue
                m = re.match(r"^([A-Z]+)(\d+)$", ref)
                if not m:
                    continue
                letters = m.group(1)
                col = 0
                for ch in letters:
                    col = col * 26 + (ord(ch) - 64)
                cur[col] = _cell_value(cell, shared)
            rows[rnum] = cur
        return rows
