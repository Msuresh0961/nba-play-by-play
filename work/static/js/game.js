const feed = document.getElementById("feed");
const scoreboard = document.getElementById("scoreboard");
const title = document.getElementById("title");
const subtitle = document.getElementById("subtitle");
const voiceToggle = document.getElementById("voiceToggle");
const testVoiceButton = document.getElementById("testVoiceButton");
const notifButton = document.getElementById("notifButton");
const analysisPanel = document.getElementById("analysisPanel");

const spoken = new Set();
const rendered = new Set();
const audioQueue = [];
let audioPlaying = false;
let gameFinal = false;

// ── Player filter state ───────────────────────────────────────────────────────
let activePlayer = null;
const knownPlayers = new Set();

if (window.puter) window.puter.quiet = true;

// ── Push notifications ────────────────────────────────────────────────────────

let notificationsEnabled = false;

async function requestNotifications() {
  if (!("Notification" in window)) {
    notifButton.textContent = "🔕 Not supported";
    notifButton.disabled = true;
    return;
  }
  if (Notification.permission === "granted") {
    notificationsEnabled = true;
    notifButton.textContent = "🔔 Alerts on";
    notifButton.style.opacity = "0.6";
    return;
  }
  const permission = await Notification.requestPermission();
  if (permission === "granted") {
    notificationsEnabled = true;
    notifButton.textContent = "🔔 Alerts on";
    notifButton.style.opacity = "0.6";
  } else {
    notifButton.textContent = "🔕 Blocked";
    notifButton.disabled = true;
  }
}

function sendNotification(event) {
  if (!notificationsEnabled) return;
  if (document.visibilityState === "visible") return;
  if (event.priority !== "high") return;

  const play = event.play || {};
  const badge = { three_pointer: "🔥", dunk: "💥", lead_change: "⚡", scoring_run: "🚀", clutch_score: "🏆" };
  const icon = badge[event.type] || "🏀";
  const body = play.description || event.narration || "Big play!";

  try {
    new Notification(`${icon} NBA Alert`, { body, tag: String(play.id ?? Date.now()) });
  } catch (e) {
    console.warn("Notification failed:", e);
  }
}

if (notifButton) {
  notifButton.addEventListener("click", requestNotifications);
  if (Notification.permission === "granted") {
    notificationsEnabled = true;
    notifButton.textContent = "🔔 Alerts on";
    notifButton.style.opacity = "0.6";
  }
}

// ── TTS ───────────────────────────────────────────────────────────────────────

// ── TTS ───────────────────────────────────────────────────────────────────────

let puterAvailable = null; // null = untested, true/false after first attempt

