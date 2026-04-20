from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


CITY_LABELS = [
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
    "기타",
]

CITY_SUFFIX = {
    "천안": "시",
    "아산": "시",
    "당진": "시",
    "예산": "군",
    "계룡": "시",
    "공주": "시",
    "금산": "군",
    "논산": "시",
    "보령": "시",
    "부여": "군",
    "서산": "시",
    "서천": "군",
    "청양": "군",
    "태안": "군",
    "홍성": "군",
}


def city_budget_label(city: str) -> str:
    if city == "기타":
        return "기타"
    return f"{city}{CITY_SUFFIX.get(city, '시')}비"


def c(row: dict[int, str], idx: int) -> str:
    return row.get(idx, "") if row else ""


def to_int(v: str) -> int:
    s = str(v).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def units(value: int) -> tuple[str, str, str, str]:
    return (
        f"{value:,}",
        f"{value / 1_000:,.0f}",
        f"{value / 1_000_000:,.3f}",
        f"{value / 100_000_000:,.4f}",
    )


def unit_value(value: int, unit: str) -> str:
    if unit == "원":
        return f"{value:,}"
    if unit == "천원":
        return f"{value / 1_000:,.0f}"
    if unit == "백만원":
        return f"{value / 1_000_000:,.3f}"
    if unit == "억원":
        return f"{value / 100_000_000:,.4f}"
    return f"{value:,}"


def load_expense_mapping(path: Path) -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            biz = (row.get("사업명") or "").strip()
            if not biz:
                continue
            out[biz] = (
                (row.get("관항") or "").strip(),
                (row.get("목") or "").strip(),
                (row.get("세목") or "").strip(),
            )
    return out


def _total_values(rows: dict[int, dict[int, str]]) -> dict[str, int]:
    total_row = rows.get(5, {})
    total = to_int(c(total_row, 11))
    national = to_int(c(total_row, 12)) or to_int(c(total_row, 52))
    dobi = to_int(c(total_row, 13))
    sigun = to_int(c(total_row, 14))
    own = to_int(c(total_row, 31))
    dobi_contrib = to_int(c(total_row, 33))
    sigun_contrib = to_int(c(total_row, 34))
    contribution = to_int(c(total_row, 32))

    dobi_subsidy = to_int(c(total_row, 53))
    sigun_subsidy = to_int(c(total_row, 54))
    if dobi_subsidy == 0 and sigun_subsidy == 0:
        dobi_subsidy = max(dobi - dobi_contrib, 0)
        sigun_subsidy = max(sigun - sigun_contrib, 0)
    subsidy = national + dobi_subsidy + sigun_subsidy
    return {
        "total": total,
        "national": national,
        "dobi": dobi,
        "sigun": sigun,
        "own": own,
        "dobi_contrib": dobi_contrib,
        "sigun_contrib": sigun_contrib,
        "contribution": contribution,
        "dobi_subsidy": dobi_subsidy,
        "sigun_subsidy": sigun_subsidy,
        "subsidy": subsidy,
    }


