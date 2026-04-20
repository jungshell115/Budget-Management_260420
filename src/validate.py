from __future__ import annotations

import csv
import re
from pathlib import Path


def find_validation_source(workspace: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(workspace.glob(pattern))
        if matches:
            return matches[0]
    return None


def _parse_codes_in_row(cells: list[str]):
    out = []
    for idx, value in enumerate(cells):
        s = str(value).strip()
        m = re.match(r"^(\d{3}(?:-\d{2})?)\b", s)
        if m:
            out.append((idx, m.group(1), s))
    return out


def _read_csv_with_fallback(path: Path):
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.reader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"지원되지 않는 인코딩: {path}")


def validate_code_hierarchy(level1: set[str], level2: set[str], level3: set[str], csv_path: Path):
    rows = _read_csv_with_fallback(csv_path)
    issues = []
    seen_codes = set()

    for r_idx, row in enumerate(rows, start=1):
        code_cells = _parse_codes_in_row(row[:6])
        if not code_cells:
            continue

        row_lvl1 = [c for _, c, _ in code_cells if "-" not in c and c.endswith("00")]
        row_lvl2 = [c for _, c, _ in code_cells if "-" not in c and not c.endswith("00")]
        row_lvl3 = [c for _, c, _ in code_cells if "-" in c]

        for _, code, raw in code_cells:
            if code == "201-13" and "교육훈련비" in raw:
                code = "201-12"
            seen_codes.add(code)
            if "-" in code:
                parent2 = code.split("-")[0]
                if code not in level3:
                    if parent2 not in level2:
                        issues.append([r_idx, raw, code, "코드미존재", "지침 코드셋 기준 미정의 세목"])
                if parent2 not in level2:
                    issues.append([r_idx, raw, code, "상위목누락", f"상위목 {parent2} 미정의"])
            else:
                if code not in level2:
                    issues.append([r_idx, raw, code, "코드미존재", "지침 코드셋 기준 미정의 목/관항"])
                if not code.endswith("00"):
                    parent1 = f"{(int(code) // 100) * 100:03d}"
                    if parent1 not in level1:
                        issues.append([r_idx, raw, code, "관항누락", f"상위관항 {parent1} 미정의"])

        if row_lvl1 and row_lvl2:
            for lv2 in row_lvl2:
                need = f"{(int(lv2) // 100) * 100:03d}"
                if need not in row_lvl1:
                    issues.append([r_idx, "", lv2, "행계층불일치", f"행 내 상위 {need} 누락"])
        if row_lvl2 and row_lvl3:
            for lv3 in row_lvl3:
                need = lv3.split("-")[0]
                if need not in row_lvl2:
                    issues.append([r_idx, "", lv3, "행계층불일치", f"행 내 상위 {need} 누락"])

    return issues, seen_codes
