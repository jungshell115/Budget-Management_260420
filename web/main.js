const won = new Intl.NumberFormat("ko-KR");
const appState = {
  data: null,
  entrusted: {
    base: null,
    supp: null,
  },
  year: window.localStorage.getItem("budget_year") || "",
  unit: window.localStorage.getItem("budget_unit") || "원",
  budgetType: window.localStorage.getItem("budget_type") || "base",
  filterGroup: "",
  filterDept: "",
  filterGcode: "",
};

function setText(id, txt) {
  const el = document.getElementById(id);
  if (el) el.textContent = txt;
}

function showToast(msg, isError = false) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  window.setTimeout(() => el.classList.remove("show"), 1600);
}

function trimTrailingZeros(textNum) {
  if (!String(textNum).includes(".")) return String(textNum);
  return String(textNum).replace(/(\.\d*?[1-9])0+$/g, "$1").replace(/\.0+$/g, "");
}

function formatDecimalWithComma(num, fractionDigits = 1) {
  return new Intl.NumberFormat("ko-KR", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(num);
}

function parseIntLike(value) {
  return Number(String(value ?? "").replace(/,/g, "")) || 0;
}

function formatByUnit(value, unit, withSign = false) {
  const num = Number(value || 0);
  const sign = withSign && num > 0 ? "+" : "";
  if (unit === "원") return `${sign}${won.format(Math.round(num))} 원`;
  if (unit === "천원") return `${sign}${won.format(Math.round(num / 1000))} 천원`;
  if (unit === "백만원") return `${sign}${formatDecimalWithComma(num / 1000000, 1)} 백만원`;
  return `${sign}${formatDecimalWithComma(num / 100000000, 1)} 억원`;
}

function toUnitValue(value, unit) {
  const num = parseIntLike(value);
  if (unit === "원") return won.format(Math.round(num));
  if (unit === "천원") return won.format(Math.round(num / 1000));
  if (unit === "백만원") return formatDecimalWithComma(num / 1000000, 1);
  return formatDecimalWithComma(num / 100000000, 1);
}

function currentIncomeRows() {
  if (!appState.data) return [];
  const rows =
    appState.budgetType === "supp" && appState.data.meta.hasSupp
    ? appState.data.tables.incomeSupp
    : appState.data.tables.incomeBase;
  return applyIncomeRollups(rows || []);
}

function currentIncomeTableName() {
  return appState.budgetType === "supp" && appState.data?.meta?.hasSupp ? "income_supp" : "income_base";
}

function currentExpenseRows() {
  if (!appState.data) return [];
  return appState.budgetType === "supp" && appState.data.meta.hasSupp
    ? appState.data.tables.expenseSupp
    : appState.data.tables.expenseBase;
}

function currentSnapshotRows() {
  if (!appState.data) return [];
  return appState.budgetType === "supp" && appState.data.meta.hasSupp
    ? appState.data.tables.suppSnapshot
    : appState.data.tables.baseSnapshot;
}

function currentEntrustedPayload() {
  const key = appState.budgetType === "supp" ? "supp" : "base";
  return appState.entrusted[key];
}

function codeAmountFromIncome(rows, code) {
  const row = (rows || []).find((x) => String(x.과목 || "").trim().startsWith(`${code} `));
  if (!row) return 0;
  return parseIntLike(row["현재예산(원)"]);
}

function filteredExpenseTopRows() {
  const topRows =
    appState.budgetType === "supp" && appState.data?.meta?.hasSupp
      ? appState.data.topExpense.supp
      : appState.data?.topExpense?.base || [];
  return topRows.filter((x) => {
    if (appState.filterGroup && x.구분 !== appState.filterGroup) return false;
    if (appState.filterDept && x.부서 !== appState.filterDept) return false;
    if (appState.filterGcode && x.관항 !== appState.filterGcode) return false;
    return true;
  });
}

function renderBars(containerId, items, valueKey, labelBuilder, negative = false) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.innerHTML = "";
  if (!items?.length) {
    root.innerHTML = "<p>데이터가 없습니다.</p>";
    return;
  }

  const max = Math.max(...items.map((x) => Math.abs(Number(x[valueKey] || 0))), 1);
  items.forEach((item) => {
    const val = Number(item[valueKey] || 0);
    const ratio = Math.max((Math.abs(val) / max) * 100, 2);
    const wrap = document.createElement("div");
    wrap.className = "bar-item";
    wrap.innerHTML = `
      <div class="bar-label">
        <span>${labelBuilder(item)}</span>
        <strong class="num">${formatByUnit(val, appState.unit, true)}</strong>
      </div>
      <div class="bar-track">
        <div class="bar-fill ${negative && val < 0 ? "neg" : ""}" style="--w:${ratio}%"></div>
      </div>
    `;
    root.appendChild(wrap);
  });
}