function speakWithBrowser(text) {
  if (!voiceToggle?.checked || !window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function speakWithPuter(text) {
  if (!window.puter?.ai?.txt2speech) {
    puterAvailable = false;
    speakWithBrowser(text);
    return;
  }
  try {
    const audio = await window.puter.ai.txt2speech(text);
    puterAvailable = true;
    audioQueue.push(audio);
    playNextAudio();
  } catch (e) {
    console.warn("Puter TTS failed:", e);
    puterAvailable = false;
    speakWithBrowser(text);
  }
}

function playNextAudio() {
  if (audioPlaying || audioQueue.length === 0) return;
  const audio = audioQueue.shift();
  audioPlaying = true;
  // Cancel any browser speech that might be running
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  audio.onended = () => { audioPlaying = false; playNextAudio(); };
  audio.onerror  = () => { audioPlaying = false; playNextAudio(); };
  audio.play().catch(() => { audioPlaying = false; playNextAudio(); });
}

async function speak(text) {
  if (!voiceToggle?.checked) return;
  // If we already know Puter works, go straight to it
  // If we already know it doesn't, go straight to browser
  if (puterAvailable === false) {
    speakWithBrowser(text);
    return;
  }
  await speakWithPuter(text);
}
// ── Scoreboard ────────────────────────────────────────────────────────────────

function renderSummary(summary) {
  if (!summary?.homeTeam || !summary?.awayTeam) return;

  const awayName = `${summary.awayTeam.teamCity || ""} ${summary.awayTeam.teamName || summary.awayTeam.teamTricode || ""}`.trim();
  const homeName = `${summary.homeTeam.teamCity || ""} ${summary.homeTeam.teamName || summary.homeTeam.teamTricode || ""}`.trim();

  title.textContent = `${awayName} at ${homeName}`;
  subtitle.textContent = `${summary.gameStatusText || "Scheduled"} | Q${summary.period || 0} | ${summary.gameClock || ""}`;

  const statusBadge = summary.gameStatus === 3
    ? `<span style="color:var(--accent-2);font-weight:700;font-size:.85rem;">FINAL</span>` : "";

  scoreboard.innerHTML = `
    <div class="card-grid">
      <div class="game-card">
        <div class="meta">${summary.awayTeam.teamTricode || ""} ${statusBadge}</div>
        <h2>${awayName}</h2>
        <div class="scoreline">${summary.awayTeam.score ?? "-"}</div>
      </div>
      <div class="game-card">
        <div class="meta">${summary.homeTeam.teamTricode || ""} ${statusBadge}</div>
        <h2>${homeName}</h2>
        <div class="scoreline">${summary.homeTeam.score ?? "-"}</div>
      </div>
    </div>`;

  if (summary.gameStatus === 3 && !gameFinal) {
    gameFinal = true;
    showGameSummary(summary);
  }
}

// ── Series info ───────────────────────────────────────────────────────────────

function renderSeries(data) {
  const el = document.getElementById("seriesInfo");
  if (!el) return;
  const parts = [];
  if (data.gameLabel)    parts.push(data.gameLabel);
  if (data.gameSubLabel) parts.push(data.gameSubLabel);
  if (data.seriesText)   parts.push(data.seriesText);
  el.textContent = parts.join(" · ");
}

// ── Game summary ──────────────────────────────────────────────────────────────

async function showGameSummary(summary) {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/analysis`);
    const data = await res.json();
    if (!data.available) return;

    const away = summary.awayTeam;
    const home = summary.homeTeam;
    const awayScore = parseInt(away.score) || 0;
    const homeScore = parseInt(home.score) || 0;
    const winner = homeScore > awayScore ? home : away;
    const loser  = homeScore > awayScore ? away : home;
    const margin = Math.abs(homeScore - awayScore);
    const bp = data.best_player;

    const descriptor = margin <= 3 ? "in a nail-biter"
      : margin <= 8  ? "in a close one"
      : margin <= 15 ? "comfortably"
      : "in dominant fashion";

    let summaryText = `Final: ${winner.teamTricode} ${Math.max(homeScore, awayScore)}, ${loser.teamTricode} ${Math.min(homeScore, awayScore)} — ${winner.teamTricode} win ${descriptor}.`;
    if (bp?.points > 0) summaryText += ` ${bp.name} led all scorers with ${bp.points} points.`;

    const banner = document.createElement("div");
    banner.className = "analysis-panel";
    banner.style.cssText = "border-color:var(--accent);margin-bottom:16px";
    banner.innerHTML = `
      <h2 class="analysis-title" style="color:var(--accent)">Final</h2>
      <p style="font-size:1.1rem;color:var(--text);margin:0 0 8px;font-weight:600">
        ${winner.teamTricode} ${Math.max(homeScore, awayScore)} &ndash; ${loser.teamTricode} ${Math.min(homeScore, awayScore)}
      </p>
      <p class="analysis-summary" style="margin:0">${summaryText}</p>`;

    const layout = document.querySelector(".game-layout");
    if (layout) layout.parentNode.insertBefore(banner, layout);
    await speak(summaryText);
  } catch (e) {
    console.error("Game summary failed:", e);
  }
}

// ── Player filter ─────────────────────────────────────────────────────────────

function setActivePlayer(name) {
  activePlayer = activePlayer === name ? null : name;
  document.querySelectorAll(".player-chip").forEach(chip => {
    const isActive = chip.dataset.player === activePlayer;
    chip.style.background  = isActive ? "var(--accent)" : "rgba(255,255,255,0.06)";
    chip.style.color       = isActive ? "var(--bg)"     : "var(--text)";
    chip.style.borderColor = isActive ? "var(--accent)" : "var(--border)";
  });
  applyPlayerFilter();
}

function applyPlayerFilter() {
  document.querySelectorAll(".play[data-player]").forEach(el => {
    el.style.display = (!activePlayer || el.dataset.player === activePlayer) ? "" : "none";
  });
}

function buildPlayerChips(teams) {
  const wrap  = document.getElementById("playerFilterWrap");
  const chips = document.getElementById("playerChips");
  if (!wrap || !chips) return;

  for (const players of Object.values(teams)) {
    for (const p of players) {
      if (!p.name || knownPlayers.has(p.name)) continue;
      knownPlayers.add(p.name);

      const chip = document.createElement("button");
      chip.className = "player-chip";
      chip.dataset.player = p.name;
      chip.textContent = p.name;
      chip.style.cssText = `
        background: rgba(255,255,255,0.06);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 99px;
        padding: 4px 10px;
        font-size: .72rem;
        cursor: pointer;
        white-space: nowrap;
        transition: background .15s, color .15s;
      `;
      chip.addEventListener("click", () => setActivePlayer(p.name));
      chips.appendChild(chip);
    }
  }
  if (knownPlayers.size > 0) wrap.style.display = "";
}

// ── Play-by-play feed ─────────────────────────────────────────────────────────

const EVENT_BADGE = {
  three_pointer: "🔥",
  dunk:          "💥",
  lead_change:   "⚡",
  scoring_run:   "🚀",
  clutch_score:  "🏆",
  made_two:      "🏀",
  freethrow:     "🎯",
  turnover:      "😬",
  block:         "🛑",
  steal:         "👀",
};

function renderEvents(events) {
  if (!events?.length) return;

  for (const event of events) {
    const play = event.play || {};
    const key  = event.id ?? play.id;
    if (key != null && rendered.has(key)) continue;
    if (key != null) rendered.add(key);

    const badge         = EVENT_BADGE[event.type] || "";
    const priorityClass = event.priority === "high" ? "play play--high" : "play";
    const score         = (play.score_away != null && play.score_home != null)
      ? `${play.score_away}–${play.score_home}` : "";
    const playerName    = play.player || play.playerName || "";

    const el = document.createElement("div");
    el.className = priorityClass;
    if (playerName) el.dataset.player = playerName;
    el.innerHTML = `
      <strong>${badge} ${play.clock || ""}</strong>
      <div>${play.description || ""}</div>
      <small>${play.team || ""} ${score}</small>`;

    if (activePlayer && playerName !== activePlayer) el.style.display = "none";

    feed.prepend(el);
    sendNotification(event);
  }
}

// ── Analysis panel ────────────────────────────────────────────────────────────

function pct(val) { return val != null ? `${val}%` : "—"; }

function renderStatRow(label, gameVal, recentVal) {
  return `<tr><td>${label}</td><td>${gameVal ?? 0}</td><td>${recentVal ?? 0}</td></tr>`;
}

function renderAnalysis(data) {
  if (!data?.available) { analysisPanel.style.display = "none"; return; }
  analysisPanel.style.display = "";

  document.getElementById("analysisSummary").textContent = data.summary || "";

  const homeProbVal = data.home.win_prob;
  const awayProbVal = data.away.win_prob;
  document.getElementById("probFillHome").style.width = `${homeProbVal}%`;
  document.getElementById("probFillAway").style.width = `${awayProbVal}%`;
  document.getElementById("probLabelHome").textContent = `${data.home.tricode} ${homeProbVal}%`;
  document.getElementById("probLabelAway").textContent = `${data.away.tricode} ${awayProbVal}%`;
  document.getElementById("homeLabel").textContent = data.home.tricode;
  document.getElementById("awayLabel").textContent = data.away.tricode;
  document.getElementById("homeProb").textContent  = `${homeProbVal}% chance`;
  document.getElementById("awayProb").textContent  = `${awayProbVal}% chance`;

  function buildStats(teamData) {
    const g = teamData.game, r = teamData.last_5_min;
    return [
      renderStatRow("Points",    g.points,            r.points),
      renderStatRow("FG%",       pct(g.fg_pct),       pct(r.fg_pct)),
      renderStatRow("3PT%",      pct(g.three_pt_pct), pct(r.three_pt_pct)),
      renderStatRow("FT%",       pct(g.ft_pct),       pct(r.ft_pct)),
      renderStatRow("Turnovers", g.turnovers,         r.turnovers),
    ].join("");
  }

  document.getElementById("homeStats").innerHTML = buildStats(data.home);
  document.getElementById("awayStats").innerHTML = buildStats(data.away);

  const periods = [...new Set([
    ...Object.keys(data.home.by_quarter),
    ...Object.keys(data.away.by_quarter),
  ])].map(Number).sort((a, b) => a - b);

  const qLabel = (p) => p <= 4 ? `Q${p}` : `OT${p - 4}`;
  const qRows  = periods.map(p => `
    <div class="q-col">
      <div class="q-header">${qLabel(p)}</div>
      <div class="q-score away">${data.away.by_quarter[p] ?? 0}</div>
      <div class="q-score home">${data.home.by_quarter[p] ?? 0}</div>
    </div>`).join("");

  document.getElementById("quarterScores").innerHTML = `
    <div class="q-grid">
      <div class="q-col q-label-col">
        <div class="q-header"></div>
        <div class="q-team">${data.away.tricode}</div>
        <div class="q-team">${data.home.tricode}</div>
      </div>
      ${qRows}
    </div>`;

  if (data.projected) {
    const p = data.projected;
    document.getElementById("projectedScore").innerHTML = `
      <span class="proj-label">Projected Final</span>
      <span class="proj-score">${data.away.tricode} <strong>${p.away}</strong> &ndash; ${data.home.tricode} <strong>${p.home}</strong></span>`;
  }

  if (data.best_player) {
    const bp = data.best_player;
    document.getElementById("bestPlayer").innerHTML = `
      <span class="proj-label">Game Leader</span>
      <span class="proj-score"><strong>${bp.name}</strong> &middot; ${bp.team} &middot; ${bp.points} pts${bp.clutch_points > 0 ? ` (${bp.clutch_points} clutch)` : ""}</span>`;
  }

  if (data.momentum?.length > 1) renderMomentumGraph(data.momentum, data.home.tricode, data.away.tricode);
}

// ── Momentum graph ────────────────────────────────────────────────────────────

function renderMomentumGraph(points, homeTricode, awayTricode) {
  const canvas = document.getElementById("momentumCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const diffs   = points.map(p => p.diff);
  const maxDiff = Math.max(10, ...diffs.map(Math.abs));
  const midY    = H / 2;
  const scaleY  = (midY - 16) / maxDiff;
  const scaleX  = (W - 32) / Math.max(1, points.length - 1);

  ctx.strokeStyle = "rgba(255,255,255,0.07)";
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, midY); ctx.lineTo(W, midY); ctx.stroke();

  const style   = getComputedStyle(document.documentElement);
  const accent  = style.getPropertyValue("--accent").trim()   || "#6ee7ff";
  const accent2 = style.getPropertyValue("--accent-2").trim() || "#8b5cf6";

  ctx.font = "11px Segoe UI, sans-serif";
  ctx.fillStyle = accent;  ctx.fillText(homeTricode, 4, 14);
  ctx.fillStyle = accent2; ctx.fillText(awayTricode, 4, H - 4);

  ctx.beginPath();
  points.forEach((p, i) => {
    const x = 16 + i * scaleX, y = midY - p.diff * scaleY;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(16 + (points.length - 1) * scaleX, midY);
  ctx.lineTo(16, midY);
  ctx.closePath();

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0,   accent  + "88");
  grad.addColorStop(0.5, "transparent");
  grad.addColorStop(1,   accent2 + "88");
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  ctx.strokeStyle = accent;
  ctx.lineWidth = 2;
  points.forEach((p, i) => {
    const x = 16 + i * scaleX, y = midY - p.diff * scaleY;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

// ── Box score ─────────────────────────────────────────────────────────────────

function renderBoxScore(data) {
  const panel   = document.getElementById("boxScorePanel");
  const content = document.getElementById("boxScoreContent");
  if (!panel || !content) return;
  if (!data?.available) { panel.style.display = "none"; return; }

  panel.style.display = "";
  buildPlayerChips(data.teams);

  const cols = ["PTS","FGM","FGA","FG%","3PM","3PA","3P%","FTM","FTA","FT%","REB","AST","STL","BLK","TO"];

  function teamTable(tricode, players) {
    const rows = players.map(p => `
      <tr>
        <td class="bs-name">${p.name}</td>
        <td class="bs-pts">${p.pts}</td>
        <td>${p.fgm}</td><td>${p.fga}</td><td>${p.fg_pct}</td>
        <td>${p.tpm}</td><td>${p.tpa}</td><td>${p.tp_pct}</td>
        <td>${p.ftm}</td><td>${p.fta}</td><td>${p.ft_pct}</td>
        <td>${p.reb}</td><td>${p.ast}</td><td>${p.stl}</td><td>${p.blk}</td><td>${p.to}</td>
      </tr>`).join("");

    return `
      <div class="bs-team-label">${tricode}</div>
      <div class="bs-wrap">
        <table class="bs-table">
          <thead>
            <tr>
              <th class="bs-name">Player</th>
              ${cols.map(c => `<th>${c}</th>`).join("")}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  content.innerHTML = Object.entries(data.teams)
    .map(([tricode, players]) => teamTable(tricode, players))
    .join("");
}

// ── Polling ───────────────────────────────────────────────────────────────────

async function pollFeed() {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/feed`);
    const data = await res.json();
    renderSummary(data.summary);
    const events = data.events || [];
    renderEvents(events);
    for (const event of events) {
      const key = event.id ?? event.play?.id;
      if (key == null || spoken.has(key)) continue;
      spoken.add(key);
      await speak(event.narration || event.play?.description || "Play recorded.");
    }
  } catch (e) { console.error("Feed polling failed:", e); }
}

async function pollAnalysis() {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/analysis`);
    const data = await res.json();
    renderAnalysis(data);
  } catch (e) { console.error("Analysis polling failed:", e); }
}

async function pollBoxScore() {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/boxscore`);
    const data = await res.json();
    renderBoxScore(data);
  } catch (e) { console.error("Box score polling failed:", e); }
}

async function pollSeries() {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/series`);
    const data = await res.json();
    renderSeries(data);
  } catch (e) { console.error("Series polling failed:", e); }
}

// ── Test voice button ─────────────────────────────────────────────────────────

if (testVoiceButton) {
  testVoiceButton.addEventListener("click", async () => {
    await fetch(`/api/game/${window.GAME_ID}/mock-play`, { method: "POST" });
    await pollFeed();
    await pollAnalysis();
    await pollBoxScore();
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

(async () => {
  try {
    const res  = await fetch(`/api/game/${window.GAME_ID}/feed`);
    const data = await res.json();
    for (const event of data.events || []) {
      const key = event.id ?? event.play?.id;
      if (key != null) { spoken.add(key); rendered.add(key); }
    }
  } catch (e) {}

  await Promise.all([pollFeed(), pollAnalysis(), pollBoxScore(), pollSeries()]);

  setInterval(pollFeed,     5000);
  setInterval(pollAnalysis, 15000);
  setInterval(pollBoxScore, 15000);
  setInterval(pollSeries,   30000);
})();