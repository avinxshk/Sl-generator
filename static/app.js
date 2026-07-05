/* SL Generator SPA — hash-routed, no build step. */
const $ = (sel, el = document) => el.querySelector(sel);
const main = $("#main");
let META = { intents: [], tones: [], demo_mode: true };
const genCache = {}; // campaign_id -> last generation response (retrieval context etc.)

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

function toast(msg, ms = 4200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), ms);
}

/* ------------------------------------------------------------- routing */
const routes = {
  new: viewNew, campaigns: viewCampaigns, history: viewHistory,
  segments: viewSegments, brand: viewBrand, review: viewReview, campaign: viewCampaignDetail,
};

function navigate() {
  const [view, arg] = location.hash.replace("#", "").split("/");
  document.querySelectorAll(".sidebar a").forEach((a) =>
    a.classList.toggle("active", a.dataset.view === (view || "new")));
  (routes[view] || viewNew)(arg);
}
window.addEventListener("hashchange", navigate);

/* --------------------------------------------------------- view: new */
async function viewNew() {
  const segs = await api("/api/segments");
  main.innerHTML = `
    <h2>New Campaign</h2>
    <div class="card">
      <label>Name</label><input type="text" id="c-name" placeholder="Summer flash sale">
      <label>Intent</label>
      <select id="c-intent">${META.intents.map((i) => `<option>${esc(i)}</option>`).join("")}</select>
      <label>Segments</label>
      <div class="seg-checks">${segs.map((s) => `
        <label><input type="checkbox" value="${s.id}"><span>${esc(s.name)} · ${s.size.toLocaleString()}</span></label>`).join("")}
      </div>
      <label>Email body</label>
      <textarea id="c-body" placeholder="Paste the email content the subject line must pay off…"></textarea>
      <div style="margin-top:16px"><button class="primary" id="c-go">Generate subject lines ▸</button></div>
      <div class="error hidden" id="c-err"></div>
    </div>`;
  $("#c-go").onclick = async () => {
    const name = $("#c-name").value.trim();
    const body = $("#c-body").value.trim();
    const segment_ids = [...main.querySelectorAll(".seg-checks input:checked")].map((c) => +c.value);
    const err = $("#c-err");
    err.classList.add("hidden");
    if (!name || !body || !segment_ids.length) {
      err.textContent = "Name, body, and at least one segment are required.";
      err.classList.remove("hidden");
      return;
    }
    const btn = $("#c-go");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>Generating…`;
    try {
      const { id } = await api("/api/campaigns", { method: "POST",
        body: { name, intent: $("#c-intent").value, body, segment_ids } });
      genCache[id] = await api(`/api/campaigns/${id}/generate`, { method: "POST" });
      location.hash = `#review/${id}`;
    } catch (e) {
      err.textContent = `Generation failed: ${e.message}`;
      err.classList.remove("hidden");
      btn.disabled = false;
      btn.textContent = "Generate subject lines ▸";
    }
  };
}

/* ------------------------------------------------------ view: review */
function badgeHtml(b) { return `<span class="badge" title="${esc(b.code)}">⚠ ${esc(b.message)}</span>`; }

function breakdownHtml(bd) {
  return Object.entries(bd).map(([k, v]) =>
    `${esc(k.replaceAll("_", " "))}: <strong>${v.points}</strong>/${v.max}`).join(" · ");
}

function candidateHtml(c, i) {
  const badges = (c.badges || []).map(badgeHtml).join(" ");
  const statusTag = c.status !== "proposed"
    ? `<span class="status-tag ${c.status}">${c.status.toUpperCase()}</span>` : "";
  return `
  <div class="candidate ${c.status === "accepted" || c.status === "edited" ? "accepted" : ""} ${c.status === "rejected" ? "rejected" : ""}" data-id="${c.id}">
    <div class="cand-top">
      <span class="rank">#${i + 1}</span>
      <button class="score-btn" data-act="score">score ${c.score} ▾</button>
      <span class="cand-text">${esc(c.display_text)}</span>
      <span class="tone">${esc(c.tone)}</span>
      ${badges} ${statusTag}
    </div>
    <div class="breakdown hidden">${breakdownHtml(c.score_breakdown)}</div>
    <div class="rationale">${esc(c.rationale)}</div>
    <div class="actions">
      <button class="primary small" data-act="accept">Accept</button>
      <button class="ghost small" data-act="edit">Edit</button>
      <button class="ghost small" data-act="reject">Reject</button>
    </div>
    <div class="edit-row hidden">
      <input type="text" value="${esc(c.display_text)}">
      <span class="charcount"></span>
      <button class="primary small" data-act="save-edit">Save</button>
    </div>
  </div>`;
}

