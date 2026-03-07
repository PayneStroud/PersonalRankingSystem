const DIMS = ["Appearance", "Personality", "Compatibility"];
const DEFAULT_WEIGHTS = { Appearance: 0.25, Personality: 0.25, Compatibility: 0.5 };

class RankingSystem {
  constructor() {
    this.nodes = {};
    this.rankings = { Appearance: [], Personality: [], Compatibility: [] };
    this.confidence = {};
    this.comparisons = new Set();
    this.weights = { ...DEFAULT_WEIGHTS };
  }

  newNode() { return { Appearance: 5, Personality: 5, Compatibility: 5, Overall: 5 }; }
  newConf() { return { Appearance: 0, Personality: 0, Compatibility: 0 }; }
  pair(a, b) { return [a, b].sort().join("||"); }

  ensure(name) {
    if (!this.confidence[name]) this.confidence[name] = this.newConf();
  }

  findGroupIndex(dim, name) {
    return this.rankings[dim].findIndex(g => g.includes(name));
  }

  recordComparison(a, b, dims = DIMS, markPair = true) {
    this.ensure(a); this.ensure(b);
    dims.forEach(d => { this.confidence[a][d]++; this.confidence[b][d]++; });
    if (markPair) this.comparisons.add(this.pair(a, b));
  }

  async addNode(name, askFn) {
    const clean = (name || "").trim();
    if (!clean || this.nodes[clean]) return false;
    this.nodes[clean] = this.newNode();
    this.confidence[clean] = this.newConf();

    for (const dim of DIMS) {
      if (!this.rankings[dim].length) this.rankings[dim] = [[clean]];
      else await this.insertNodeRanked(clean, dim, askFn);
    }
    this.rebalance();
    return true;
  }

  async insertNodeRanked(name, dim, askFn) {
    const ranking = this.rankings[dim];
    let low = 0, high = ranking.length;
    while (low < high) {
      const mid = Math.floor((low + high) / 2);
      const compareTo = ranking[mid][0];
      const r = await askFn(`For ${dim}, is ${name} better than ${compareTo}?`, [name, compareTo, "Equal / Skip"]);
      if (!r) return;
      if (r === name) {
        this.recordComparison(name, compareTo, [dim], false);
        high = mid;
      } else if (r === compareTo) {
        this.recordComparison(name, compareTo, [dim], false);
        low = mid + 1;
      } else {
        this.recordComparison(name, compareTo, [dim], false);
        ranking[mid].push(name);
        return;
      }
    }
    ranking.splice(low, 0, [name]);
  }

  moveWinnerAboveLoser(winner, loser, dims = DIMS, markPair = false) {
    if (!this.nodes[winner] || !this.nodes[loser] || winner === loser) return false;
    let changed = false;
    for (const dim of dims) {
      const ranking = this.rankings[dim];
      const wi = this.findGroupIndex(dim, winner);
      const li = this.findGroupIndex(dim, loser);
      if (wi < 0 || li < 0 || wi < li) continue;
      ranking[wi] = ranking[wi].filter(n => n !== winner);
      if (!ranking[wi].length) ranking.splice(wi, 1);
      const li2 = this.findGroupIndex(dim, loser);
      if (li2 < 0) continue;
      ranking.splice(li2, 0, [winner]);
      changed = true;
    }
    this.recordComparison(winner, loser, dims, markPair);
    if (changed) this.rebalance();
    return changed;
  }

  deleteNode(name) {
    if (!this.nodes[name]) return;
    delete this.nodes[name];
    delete this.confidence[name];
    for (const dim of DIMS) {
      this.rankings[dim] = this.rankings[dim].map(g => g.filter(n => n !== name)).filter(g => g.length);
    }
    this.comparisons = new Set([...this.comparisons].filter(p => !p.split("||").includes(name)));
    this.rebalance();
  }

  rebalance() {
    for (const dim of DIMS) {
      const ranking = this.rankings[dim];
      if (!ranking.length) continue;
      if (ranking.length === 1) {
        ranking[0].forEach(n => this.nodes[n][dim] = 5);
        continue;
      }
      ranking.forEach((group, idx) => {
        const rating = 10 - (idx / (ranking.length - 1)) * 10;
        group.forEach(n => this.nodes[n][dim] = rating);
      });
    }
    Object.keys(this.nodes).forEach(n => {
      this.nodes[n].Overall = DIMS.reduce((s, d) => s + this.nodes[n][d] * this.weights[d], 0);
    });
  }