function renderBadges(issueSummary) {
  const root = document.getElementById("issueBadges");
  if (!root) return;
  root.innerHTML = "";
  const entries = Object.entries(issueSummary || {});
  if (!entries.length) {
    root.innerHTML = "<span class='badge'>이슈 없음</span>";
    return;
  }
  entries.sort((a, b) => b[1] - a[1]);
  entries.forEach(([k, v]) => {
    const span = document.createElement("span");
    span.className = "badge";
    span.textContent = `${k || "기타"}: ${v}`;
    root.appendChild(span);
  });
}

function mapIncomeRowsForView(rows) {
  return (rows || []).map((row) => ({
    _level: Number(row.레벨 ?? 9),
    과목: row.과목 ?? "",
    현재예산: `${toUnitValue(row["현재예산(원)"], appState.unit)} ${appState.unit}`,
    기정예산: `${toUnitValue(row["기정예산(원)"], appState.unit)} ${appState.unit}`,
    증감: `${toUnitValue(row["증감(원)"], appState.unit)} ${appState.unit}`,
    산출기초: String(row.산출기초 || "").trim() === "수기작성" ? "" : row.산출기초 ?? "",
  }));
}

function mapExpenseRowsForView(rows) {
  return (rows || []).map((row) => ({
    _level: Number(row.레벨 ?? 9),
    구분: row.유형 ?? "",
    항목: row.표시 ?? "",
    관항: row.관항 ?? "",
    목: row.목 ?? "",
    세목: row.세목 ?? "",
    현재예산: `${toUnitValue(row["현재예산(원)"], appState.unit)} ${appState.unit}`,
    기정예산: `${toUnitValue(row["기정예산(원)"], appState.unit)} ${appState.unit}`,
    증감: `${toUnitValue(row["증감(원)"], appState.unit)} ${appState.unit}`,
    부서: row.부서 ?? "",
  }));
}

function mapSnapshotRowsForView(rows) {
  return (rows || [])
    .filter((row) => parseIntLike(row.합계) !== 0)
    .map((row) => ({
    구분: row.구분 ?? "",
    사업명: row.사업명 ?? "",
    부서: row.부서 ?? "",
    합계: `${toUnitValue(row.합계, appState.unit)} ${appState.unit}`,
    국비: `${toUnitValue(row.국비, appState.unit)} ${appState.unit}`,
    도비: `${toUnitValue(row.도비, appState.unit)} ${appState.unit}`,
    시군비: `${toUnitValue(row.시군비, appState.unit)} ${appState.unit}`,
    자체: `${toUnitValue(row.자체, appState.unit)} ${appState.unit}`,
  }));
}

function isNumberLike(value) {
  if (value === null || value === undefined) return false;
  return /^-?[\d,]+(?:\.\d+)?$/.test(String(value).trim());
}

function sourcePillClass(sourceName) {
  const key = String(sourceName || "").trim();
  if (key === "국비") return "pill-national";
  if (key === "도비") return "pill-province";
  if (key.startsWith("천안")) return "pill-cheonan";
  if (key.startsWith("아산")) return "pill-asan";
  if (key.startsWith("당진")) return "pill-dangjin";
  if (key.startsWith("예산")) return "pill-yesan";
  if (key.startsWith("홍성")) return "pill-hongseong";
  if (key.startsWith("태안")) return "pill-taean";
  if (key === "순세계잉여금") return "pill-surplus";
  if (key === "보조금사용잔액") return "pill-balance";
  return "pill-default";
}

function deptPillClass(deptName) {
  const key = String(deptName || "").trim();
  if (!key) return "pill-default";
  const palette = [
    "pill-cheonan",
    "pill-asan",
    "pill-dangjin",
    "pill-yesan",
    "pill-province",
    "pill-national",
    "pill-hongseong",
    "pill-taean",
  ];
  let acc = 0;
  for (const ch of Array.from(key)) acc += ch.charCodeAt(0);
  return palette[acc % palette.length];
}