function comparablesHtml(retr) {
  const row = (p) => `<tr><td>“${esc(p.subject_line)}”</td><td>${esc(p.tone)}</td>
    <td>${p.open_rate}%</td><td class="muted">${esc(p.match_reason)}</td></tr>`;
  return `
  <details class="comparables">
    <summary>Grounded on ${retr.positives.length} similar campaigns — view comparables</summary>
    <table><thead><tr><th>Subject line</th><th>Tone</th><th>Open rate</th><th>Match</th></tr></thead>
    <tbody>${retr.positives.map(row).join("")}${retr.negatives.map((n) =>
      row(n).replace("<tr>", '<tr style="opacity:.55" title="negative example">')).join("")}</tbody></table>
  </details>`;
}

async function viewReview(campaignId) {
  const gen = genCache[campaignId];
  if (!gen) { location.hash = `#campaign/${campaignId}`; return; }
  const camp = await api(`/api/campaigns/${campaignId}`);
  main.innerHTML = `
    <h2>${esc(camp.name)} <span class="muted">· ${esc(camp.intent)}</span></h2>
    <div class="tabs">${gen.segments.map((s, i) =>
      `<button data-tab="${i}" class="${i === 0 ? "active" : ""}">${esc(s.segment.name)}</button>`).join("")}</div>
    <div id="seg-panels"></div>
    <div style="margin-top:18px">
      <button class="primary" onclick="location.hash='#campaign/${campaignId}'">Finalize selection ▸</button>
    </div>`;
  const renderPanel = (i) => {
    const s = gen.segments[i];
    const seg = s.segment;
    $("#seg-panels").innerHTML = `
      <div class="card">
        <div class="muted">Audience: ${esc(seg.description)} · avg opens 90d: ${seg.avg_opens_90d} ·
          days since open: ${seg.avg_days_since_open} ·
          top products: ${seg.top_products.map((p) => `${esc(p.product)} (${Math.round(p.share * 100)}%)`).join(", ")}</div>
        ${s.no_history ? `<div class="notice">No similar past campaigns — ranking uses length + brand fit only.</div>` : comparablesHtml(s.retrieval)}
        ${s.removed_by_guardrails ? `<div class="notice">${s.removed_by_guardrails} candidate(s) removed by brand guardrails.</div>` : ""}
        <div id="cands">${s.candidates.map(candidateHtml).join("")}</div>
        <div class="muted" id="ab-note">Accepted (max 2 = A/B): ${abSummary(s.candidates)}</div>
      </div>`;
    wireCandidates(s);
  };
  const abSummary = (cands) => {
    const acc = cands.filter((c) => c.status === "accepted" || c.status === "edited");
    return acc.length ? acc.map((c, j) => `<strong>${"AB"[j] || "?"}:</strong> “${esc(c.display_text)}”`).join("  ") : "none yet";
  };
  function wireCandidates(s) {
    main.querySelectorAll(".candidate").forEach((el) => {
      const cand = s.candidates.find((c) => c.id === +el.dataset.id);
      el.querySelector('[data-act="score"]').onclick = () =>
        el.querySelector(".breakdown").classList.toggle("hidden");
      el.querySelector('[data-act="edit"]').onclick = () => {
        el.querySelector(".edit-row").classList.toggle("hidden");
        updateCount(el);
      };
      const input = el.querySelector(".edit-row input");
      const updateCount = () => {
        const n = input.value.length;
        el.querySelector(".charcount").textContent =
          `${n} chars${n > 55 ? " ⚠ may truncate" : ""}`;
      };
      input.oninput = updateCount;
      const setStatus = async (status, edited_text) => {
        try {
          const updated = await api(`/api/candidates/${cand.id}/status`,
            { method: "POST", body: { status, edited_text } });
          Object.assign(cand, updated);
          if (updated.edited_badges?.length)
            toast("Note: " + updated.edited_badges.map((b) => b.message).join("; "));
          renderPanel(gen.segments.indexOf(s));
        } catch (e) { toast(e.message); }
      };
      el.querySelector('[data-act="accept"]').onclick = () => setStatus("accepted");
      el.querySelector('[data-act="reject"]').onclick = () => setStatus("rejected");
      el.querySelector('[data-act="save-edit"]').onclick = () => setStatus("edited", input.value.trim());
    });
  }
  main.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => {
    main.querySelectorAll(".tabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    renderPanel(+b.dataset.tab);
  }));
  renderPanel(0);
}