  getConfidence(name, dim = null) {
    if (!this.nodes[name]) return 0;
    const max = Math.max(1, Object.keys(this.nodes).length - 1);
    if (dim) return Math.min(100, Math.floor((this.confidence[name][dim] / max) * 100));
    return Math.floor(DIMS.reduce((s, d) => s + this.getConfidence(name, d), 0) / DIMS.length);
  }

  sortedNodes(key = "Overall") {
    const arr = Object.entries(this.nodes);
    if (key === "Name") return arr.sort((a, b) => a[0].localeCompare(b[0]));
    if (key === "Confidence") return arr.sort((a, b) => this.getConfidence(b[0]) - this.getConfidence(a[0]));
    return arr.sort((a, b) => b[1][key] - a[1][key]);
  }

  suggestComparison() {
    const names = Object.keys(this.nodes);
    let best = null, bestScore = Infinity;
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const a = names[i], b = names[j];
        if (this.comparisons.has(this.pair(a, b))) continue;
        const diff = Math.abs(this.nodes[a].Overall - this.nodes[b].Overall);
        const un = (100 - this.getConfidence(a)) + (100 - this.getConfidence(b));
        const score = diff + un * 0.05;
        if (score < bestScore) { bestScore = score; best = [a, b]; }
      }
    }
    return best;
  }

  reviewPairs(limit = 12) {
    const names = Object.keys(this.nodes); const rows = [];
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const a = names[i], b = names[j];
        const diff = Math.abs(this.nodes[a].Overall - this.nodes[b].Overall);
        const cA = this.getConfidence(a), cB = this.getConfidence(b);
        const score = ((200 - (cA + cB)) / 2) * 0.7 + Math.max(0, 10 - diff) * 3;
        rows.push([score, a, b]);
      }
    }
    rows.sort((x, y) => y[0] - x[0]);
    return rows.slice(0, limit);
  }

  toJSON() {
    return {
      nodes: this.nodes,
      rankings: this.rankings,
      confidence: this.confidence,
      comparisons: [...this.comparisons],
      weights: this.weights,
    };
  }

  fromJSON(data) {
    this.nodes = data.nodes || {};
    this.rankings = data.rankings || { Appearance: [], Personality: [], Compatibility: [] };
    this.confidence = data.confidence || {};
    this.comparisons = new Set(data.comparisons || []);
    this.weights = data.weights || { ...DEFAULT_WEIGHTS };
    this.rebalance();
  }
}

const state = {
  sys: new RankingSystem(),
  undo: [],
  redo: [],
  maxUndo: 100,
};

const el = {
  list: document.getElementById("list"),
  status: document.getElementById("status"),
  search: document.getElementById("searchInput"),
  sort: document.getElementById("sortSelect"),
  conf: document.getElementById("confRange"),
  confValue: document.getElementById("confValue"),
  theme: document.getElementById("themeSelect"),
  choiceDialog: document.getElementById("choiceDialog"),
  choiceTitle: document.getElementById("choiceTitle"),
  choiceSubtitle: document.getElementById("choiceSubtitle"),
  choiceButtons: document.getElementById("choiceButtons"),
};

function setStatus(msg) { el.status.textContent = msg; }
function pushUndo(reason) {
  state.undo.push({ reason, snapshot: JSON.stringify(state.sys.toJSON()) });
  if (state.undo.length > state.maxUndo) state.undo.shift();
  state.redo = [];
}
function applySnapshot(snapshot) { state.sys.fromJSON(JSON.parse(snapshot)); saveLocal(); render(); }
function saveLocal() { localStorage.setItem("prs_state", JSON.stringify(state.sys.toJSON())); }
function loadLocal() {
  const raw = localStorage.getItem("prs_state");
  if (!raw) return;
  try { state.sys.fromJSON(JSON.parse(raw)); } catch {}
}

function colorFor(r) {
  if (r <= 5) return `rgb(255, ${Math.floor(130 + 125 * (r / 5))}, 0)`;
  const ratio = (r - 5) / 5;
  return `rgb(${Math.floor(255 * (1 - ratio) * 0.7)}, ${Math.floor(255 * (1 - 0.2 * ratio))}, 0)`;
}