def _iter_budget_items(
    rows: dict[int, dict[int, str]],
    mapping: dict[str, tuple[str, str, str]],
) -> list[dict[str, str | int]]:
    out: list[dict[str, str | int]] = []
    current_group = ""
    for r in range(6, 500):
        row = rows.get(r, {})
        group = str(c(row, 8)).strip()
        if group:
            current_group = group
        else:
            group = current_group
        biz = str(c(row, 9)).strip()
        dept = str(c(row, 10)).strip()
        if not biz or biz == "0" or biz == "소계":
            continue

        total = to_int(c(row, 11))
        national = to_int(c(row, 12))
        dobi = to_int(c(row, 13))
        sigun = to_int(c(row, 14))
        own = to_int(c(row, 31))
        dobi_contrib = to_int(c(row, 33))
        city_contrib = {name: to_int(c(row, 35 + i)) for i, name in enumerate(CITY_LABELS)}
        sigun_contrib = sum(city_contrib.values()) if any(city_contrib.values()) else to_int(c(row, 34))
        dobi_subsidy = to_int(c(row, 53))
        city_subsidy = {name: to_int(c(row, 55 + i)) for i, name in enumerate(CITY_LABELS)}
        sigun_subsidy = sum(city_subsidy.values()) if any(city_subsidy.values()) else to_int(c(row, 54))

        _l1, mcode, scode = mapping.get(biz, ("", "", ""))
        if not mcode:
            mcode = "000"
        if not scode:
            scode = f"{mcode}-00" if mcode != "000" else "000-00"
        gcode = f"{(int(mcode) // 100) * 100:03d}" if mcode.isdigit() else "000"

        out.append(
            {
                "구분": group,
                "사업명": biz,
                "부서": dept,
                "관항": gcode,
                "목": mcode,
                "세목": scode,
                "합계": total,
                "국비": national,
                "도비": dobi,
                "시군비": sigun,
                "자체": own,
                "도비보조": dobi_subsidy,
                "시군보조": sigun_subsidy,
                "도비출연": dobi_contrib,
                "시군출연": sigun_contrib,
                **{f"출연_{name}": amt for name, amt in city_contrib.items()},
                **{f"보조_{name}": amt for name, amt in city_subsidy.items()},
            }
        )
    return out


def _amount_map_by_biz(items: Iterable[dict[str, str | int]]) -> dict[str, int]:
    return {str(x["사업명"]): int(x["합계"]) for x in items}


def _income_foundation_notes(cur: dict[str, int], items: list[dict[str, str | int]]) -> dict[str, str]:
    # 산출기초 라인 포맷:
    # <indent><label> : <amount> 원
    # 정렬은 웹 렌더러가 ":" / 금액 컬럼을 고정 그리드로 맞춘다.
    def line_group(label: str, amount: int) -> str:
        return f"○ {label} {amount:,}원"

    def line_parent(label: str, amount: int) -> str:
        # 요청 포맷:
        # - 국비/도비(2글자): 공백 10 + ":" + 공백 2 + 값
        # - 천안시비/당진시비(4글자): 공백 4 + ":" + 공백 2 + 값
        label_len = len(label)
        if label_len <= 2:
            pad = " " * 10
        elif label_len == 4:
            pad = " " * 4
        else:
            pad = " " * 4
        return f"  - {label}{pad}:  {amount:,}원"

    def line_item(label: str, amount: int) -> str:
        return f"    * {label} : {amount:,}원"

    def grouped_note(source_defs: list[tuple[str, str]]) -> str:
        lines: list[str] = []
        for top_group in ("기관운영", "목적사업"):
            g_items = [x for x in items if str(x.get("구분", "")) == top_group]
            has_any = any(sum(int(x.get(k, 0)) for x in g_items) > 0 for k, _ in source_defs)
            if not has_any:
                continue
            g_total = sum(sum(int(x.get(k, 0)) for x in g_items) for k, _ in source_defs)
            lines.append(line_group(top_group, g_total))
            for key, label in source_defs:
                total_amt = sum(int(x.get(key, 0)) for x in g_items)
                if total_amt <= 0:
                    continue
                lines.append(line_parent(label, total_amt))
                for it in g_items:
                    amt = int(it.get(key, 0))
                    if amt <= 0:
                        continue
                    lines.append(line_item(str(it["사업명"]), amt))
        return "\n".join(lines)

    notes: dict[str, str] = {}

    # 646-01 국비보조금수익
    notes["646-01"] = grouped_note([("국비", "국비")])

    # 646-02 자치단체보조금수익: 도비 + 시군별
    subsidy_sources = [("도비보조", "도비")]
    subsidy_sources.extend((f"보조_{city}", city_budget_label(city)) for city in CITY_LABELS if city != "기타")
    notes["646-02"] = grouped_note(subsidy_sources)

    # 648-02 자치단체출연금수익: 도비 + 시군별
    contrib_sources = [("도비출연", "도비")]
    contrib_sources.extend((f"출연_{city}", city_budget_label(city)) for city in CITY_LABELS if city != "기타")
    notes["648-02"] = grouped_note(contrib_sources)

    return notes