/* --------------------------------------------------- view: campaigns */
async function viewCampaigns() {
  const camps = await api("/api/campaigns");
  main.innerHTML = `<h2>Campaigns</h2>` + (camps.length ? `
    <table><thead><tr><th>Name</th><th>Intent</th><th>Status</th><th>Created</th><th></th></tr></thead>
    <tbody>${camps.map((c) => `<tr>
      <td>${esc(c.name)}</td><td>${esc(c.intent)}</td><td>${esc(c.status)}</td>
      <td class="muted">${esc(c.created_at)}</td>
      <td><a href="#campaign/${c.id}">open</a></td></tr>`).join("")}</tbody></table>`
    : `<div class="empty">No campaigns yet — <a href="#new">create one</a>.</div>`);
}

async function viewCampaignDetail(id) {
  const camp = await api(`/api/campaigns/${id}`);
  main.innerHTML = `
    <h2>${esc(camp.name)} <span class="muted">· ${esc(camp.intent)}</span></h2>
    ${genCache[id] ? `<p style="margin-bottom:12px"><a href="#review/${id}">← back to candidate review</a></p>` : ""}
    ${camp.segments.map((s) => segmentOutcomeCard(camp, s)).join("") ||
      `<div class="empty">No candidates generated yet.</div>`}`;
  camp.segments.forEach((s) => {
    const form = $(`#outcome-${s.segment.id}`);
    const saveBtn = $(`#save-${s.segment.id}`);
    if (!form || !saveBtn) return; // no accepted candidates, or all outcomes already logged
    saveBtn.onclick = async () => {
      const results = [...form.querySelectorAll("[data-cand]")].map((inp) => ({
        candidate_id: +inp.dataset.cand,
        open_rate: parseFloat(inp.value),
        variant: inp.dataset.variant,
      })).filter((r) => !Number.isNaN(r.open_rate));
      if (!results.length) { toast("Enter at least one open rate."); return; }
      try {
        await api(`/api/campaigns/${id}/outcome`, { method: "POST",
          body: { segment_id: s.segment.id, sent_at: $(`#sent-${s.segment.id}`).value || null, results } });
        toast(`Added to history. Future ${camp.intent} generations will see this.`);
        viewCampaignDetail(id);
      } catch (e) { toast(e.message); }
    };
  });
}

function segmentOutcomeCard(camp, s) {
  const chosen = s.candidates.filter((c) => c.status === "accepted" || c.status === "edited");
  const logged = new Set(s.outcomes.map((o) => o.candidate_id));
  return `
  <div class="card">
    <h3>${esc(s.segment.name)} <span class="muted">· ${s.segment.size.toLocaleString()} recipients</span></h3>
    ${chosen.length === 0 ? `<div class="muted">No accepted candidates for this segment.</div>` : `
      <div id="outcome-${s.segment.id}">
      ${chosen.map((c, j) => `
        <div style="display:flex;gap:10px;align-items:center;margin:8px 0">
          <strong>${"AB"[j] || "•"}:</strong> <span>“${esc(c.display_text)}”</span>
          ${logged.has(c.id)
            ? `<span class="status-tag accepted">open rate ${s.outcomes.find((o) => o.candidate_id === c.id).open_rate}% ✓</span>`
            : `<input type="number" step="0.1" min="0" max="100" placeholder="open %" style="width:110px"
                 data-cand="${c.id}" data-variant="${"AB"[j] || ""}">`}
        </div>`).join("")}
      ${chosen.every((c) => logged.has(c.id)) ? "" : `
        <div style="display:flex;gap:10px;align-items:center;margin-top:10px">
          <input type="date" id="sent-${s.segment.id}" style="width:170px">
          <button class="primary small" id="save-${s.segment.id}">Save outcome</button>
        </div>`}
      </div>`}
  </div>`;
}