function renderFoundationCell(td, value) {
  const text = String(value || "");
  const lines = text.split("\n");
  let groupCount = 0;
  td.innerHTML = "";
  lines.forEach((raw) => {
    const line = String(raw || "");
    if (!line.trim()) return;
    const indent = (line.match(/^(\s*)/)?.[1].length ?? 0) / 2;
    const noIndent = line.trimStart();
    const hasColon = noIndent.includes(" : ");
    if (!hasColon) {
      const groupMatch = noIndent.match(/^(○\s+.+?)\s+([0-9,]+원)$/);
      if (groupMatch) {
        const row = document.createElement("div");
        row.className = "foundation-row foundation-group";
        if (groupCount > 0) row.classList.add("foundation-group-second");
        groupCount += 1;
        row.style.setProperty("--indent", `${indent}`);
        const labelEl = document.createElement("span");
        labelEl.className = "foundation-label";
        labelEl.textContent = groupMatch[1];
        const colonEl = document.createElement("span");
        colonEl.className = "foundation-colon";
        colonEl.textContent = "";
        const amountEl = document.createElement("span");
        amountEl.className = "foundation-amount";
        amountEl.textContent = groupMatch[2];
        row.appendChild(labelEl);
        row.appendChild(colonEl);
        row.appendChild(amountEl);
        td.appendChild(row);
        return;
      }
      const row = document.createElement("div");
      row.className = "foundation-text foundation-title";
      row.style.setProperty("--indent", `${indent}`);
      row.textContent = noIndent;
      td.appendChild(row);
      return;
    }
    if (noIndent.startsWith("- ")) {
      const m = noIndent.match(/^-\s*(.+?)\s*:\s*(.+)$/);
      if (m) {
        const src = m[1].trim();
        const amount = m[2].trim();
        const row = document.createElement("div");
        row.className = "foundation-row foundation-parent";
        row.style.setProperty("--indent", `${indent}`);

        const labelEl = document.createElement("span");
        labelEl.className = "foundation-label";
        const pill = document.createElement("span");
        pill.className = `source-pill ${sourcePillClass(src)}`;
        pill.textContent = src;
        const spacer = document.createElement("span");
        spacer.className = "source-pill-gap";
        spacer.textContent = "\u00A0";
        const gapChars = Math.max(2, 10 - Array.from(src).length);
        spacer.style.width = `${gapChars}ch`;
        labelEl.appendChild(pill);
        labelEl.appendChild(spacer);

        const colonEl = document.createElement("span");
        colonEl.className = "foundation-colon";
        colonEl.textContent = ":";

        const amountEl = document.createElement("span");
        amountEl.className = "foundation-amount foundation-amount-parent";
        amountEl.textContent = `\u00A0\u00A0${amount}`;

        row.appendChild(labelEl);
        row.appendChild(colonEl);
        row.appendChild(amountEl);
        td.appendChild(row);
        return;
      }
      const row = document.createElement("div");
      row.className = "foundation-text foundation-parent-text";
      row.style.setProperty("--indent", `${indent}`);
      row.textContent = noIndent;
      td.appendChild(row);
      return;
    }
    const [label, amount] = noIndent.split(" : ", 2);
    const row = document.createElement("div");
    row.className = "foundation-row";
    const trimmed = label.trimStart();
    if (trimmed.startsWith("○ ")) row.classList.add("foundation-group");
    if (trimmed.startsWith("- ")) row.classList.add("foundation-parent");
    if (trimmed.startsWith("* ")) row.classList.add("foundation-item");
    row.style.setProperty("--indent", `${indent}`);
    const labelEl = document.createElement("span");
    labelEl.className = "foundation-label";
    labelEl.textContent = trimmed.startsWith("* ") ? label.replace(/^\s*\*\s/, "· ") : label;
    const colonEl = document.createElement("span");
    colonEl.className = "foundation-colon";
    colonEl.textContent = ":";
    const amountEl = document.createElement("span");
    amountEl.className = "foundation-amount";
    amountEl.textContent = amount;
    row.appendChild(labelEl);
    row.appendChild(colonEl);
    row.appendChild(amountEl);
    td.appendChild(row);
  });
}