def build_income_rows(
    current_rows: dict[int, dict[int, str]],
    prior_rows: dict[int, dict[int, str]] | None,
    items: list[dict[str, str | int]],
    prior_items: list[dict[str, str | int]] | None = None,
) -> list[list[str]]:
    cur = _total_values(current_rows)
    pre = _total_values(prior_rows or {})
    org_total_cur = cur["total"]  # 기관 총계(600+100, 현재 데이터에서는 600과 동일)
    org_total_pre = pre["total"]

    # 사용자 요구값 기준: 610은 본예산 구조상 전체를 대표하도록 600과 동일하게 표시
    rows = [
        [
            "레벨",
            "과목",
            "현재예산(원)",
            "기정예산(원)",
            "증감(원)",
            "현재예산(천원)",
            "기정예산(천원)",
            "증감(천원)",
            "산출기초",
        ]
    ]

    revision_mode = bool(prior_items)
    foundation_notes = _income_foundation_notes(cur, items)
    if revision_mode:
        foundation_notes = _income_foundation_notes_revision(cur, pre, items, prior_items or [])

    def add(level: int, code: str, subject: str, cur_amt: int, pre_amt: int, note: str = ""):
        diff = cur_amt - pre_amt
        subject_text = f"{'  ' * level}{code + ' ' if code else ''}{subject}"
        rows.append(
            [
                str(level),
                subject_text,
                f"{cur_amt:,}",
                f"{pre_amt:,}",
                f"{diff:,}",
                unit_value(cur_amt, "천원"),
                unit_value(pre_amt, "천원"),
                unit_value(diff, "천원"),
                note,
            ]
        )

    add(0, "", "(재) 충남콘텐츠진흥원", org_total_cur, org_total_pre, "")
    add(1, "600", "사업수익", cur["total"], pre["total"])
    add(2, "610", "영업수익", cur["total"], pre["total"])
    changed_646_01 = cur["national"] != pre["national"]
    changed_646_02 = (cur["dobi_subsidy"] + cur["sigun_subsidy"]) != (pre["dobi_subsidy"] + pre["sigun_subsidy"])
    changed_648_02 = cur["contribution"] != pre["contribution"]
    changed_646 = changed_646_01 or changed_646_02
    changed_648 = changed_648_02

    if (not revision_mode) or changed_646:
        add(3, "646", "보조금수익", cur["subsidy"], pre["subsidy"])
    if (not revision_mode) or changed_646_01:
        add(4, "646-01", "국비보조금수익", cur["national"], pre["national"], foundation_notes.get("646-01", ""))
    if (not revision_mode) or changed_646_02:
        add(
            4,
            "646-02",
            "자치단체보조금수익",
            cur["dobi_subsidy"] + cur["sigun_subsidy"],
            pre["dobi_subsidy"] + pre["sigun_subsidy"],
            foundation_notes.get("646-02", ""),
        )
    if (not revision_mode) or changed_648:
        add(3, "648", "출연금수익", cur["contribution"], pre["contribution"])
    if (not revision_mode) or changed_648_02:
        add(4, "648-02", "자치단체출연금수익", cur["contribution"], pre["contribution"], foundation_notes.get("648-02", ""))

    # 수기 작성용 항목(자본적수입 계열)
    add(1, "100", "자본적수입", 0, 0)
    add(2, "180", "유보자금", 0, 0)
    add(3, "181", "잉여금", 0, 0)
    add(4, "181-01", "순세계잉여금", 0, 0, "수기작성")
    add(4, "181-02", "보조금사용잔액", 0, 0, "수기작성")
    return rows


