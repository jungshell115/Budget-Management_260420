from __future__ import annotations

import csv
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.transform import _iter_budget_items
from src.xlsx_reader import read_budget_sheet


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
OUTPUT_DIR = BASE_DIR / "output"
EDIT_DIR = BASE_DIR / "web_edits"
CITY_KEYS = [
    "천안",
    "아산",
    "당진",
    "예산",
    "계룡",
    "공주",
    "금산",
    "논산",
    "보령",
    "부여",
    "서산",
    "서천",
    "청양",
    "태안",
    "홍성",
]
ENTRUSTED_KEYS = ["국비", "도비", *CITY_KEYS]


def to_int(value: str) -> int:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def amount_by_subject_prefix(rows: list[dict[str, str]], prefix: str) -> int:
    for row in rows:
        subject = (row.get("과목") or "").strip()
        if subject.startswith(prefix):
            return to_int(row.get("현재예산(원)", "0"))
    return 0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_edits_with_fallback(current_stamp: str) -> dict:
    current_path = EDIT_DIR / f"{current_stamp}.json"
    edits = read_json(current_path)
    if edits:
        return edits
    if not EDIT_DIR.exists():
        return {}
    for p in sorted(EDIT_DIR.glob("*.json"), reverse=True):
        if p.stem == current_stamp:
            continue
        data = read_json(p)
        if data:
            return data
    return {}