async function saveCellEdit(tableName, rowIndex, column, value) {
  const res = await fetch("/api/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ table: tableName, rowIndex, column, value }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "저장 실패");
}

function entrustedInputNumber(value) {
  return Number(String(value ?? "").replace(/[^\d-]/g, "")) || 0;
}

async function saveEntrustedEntry(payload) {
  const res = await fetch("/api/entrusted/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "위탁사업비 저장 실패");
}

async function loadEntrusted() {
  const budgetType = appState.budgetType === "supp" ? "supp" : "base";
  const yearParam = appState.year ? `&year=${encodeURIComponent(appState.year)}` : "";
  const res = await fetch(`/api/entrusted?budgetType=${budgetType}${yearParam}`);
  const data = await res.json();
  if (!data.ok) throw new Error(data.message || "위탁사업비 로드 실패");
  appState.entrusted[budgetType] = data;
  renderEntrustedTable();
}

function renderEntrustedSummary(payload) {
  const root = document.getElementById("entrustedSummary");
  if (!root) return;
  if (!payload?.summary) {
    root.textContent = "위탁사업비 데이터가 없습니다.";
    return;
  }
  const s = payload.summary;
  root.textContent = `지정 사업 ${s.enabledCount || 0}건 / 경고 ${s.warningCount || 0}건 / 합계 ${formatByUnit(
    s.totalAmount || 0,
    appState.unit
  )}`;
}

function collectEntrustedPayloadFromRow(tr) {
  const business = tr?.dataset?.business || "";
  const enabled = {};
  const amounts = {};
  tr.querySelectorAll(".source-line").forEach((line) => {
    const sourceId = line.dataset.sourceId || "";
    if (!sourceId) return;
    const checkbox = line.querySelector("input[type='checkbox']");
    const input = line.querySelector("input.entrusted-amount");
    enabled[sourceId] = Boolean(checkbox?.checked);
    amounts[sourceId] = entrustedInputNumber(input?.value || "0");
  });
  return { business, enabled, amounts };
}

function renderEntrustedTable() {
  const table = document.getElementById("entrustedTable");
  if (!table) return;
  const payload = currentEntrustedPayload();
  renderEntrustedSummary(payload);
  table.innerHTML = "";
  if (!payload?.rows?.length) {
    table.innerHTML = "<tr><td>데이터 없음</td></tr>";
    return;
  }

  const columns = ["사업명", "부서", "보조 재원별 위탁사업비", "경고", "저장"];
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  const buildSourceEditorsCell = (tr, row) => {
    const td = document.createElement("td");
    td.className = "entrusted-source";
    const editors = {};
    const sources = row?.sources || [];
    sources.forEach((source) => {
      const sourceId = source.id;
      const line = document.createElement("div");
      line.className = "source-line";
      const limit = parseIntLike(source.limit || 0);
      const enabled = Boolean(row?.enabled?.[sourceId]);
      const amountVal = parseIntLike(row?.amounts?.[sourceId] ?? 0);
      line.dataset.sourceId = sourceId;

      const label = document.createElement("span");
      label.className = "source-name";
      const pill = document.createElement("span");
      pill.className = `source-pill ${sourcePillClass(source.label)}`;
      pill.textContent = source.label;
      label.appendChild(pill);

      const budgetEl = document.createElement("span");
      budgetEl.className = "source-budget num";
      budgetEl.textContent = formatByUnit(limit, appState.unit);

      const toggleWrap = document.createElement("label");
      toggleWrap.className = "toggle-wrap";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = enabled;
      const txt = document.createElement("span");
      txt.textContent = checkbox.checked ? "여" : "부";
      toggleWrap.appendChild(checkbox);
      toggleWrap.appendChild(txt);

      const input = document.createElement("input");
      input.type = "text";
      input.className = "entrusted-amount";
      input.value = String(amountVal);
      input.placeholder = "금액";
      input.disabled = !enabled;
      input.addEventListener("input", () => {
        input.value = input.value.replace(/[^\d]/g, "");
      });
      checkbox.addEventListener("change", () => {
        txt.textContent = checkbox.checked ? "여" : "부";
        input.disabled = !checkbox.checked;
        if (!checkbox.checked) input.value = "0";
      });

      line.appendChild(label);
      line.appendChild(budgetEl);
      line.appendChild(toggleWrap);
      line.appendChild(input);
      td.appendChild(line);
      editors[sourceId] = { checkbox, input };
    });
    tr.appendChild(td);
    return editors;
  };

  payload.rows.forEach((row) => {
    const tr = document.createElement("tr");
    if (row.warnings?.length) tr.classList.add("row-warning");

    const appendTextCell = (text, cls = "") => {
      const td = document.createElement("td");
      td.textContent = text ?? "";
      if (cls) td.classList.add(cls);
      tr.appendChild(td);
    };
    appendTextCell(row.사업명 || "");
    const tdDept = document.createElement("td");
    const deptPill = document.createElement("span");
    deptPill.className = `source-pill ${deptPillClass(row.부서)}`;
    deptPill.textContent = row.부서 || "-";
    tdDept.appendChild(deptPill);
    tr.appendChild(tdDept);
    const editors = buildSourceEditorsCell(tr, row);
    tr.dataset.business = row.사업명 || "";

    const tdWarn = document.createElement("td");
    tdWarn.className = "entrusted-warn";
    tdWarn.textContent = row.warnings?.length ? row.warnings.join(", ") : "";
    tr.appendChild(tdWarn);

    const tdSave = document.createElement("td");
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn btn-mini";
    saveBtn.textContent = "저장";
    saveBtn.addEventListener("click", async () => {
      const { business, enabled, amounts } = collectEntrustedPayloadFromRow(tr);
      try {
        await saveEntrustedEntry({
          budgetType: appState.budgetType,
          year: appState.year,
          business,
          enabled,
          amounts,
        });
        await loadEntrusted();
        await loadDashboard();
        showToast("위탁사업비 저장 완료");
      } catch (err) {
        showToast(String(err.message || "저장 실패"), true);
      }
    });
    tdSave.appendChild(saveBtn);
    tr.appendChild(tdSave);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
}

function parseNumberInput(text) {
  const raw = String(text || "").replace(/[^\d-]/g, "");
  if (!raw) return 0;
  return Number(raw) || 0;
}

function findIncomeRow(rows, codePrefix) {
  return rows.find((r) => String(r.과목 || "").trim().startsWith(`${codePrefix} `));
}

function setIncomeAmounts(row, current, prior) {
  if (!row) return;
  const diff = current - prior;
  row["현재예산(원)"] = String(current);
  row["기정예산(원)"] = String(prior);
  row["증감(원)"] = String(diff);
  row["현재예산(천원)"] = String(Math.round(current / 1000));
  row["기정예산(천원)"] = String(Math.round(prior / 1000));
  row["증감(천원)"] = String(Math.round(diff / 1000));
}

function applyIncomeRollups(sourceRows) {
  const rows = sourceRows.map((r) => ({ ...r }));
  const rOrg = rows.find((r) => String(r.과목 || "").trim().startsWith("(재)"));
  const r600 = findIncomeRow(rows, "600");
  const r18101 = findIncomeRow(rows, "181-01");
  const r18102 = findIncomeRow(rows, "181-02");
  const r181 = findIncomeRow(rows, "181");
  const r180 = findIncomeRow(rows, "180");
  const r100 = findIncomeRow(rows, "100");

  const current18101 = parseIntLike(r18101?.["현재예산(원)"]);
  const current18102 = parseIntLike(r18102?.["현재예산(원)"]);
  const prior18101 = parseIntLike(r18101?.["기정예산(원)"]);
  const prior18102 = parseIntLike(r18102?.["기정예산(원)"]);
  const sumCurrent = current18101 + current18102;
  const sumPrior = prior18101 + prior18102;

  setIncomeAmounts(r181, sumCurrent, sumPrior);
  setIncomeAmounts(r180, sumCurrent, sumPrior);
  setIncomeAmounts(r100, sumCurrent, sumPrior);
  // 기관합계 = 600 + 100(자본적수입)
  const cur600 = parseIntLike(r600?.["현재예산(원)"]);
  const pre600 = parseIntLike(r600?.["기정예산(원)"]);
  const cur100 = parseIntLike(r100?.["현재예산(원)"]);
  const pre100 = parseIntLike(r100?.["기정예산(원)"]);
  setIncomeAmounts(rOrg, cur600 + cur100, pre600 + pre100);
  return rows;
}

async function saveManualIncomeEntry() {
  const code = document.getElementById("manualCodeSelect")?.value || "181-01";
  const amountInput = document.getElementById("manualAmountInput");
  const amount = parseNumberInput(amountInput?.value || "0");
  const rows = currentIncomeRows();
  const rowIndex = rows.findIndex((r) => String(r.과목 || "").trim().startsWith(`${code} `));
  if (rowIndex < 0) throw new Error(`${code} 행을 찾지 못했습니다.`);

  const row = rows[rowIndex];
  const prior = parseIntLike(row["기정예산(원)"]);
  const current = amount;
  const diff = current - prior;

  const updates = {
    "현재예산(원)": `${current}`,
    "증감(원)": `${diff}`,
    "현재예산(천원)": `${Math.round(current / 1000)}`,
    "기정예산(천원)": `${Math.round(prior / 1000)}`,
    "증감(천원)": `${Math.round(diff / 1000)}`,
    산출기초: `○ ${code === "181-01" ? "순세계잉여금" : "보조금사용잔액"} ${current.toLocaleString()}원\n  - ${
      code === "181-01" ? "순세계잉여금" : "보조금사용잔액"
    } :  ${prior.toLocaleString()}원 ⇨ ${current.toLocaleString()}원`,
  };

  const table = currentIncomeTableName();
  for (const [col, val] of Object.entries(updates)) {
    await saveCellEdit(table, rowIndex, col, val);
  }
}

function renderTable(tableId, rows, tableName = "", editable = false, rowClassFn = null, editableCellFn = null) {
  const table = document.getElementById(tableId);
  if (!table) return;
  table.innerHTML = "";
  if (!rows?.length) {
    table.innerHTML = "<tr><td>데이터 없음</td></tr>";
    return;
  }

  const columns = Object.keys(rows[0]).filter((c) => !c.startsWith("_"));
  const thead = document.createElement("thead");
  const trHead = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    trHead.appendChild(th);
  });
  thead.appendChild(trHead);

  const tbody = document.createElement("tbody");
  rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    if (tableId === "incomeTable" && String(row.산출기초 || "").trim()) {
      tr.classList.add("row-note-top");
    }
    if (typeof rowClassFn === "function") {
      const extraClass = rowClassFn(row);
      if (extraClass) tr.classList.add(extraClass);
    }
    columns.forEach((c) => {
      const td = document.createElement("td");
      const value = row[c] ?? "";
      if (c === "과목" || c === "항목") td.classList.add("subject-indent");
      if (tableId === "incomeTable" && c === "산출기초") {
        td.classList.add("foundation-note");
        renderFoundationCell(td, value);
      } else if (tableId === "baseSnapshotTable" && c === "부서") {
        const deptPill = document.createElement("span");
        deptPill.className = `source-pill ${deptPillClass(value)}`;
        deptPill.textContent = value || "-";
        td.appendChild(deptPill);
      } else {
        td.textContent = value;
      }
      if (
        ["현재예산", "기정예산", "증감", "합계", "국비", "도비", "시군비", "자체"].includes(c) ||
        isNumberLike(value)
      ) {
        td.classList.add("num");
      }
      const canEdit = editable && (typeof editableCellFn !== "function" || editableCellFn(row, c));
      if (canEdit) {
        td.contentEditable = "true";
        td.addEventListener("focus", () => {
          td.dataset.before = td.textContent ?? "";
        });
        td.addEventListener("blur", async () => {
          const before = td.dataset.before ?? "";
          const after = td.textContent ?? "";
          if (before === after) return;
          try {
            await saveCellEdit(tableName, rowIndex, c, after);
            showToast("수정내용 저장됨");
          } catch (err) {
            td.textContent = before;
            showToast(String(err.message || "저장 실패"), true);
          }
        });
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
}

function updateDocMeta() {
  const meta = appState.data?.meta;
  if (!meta) return;
  const budgetLabel = appState.budgetType === "supp" && meta.hasSupp ? meta.suppLabel : meta.baseLabel;
  const fileName = appState.budgetType === "supp" && meta.hasSupp ? meta.suppFile : meta.baseFile;
  setText("docMeta", `${meta.year || "-"}년 / ${budgetLabel || "-"} / ${fileName || "-"}`);
  setText("headerRoundMeta", `${meta.year || "-"}년 / ${budgetLabel || "-"}`);
}

function renderAll() {
  const data = appState.data;
  if (!data) return;
  const incomeRowsRaw = currentIncomeRows();
  const totalRevenue = codeAmountFromIncome(incomeRowsRaw, "600");
  const operatingRevenue = codeAmountFromIncome(incomeRowsRaw, "610");
  const subsidyRevenue = codeAmountFromIncome(incomeRowsRaw, "646");
  const contributionRevenue = codeAmountFromIncome(incomeRowsRaw, "648");

  setText("mTotal", formatByUnit(totalRevenue, appState.unit));
  setText("mOperating", formatByUnit(operatingRevenue, appState.unit));
  setText("mSubsidy", formatByUnit(subsidyRevenue, appState.unit));
  setText("mContribution", formatByUnit(contributionRevenue, appState.unit));
  const entrustedTotal =
    appState.budgetType === "supp"
      ? data.metrics.entrustedSuppTotal || 0
      : data.metrics.entrustedBaseTotal || 0;
  setText("mEntrusted", formatByUnit(entrustedTotal, appState.unit));
  setText("mIssue", `${data.metrics.issueCount}건`);
  setText("summaryBox", data.summaryText || "");
  updateDocMeta();

  renderBars(
    "expenseBars",
    filteredExpenseTopRows(),
    "합계원",
    (x) => `${x.사업명} (${x.관항 || "-"}-${x.목 || "-"}-${x.세목 || "-"})`
  );
  renderBars("changeBars", data.topChanges, "증감", (x) => x.사업명, true);
  renderBadges(data.issueSummary);

  const incomeRowsView = mapIncomeRowsForView(currentIncomeRows());
  const incomeRowClassFn = (row) => {
    const lv = Number(row._level);
    if (lv === 0) return "row-lv0";
    if (lv === 1) return "row-lv1";
    if (lv === 2) return "row-lv2";
    if (lv === 3) return "row-lv3";
    return "";
  };
  renderTable(
    "incomeTable",
    incomeRowsView,
    "",
    false,
    incomeRowClassFn
  );
  const expenseRowsView = mapExpenseRowsForView(currentExpenseRows());
  const expenseRowClassFn = (row) => {
    const lv = Number(row._level);
    if (lv === 0) return "row-lv0";
    if (lv === 1) return "row-lv1";
    if (lv === 2) return "row-lv2";
    if (lv === 3) return "row-lv3";
    return "";
  };
  renderTable("expenseTable", expenseRowsView, "", false, expenseRowClassFn);
  renderTable("baseSnapshotTable", mapSnapshotRowsForView(currentSnapshotRows()), appState.budgetType === "supp" ? "snapshot_supp" : "snapshot_base", true);
  renderTable("issueSummaryTable", data.tables.issuesByCode || [], "", false);
  renderTable("issueTable", data.tables.issues || [], "issues", true);
  renderEntrustedTable();
}

function initTabs() {
  const savedTab = window.localStorage.getItem("budget_active_tab");
  if (savedTab) {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === savedTab);
    });
    document.querySelectorAll(".panel").forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panel === savedTab);
    });
  }

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
      btn.classList.add("active");
      const target = btn.dataset.tab;
      window.localStorage.setItem("budget_active_tab", target);
      document.querySelectorAll(".panel").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.panel === target);
      });
    });
  });
}