/* ----------------------------------------------------- view: history */
async function viewHistory() {
  const opts = (list) => `<option value="">all</option>` +
    list.map((x) => `<option>${esc(x)}</option>`).join("");
  main.innerHTML = `
    <h2>History</h2>
    <div class="filters">
      <select id="f-intent">${opts(META.intents)}</select>
      <select id="f-tone">${opts(META.tones)}</select>
    </div>
    <div id="h-table"></div>`;
  const load = async () => {
    const q = new URLSearchParams();
    if ($("#f-intent").value) q.set("intent", $("#f-intent").value);
    if ($("#f-tone").value) q.set("tone", $("#f-tone").value);
    const rows = await api(`/api/history?${q}`);
    $("#h-table").innerHTML = rows.length ? `
      <table><thead><tr><th>Subject line</th><th>Intent</th><th>Tone</th>
        <th>Audience</th><th>Open rate</th><th>Sent</th><th>Source</th></tr></thead>
      <tbody>${rows.map((r) => `<tr>
        <td>“${esc(r.subject_line)}”</td><td>${esc(r.intent)}</td><td>${esc(r.tone)}</td>
        <td>${r.audience_size.toLocaleString()}</td><td><strong>${r.open_rate}%</strong></td>
        <td class="muted">${esc(r.sent_at || "")}</td>
        <td><span class="pill ${esc(r.source)}">${esc(r.source)}</span></td></tr>`).join("")}</tbody></table>`
      : `<div class="empty">No matching history.</div>`;
  };
  $("#f-intent").onchange = load;
  $("#f-tone").onchange = load;
  load();
}

/* ---------------------------------------------------- view: segments */
async function viewSegments() {
  const segs = await api("/api/segments");
  main.innerHTML = `<h2>Segments</h2><div class="grid">${segs.map((s) => `
    <div class="card">
      <h3 style="margin-top:0">${esc(s.name)}</h3>
      <div class="muted">${esc(s.description)}</div>
      <div class="taglist">${s.traits.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <table><tbody>
        <tr><td>Size</td><td><strong>${s.size.toLocaleString()}</strong></td></tr>
        <tr><td>Avg opens (90d)</td><td>${s.avg_opens_90d}</td></tr>
        <tr><td>Avg clicks (90d)</td><td>${s.avg_clicks_90d}</td></tr>
        <tr><td>Days since open</td><td>${s.avg_days_since_open}</td></tr>
        <tr><td>Top products</td><td>${s.top_products.map((p) =>
          `${esc(p.product)} (${Math.round(p.share * 100)}%)`).join("<br>")}</td></tr>
      </tbody></table>
    </div>`).join("")}</div>`;
}

/* ------------------------------------------------------- view: brand */
async function viewBrand() {
  const brand = await api("/api/brand");
  const tagList = (items, id) => `
    <div class="taglist" id="${id}">${items.map((t, i) =>
      `<span class="tag" data-i="${i}">${esc(t)}<button title="remove">✕</button></span>`).join("")}</div>
    <div style="display:flex;gap:8px"><input type="text" id="${id}-new" placeholder="add and press Enter"></div>`;
  main.innerHTML = `
    <h2>Brand Voice</h2>
    <div class="notice">Changes affect all future generations.</div>
    <div class="card">
      <label>Voice guidelines</label>
      <textarea id="b-guidelines">${esc(brand.guidelines)}</textarea>
      <label>Banned words / claims</label>
      ${tagList(brand.banned_terms, "b-banned")}
      <label>Exemplar subject lines</label>
      ${tagList(brand.exemplars, "b-exemplars")}
      <div style="margin-top:16px"><button class="primary" id="b-save">Save</button></div>
    </div>`;
  const state = { banned: [...brand.banned_terms], exemplars: [...brand.exemplars] };
  const wire = (id, arr) => {
    $(`#${id}`).onclick = (e) => {
      if (e.target.tagName !== "BUTTON") return;
      arr.splice(+e.target.parentElement.dataset.i, 1);
      viewBrandRefresh(id, arr);
    };
    $(`#${id}-new`).onkeydown = (e) => {
      if (e.key === "Enter" && e.target.value.trim()) {
        arr.push(e.target.value.trim());
        e.target.value = "";
        viewBrandRefresh(id, arr);
      }
    };
  };
  const viewBrandRefresh = (id, arr) => {
    $(`#${id}`).innerHTML = arr.map((t, i) =>
      `<span class="tag" data-i="${i}">${esc(t)}<button title="remove">✕</button></span>`).join("");
  };
  wire("b-banned", state.banned);
  wire("b-exemplars", state.exemplars);
  $("#b-save").onclick = async () => {
    await api("/api/brand", { method: "PUT", body: {
      guidelines: $("#b-guidelines").value,
      banned_terms: state.banned,
      exemplars: state.exemplars,
    } });
    toast("Brand voice saved — applies to the next generation.");
  };
}

/* --------------------------------------------------------------- boot */
(async function boot() {
  META = await api("/api/meta");
  $("#demo-banner").classList.toggle("hidden", !META.demo_mode);
  navigate();
})();