function render() {
  el.list.innerHTML = "";
  const search = el.search.value.trim().toLowerCase();
  const minConf = Number(el.conf.value);
  const sort = el.sort.value;

  const rows = state.sys.sortedNodes(sort);
  let shown = 0;
  rows.forEach(([name, data]) => {
    if (search && !name.toLowerCase().includes(search)) return;
    const conf = state.sys.getConfidence(name);
    if (conf < minConf) return;
    shown++;

    const card = document.createElement("article");
    card.className = "card item";
    card.innerHTML = `
      <div class="item-head">
        <div class="name">${name}</div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="pill" style="background:${colorFor(data.Overall)}">${data.Overall.toFixed(1)}</span>
          <button data-del="${name}">Remove</button>
        </div>
      </div>
    `;

    DIMS.forEach(dim => {
      const c = state.sys.getConfidence(name, dim);
      const row = document.createElement("div");
      row.className = "row";
      row.innerHTML = `
        <div>${dim}</div>
        <div class="bar"><div class="fill" style="width:${Math.max(0, Math.min(100, data[dim] * 10))}%;background:${colorFor(data[dim])}"></div></div>
        <div class="sub">${data[dim].toFixed(1)} (${c}%)</div>
      `;
      card.appendChild(row);
    });

    const sub = document.createElement("div");
    sub.className = "sub";
    sub.textContent = `Overall confidence: ${conf}%`;
    card.appendChild(sub);

    card.querySelector("[data-del]").addEventListener("click", async () => {
      const choice = await askChoice("Delete person?", name, ["Delete", "Cancel"]);
      if (choice !== "Delete") return;
      pushUndo("delete");
      state.sys.deleteNode(name);
      saveLocal(); render();
    });

    el.list.appendChild(card);
  });

  setStatus(`Showing ${shown} people. Auto-saved locally.`);
}

function askChoice(title, subtitle = "", options = []) {
  return new Promise(resolve => {
    el.choiceTitle.textContent = title;
    el.choiceSubtitle.textContent = subtitle;
    el.choiceButtons.innerHTML = "";

    options.forEach(opt => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = opt;
      b.addEventListener("click", () => {
        el.choiceDialog.close();
        resolve(opt);
      });
      el.choiceButtons.appendChild(b);
    });

    el.choiceDialog.onclose = () => resolve(null);
    el.choiceDialog.showModal();
  });
}

async function comparePairByDim(a, b, prefix) {
  const decisions = {};
  for (const dim of DIMS) {
    const c = await askChoice(`${prefix}: ${dim}`, `${a} vs ${b}`, [a, b, "Equal / Skip"]);
    if (!c) return null;
    decisions[dim] = c;
  }
  return decisions;
}

function applyDecisions(a, b, decisions) {
  for (const dim of DIMS) {
    const c = decisions[dim];
    if (c === a) state.sys.moveWinnerAboveLoser(a, b, [dim], false);
    else if (c === b) state.sys.moveWinnerAboveLoser(b, a, [dim], false);
    else state.sys.recordComparison(a, b, [dim], false);
  }
  state.sys.comparisons.add(state.sys.pair(a, b));
}

