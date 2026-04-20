from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.pdf_codes import extract_valid_codes_from_pdf, extract_valid_codes_from_text_file
from src.report import write_csv, write_text
from src.transform import (
    build_base_snapshot_rows,
    build_compare_rows,
    build_expense_rows,
    build_income_rows,
    load_expense_mapping,
    _iter_budget_items,
)
from src.validate import find_validation_source, validate_code_hierarchy
from src.xlsx_reader import read_budget_sheet


def load_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def resolve_year_config(tool_root: Path, requested_year: str) -> tuple[Path, str]:
    try:
        target = int(requested_year)
    except ValueError:
        target = 2026

    for y in range(target, 1999, -1):
        p = tool_root / "config" / f"year_{y}.json"
        if p.exists():
            return p, str(y)
    raise FileNotFoundError("사용 가능한 연도 설정(config/year_YYYY.json)을 찾지 못했습니다.")


def find_first_file(base_dir: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(base_dir.glob(pattern))
        if matches:
            return matches[0]
    return None


def read_first_existing_sheet(xlsx: Path | None, candidates: list[str]) -> dict[int, dict[int, str]]:
    if not xlsx:
        return {}
    for name in candidates:
        rows = read_budget_sheet(xlsx, name)
        if rows:
            return rows
    return {}


def resolve_reference_doc(
    workspace: Path,
    config: dict,
    requested_year: str,
) -> tuple[str, Path, str]:
    # 1) 명시 패턴(TXT) 우선
    ref_text_patterns = config.get("reference_text_patterns", [])
    if ref_text_patterns:
        ref_text_file = find_first_file(workspace, ref_text_patterns)
        if ref_text_file:
            return "txt", ref_text_file, requested_year

    # 2) 요청 연도 -> 과거 연도 순으로 자동 탐색(TXT)
    try:
        target = int(requested_year)
    except ValueError:
        target = 2026
    for y in range(target, 1999, -1):
        txt_patterns = [
            f"*{y}*예산편성지침*.txt",
            f"*{y}*지방출자*예산편성지침*.txt",
            f"*{y}*지침*.txt",
        ]
        p = find_first_file(workspace, txt_patterns)
        if p:
            return "txt", p, str(y)

    # 3) config에 지정된 PDF
    pdf_name = config.get("reference_pdf", "")
    if pdf_name:
        p = workspace / pdf_name
        if p.exists():
            return "pdf", p, requested_year

    # 4) 요청 연도 -> 과거 연도 순으로 PDF 탐색
    for y in range(target, 1999, -1):
        pdf_patterns = [
            f"*{y}*예산편성지침*.pdf",
            f"*{y}*지방출자*예산편성지침*.pdf",
            f"*{y}*지침*.pdf",
        ]
        p = find_first_file(workspace, pdf_patterns)
        if p:
            return "pdf", p, str(y)

    raise FileNotFoundError("참조할 예산편성지침(TXT/PDF)을 찾지 못했습니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="예산 자동 분석/검증 도구")
    parser.add_argument("--year", default="2026", help="연도(설정파일 선택용)")
    parser.add_argument("--workspace", default=None, help="작업 폴더 경로")
    parser.add_argument("--base-file", default=None, help="본예산 xlsx 파일명 또는 경로")
    parser.add_argument("--supp-file", default=None, help="추경 xlsx 파일명 또는 경로")
    args = parser.parse_args()

    tool_root = Path(__file__).resolve().parent
    workspace = Path(args.workspace).resolve() if args.workspace else tool_root.parent
    config_path, applied_config_year = resolve_year_config(tool_root, args.year)
    config = load_config(config_path)

    if args.base_file:
        base_file = Path(args.base_file)
        if not base_file.is_absolute():
            base_file = workspace / base_file
    else:
        base_file = find_first_file(workspace, config["base_file_patterns"])
    if not base_file or not base_file.exists():
        raise FileNotFoundError("본예산 파일을 찾지 못했습니다.")

    supp_file = None
    if args.supp_file:
        supp_file = Path(args.supp_file)
        if not supp_file.is_absolute():
            supp_file = workspace / supp_file
    else:
        supp_file = find_first_file(workspace, config["supp_file_patterns"])
    if supp_file and not supp_file.exists():
        supp_file = None

    prev_file = find_first_file(workspace, config.get("prev_file_patterns", []))

    mapping_csv = tool_root / "master" / config["expense_mapping_file"]
    mapping = load_expense_mapping(mapping_csv)

    base_rows = read_budget_sheet(base_file, config["base_sheet_name"])
    supp_rows = read_budget_sheet(supp_file, config["supp_sheet_name"]) if supp_file else None
    prev_sheet_candidates = config.get(
        "prev_sheet_candidates",
        ["최종추경_기초", "3차추경_기초", "2차추경_기초", "1차추경_기초", "본예산_기초"],
    )
    prev_rows = read_first_existing_sheet(prev_file, prev_sheet_candidates) if prev_file else {}

    base_items = _iter_budget_items(base_rows, mapping)
    supp_items = _iter_budget_items(supp_rows or {}, mapping)

    income_rows = build_income_rows(base_rows, prev_rows or None, base_items, None)
    expense_rows, mapping_issues = build_expense_rows(base_rows, prev_rows or None, mapping)
    supp_income_rows = build_income_rows(supp_rows, base_rows, supp_items, base_items) if supp_rows else []
    supp_expense_rows = []
    if supp_rows:
        supp_expense_rows, _ = build_expense_rows(supp_rows, base_rows, mapping)
    compare_rows = build_compare_rows(base_rows, supp_rows)
    base_snapshot_rows = build_base_snapshot_rows(base_rows)
    supp_snapshot_rows = build_base_snapshot_rows(supp_rows or {})

    source_type, source_path, applied_guide_year = resolve_reference_doc(workspace, config, args.year)
    if source_type == "txt":
        lvl1, lvl2, lvl3 = extract_valid_codes_from_text_file(source_path)
        code_source = f"txt:{source_path.name}"
    else:
        lvl1, lvl2, lvl3 = extract_valid_codes_from_pdf(
            source_path, config["pdf_page_start"], config["pdf_page_end"]
        )
        code_source = f"pdf:{source_path.name}"

    validation_source = find_validation_source(workspace, config["validation_source_patterns"])
    validation_issues = []
    seen_codes = set()
    if validation_source:
        validation_issues, seen_codes = validate_code_hierarchy(lvl1, lvl2, lvl3, validation_source)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = tool_root / "output" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / "세입예산명세서_다중단위.csv", income_rows)
    write_csv(out_dir / "세출예산명세서_사업단위_다중단위.csv", expense_rows)
    write_csv(out_dir / "본예산_기초_파싱표.csv", base_snapshot_rows)
    if supp_rows:
        write_csv(out_dir / "세입예산명세서_추경_다중단위.csv", supp_income_rows)
        write_csv(out_dir / "세출예산명세서_추경_사업단위_다중단위.csv", supp_expense_rows)
        write_csv(out_dir / "추경_기초_파싱표.csv", supp_snapshot_rows)
    write_csv(out_dir / "본예산_추경_비교표.csv", compare_rows)

    issue_rows = [["종류", "행", "원본값", "코드", "유형", "설명"]]
    issue_rows.extend([["코드검증", *x] for x in validation_issues])
    issue_rows.extend([["세출매핑", "", biz, "", "매핑누락", msg] for biz, msg in mapping_issues])
    write_csv(out_dir / "정합성검증_리포트.csv", issue_rows)

    summary = []
    summary.append("예산 자동 분석 결과")
    summary.append(f"- 요청 연도: {args.year}")
    summary.append(f"- 적용 설정 연도: {applied_config_year}")
    summary.append(f"- 적용 지침 연도: {applied_guide_year}")
    summary.append(f"- 작업폴더: {workspace}")
    summary.append(f"- 본예산 파일: {base_file.name}")
    summary.append(f"- 추경 파일: {supp_file.name if supp_file else '없음'}")
    summary.append(f"- 비교기준 파일(전년도/기정): {prev_file.name if prev_file else '없음'}")
    summary.append(f"- 출력 폴더: {out_dir}")
    summary.append(f"- 코드셋 기준: {code_source}")
    summary.append(f"- 코드셋 크기: lvl1={len(lvl1)}, lvl2={len(lvl2)}, lvl3={len(lvl3)}")
    summary.append(f"- 코드검증 대상 코드 수: {len(seen_codes)}")
    summary.append(f"- 코드 검증 이슈: {len(validation_issues)}")
    summary.append(f"- 세출 매핑 누락: {len(mapping_issues)}")
    write_text(out_dir / "요약.txt", "\n".join(summary))

    print(out_dir)


if __name__ == "__main__":
    main()
