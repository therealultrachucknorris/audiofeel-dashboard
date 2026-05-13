/* ═══════════════════════════════════════════
   AudioFeel Dashboard — app.js
   ═══════════════════════════════════════════ */

let dashboardData = null;
let charts = {};

const PLATFORM_LABELS = { WHATSAPP: "WhatsApp", INSTAGRAM: "Instagram", LIVE_CHAT: "Live Chat" };
const TOPIC_LABELS = {
  product_inquiry: "Product Inquiry", order_issue: "Order Issue", delivery: "Delivery",
  complaint: "Complaint", affiliate: "Affiliate", support: "Support", general: "General"
};

// Palette — OLED-friendly with high contrast
const C = {
  amber: "#e8a838",
  amberDim: "rgba(232,168,56,0.12)",
  positive: "#4ade80",
  negative: "#f87171",
  info: "#60a5fa",
  neutral: "#94a3b8",
  purple: "#a78bfa",
  teal: "#2dd4bf",
  rose: "#fb7185",
};

/* ── Data Loading ── */
async function loadData() {
  try {
    const res = await fetch("../dashboard_data.json?t=" + Date.now());
    if (!res.ok) throw new Error("No data file");
    dashboardData = await res.json();
    render();
    document.getElementById("sidebar-status").textContent = "Live \u2014 Auto-refresh";
  } catch (e) {
    document.getElementById("no-data").style.display = "flex";
    document.getElementById("convo-table").style.display = "none";
    document.getElementById("sidebar-status").textContent = "No data available";
  }
}

/* ── Render All ── */
function render() {
  if (!dashboardData?.conversations) return;
  const convos = dashboardData.conversations;
  const stats = dashboardData.stats || computeStats(convos);

  document.getElementById("no-data").style.display = "none";
  document.getElementById("convo-table").style.display = "table";

  // Header
  document.getElementById("last-updated").textContent =
    "Updated " + (dashboardData.last_updated || "N/A") + " \u00B7 " + convos.length + " total conversations";

  // KPIs with animated counters
  animateValue("kpi-total", convos.length);
  document.getElementById("kpi-resolution").textContent = stats.resolution_rate + "%";
  document.getElementById("kpi-lead-score").textContent = stats.avg_lead_score;
  animateValue("kpi-escalations", stats.escalation_count);

  // Alert badge in sidebar
  const alertBadge = document.getElementById("nav-alert-count");
  alertBadge.textContent = stats.escalation_count;
  alertBadge.dataset.count = stats.escalation_count;

  renderCharts(stats);
  renderEscalations(convos);
  renderTable();
}

