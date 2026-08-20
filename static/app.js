const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// ── Theme ──────────────────────────────────────────────
function applyTheme() {
  const isDark = tg.colorScheme === "dark";
  document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
}
applyTheme();
tg.onEvent("themeChanged", applyTheme);

// ── User ───────────────────────────────────────────────
const tgUser = tg.initDataUnsafe?.user;
const USER_ID = tgUser?.id || 1;

document.getElementById("username").textContent =
  tgUser ? `@${tgUser.username || tgUser.first_name}` : "Demo Mode";

// ── State ──────────────────────────────────────────────
let txType = "in";
let historyOffset = 0;
const PAGE_SIZE = 20;
let pendingDeleteId = null;
let currentSummaryPeriod = "month";
let userSettings = { currency: "MMK", timezone: "UTC" };

// ── Cache & rate limit ─────────────────────────────────
const CACHE_TTL_MS = 30_000;
const TAB_COOLDOWN_MS = 1000;
const cache = {};
const isFetching = {};
let lastTabSwitch = 0;
let tabSpamCount = 0;
let tabSpamTimer = null;

function getCached(key) {
  const c = cache[key];
  return (c && Date.now() - c.ts < CACHE_TTL_MS) ? c.data : null;
}
function setCache(key, data) { cache[key] = { data, ts: Date.now() }; }
function bustCache(...keys) { keys.forEach(k => delete cache[k]); }

// ── Helpers ────────────────────────────────────────────
function fmt(amount) {
  if (amount >= 1_000_000) return (amount / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "m";
  if (amount >= 1_000) return (amount / 1_000).toFixed(2).replace(/\.?0+$/, "") + "k";
  return amount.toLocaleString();
}

function fmtFull(amount) {
  return amount.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function cur() { return userSettings.currency || "MMK"; }

function fmtDate(utcStr) {
  try {
    const tz = userSettings.timezone || "UTC";
    const dt = new Date(utcStr.replace(" ", "T") + "Z");
    const dtYear = new Intl.DateTimeFormat("en", { timeZone: tz, year: "numeric" }).format(dt);
    const nowYear = new Intl.DateTimeFormat("en", { timeZone: tz, year: "numeric" }).format(new Date());
    const opts = { timeZone: tz, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false };
    if (dtYear !== nowYear) opts.year = "numeric";
    return new Intl.DateTimeFormat("en-GB", opts).format(dt).replace(",", "");
  } catch { return utcStr; }
}

function showToast(msg, duration = 2200) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), duration);
}

// ── Tabs ───────────────────────────────────────────────
function switchTab(name) {
  const now = Date.now();
  if (now - lastTabSwitch < TAB_COOLDOWN_MS) {
    tabSpamCount++;
    clearTimeout(tabSpamTimer);
    tabSpamTimer = setTimeout(() => { tabSpamCount = 0; }, 2500);
    if (tabSpamCount >= 3) showToast("⏳ Slow down!", 2000);
    return;
  }
  tabSpamCount = 0;
  lastTabSwitch = now;

  document.querySelectorAll(".tab").forEach((el, i) => {
    el.classList.toggle("active", ["add","history","summary"][i] === name);
  });
  document.querySelectorAll(".panel").forEach(el => el.classList.remove("active"));
  document.getElementById(`panel-${name}`).classList.add("active");

  if (name === "history") { historyOffset = 0; loadHistory(); }
  if (name === "summary") loadSummary();
}

// ── Type Toggle ────────────────────────────────────────
function setType(type) {
  txType = type;
  document.getElementById("btn-income").classList.toggle("active", type === "in");
  document.getElementById("btn-expense").classList.toggle("active", type === "out");
}

// ── Balance ────────────────────────────────────────────
async function loadBalance(force = false) {
  const ckey = `bal_${USER_ID}`;
  if (!force) {
    const cached = getCached(ckey);
    if (cached) { renderBalance(cached); return; }
  }
  if (isFetching[ckey]) return;
  isFetching[ckey] = true;
  try {
    const res = await fetch(`/api/balance?user_id=${USER_ID}`);
    const data = await res.json();
    setCache(ckey, data);
    renderBalance(data);
  } finally { isFetching[ckey] = false; }
}

function renderBalance(data) {
  document.getElementById("balance-display").textContent = fmtFull(data.balance) + " " + cur();
  document.getElementById("total-in-display").textContent = fmt(data.total_in) + " " + cur();
  document.getElementById("total-out-display").textContent = fmt(data.total_out) + " " + cur();
}

