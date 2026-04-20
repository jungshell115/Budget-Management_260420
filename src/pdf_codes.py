from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader


def _extract_valid_codes_from_text(text: str):
    raw_codes = set(re.findall(r"(?<!\d)\d{3}(?:-\d{2})?(?!\d)", text))
    lvl2 = {x for x in raw_codes if "-" not in x and 100 <= int(x) <= 899}
    lvl3 = {x for x in raw_codes if "-" in x}

    # 지침 본문에서 "201" + "01" 형태로 분리 표기되는 세목을 보강 조합한다.
    token_re = re.compile(r"(?<!\d)(\d{3}(?:-\d{2})?|\d{2})(?!\d)")
    current_3digit = None
    for line in text.splitlines():
        for tk in token_re.findall(line):
            if re.fullmatch(r"\d{3}", tk):
                current_3digit = tk if tk in lvl2 else None
            elif re.fullmatch(r"\d{3}-\d{2}", tk):
                lvl3.add(tk)
                current_3digit = tk.split("-")[0]
            elif re.fullmatch(r"\d{2}", tk) and current_3digit is not None:
                lvl3.add(f"{current_3digit}-{tk}")

    lvl1 = {x for x in lvl2 if x.endswith("00")}
    return lvl1, lvl2, lvl3


def extract_valid_codes_from_text_file(text_path: Path):
    if not text_path.exists():
        raise FileNotFoundError(f"지침 TXT 없음: {text_path}")
    text = text_path.read_text(encoding="utf-8")
    return _extract_valid_codes_from_text(text)


def extract_valid_codes_from_pdf(pdf_path: Path, page_start: int, page_end: int):
    if not pdf_path.exists():
        raise FileNotFoundError(f"지침 PDF 없음: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    start_idx = max(page_start - 1, 0)
    end_idx = min(page_end - 1, len(reader.pages) - 1)
    text = "\n".join((reader.pages[i].extract_text() or "") for i in range(start_idx, end_idx + 1))
    return _extract_valid_codes_from_text(text)