function animateValue(id, target) {
  const el = document.getElementById(id);
  const start = parseInt(el.textContent) || 0;
  if (start === target) { el.textContent = target; return; }

  // Respect reduced motion
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.textContent = target;
    return;
  }

  const duration = 500;
  const startTime = performance.now();
  function tick(now) {
    const p = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(start + (target - start) * ease);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

/* ── Stats ── */
function computeStats(convos) {
  const platforms = {}, topics = {}, sentiments = {}, daily = {};
  let resolved = 0, escalations = 0, leadSum = 0, leadCount = 0;
  convos.forEach(c => {
    platforms[c.platform] = (platforms[c.platform] || 0) + 1;
    topics[c.topic] = (topics[c.topic] || 0) + 1;
    sentiments[c.sentiment] = (sentiments[c.sentiment] || 0) + 1;
    daily[c.date] = (daily[c.date] || 0) + 1;
    if (c.resolution === "resolved") resolved++;
    if (c.escalation_needed) escalations++;
    if (c.lead_score) { leadSum += c.lead_score; leadCount++; }
  });
  return {
    platforms, topics, sentiments, daily,
    resolution_rate: convos.length ? Math.round(resolved / convos.length * 100) : 0,
    escalation_count: escalations,
    avg_lead_score: leadCount ? (leadSum / leadCount).toFixed(1) : "N/A"
  };
}

/* ── Charts ── */
function renderCharts(stats) {
  Object.values(charts).forEach(c => c.destroy());
  charts = {};

  Chart.defaults.color = "#4e525e";
  Chart.defaults.borderColor = "rgba(255,255,255,0.03)";
  Chart.defaults.font.family = "'Fira Sans', sans-serif";

  // Custom tooltip style
  const tooltipConfig = {
    backgroundColor: "#1a1c22",
    borderColor: "rgba(255,255,255,0.08)",
    borderWidth: 1,
    titleColor: "#eceae4",
    bodyColor: "#8a8d98",
    titleFont: { family: "'Fira Code', monospace", size: 12, weight: 600 },
    bodyFont: { family: "'Fira Sans', sans-serif", size: 12 },
    padding: 10,
    cornerRadius: 8,
    displayColors: true,
    boxPadding: 4,
  };

  const legendOpts = {
    position: "bottom",
    labels: { padding: 14, usePointStyle: true, pointStyleWidth: 8, font: { size: 11 } }
  };

  // Daily volume — smooth area chart with amber
  const dates = Object.keys(stats.daily).sort();
  const shortDates = dates.map(d => { const p = d.split("-"); return p[2] + "/" + p[1]; });
  charts.daily = new Chart(document.getElementById("chart-daily"), {
    type: "line",
    data: {
      labels: shortDates,
      datasets: [{
        data: dates.map(d => stats.daily[d]),
        borderColor: C.amber,
        backgroundColor: "rgba(232,168,56,0.05)",
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: C.amber,
        pointHoverBorderColor: "#08090b",
        pointHoverBorderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { ...tooltipConfig, mode: "index", intersect: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxRotation: 0, maxTicksLimit: 10, font: { size: 10 } } },
        y: { grid: { color: "rgba(255,255,255,0.025)" }, ticks: { font: { family: "'Fira Code'", size: 10 } }, beginAtZero: true }
      },
      interaction: { mode: "nearest", axis: "x", intersect: false },
    }
  });

  // Platform doughnut
  const platKeys = Object.keys(stats.platforms);
  charts.platform = new Chart(document.getElementById("chart-platform"), {
    type: "doughnut",
    data: {
      labels: platKeys.map(k => PLATFORM_LABELS[k] || k),
      datasets: [{
        data: platKeys.map(k => stats.platforms[k]),
        backgroundColor: [C.positive, C.rose, C.info],
        borderWidth: 0,
        spacing: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "66%",
      plugins: { legend: legendOpts, tooltip: tooltipConfig }
    }
  });

  // Sentiment doughnut
  const sentOrder = ["positive", "neutral", "negative"];
  const sentColors = [C.positive, C.neutral, C.negative];
  charts.sentiment = new Chart(document.getElementById("chart-sentiment"), {
    type: "doughnut",
    data: {
      labels: sentOrder.map(s => s[0].toUpperCase() + s.slice(1)),
      datasets: [{
        data: sentOrder.map(s => stats.sentiments[s] || 0),
        backgroundColor: sentColors,
        borderWidth: 0,
        spacing: 3,
        hoverOffset: 6,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "66%",
      plugins: { legend: legendOpts, tooltip: tooltipConfig }
    }
  });

  // Topic horizontal bar — each bar a distinct color
  const topicKeys = Object.keys(stats.topics).sort((a, b) => stats.topics[b] - stats.topics[a]);
  const topicColors = [C.amber, C.info, C.purple, C.teal, C.negative, C.positive, C.neutral];
  charts.topic = new Chart(document.getElementById("chart-topic"), {
    type: "bar",
    data: {
      labels: topicKeys.map(k => TOPIC_LABELS[k] || k),
      datasets: [{
        data: topicKeys.map(k => stats.topics[k]),
        backgroundColor: topicKeys.map((_, i) => topicColors[i % topicColors.length]),
        borderRadius: 4,
        borderSkipped: false,
        barPercentage: 0.65,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: tooltipConfig },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.025)" }, ticks: { font: { family: "'Fira Code'", size: 10 } } },
        y: { grid: { display: false }, ticks: { font: { size: 10 } } }
      }
    }
  });
}

/* ── Escalations ── */
function renderEscalations(convos) {
  const esc = convos.filter(c => c.escalation_needed);
  const section = document.getElementById("escalations-section");
  const container = document.getElementById("escalation-cards");

  document.getElementById("esc-count").textContent = esc.length;
  if (!esc.length) { section.style.display = "none"; return; }
  section.style.display = "block";

  container.innerHTML = esc.slice(0, 12).map(c => {
    const idx = convos.indexOf(c);
    return `<div class="esc-card" onclick="openModal(${idx})" role="button" tabindex="0" onkeydown="if(event.key==='Enter')openModal(${idx})">
      <div class="esc-name">${h(c.contact_name)}</div>
      <div class="esc-summary">${h(c.summary || "")}</div>
      <div class="esc-meta">
        <span>${c.date}</span>
        <span>${PLATFORM_LABELS[c.platform] || c.platform}</span>
        <span>${TOPIC_LABELS[c.topic] || c.topic}</span>
      </div>
    </div>`;
  }).join("");
}

/* ── Table ── */
function renderTable() {
  if (!dashboardData) return;
  const convos = dashboardData.conversations;
  const search = document.getElementById("filter-search").value.toLowerCase();
  const platform = document.getElementById("filter-platform").value;
  const topic = document.getElementById("filter-topic").value;
  const sentiment = document.getElementById("filter-sentiment").value;

  const filtered = convos.filter(c => {
    if (platform && c.platform !== platform) return false;
    if (topic && c.topic !== topic) return false;
    if (sentiment && c.sentiment !== sentiment) return false;
    if (search && !(c.contact_name || "").toLowerCase().includes(search) &&
        !(c.summary || "").toLowerCase().includes(search)) return false;
    return true;
  });

  document.getElementById("conv-count").textContent = filtered.length;

  const tbody = document.getElementById("convo-tbody");
  tbody.innerHTML = filtered.map(c => {
    const idx = convos.indexOf(c);
    const sentClass = c.sentiment || "neutral";
    const leadClass = c.lead_score >= 4 ? "lead-high" : c.lead_score >= 2 ? "lead-mid" : "lead-low";
    const statusClass = c.resolution === "resolved" ? "resolved" : c.resolution === "unresolved" ? "unresolved" : "unclear";

    return `<tr onclick="openModal(${idx})" tabindex="0" onkeydown="if(event.key==='Enter')openModal(${idx})" role="row">
      <td>${c.date || ""}</td>
      <td>${h(c.contact_name || "")}</td>
      <td><span class="pill pill--platform">${PLATFORM_LABELS[c.platform] || c.platform}</span></td>
      <td><span class="pill pill--topic">${TOPIC_LABELS[c.topic] || c.topic || "--"}</span></td>
      <td><span class="pill pill--${sentClass}">${sentClass}</span></td>
      <td><span class="lead-score ${leadClass}">${c.lead_score || "--"}</span></td>
      <td><span class="status-dot status-${statusClass}"></span>${c.resolution || "--"}</td>
      <td class="summary-cell">${h(c.summary || "")}</td>
    </tr>`;
  }).join("");
}

/* ── Modal ── */
function openModal(idx) {
  const c = dashboardData.conversations[idx];
  if (!c) return;

  document.getElementById("modal-title").textContent = c.contact_name || "Conversation";

  const meta = document.getElementById("modal-meta");
  meta.innerHTML = [
    c.date,
    PLATFORM_LABELS[c.platform] || c.platform,
    (c.message_count || 0) + " messages",
    c.bot_vs_human,
  ].filter(Boolean).map(t => `<span class="meta-tag">${t}</span>`).join("");

  // Analysis pills
  const analysis = document.getElementById("modal-analysis");
  const sentClass = c.sentiment || "neutral";
  analysis.innerHTML = [
    c.topic ? `<span class="pill pill--topic">${TOPIC_LABELS[c.topic] || c.topic}</span>` : "",
    c.sentiment ? `<span class="pill pill--${sentClass}">${c.sentiment}</span>` : "",
    c.resolution ? `<span class="pill pill--${c.resolution === 'resolved' ? 'positive' : c.resolution === 'unresolved' ? 'negative' : 'neutral'}">${c.resolution}</span>` : "",
    c.lead_score ? `<span class="pill" style="background:var(--amber-dim);color:var(--amber)">Lead: ${c.lead_score}/5</span>` : "",
    c.escalation_needed ? `<span class="pill pill--negative">Escalation needed</span>` : "",
  ].filter(Boolean).join("");

  // Messages
  const msgs = (c.messages || []).filter(m => m.event_type !== "open_chat");
  const msgContainer = document.getElementById("modal-messages");
  msgContainer.innerHTML = msgs.map((m, i) => {
    if (m.direction === "system" || m.type === "system") {
      return `<div class="msg-bubble msg-system">${m.event_type || "system"}</div>`;
    }
    const dir = m.direction === "inbound" ? "msg-inbound" : "msg-outbound";
    const isHuman = m.sender && m.sender !== "Bot" && m.sender !== "customer";
    const humanClass = isHuman ? " msg-human" : "";
    const senderLabel = m.direction === "inbound" ? (c.contact_name || "Customer") : (m.sender || "Bot");
    const text = m.text || `[${m.type || "no text"}]`;
    return `<div class="msg-bubble ${dir}${humanClass}" style="animation-delay:${i * 0.025}s">
      <div class="msg-sender">${h(senderLabel)}</div>
      <div>${h(text)}</div>
      <div class="msg-time">${m.time || ""}</div>
    </div>`;
  }).join("");

  document.getElementById("modal").classList.add("active");
  document.body.style.overflow = "hidden";

  // Focus trap: focus close button
  setTimeout(() => document.querySelector(".modal-close")?.focus(), 100);
}

function closeModal() {
  document.getElementById("modal").classList.remove("active");
  document.body.style.overflow = "";
}

/* ── Helpers ── */
function h(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/* ── Init ── */
loadData();
setInterval(loadData, 60000);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// Smooth scroll for nav links
document.querySelectorAll(".nav-item[href^='#']").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute("href"));
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});