// ── Add Transaction ────────────────────────────────────
async function submitTransaction() {
  const rawAmount = document.getElementById("amount-input").value.trim();
  const note = document.getElementById("note-input").value.trim();
  const dtLocal = document.getElementById("datetime-input").value; // "YYYY-MM-DDTHH:MM"
  if (!rawAmount) { showToast("⚠️ Enter an amount"); return; }

  // Convert local datetime to UTC SQL string, or null to let DB default
  let created_at = null;
  if (dtLocal) {
    const localDate = new Date(dtLocal); // browser treats datetime-local as local time
    const now = new Date(); // Current time

    // --- FUTURE DATE CHECK ---
    if (localDate > now) {
      showToast("⚠️ Future dates are not allowed");
      return; // Stop the function here
    }

    const pad = n => String(n).padStart(2, "0");
    created_at = `${localDate.getUTCFullYear()}-${pad(localDate.getUTCMonth()+1)}-${pad(localDate.getUTCDate())} ` +
                 `${pad(localDate.getUTCHours())}:${pad(localDate.getUTCMinutes())}:${pad(localDate.getUTCSeconds())}`;
  }

  const btn = document.querySelector(".btn-submit");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';

  try {
    const res = await fetch("/api/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, amount: txType === "in" ? rawAmount : `-${rawAmount}`, note, created_at })
    });
    const data = await res.json();
    if (data.status === "ok") {
      document.getElementById("amount-input").value = "";
      document.getElementById("note-input").value = "";
      document.getElementById("datetime-input").value = "";
      showToast(txType === "in" ? "✅ Income added!" : "✅ Expense added!");
      bustCache(`bal_${USER_ID}`, `hist_${USER_ID}_0`);
      loadBalance(true);
    } else {
      showToast("❌ " + (data.error || "Failed"));
    }
  } catch {
    showToast("❌ Network error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Add Transaction";
  }
}

// ── History ────────────────────────────────────────────
async function loadHistory(append = false) {
  if (!append) {
    historyOffset = 0;
    const cached = getCached(`hist_${USER_ID}_0`);
    if (cached) { renderHistory(cached, false); return; }
    document.getElementById("tx-list").innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
  }

  const ckey = `hist_${USER_ID}_${historyOffset}`;
  if (isFetching[ckey]) return;
  isFetching[ckey] = true;

  try {
    const res = await fetch(`/api/history?user_id=${USER_ID}&limit=${PAGE_SIZE}&offset=${historyOffset}`);
    const data = await res.json();
    if (!append) setCache(`hist_${USER_ID}_0`, data);
    renderHistory(data, append);
  } finally { isFetching[ckey] = false; }
}

function renderHistory(data, append) {
  const list = document.getElementById("tx-list");
  if (!append) list.innerHTML = "";

  if (!data.transactions.length && !append) {
    list.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>No transactions yet</p></div>';
    document.getElementById("load-more-btn").style.display = "none";
    return;
  }

  data.transactions.forEach(tx => list.appendChild(buildTxItem(tx)));
  historyOffset += data.transactions.length;
  document.getElementById("load-more-btn").style.display =
    data.transactions.length === PAGE_SIZE ? "block" : "none";
}

function buildTxItem(tx) {
  const isIn = tx.type === "in";
  const div = document.createElement("div");
  div.className = "tx-item";
  div.innerHTML = `
    <div class="tx-icon ${isIn ? "income" : "expense"}">${isIn ? "💰" : "💸"}</div>
    <div class="tx-info">
      <div class="tx-note">${tx.note || (isIn ? "Income" : "Expense")}</div>
      <div class="tx-date">#${tx.id} · ${fmtDate(tx.created_at)}</div>
    </div>
    <div class="tx-amount ${isIn ? "income" : "expense"}">${isIn ? "+" : "-"}${fmt(tx.amount)}</div>
    <button class="tx-edit" aria-label="Edit transaction" onclick="openEditModal(${tx.id})">✎</button>
    <button class="tx-delete" aria-label="Delete transaction" onclick="openDeleteModal(${tx.id}, '${(tx.note || "").replace(/'/g, "\\'")}', ${tx.amount}, '${tx.type}')">🗑</button>
  `;
  return div;
}

async function openEditModal(id) {
  const res = await fetch(`/api/history?user_id=${USER_ID}&limit=50&offset=0`);
  const data = await res.json();
  const tx = data.transactions.find(item => item.id === id);
  if (!tx) { showToast("❌ Transaction not found"); return; }
  document.getElementById("edit-transaction-id").value = tx.id;
  document.getElementById("edit-type").value = tx.type;
  document.getElementById("edit-amount").value = tx.amount;
  document.getElementById("edit-note").value = tx.note || "";
  document.getElementById("edit-datetime").value = tx.created_at.replace(" ", "T").slice(0, 16);
  document.getElementById("edit-modal").classList.add("show");
}

