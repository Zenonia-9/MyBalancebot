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
const USER_ID = tgUser?.id || 1; // fallback for local testing

document.getElementById("username").textContent =
  tgUser ? `@${tgUser.username || tgUser.first_name}` : "Demo Mode";

// ── State ──────────────────────────────────────────────
let txType = "in";
let historyOffset = 0;
const PAGE_SIZE = 20;
let pendingDeleteId = null;
let currentSummaryPeriod = "month";

// ── Helpers ────────────────────────────────────────────
function fmt(amount) {
  if (amount >= 1_000_000) return (amount / 1_000_000).toFixed(2).replace(/\.?0+$/, "") + "m";
  if (amount >= 1_000) return (amount / 1_000).toFixed(2).replace(/\.?0+$/, "") + "k";
  return amount.toLocaleString();
}

function fmtFull(amount) {
  return amount.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function showToast(msg, duration = 2200) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), duration);
}

// ── Tabs ───────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((el, i) => {
    const names = ["add", "history", "summary"];
    el.classList.toggle("active", names[i] === name);
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
async function loadBalance() {
  const res = await fetch(`/api/balance?user_id=${USER_ID}`);
  const data = await res.json();
  document.getElementById("balance-display").textContent = fmtFull(data.balance) + " MMK";
  document.getElementById("total-in-display").textContent = fmt(data.total_in) + " MMK";
  document.getElementById("total-out-display").textContent = fmt(data.total_out) + " MMK";
}

// ── Add Transaction ────────────────────────────────────
async function submitTransaction() {
  const rawAmount = document.getElementById("amount-input").value.trim();
  const note = document.getElementById("note-input").value.trim();

  if (!rawAmount) { showToast("⚠️ Enter an amount"); return; }

  const btn = document.querySelector(".btn-submit");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';

  try {
    const res = await fetch("/api/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, amount: txType === "in" ? rawAmount : `-${rawAmount}`, note })
    });
    const data = await res.json();
    if (data.status === "ok") {
      document.getElementById("amount-input").value = "";
      document.getElementById("note-input").value = "";
      showToast(txType === "in" ? "✅ Income added!" : "✅ Expense added!");
      loadBalance();
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
    document.getElementById("tx-list").innerHTML = '<div class="empty-state"><div class="spinner"></div></div>';
  }

  const res = await fetch(`/api/history?user_id=${USER_ID}&limit=${PAGE_SIZE}&offset=${historyOffset}`);
  const data = await res.json();
  const list = document.getElementById("tx-list");

  if (!append) list.innerHTML = "";

  if (data.transactions.length === 0 && !append) {
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
      <div class="tx-date">#${tx.id} · ${tx.created_at}</div>
    </div>
    <div class="tx-amount ${isIn ? "income" : "expense"}">${isIn ? "+" : "-"}${fmt(tx.amount)}</div>
    <button class="tx-delete" onclick="openDeleteModal(${tx.id}, '${(tx.note || "").replace(/'/g, "\\'")}', ${tx.amount}, '${tx.type}')">🗑</button>
  `;
  return div;
}

function loadMore() { loadHistory(true); }

// ── Delete ─────────────────────────────────────────────
function openDeleteModal(id, note, amount, type) {
  pendingDeleteId = id;
  const icon = type === "in" ? "💰" : "💸";
  document.getElementById("delete-modal-body").innerHTML =
    `${icon} <b>${fmtFull(amount)} MMK</b>${note ? ` — ${note}` : ""}<br><small style="color:var(--text-muted)">Transaction #${id}</small>`;
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
    loadBalance();
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
  if (currentSummaryPeriod === "month") {
    ["sum-in","sum-out","sum-net"].forEach(id => {
      document.getElementById(id).innerHTML = '<span class="spinner"></span>';
    });
    const res = await fetch(`/api/summary?user_id=${USER_ID}&period=month`);
    const data = await res.json();
    document.getElementById("sum-in").textContent  = fmtFull(data.total_in)  + " MMK";
    document.getElementById("sum-out").textContent = fmtFull(data.total_out) + " MMK";
    const net = data.total_in - data.total_out;
    const netEl = document.getElementById("sum-net");
    netEl.textContent = (net >= 0 ? "+" : "") + fmtFull(net) + " MMK";
    netEl.className = "net-value " + (net >= 0 ? "positive" : "negative");

  } else if (currentSummaryPeriod === "year") {
    document.getElementById("year-nav-label").textContent = currentYear;
    document.getElementById("monthly-list").innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    const res = await fetch(`/api/summary/monthly?user_id=${USER_ID}&year=${currentYear}`);
    const data = await res.json();
    renderBreakdown("monthly-list", data.rows, r => MONTHS[r.month - 1]);

  } else {
    document.getElementById("yearly-list").innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';
    const res = await fetch(`/api/summary/yearly?user_id=${USER_ID}`);
    const data = await res.json();
    renderBreakdown("yearly-list", data.rows, r => String(r.year));
  }
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

// ── Enter key support ──────────────────────────────────
document.getElementById("note-input").addEventListener("keydown", e => {
  if (e.key === "Enter") submitTransaction();
});
document.getElementById("amount-input").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("note-input").focus();
});

// ── Init ───────────────────────────────────────────────
loadBalance();
