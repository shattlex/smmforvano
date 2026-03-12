const kpiGrid = document.getElementById("kpiGrid");
const runsBody = document.getElementById("runsBody");
const resultsBody = document.getElementById("resultsBody");
const runBtn = document.getElementById("runBtn");
const refreshBtn = document.getElementById("refreshBtn");
const logoutBtn = document.getElementById("logoutBtn");
const userEmail = document.getElementById("userEmail");
const toast = document.getElementById("toast");

function showToast(text) {
  toast.textContent = text;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

function statusClass(status) {
  return `s-${String(status || "").toLowerCase().replace(/_/g, "-")}`;
}

function num(v) {
  return Number(v || 0);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "include",
    ...options,
  });

  if (res.status === 401) {
    window.location.href = "/login";
    return null;
  }

  const data = await res.json();
  return { res, data };
}

async function loadMe() {
  const out = await api("/api/me");
  if (!out) return;
  userEmail.textContent = out.data.email || "";
}

async function loadKpi() {
  const out = await api("/api/kpi");
  if (!out) return;
  const data = out.data;

  const cards = [
    ["Total checks", num(data.total_checks), "Все проверки"],
    ["Inbox rate", `${num(data.inbox_rate_pct)}%`, `${num(data.inbox)} писем`],
    ["Spam rate", `${num(data.spam_rate_pct)}%`, `${num(data.spam)} писем`],
    ["Missing rate", `${num(data.missing_rate_pct)}%`, `${num(data.not_delivered)} писем`],
    ["Errors", num(data.errors), "Проверьте auth/IMAP"],
  ];

  kpiGrid.innerHTML = cards
    .map(
      ([title, value, sub]) => `
      <article class="kpi-card">
        <p class="kpi-title">${title}</p>
        <p class="kpi-value">${value}</p>
        <p class="kpi-sub">${sub}</p>
      </article>
    `
    )
    .join("");
}

async function loadRuns() {
  const out = await api("/api/runs?limit=12");
  if (!out) return;
  const runs = out.data.runs || [];

  runsBody.innerHTML = runs
    .map(
      (row) => `
      <tr>
        <td>${row.run_id}</td>
        <td><span class="status ${statusClass(row.status)}">${row.status}</span></td>
        <td>${num(row.inbox)}</td>
        <td>${num(row.spam)}</td>
        <td>${num(row.not_delivered)}</td>
        <td>${num(row.errors)}</td>
        <td>${row.started_at_utc || ""}</td>
      </tr>
    `
    )
    .join("");
}

async function loadResults() {
  const out = await api("/api/results?limit=150");
  if (!out) return;
  const rows = out.data.results || [];

  resultsBody.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.run_id}</td>
        <td>${row.campaign_name}</td>
        <td>${row.seed_name}<br><small>${row.seed_email}</small></td>
        <td><span class="status ${statusClass(row.status)}">${row.status}</span></td>
        <td>${row.found_folder || ""}</td>
        <td>${row.latest_message_utc || ""}</td>
        <td>${row.error || ""}</td>
      </tr>
    `
    )
    .join("");
}

async function refreshAll() {
  await Promise.all([loadMe(), loadKpi(), loadRuns(), loadResults()]);
}

runBtn.addEventListener("click", async () => {
  runBtn.disabled = true;
  runBtn.textContent = "Running...";
  try {
    const out = await api("/api/run", { method: "POST" });
    if (!out) return;
    const { res, data } = out;
    if (!res.ok) {
      showToast(data.error || "Run failed");
    } else {
      showToast(`Run #${data.run_id} completed`);
      await refreshAll();
    }
  } catch (err) {
    showToast("Network error");
  } finally {
    runBtn.disabled = false;
    runBtn.textContent = "Run Check";
  }
});

logoutBtn.addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  window.location.href = "/login";
});

refreshBtn.addEventListener("click", refreshAll);

refreshAll();