function closeEditModal() { document.getElementById("edit-modal").classList.remove("show"); }

async function saveEdit() {
  const localDate = new Date(document.getElementById("edit-datetime").value);
  if (!Number.isFinite(localDate.getTime()) || localDate > new Date()) { showToast("⚠️ Invalid or future date"); return; }
  const pad = n => String(n).padStart(2, "0");
  const created_at = `${localDate.getUTCFullYear()}-${pad(localDate.getUTCMonth()+1)}-${pad(localDate.getUTCDate())} ${pad(localDate.getUTCHours())}:${pad(localDate.getUTCMinutes())}:${pad(localDate.getUTCSeconds())}`;
  const res = await fetch("/api/update", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    user_id: USER_ID, transaction_id: Number(document.getElementById("edit-transaction-id").value), type: document.getElementById("edit-type").value,
    amount: document.getElementById("edit-amount").value, note: document.getElementById("edit-note").value.trim(), created_at
  })});
  const data = await res.json();
  if (data.status !== "ok") { showToast("❌ " + (data.error || "Failed")); return; }
  closeEditModal(); showToast("✅ Transaction updated");
  bustCache(`bal_${USER_ID}`, `hist_${USER_ID}_0`); loadBalance(true); historyOffset = 0; loadHistory();
}

function loadMore() { loadHistory(true); }

// ── Delete ─────────────────────────────────────────────
function openDeleteModal(id, note, amount, type) {
  pendingDeleteId = id;
  const icon = type === "in" ? "💰" : "💸";
  document.getElementById("delete-modal-body").innerHTML =
    `${icon} <b>${fmtFull(amount)} ${cur()}</b>${note ? ` — ${note}` : ""}<br><small style="color:var(--text-muted)">Transaction #${id}</small>`;
  document.getElementById("delete-modal").classList.add("show");
}

function closeDeleteModal() {
  document.getElementById("delete-modal").classList.remove("show");
  pendingDeleteId = null;
}

async function confirmDelete() {
  if (!pendingDeleteId) return;
  const res = await fetch("/api/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, transaction_id: pendingDeleteId })
  });
  const data = await res.json();
  closeDeleteModal();
  if (data.status === "ok") {
    showToast("🗑 Deleted");
    bustCache(`bal_${USER_ID}`, `hist_${USER_ID}_0`);
    loadBalance(true);
    historyOffset = 0;
    loadHistory();
  } else {
    showToast("❌ " + (data.error || "Failed"));
  }
}

// ── Summary ────────────────────────────────────────────
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
let currentYear = new Date().getFullYear();

function setSummaryPeriod(period) {
  currentSummaryPeriod = period;
  document.querySelectorAll(".period-btn").forEach((el, i) => {
    el.classList.toggle("active", ["month","year","all"][i] === period);
  });
  document.getElementById("summary-month-view").style.display = period === "month" ? "block" : "none";
  document.getElementById("summary-year-view").style.display  = period === "year"  ? "block" : "none";
  document.getElementById("summary-all-view").style.display   = period === "all"   ? "block" : "none";
  loadSummary();
}

async function loadSummary() {
  const ckey = `sum_${USER_ID}_${currentSummaryPeriod}${currentSummaryPeriod === "year" ? "_" + currentYear : ""}`;
  const cached = getCached(ckey);

  if (currentSummaryPeriod === "month") {
    if (cached) { renderMonthSummary(cached); return; }
    if (isFetching[ckey]) return;
    isFetching[ckey] = true;
    ["sum-in","sum-out","sum-net"].forEach(id => {
      document.getElementById(id).innerHTML = '<span class="spinner"></span>';
    });
    try {
      const res = await fetch(`/api/summary?user_id=${USER_ID}&period=month`);
      const data = await res.json();
      setCache(ckey, data);
      renderMonthSummary(data);
    } finally { isFetching[ckey] = false; }

  } else if (currentSummaryPeriod === "year") {
    document.getElementById("year-nav-label").textContent = currentYear;
    if (cached) { renderBreakdown("monthly-list", cached.rows, r => MONTHS[r.month - 1]); return; }
    if (isFetching[ckey]) return;
    isFetching[ckey] = true;
    document.getElementById("monthly-list").innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    try {
      const res = await fetch(`/api/summary/monthly?user_id=${USER_ID}&year=${currentYear}`);
      const data = await res.json();
      setCache(ckey, data);
      renderBreakdown("monthly-list", data.rows, r => MONTHS[r.month - 1]);
    } finally { isFetching[ckey] = false; }

  } else {
    if (cached) { renderBreakdown("yearly-list", cached.rows, r => String(r.year)); return; }
    if (isFetching[ckey]) return;
    isFetching[ckey] = true;
    document.getElementById("yearly-list").innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    try {
      const res = await fetch(`/api/summary/yearly?user_id=${USER_ID}`);
      const data = await res.json();
      setCache(ckey, data);
      renderBreakdown("yearly-list", data.rows, r => String(r.year));
    } finally { isFetching[ckey] = false; }
  }
}