function exportJson() {
  const blob = new Blob([JSON.stringify(state.sys.toJSON(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "personal-ranking.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportCsv() {
  const header = ["Name", ...DIMS, "Overall", "ConfOverall", "ConfAppearance", "ConfPersonality", "ConfCompatibility"];
  const rows = [header.join(",")];
  state.sys.sortedNodes("Overall").forEach(([name, d]) => {
    rows.push([
      JSON.stringify(name), d.Appearance.toFixed(2), d.Personality.toFixed(2), d.Compatibility.toFixed(2), d.Overall.toFixed(2),
      state.sys.getConfidence(name), state.sys.getConfidence(name, "Appearance"), state.sys.getConfidence(name, "Personality"), state.sys.getConfidence(name, "Compatibility")
    ].join(","));
  });
  const blob = new Blob([rows.join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "personal-ranking.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const header = lines[0].split(",").map(x => x.replace(/^"|"$/g, ""));
  const rows = [];
  for (const line of lines.slice(1)) {
    const parts = line.match(/("[^"]*"|[^,]+)/g) || [];
    const obj = {};
    header.forEach((h, i) => obj[h] = (parts[i] || "").replace(/^"|"$/g, ""));
    rows.push(obj);
  }
  return rows;
}

function importCsvRows(rows) {
  state.sys = new RankingSystem();
  rows.forEach(r => {
    const name = (r.Name || "").trim();
    if (!name) return;
    state.sys.nodes[name] = {
      Appearance: Number(r.Appearance || 5),
      Personality: Number(r.Personality || 5),
      Compatibility: Number(r.Compatibility || 5),
      Overall: Number(r.Overall || 5),
    };
    state.sys.confidence[name] = {
      Appearance: Number(r.ConfAppearance || 0),
      Personality: Number(r.ConfPersonality || 0),
      Compatibility: Number(r.ConfCompatibility || 0),
    };
  });
  DIMS.forEach(dim => {
    const names = Object.keys(state.sys.nodes).sort((a, b) => state.sys.nodes[b][dim] - state.sys.nodes[a][dim]);
    const groups = [];
    let last = null;
    names.forEach(n => {
      const val = state.sys.nodes[n][dim];
      if (last === null || Math.abs(last - val) > 1e-9) { groups.push([n]); last = val; }
      else groups[groups.length - 1].push(n);
    });
    state.sys.rankings[dim] = groups;
  });
  state.sys.rebalance();
}

document.getElementById("addBtn").addEventListener("click", async () => {
  const name = prompt("Enter person name:");
  if (!name) return;
  pushUndo("add");
  await state.sys.addNode(name, askChoice);
  saveLocal(); render();
});

document.getElementById("manualBtn").addEventListener("click", async () => {
  const better = prompt("Who is better?");
  const worse = prompt("Who is worse?");
  if (!better || !worse) return;
  const b = Object.keys(state.sys.nodes).find(n => n.toLowerCase() === better.trim().toLowerCase());
  const w = Object.keys(state.sys.nodes).find(n => n.toLowerCase() === worse.trim().toLowerCase());
  if (!b || !w || b === w) return alert("Invalid names");
  const dim = await askChoice("Compare which dimension?", `${b} vs ${w}`, ["All", ...DIMS]);
  if (!dim) return;
  pushUndo("manual");
  state.sys.moveWinnerAboveLoser(b, w, dim === "All" ? DIMS : [dim], dim === "All");
  saveLocal(); render();
});

document.getElementById("suggestBtn").addEventListener("click", async () => {
  const pair = state.sys.suggestComparison();
  if (!pair) return alert("No useful un-compared pairs left.");
  const [a, b] = pair;
  const decisions = await comparePairByDim(a, b, "Who is better");
  if (!decisions) return;
  pushUndo("suggest");
  applyDecisions(a, b, decisions);
  saveLocal(); render();
});

document.getElementById("reviewBtn").addEventListener("click", async () => {
  const top = state.sys.reviewPairs(1)[0];
  if (!top) return alert("Not enough people for review queue.");
  const a = top[1], b = top[2];
  const decisions = await comparePairByDim(a, b, "Review pair");
  if (!decisions) return;
  pushUndo("review");
  applyDecisions(a, b, decisions);
  saveLocal(); render();
});

document.getElementById("undoBtn").addEventListener("click", () => {
  const item = state.undo.pop();
  if (!item) return;
  state.redo.push(JSON.stringify(state.sys.toJSON()));
  applySnapshot(item.snapshot);
});

document.getElementById("redoBtn").addEventListener("click", () => {
  const item = state.redo.pop();
  if (!item) return;
  state.undo.push({ reason: "redo", snapshot: JSON.stringify(state.sys.toJSON()) });
  applySnapshot(item);
});

document.getElementById("saveBtn").addEventListener("click", exportJson);
document.getElementById("exportCsvBtn").addEventListener("click", exportCsv);

document.getElementById("loadInput").addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  const text = await f.text();
  pushUndo("load json");
  state.sys.fromJSON(JSON.parse(text));
  saveLocal(); render();
});

document.getElementById("importCsvInput").addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  const text = await f.text();
  pushUndo("import csv");
  importCsvRows(parseCsv(text));
  saveLocal(); render();
});

el.search.addEventListener("input", render);
el.sort.addEventListener("change", render);
el.conf.addEventListener("input", () => {
  el.confValue.textContent = `${el.conf.value}%`;
  render();
});
el.theme.addEventListener("change", () => {
  document.documentElement.style.colorScheme = el.theme.value === "system" ? "" : el.theme.value;
});

loadLocal();
render();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}