def _income_foundation_notes_revision(
    cur: dict[str, int],
    pre: dict[str, int],
    cur_items: list[dict[str, str | int]],
    pre_items: list[dict[str, str | int]],
) -> dict[str, str]:
    def line_group(label: str, amount: int) -> str:
        return f"○ {label} {amount:,}원"

    def line_parent(label: str, before: int, after: int) -> str:
        label_len = len(label)
        if label_len <= 2:
            pad = " " * 10
        elif label_len == 4:
            pad = " " * 6
        else:
            pad = " " * 4
        return f"  - {label}{pad}:  {before:,}원 ⇨ {after:,}원"

    def line_item(label: str, delta: int) -> str:
        sign = "-" if delta < 0 else ""
        return f"    * {label} : {sign}{abs(delta):,}원"

    pre_map = {str(x["사업명"]): x for x in pre_items}
    cur_map = {str(x["사업명"]): x for x in cur_items}

    def grouped_note(source_defs: list[tuple[str, str]]) -> str:
        lines: list[str] = []
        for top_group in ("기관운영", "목적사업"):
            c_group = [x for x in cur_items if str(x.get("구분", "")) == top_group]
            p_group = [x for x in pre_items if str(x.get("구분", "")) == top_group]
            detail_lines: list[str] = []
            for key, label in source_defs:
                c_total = sum(int(x.get(key, 0)) for x in c_group)
                p_total = sum(int(x.get(key, 0)) for x in p_group)
                if c_total == p_total:
                    continue
                detail_lines.append(line_parent(label, p_total, c_total))
                bizs = sorted(
                    {
                        str(x["사업명"])
                        for x in c_group
                        if int(x.get(key, 0)) > 0
                    }
                    | {
                        str(x["사업명"])
                        for x in p_group
                        if int(x.get(key, 0)) > 0
                    }
                )
                for biz in bizs:
                    c_amt = int(cur_map.get(biz, {}).get(key, 0)) if biz in cur_map else 0
                    p_amt = int(pre_map.get(biz, {}).get(key, 0)) if biz in pre_map else 0
                    d = c_amt - p_amt
                    if d == 0:
                        continue
                    detail_lines.append(line_item(biz, d))
            if detail_lines:
                c_group_total = 0
                for key, _ in source_defs:
                    c_group_total += sum(int(x.get(key, 0)) for x in c_group)
                lines.append(line_group(top_group, c_group_total))
                lines.extend(detail_lines)
        return "\n".join(lines)

    notes: dict[str, str] = {}
    notes["646-01"] = grouped_note([("국비", "국비")])
    subsidy_sources = [("도비보조", "도비")]
    subsidy_sources.extend((f"보조_{city}", city_budget_label(city)) for city in CITY_LABELS if city != "기타")
    notes["646-02"] = grouped_note(subsidy_sources)
    contrib_sources = [("도비출연", "도비")]
    contrib_sources.extend((f"출연_{city}", city_budget_label(city)) for city in CITY_LABELS if city != "기타")
    notes["648-02"] = grouped_note(contrib_sources)
    return notes