function renderMonthSummary(data) {
  document.getElementById("sum-in").textContent  = fmtFull(data.total_in)  + " " + cur();
  document.getElementById("sum-out").textContent = fmtFull(data.total_out) + " " + cur();
  const net = data.total_in - data.total_out;
  const netEl = document.getElementById("sum-net");
  netEl.textContent = (net >= 0 ? "+" : "") + fmtFull(net) + " " + cur();
  netEl.className = "net-value " + (net >= 0 ? "positive" : "negative");
}

function renderBreakdown(containerId, rows, labelFn) {
  const list = document.getElementById(containerId);
  if (!rows.length) {
    list.innerHTML = '<div class="empty-state"><div class="icon">📊</div><p>No data</p></div>';
    return;
  }
  const maxIn = Math.max(...rows.map(r => r.total_in), 1);
  list.innerHTML = "";
  rows.forEach(r => {
    const net = r.total_in - r.total_out;
    const barPct = Math.round((r.total_in / maxIn) * 100);
    const div = document.createElement("div");
    div.className = "breakdown-row";
    div.innerHTML = `
      <div class="breakdown-row-top">
        <div class="breakdown-label">${labelFn(r)}</div>
        <div class="breakdown-net ${net >= 0 ? "positive" : "negative"}">${net >= 0 ? "+" : ""}${fmt(net)}</div>
      </div>
      <div class="breakdown-bar-wrap"><div class="breakdown-bar-in" style="width:${barPct}%"></div></div>
      <div class="breakdown-sub">
        <span class="inc">↑ ${fmt(r.total_in)}</span>
        <span class="exp">↓ ${fmt(r.total_out)}</span>
      </div>
    `;
    list.appendChild(div);
  });
}

function shiftYear(delta) {
  currentYear += delta;
  loadSummary();
}

// ── Settings ───────────────────────────────────────────
async function loadSettings() {
  const res = await fetch(`/api/settings?user_id=${USER_ID}`);
  userSettings = await res.json();
}

function openSettings() {
  const detectedTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  document.getElementById("settings-currency").value = userSettings.currency || "MMK";
  document.getElementById("settings-timezone").value = userSettings.timezone || detectedTz;
  document.getElementById("tz-detected").textContent =
    detectedTz ? `🌐 Browser detected: ${detectedTz}` : "";
  document.getElementById("settings-modal").classList.add("show");
}

function closeSettings() {
  document.getElementById("settings-modal").classList.remove("show");
}

async function saveSettings() {
  const currency = document.getElementById("settings-currency").value.trim().toUpperCase();
  const timezone = document.getElementById("settings-timezone").value.trim();
  if (!currency) { showToast("⚠️ Enter a currency"); return; }
  if (!timezone)  { showToast("⚠️ Enter a timezone");  return; }
  try { Intl.DateTimeFormat(undefined, { timeZone: timezone }); }
  catch { showToast("❌ Invalid timezone"); return; }

  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, currency, timezone })
  });
  const data = await res.json();
  if (data.status === "ok") {
    userSettings = { currency, timezone };
    // bust all caches so re-renders use new currency label
    Object.keys(cache).forEach(k => delete cache[k]);
    closeSettings();
    showToast("✅ Settings saved");
    loadBalance(true);
    const activePanel = document.querySelector(".panel.active")?.id;
    if (activePanel === "panel-history") { historyOffset = 0; loadHistory(); }
    if (activePanel === "panel-summary") loadSummary();
  } else {
    showToast("❌ Failed to save");
  }
}

// ── Enter key support ──────────────────────────────────
document.getElementById("note-input").addEventListener("keydown", e => {
  if (e.key === "Enter") submitTransaction();
});
document.getElementById("amount-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("note-input").focus();
});

// ── Init ───────────────────────────────────────────────
async function init() {
  const detectedTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  await loadSettings();
  if (userSettings.timezone === "UTC" && detectedTz && detectedTz !== "UTC") {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, currency: userSettings.currency, timezone: detectedTz })
    });
    userSettings.timezone = detectedTz;
  }
  loadBalance();
}
init();