function fillSelect(id, values) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = "<option value=''>전체</option>";
  (values || []).forEach((v) => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    el.appendChild(opt);
  });
}

function initControls() {
  const yearSelect = document.getElementById("yearSelect");
  const unitSelect = document.getElementById("unitSelect");
  const budgetTypeSelect = document.getElementById("budgetTypeSelect");
  if (yearSelect && appState.year) yearSelect.value = appState.year;
  if (unitSelect) unitSelect.value = appState.unit;
  yearSelect?.addEventListener("change", async (e) => {
    appState.year = e.target.value;
    window.localStorage.setItem("budget_year", appState.year);
    await loadDashboard();
  });
  unitSelect?.addEventListener("change", (e) => {
    appState.unit = e.target.value;
    window.localStorage.setItem("budget_unit", appState.unit);
    renderAll();
  });
  budgetTypeSelect?.addEventListener("change", (e) => {
    appState.budgetType = e.target.value;
    window.localStorage.setItem("budget_type", appState.budgetType);
    loadEntrusted()
      .catch((err) => showToast(String(err.message || "위탁사업비 로드 실패"), true))
      .finally(() => renderAll());
  });

  document.getElementById("filterGroup")?.addEventListener("change", (e) => {
    appState.filterGroup = e.target.value;
    renderAll();
  });
  document.getElementById("filterDept")?.addEventListener("change", (e) => {
    appState.filterDept = e.target.value;
    renderAll();
  });
  document.getElementById("filterGcode")?.addEventListener("change", (e) => {
    appState.filterGcode = e.target.value;
    renderAll();
  });
}