def build_expense_rows(
    current_rows: dict[int, dict[int, str]],
    prior_rows: dict[int, dict[int, str]] | None,
    mapping: dict[str, tuple[str, str, str]],
):
    current_items = _iter_budget_items(current_rows, mapping)
    prior_items = _iter_budget_items(prior_rows or {}, mapping)
    prior_biz = _amount_map_by_biz(prior_items)

    rows = [
        [
            "레벨",
            "유형",
            "표시",
            "관항",
            "목",
            "세목",
            "구분",
            "사업명",
            "부서",
            "현재예산(원)",
            "기정예산(원)",
            "증감(원)",
            "현재예산(천원)",
            "기정예산(천원)",
            "증감(천원)",
        ]
    ]
    mapping_issues: list[tuple[str, str]] = []
    for x in current_items:
        if str(x["목"]) == "000" or str(x["세목"]).startswith("000"):
            mapping_issues.append((str(x["사업명"]), "3계층 코드 매핑 누락"))

    def add_row(
        level: int,
        row_type: str,
        label: str,
        gcode: str,
        mcode: str,
        scode: str,
        group: str,
        biz: str,
        dept: str,
        cur_amt: int,
        pre_amt: int,
    ):
        diff = cur_amt - pre_amt
        rows.append(
            [
                str(level),
                row_type,
                f"{'  ' * level}{label}",
                gcode,
                mcode,
                scode,
                group,
                biz,
                dept,
                f"{cur_amt:,}",
                f"{pre_amt:,}",
                f"{diff:,}",
                unit_value(cur_amt, "천원"),
                unit_value(pre_amt, "천원"),
                unit_value(diff, "천원"),
            ]
        )

    total_cur = sum(int(x["합계"]) for x in current_items)
    total_pre = sum(int(x["합계"]) for x in prior_items)
    add_row(0, "총합", "사업비 총합", "", "", "", "", "", "", total_cur, total_pre)

    gkeys = sorted({str(x["관항"]) for x in current_items})
    for g in gkeys:
        g_items = [x for x in current_items if str(x["관항"]) == g]
        g_cur = sum(int(x["합계"]) for x in g_items)
        g_pre = sum(prior_biz.get(str(x["사업명"]), 0) for x in g_items)
        add_row(1, "관항소계", f"{g} 관항 소계", g, "", "", "", "", "", g_cur, g_pre)

        mkeys = sorted({str(x["목"]) for x in g_items})
        for m in mkeys:
            m_items = [x for x in g_items if str(x["목"]) == m]
            m_cur = sum(int(x["합계"]) for x in m_items)
            m_pre = sum(prior_biz.get(str(x["사업명"]), 0) for x in m_items)
            add_row(2, "목소계", f"{m} 목 소계", g, m, "", "", "", "", m_cur, m_pre)

            skeys = sorted({str(x["세목"]) for x in m_items})
            for s in skeys:
                s_items = [x for x in m_items if str(x["세목"]) == s]
                s_cur = sum(int(x["합계"]) for x in s_items)
                s_pre = sum(prior_biz.get(str(x["사업명"]), 0) for x in s_items)
                add_row(3, "세목소계", f"{s} 세목 소계", g, m, s, "", "", "", s_cur, s_pre)

                for it in sorted(s_items, key=lambda x: str(x["사업명"])):
                    biz = str(it["사업명"])
                    cur_amt = int(it["합계"])
                    pre_amt = prior_biz.get(biz, 0)
                    add_row(
                        4,
                        "사업",
                        biz,
                        g,
                        m,
                        s,
                        str(it["구분"]),
                        biz,
                        str(it["부서"]),
                        cur_amt,
                        pre_amt,
                    )
    return rows, mapping_issues


def build_compare_rows(
    base_rows: dict[int, dict[int, str]],
    supp_rows: dict[int, dict[int, str]] | None,
) -> list[list[str]]:
    header = ["사업명", "본예산(원)", "추경(원)", "증감(원)", "증감(천원)"]
    if not supp_rows:
        return [header]

    base_map: dict[str, int] = {}
    supp_map: dict[str, int] = {}
    for r in range(6, 500):
        b = base_rows.get(r, {})
        s = supp_rows.get(r, {})
        biz_b = str(c(b, 9)).strip()
        biz_s = str(c(s, 9)).strip()
        if biz_b and biz_b != "0":
            base_map[biz_b] = to_int(c(b, 11))
        if biz_s and biz_s != "0":
            supp_map[biz_s] = to_int(c(s, 11))

    all_keys = sorted(set(base_map) | set(supp_map))
    out = [header]
    for biz in all_keys:
        b = base_map.get(biz, 0)
        s = supp_map.get(biz, 0)
        d = s - b
        out.append([biz, f"{b:,}", f"{s:,}", f"{d:,}", f"{d / 1_000:,.0f}"])
    return out


def build_base_snapshot_rows(rows: dict[int, dict[int, str]]) -> list[list[str]]:
    out = [
        [
            "구분",
            "사업명",
            "부서",
            "합계",
            "국비",
            "도비",
            "시군비",
            "자체",
        ]
    ]
    for r in range(5, 500):
        row = rows.get(r, {})
        biz = str(c(row, 9)).strip()
        group = str(c(row, 8)).strip()
        dept = str(c(row, 10)).strip()
        if not group and not biz:
            continue
        out.append(
            [
                group,
                biz,
                dept,
                f"{to_int(c(row, 11)):,}",
                f"{to_int(c(row, 12)):,}",
                f"{to_int(c(row, 13)):,}",
                f"{to_int(c(row, 14)):,}",
                f"{to_int(c(row, 31)):,}",
            ]
        )
    return out