def latest_output_dir() -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    candidates = [p for p in OUTPUT_DIR.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def list_output_dirs() -> list[Path]:
    if not OUTPUT_DIR.exists():
        return []
    return sorted([p for p in OUTPUT_DIR.iterdir() if p.is_dir()])


def parse_issue_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    counter: dict[str, int] = {}
    for row in rows:
        issue_type = (row.get("유형") or row.get("종류") or "").strip()
        if not issue_type:
            issue_type = (row.get("설명") or "").strip()
        counter[issue_type] = counter.get(issue_type, 0) + 1
    return counter


def parse_issue_by_code(rows: list[dict[str, str]]) -> list[dict]:
    bucket: dict[str, dict] = {}
    for row in rows:
        code = (row.get("코드") or "").strip()
        raw = (row.get("원본값") or "").strip()
        issue_type = (row.get("유형") or "").strip()
        if not code:
            continue
        key = f"{code}|{issue_type or '기타'}"
        if key not in bucket:
            bucket[key] = {
                "코드": code,
                "원본값": raw,
                "유형": issue_type or "기타",
                "건수": 0,
            }
        bucket[key]["건수"] += 1
    return sorted(bucket.values(), key=lambda x: x["건수"], reverse=True)


def extract_year_and_round(filename: str, default_label: str) -> tuple[str, str]:
    year_match = re.search(r"(20\d{2})년", filename or "")
    year = year_match.group(1) if year_match else ""
    round_label = default_label
    if "추경" in (filename or ""):
        m = re.search(r"(\d+)차\s*추경", filename)
        round_label = f"{m.group(1)}차 추경" if m else "추경"
    elif "본예산" in (filename or ""):
        round_label = "본예산"
    return year, round_label


def parse_summary_meta(summary_text: str) -> dict:
    meta = {"baseFile": "", "suppFile": "", "workspace": ""}
    for line in summary_text.splitlines():
        if line.startswith("- 본예산 파일:"):
            meta["baseFile"] = line.split(":", 1)[1].strip()
        elif line.startswith("- 추경 파일:"):
            value = line.split(":", 1)[1].strip()
            meta["suppFile"] = "" if value == "없음" else value
        elif line.startswith("- 작업폴더:"):
            meta["workspace"] = line.split(":", 1)[1].strip()
    return meta


def infer_output_year(output_dir: Path) -> str:
    summary_file = output_dir / "요약.txt"
    if not summary_file.exists():
        return ""
    summary_meta = parse_summary_meta(summary_file.read_text(encoding="utf-8"))
    y_base, _ = extract_year_and_round(summary_meta.get("baseFile", ""), "본예산")
    y_supp, _ = extract_year_and_round(summary_meta.get("suppFile", ""), "추경")
    return y_base or y_supp


def select_output_dir(selected_year: str | None = None) -> tuple[Path | None, list[str], str]:
    dirs = list_output_dirs()
    if not dirs:
        return None, [], ""
    year_pairs: list[tuple[Path, str]] = []
    for d in dirs:
        y = infer_output_year(d)
        if y:
            year_pairs.append((d, y))
    available_years = sorted({y for _, y in year_pairs}, reverse=True)
    if selected_year:
        matched = [d for d, y in year_pairs if y == str(selected_year)]
        if matched:
            chosen = matched[-1]
            return chosen, available_years, str(selected_year)
    chosen_latest = dirs[-1]
    chosen_year = infer_output_year(chosen_latest)
    return chosen_latest, available_years, chosen_year


def apply_table_edits(rows: list[dict[str, str]], table_name: str, edits: dict):
    table_edits = edits.get("tables", {}).get(table_name, {})
    for r_idx_str, col_map in table_edits.items():
        try:
            r_idx = int(r_idx_str)
        except ValueError:
            continue
        if r_idx < 0 or r_idx >= len(rows):
            continue
        for col, value in col_map.items():
            rows[r_idx][col] = str(value)


def normalize_budget_type(value: str) -> str:
    return "supp" if str(value).strip().lower() == "supp" else "base"


def pick_snapshot_rows(
    budget_type: str,
    base_snapshot_rows: list[dict[str, str]],
    supp_snapshot_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    if budget_type == "supp" and supp_snapshot_rows:
        return supp_snapshot_rows
    return base_snapshot_rows


def _empty_entrusted_flags() -> dict[str, bool]:
    return {}


def _empty_entrusted_amounts() -> dict[str, int]:
    return {}


def _to_entrusted_amounts(raw: dict | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        out[str(key)] = to_int(str(value))
    return out


def _to_entrusted_flags(raw: dict | None) -> dict[str, bool]:
    out: dict[str, bool] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        out[str(key)] = str(value).strip().lower() in {"1", "true", "yes", "y", "여"}
    return out


def _business_limit_rows(snapshot_rows: list[dict[str, str]], item_map: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in snapshot_rows:
        biz = (row.get("사업명") or "").strip()
        if not biz or biz in {"0", "소계"} or biz in seen:
            continue
        seen.add(biz)
        item = item_map.get(biz, {})
        source_limits: dict[str, int] = {}
        national = to_int(str(item.get("국비", row.get("국비", "0"))))
        dobi_subsidy = to_int(str(item.get("도비보조", row.get("도비", "0"))))
        if national > 0:
            source_limits["국비"] = national
        if dobi_subsidy > 0:
            source_limits["도비"] = dobi_subsidy
        city_added = False
        for city in CITY_KEYS:
            c_amt = to_int(str(item.get(f"보조_{city}", 0)))
            if c_amt > 0:
                source_limits[f"시군_{city}"] = c_amt
                city_added = True
        if not city_added:
            city_total = to_int(str(item.get("시군보조", row.get("시군비", "0"))))
            if city_total > 0:
                source_limits["시군비"] = city_total
        if not source_limits:
            continue
        out.append(
            {
                "사업명": biz,
                "구분": (row.get("구분") or "").strip(),
                "부서": (row.get("부서") or "").strip(),
                "limits": source_limits,
            }
        )
    return out


def _get_entrusted_bucket(edits: dict, budget_type: str) -> dict:
    entrusted = edits.setdefault("entrusted", {})
    return entrusted.setdefault(normalize_budget_type(budget_type), {})


def _label_for_source(source: str) -> str:
    if source == "국비":
        return "국비"
    if source == "도비":
        return "도비"
    if source == "시군비":
        return "시군비"
    if source.startswith("시군_"):
        city = source.split("_", 1)[1]
        return f"{city}시비"
    return source


def _validate_entrusted(enabled: dict[str, bool], amounts: dict[str, int], limits: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    for source, limit in limits.items():
        is_enabled = bool(enabled.get(source, False))
        amount = to_int(str(amounts.get(source, 0)))
        label = _label_for_source(source)
        if is_enabled and amount > limit:
            warnings.append(f"{label} 위탁사업비가 보조 한도를 초과")
        if (not is_enabled) and amount > 0:
            warnings.append(f"{label} 여부가 부인데 금액이 입력됨")
    for source, amount in amounts.items():
        if source not in limits and to_int(str(amount)) > 0:
            warnings.append(f"{_label_for_source(source)}는 보조금이 없어 입력할 수 없음")
    return warnings


def _legacy_enabled_to_flags(enabled_raw: object) -> dict[str, bool]:
    # 이전 버전(bool 단일 enabled) 저장값 호환
    if isinstance(enabled_raw, bool):
        return {"국비": enabled_raw, "도비": enabled_raw, "시군비": enabled_raw}
    return _to_entrusted_flags(enabled_raw if isinstance(enabled_raw, dict) else {})


def _legacy_amounts_to_simple(amounts_raw: dict | None) -> dict[str, int]:
    amounts = _to_entrusted_amounts(amounts_raw)
    # 구버전 키(도비보조, 시군별 도시 키들)를 단순축으로 흡수
    if isinstance(amounts_raw, dict):
        amounts["도비"] = to_int(str(amounts_raw.get("도비", amounts_raw.get("도비보조", amounts.get("도비", 0)))))
        if "시군비" in amounts_raw:
            city_total = to_int(str(amounts_raw.get("시군비", "0")))
            if city_total > 0 and not any(to_int(str(amounts_raw.get(city, "0"))) > 0 for city in CITY_KEYS):
                amounts["천안"] = city_total
        else:
            for city in CITY_KEYS:
                amounts[city] = to_int(str(amounts_raw.get(city, "0")))
            if not any(amounts[city] > 0 for city in CITY_KEYS):
                for key, value in amounts_raw.items():
                    if key not in {"국비", "도비", "도비보조"}:
                        amounts["천안"] += to_int(str(value))
    return amounts


def _load_item_map_for_latest(latest: Path, budget_type: str, summary_meta: dict) -> dict[str, dict]:
    workspace = Path(summary_meta.get("workspace") or BASE_DIR.parent)
    file_name = summary_meta.get("suppFile" if budget_type == "supp" else "baseFile", "")
    if not file_name:
        return {}
    xlsx = workspace / file_name
    if not xlsx.exists():
        return {}
    sheet_candidates = ["본예산_기초"]
    if budget_type == "supp":
        sheet_candidates = ["1차추경_기초", "2차추경_기초", "3차추경_기초", "최종추경_기초"]
    rows: dict[int, dict[int, str]] = {}
    for sheet in sheet_candidates:
        rows = read_budget_sheet(xlsx, sheet)
        if rows:
            break
    if not rows:
        return {}
    items = _iter_budget_items(rows, {})
    return {str(it.get("사업명", "")): it for it in items if str(it.get("사업명", "")).strip()}


def _append_income_formula_issues(issue_rows: list[dict[str, str]], income_rows: list[dict[str, str]], label: str) -> None:
    def amt(prefix: str) -> int | None:
        for row in income_rows:
            subj = (row.get("과목") or "").strip()
            if subj.startswith(prefix):
                return to_int(row.get("현재예산(원)", "0"))
        return None

    org_amt = None
    for row in income_rows:
        subj = (row.get("과목") or "").strip()
        if subj.startswith("(재)"):
            org_amt = to_int(row.get("현재예산(원)", "0"))
            break
    v600 = amt("600 ")
    v100 = amt("100 ")
    v610 = amt("610 ")
    v646 = amt("646 ")
    v64601 = amt("646-01 ")
    v64602 = amt("646-02 ")
    v648 = amt("648 ")
    v64802 = amt("648-02 ")

    def add(code: str, desc: str):
        issue_rows.append({"종류": "산식검증", "행": "", "원본값": label, "코드": code, "유형": "산식오류", "설명": desc})

    if org_amt is None or v600 is None or v610 is None:
        add("600/610", "핵심 세입 과목(기관/600/610) 누락")
        return
    total_target = v600 + (v100 or 0)
    if org_amt != total_target:
        add("기관/합계", f"기관합계({org_amt:,})와 600+100({total_target:,}) 불일치")
    if v600 != v610:
        add("600/610", f"600({v600:,})와 610({v610:,}) 불일치")
    if v646 is not None and v64601 is not None and v64602 is not None and v646 != (v64601 + v64602):
        add("646", f"646({v646:,}) != 646-01+646-02({v64601 + v64602:,})")
    if v648 is not None and v64802 is not None and v648 != v64802:
        add("648", f"648({v648:,}) != 648-02({v64802:,})")


def load_entrusted_rows_for_latest(budget_type: str, selected_year: str | None = None) -> dict:
    latest, available_years, selected = select_output_dir(selected_year)
    if latest is None:
        return {"ok": False, "message": "output 폴더에 분석 결과가 없습니다."}

    edits = load_edits_with_fallback(latest.name) or {}
    summary_text = (latest / "요약.txt").read_text(encoding="utf-8") if (latest / "요약.txt").exists() else ""
    summary_meta = parse_summary_meta(summary_text)
    base_snapshot_rows = read_csv(latest / "본예산_기초_파싱표.csv")
    supp_snapshot_rows = read_csv(latest / "추경_기초_파싱표.csv")
    apply_table_edits(base_snapshot_rows, "snapshot_base", edits)
    apply_table_edits(supp_snapshot_rows, "snapshot_supp", edits)

    snapshot_rows = pick_snapshot_rows(normalize_budget_type(budget_type), base_snapshot_rows, supp_snapshot_rows)
    item_map = _load_item_map_for_latest(latest, normalize_budget_type(budget_type), summary_meta)
    limit_rows = _business_limit_rows(snapshot_rows, item_map)
    bucket = _get_entrusted_bucket(edits, budget_type)

    rows: list[dict] = []
    for info in limit_rows:
        biz = info["사업명"]
        saved = bucket.get(biz, {})
        enabled_raw = _legacy_enabled_to_flags(saved.get("enabled", {}))
        amounts_raw = _legacy_amounts_to_simple(saved.get("amounts", {}))
        enabled = {src: bool(enabled_raw.get(src, False)) for src in info["limits"].keys()}
        amounts = {src: to_int(str(amounts_raw.get(src, 0))) for src in info["limits"].keys()}
        warnings = _validate_entrusted(enabled, amounts, info["limits"])
        rows.append(
            {
                "사업명": biz,
                "구분": info["구분"],
                "부서": info["부서"],
                "enabled": enabled,
                "limits": info["limits"],
                "sources": [
                    {"id": src, "label": _label_for_source(src), "limit": lim}
                    for src, lim in info["limits"].items()
                ],
                "amounts": amounts,
                "warnings": warnings,
            }
        )

    enabled_rows = [r for r in rows if any(r.get("enabled", {}).values())]
    total_amount = 0
    for row in enabled_rows:
        for src in row["limits"].keys():
            if row["enabled"].get(src):
                total_amount += to_int(str(row["amounts"].get(src, 0)))

    return {
        "ok": True,
        "latestFolder": latest.name,
        "budgetType": normalize_budget_type(budget_type),
        "selectedYear": selected,
        "availableYears": available_years,
        "keys": ENTRUSTED_KEYS,
        "rows": rows,
        "summary": {
            "enabledCount": len(enabled_rows),
            "totalAmount": total_amount,
            "warningCount": sum(1 for r in rows if r.get("warnings")),
        },
    }


def save_entrusted_entry(payload: dict) -> tuple[bool, str]:
    latest, _years, _selected = select_output_dir(str(payload.get("year", "")).strip() or None)
    if latest is None:
        return False, "output 폴더에 분석 결과가 없습니다."

    budget_type = normalize_budget_type(payload.get("budgetType", "base"))
    business = str(payload.get("business", "")).strip()
    if not business:
        return False, "사업명이 필요합니다."

    enabled = _legacy_enabled_to_flags(payload.get("enabled", {}))
    amounts = _legacy_amounts_to_simple(payload.get("amounts", {}))
    for key, flag in enabled.items():
        if not flag:
            amounts[key] = 0
    if any(v < 0 for v in amounts.values()):
        return False, "위탁사업비 금액은 0 이상이어야 합니다."

    edits_path = EDIT_DIR / f"{latest.name}.json"
    edits = read_json(edits_path) or load_edits_with_fallback(latest.name) or {}
    base_snapshot_rows = read_csv(latest / "본예산_기초_파싱표.csv")
    supp_snapshot_rows = read_csv(latest / "추경_기초_파싱표.csv")
    apply_table_edits(base_snapshot_rows, "snapshot_base", edits)
    apply_table_edits(supp_snapshot_rows, "snapshot_supp", edits)

    summary_text = (latest / "요약.txt").read_text(encoding="utf-8") if (latest / "요약.txt").exists() else ""
    summary_meta = parse_summary_meta(summary_text)
    snapshot_rows = pick_snapshot_rows(budget_type, base_snapshot_rows, supp_snapshot_rows)
    item_map = _load_item_map_for_latest(latest, budget_type, summary_meta)
    limits: dict[str, int] = {}
    for info in _business_limit_rows(snapshot_rows, item_map):
        if info["사업명"] == business:
            limits = info["limits"]
            break
    enabled = {src: bool(enabled.get(src, False)) for src in limits.keys()}
    amounts = {src: to_int(str(amounts.get(src, 0))) for src in limits.keys()}
    warnings = _validate_entrusted(enabled, amounts, limits)
    if warnings:
        return False, f"검증 실패: {warnings[0]}"

    bucket = _get_entrusted_bucket(edits, budget_type)
    bucket[business] = {"enabled": enabled, "amounts": amounts}
    write_json(edits_path, edits)
    return True, "저장되었습니다."


def load_dashboard_payload(selected_year: str | None = None) -> dict:
    latest, available_years, selected = select_output_dir(selected_year)
    if latest is None:
        return {"ok": False, "message": "output 폴더에 분석 결과가 없습니다."}

    income_rows = read_csv(latest / "세입예산명세서_다중단위.csv")
    expense_rows = read_csv(latest / "세출예산명세서_사업단위_다중단위.csv")
    compare_rows = read_csv(latest / "본예산_추경_비교표.csv")
    issue_rows = read_csv(latest / "정합성검증_리포트.csv")
    summary_text = (latest / "요약.txt").read_text(encoding="utf-8") if (latest / "요약.txt").exists() else ""
    edits = load_edits_with_fallback(latest.name)

    supp_income_rows = read_csv(latest / "세입예산명세서_추경_다중단위.csv")
    supp_expense_rows = read_csv(latest / "세출예산명세서_추경_사업단위_다중단위.csv")
    base_snapshot_rows = read_csv(latest / "본예산_기초_파싱표.csv")
    supp_snapshot_rows = read_csv(latest / "추경_기초_파싱표.csv")

    apply_table_edits(income_rows, "income_base", edits)
    apply_table_edits(expense_rows, "expense_base", edits)
    apply_table_edits(issue_rows, "issues", edits)
    apply_table_edits(supp_income_rows, "income_supp", edits)
    apply_table_edits(supp_expense_rows, "expense_supp", edits)
    apply_table_edits(base_snapshot_rows, "snapshot_base", edits)
    apply_table_edits(supp_snapshot_rows, "snapshot_supp", edits)
    _append_income_formula_issues(issue_rows, income_rows, "본예산")
    if supp_income_rows:
        _append_income_formula_issues(issue_rows, supp_income_rows, "추경")
    entrusted_base = load_entrusted_rows_for_latest("base", selected)
    entrusted_supp = load_entrusted_rows_for_latest("supp", selected)

    total_revenue = amount_by_subject_prefix(income_rows, "600 ")
    op_revenue = amount_by_subject_prefix(income_rows, "610 ")
    subsidy = amount_by_subject_prefix(income_rows, "646 ")
    contribution = amount_by_subject_prefix(income_rows, "648 ")

    def top_expense_rows(rows: list[dict[str, str]]) -> list[dict]:
        biz_rows = [r for r in rows if (r.get("유형") or "") == "사업"]
        sorted_rows = sorted(biz_rows, key=lambda r: to_int(r.get("현재예산(원)", "0")), reverse=True)
        return [
            {
                "사업명": r.get("사업명", ""),
                "부서": r.get("부서", ""),
                "합계원": to_int(r.get("현재예산(원)", "0")),
                "관항": r.get("관항", ""),
                "목": r.get("목", ""),
                "세목": r.get("세목", ""),
                "구분": r.get("구분", ""),
            }
            for r in sorted_rows[:8]
            if r.get("사업명")
        ]

    top_expense_base = top_expense_rows(expense_rows)
    top_expense_supp = top_expense_rows(supp_expense_rows) if supp_expense_rows else []

    compare_sorted = sorted(
        compare_rows,
        key=lambda r: abs(to_int(r.get("증감(원)", "0"))),
        reverse=True,
    )
    compare_top = [
        {
            "사업명": r.get("사업명", ""),
            "본예산": to_int(r.get("본예산(원)", "0")),
            "추경": to_int(r.get("추경(원)", "0")),
            "증감": to_int(r.get("증감(원)", "0")),
        }
        for r in compare_sorted[:8]
        if r.get("사업명")
    ]

    issue_summary = parse_issue_summary(issue_rows)
    issue_by_code = parse_issue_by_code(issue_rows)
    summary_meta = parse_summary_meta(summary_text)
    year_from_base, base_label = extract_year_and_round(summary_meta.get("baseFile", ""), "본예산")
    year_from_supp, supp_label = extract_year_and_round(summary_meta.get("suppFile", ""), "추경")
    year = year_from_base or year_from_supp

    def list_unique(rows: list[dict[str, str]], key: str) -> list[str]:
        return sorted({(r.get(key) or "").strip() for r in rows if (r.get(key) or "").strip()})

    filter_options = {
        "구분": list_unique(expense_rows, "구분"),
        "부서": list_unique(expense_rows, "부서"),
        "관항": list_unique(expense_rows, "관항"),
        "목": list_unique(expense_rows, "목"),
    }

    def short_rows(rows: list[dict[str, str]], limit: int = 20):
        return rows[:limit]

    return {
        "ok": True,
        "latestFolder": latest.name,
        "summaryText": summary_text,
        "metrics": {
            "totalRevenue": total_revenue,
            "operatingRevenue": op_revenue,
            "subsidyRevenue": subsidy,
            "contributionRevenue": contribution,
            "issueCount": len(issue_rows),
            "entrustedBaseTotal": entrusted_base.get("summary", {}).get("totalAmount", 0),
            "entrustedSuppTotal": entrusted_supp.get("summary", {}).get("totalAmount", 0),
        },
        "meta": {
            "year": year,
            "selectedYear": selected or year,
            "availableYears": available_years,
            "baseLabel": base_label,
            "suppLabel": supp_label if summary_meta.get("suppFile") else "",
            "baseFile": summary_meta.get("baseFile", ""),
            "suppFile": summary_meta.get("suppFile", ""),
            "hasSupp": bool(supp_income_rows and supp_expense_rows),
        },
        "topExpense": {
            "base": top_expense_base,
            "supp": top_expense_supp,
        },
        "topChanges": compare_top,
        "issueSummary": issue_summary,
        "issueByCodeSummary": issue_by_code,
        "filterOptions": filter_options,
        "tables": {
            "incomeBase": short_rows(income_rows, 200),
            "expenseBase": short_rows(expense_rows, 400),
            "incomeSupp": short_rows(supp_income_rows, 200),
            "expenseSupp": short_rows(supp_expense_rows, 400),
            "baseSnapshot": short_rows(base_snapshot_rows, 400),
            "suppSnapshot": short_rows(supp_snapshot_rows, 400),
            "issues": short_rows(issue_rows, 40),
            "issuesByCode": short_rows(issue_by_code, 40),
        },
        "entrustedSummary": {
            "base": entrusted_base.get("summary", {}),
            "supp": entrusted_supp.get("summary", {}),
        },
    }


def save_edit(payload: dict) -> tuple[bool, str]:
    latest = latest_output_dir()
    if latest is None:
        return False, "output 폴더에 분석 결과가 없습니다."

    table = str(payload.get("table", "")).strip()
    row_index = payload.get("rowIndex")
    column = str(payload.get("column", "")).strip()
    value = str(payload.get("value", ""))
    if not table or row_index is None or not column:
        return False, "요청값(table,rowIndex,column)이 누락되었습니다."
    try:
        row_index = int(row_index)
    except ValueError:
        return False, "rowIndex는 숫자여야 합니다."
    if row_index < 0:
        return False, "rowIndex는 0 이상이어야 합니다."

    edit_path = EDIT_DIR / f"{latest.name}.json"
    edits = read_json(edit_path) or load_edits_with_fallback(latest.name) or {}
    tables = edits.setdefault("tables", {})
    table_map = tables.setdefault(table, {})
    row_map = table_map.setdefault(str(row_index), {})
    row_map[column] = value
    write_json(edit_path, edits)
    return True, "저장되었습니다."


class BudgetHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            query = parse_qs(parsed.query)
            year = (query.get("year") or [""])[0].strip() or None
            payload = load_dashboard_payload(year)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/entrusted":
            query = parse_qs(parsed.query)
            budget_type = normalize_budget_type((query.get("budgetType") or ["base"])[0])
            year = (query.get("year") or [""])[0].strip() or None
            payload = load_entrusted_rows_for_latest(budget_type, year)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200 if payload.get("ok") else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/edit", "/api/entrusted/save"}:
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if parsed.path == "/api/entrusted/save":
            ok, message = save_entrusted_entry(payload)
        else:
            ok, message = save_edit(payload)
        res = json.dumps({"ok": ok, "message": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(res)))
        self.end_headers()
        self.wfile.write(res)


def run(port: int = 8787):
    server = ThreadingHTTPServer(("127.0.0.1", port), BudgetHandler)
    print(f"Budget dashboard: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