function openManualModal() {
  const modal = document.getElementById("manualModal");
  const meta = appState.data?.meta || {};
  const targetLabel =
    appState.budgetType === "supp" && meta.hasSupp
      ? `${meta.year || ""} ${meta.suppLabel || "추경"}`
      : `${meta.year || ""} ${meta.baseLabel || "본예산"}`;
  setText("manualTarget", `입력 대상: ${targetLabel}`);
  const input = document.getElementById("manualAmountInput");
  if (input) input.value = "";
  modal?.classList.add("open");
}

function closeManualModal() {
  document.getElementById("manualModal")?.classList.remove("open");
}

async function loadDashboard() {
  try {
    const yearParam = appState.year ? `?year=${encodeURIComponent(appState.year)}` : "";
    const res = await fetch(`/api/dashboard${yearParam}`);
    const data = await res.json();
    if (!data.ok) {
      setText("subline", data.message || "결과 없음");
      return;
    }
    appState.data = data;

    const budgetTypeSelect = document.getElementById("budgetTypeSelect");
    const yearSelect = document.getElementById("yearSelect");
    if (yearSelect) {
      yearSelect.innerHTML = "";
      const years = data.meta?.availableYears || [];
      years.forEach((y) => {
        const opt = document.createElement("option");
        opt.value = y;
        opt.textContent = `${y}년`;
        yearSelect.appendChild(opt);
      });
      appState.year = data.meta?.selectedYear || data.meta?.year || appState.year;
      if (appState.year && !years.includes(appState.year)) {
        const opt = document.createElement("option");
        opt.value = appState.year;
        opt.textContent = `${appState.year}년`;
        yearSelect.appendChild(opt);
      }
      if (appState.year) yearSelect.value = appState.year;
      window.localStorage.setItem("budget_year", appState.year || "");
    }
    if (budgetTypeSelect) {
      budgetTypeSelect.innerHTML = "<option value='base'>본예산</option>";
      if (data.meta?.hasSupp) {
        const opt = document.createElement("option");
        opt.value = "supp";
        opt.textContent = data.meta.suppLabel || "추경";
        budgetTypeSelect.appendChild(opt);
      }
      if (!data.meta?.hasSupp) appState.budgetType = "base";
      if (appState.budgetType === "supp" && !data.meta?.hasSupp) appState.budgetType = "base";
      budgetTypeSelect.value = appState.budgetType;
      window.localStorage.setItem("budget_type", appState.budgetType);
    }

    fillSelect("filterGroup", data.filterOptions?.구분 || []);
    fillSelect("filterDept", data.filterOptions?.부서 || []);
    fillSelect("filterGcode", data.filterOptions?.관항 || []);

    setText("subline", `최신 결과: ${data.latestFolder}`);
    await loadEntrusted();
    renderAll();
  } catch (e) {
    setText("subline", "데이터 로드 중 오류가 발생했습니다.");
    // eslint-disable-next-line no-console
    console.error(e);
  }
}

document.getElementById("refreshBtn")?.addEventListener("click", loadDashboard);
document.getElementById("entrustedReloadBtn")?.addEventListener("click", async () => {
  try {
    await loadEntrusted();
    renderEntrustedTable();
    showToast("위탁사업비를 다시 불러왔습니다.");
  } catch (e) {
    showToast(String(e.message || "로드 실패"), true);
  }
});
document.getElementById("entrustedSaveAllBtn")?.addEventListener("click", async () => {
  try {
    const rows = Array.from(document.querySelectorAll("#entrustedTable tbody tr"));
    for (const tr of rows) {
      const { business, enabled, amounts } = collectEntrustedPayloadFromRow(tr);
      await saveEntrustedEntry({
        budgetType: appState.budgetType,
        year: appState.year,
        business,
        enabled,
        amounts,
      });
    }
    await loadEntrusted();
    await loadDashboard();
    showToast("일괄저장 완료");
  } catch (e) {
    showToast(String(e.message || "일괄저장 실패"), true);
  }
});
document.getElementById("manualEntryBtn")?.addEventListener("click", openManualModal);
document.getElementById("manualCancelBtn")?.addEventListener("click", closeManualModal);
document.getElementById("manualSaveBtn")?.addEventListener("click", async () => {
  try {
    await saveManualIncomeEntry();
    closeManualModal();
    await loadDashboard();
    showToast("수기입력 반영 완료");
  } catch (e) {
    showToast(String(e.message || "수기입력 실패"), true);
  }
});
initTabs();
initControls();
loadDashboard();
