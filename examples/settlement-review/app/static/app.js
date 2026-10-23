let ME = null, SEL = null;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = (c, cur) => new Intl.NumberFormat("en-US", {style: "currency", currency: cur}).format(c / 100);

async function api(path, opts = {}) {
  const headers = {"Content-Type": "application/json"};
  if (ME && opts.method && opts.method !== "GET") headers["X-CSRF-Token"] = ME.csrf_token;
  const r = await fetch(path, {credentials: "same-origin", ...opts, headers});
  const body = await r.json().catch(() => ({}));
  if (r.status === 401 && path !== "/api/login") { showLogin(); }
  return {status: r.status, body};
}

function showLogin() { ME = null; $("login").classList.remove("hidden"); $("appView").classList.add("hidden"); $("who").innerHTML = ""; }

async function boot() {
  const r = await api("/api/me");
  if (r.status === 200) { ME = r.body; await showApp(); } else showLogin();
}

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await api("/api/login", {method: "POST", body: JSON.stringify({username: $("u").value, password: $("p").value})});
  if (r.status !== 200) { $("loginErr").textContent = r.body.detail || "Sign-in failed"; return; }
  $("loginErr").textContent = ""; $("p").value = ""; ME = r.body; await showApp();
});

async function showApp() {
  $("integrationProof").textContent = "Ready to request a risk result from the simulated vendor through this app’s backend.";
  $("login").classList.add("hidden"); $("appView").classList.remove("hidden");
  $("who").innerHTML = `${esc(ME.display_name)} · ${esc(ME.role_label)} · ${esc(ME.tenant_name)} <button id="logout">Sign out</button>`;
  $("logout").onclick = async () => { await api("/api/logout", {method: "POST"}); SEL = null; $("detail").classList.add("hidden"); showLogin(); };
  $("access").innerHTML = `<div class="kv"><div>Signed in as</div><div>${esc(ME.display_name)} (${esc(ME.username)})</div>
    <div>Role</div><div><b>${esc(ME.role_label)}</b></div><div>Tenant</div><div>${esc(ME.tenant_name)}</div></div>
    <h3>You can</h3><ul>${ME.permissions.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
    <h3>You cannot</h3><ul id="cannot">${ME.not_permitted.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
    <p class="tiny muted">${esc(ME.how_assigned)} Session expires after ${Math.round(ME.session_expires_in / 60)} minutes.</p>`;
  await Promise.all([loadQueue(), loadIntegration()]);
}

async function loadQueue() {
  const r = await api("/api/exceptions"); if (r.status !== 200) return;
  $("queueTitle").textContent = `Settlement exceptions — ${r.body.tenant_name}`;
  $("counts").innerHTML = Object.entries(r.body.counts).map(([k, v]) => `<span>${k[0].toUpperCase() + k.slice(1)}: <b>${v}</b></span>`).join("");
  $("rows").innerHTML = r.body.items.map((i) => `<tr class="row ${i.id === SEL ? "sel" : ""}" data-id="${esc(i.id)}"><td>${esc(i.id)}</td>
    <td>${esc(i.counterparty)}</td><td>${esc(i.exception_type)}</td><td>${money(i.amount_cents, i.currency)}</td>
    <td>${esc(i.account_number)}</td><td><span class="pill ${esc(i.status)}">${esc(i.status)}</span></td></tr>`).join("");
  document.querySelectorAll("tr.row").forEach((tr) => tr.onclick = () => openDetail(tr.dataset.id));
}

async function openDetail(id) {
  SEL = id; await loadQueue();
  const r = await api(`/api/exceptions/${encodeURIComponent(id)}`); if (r.status !== 200) return;
  const d = r.body; $("detail").classList.remove("hidden");
  $("kv").innerHTML = `<div>ID</div><div>${esc(d.id)}</div><div>Reference</div><div>${esc(d.reference)}</div>
    <div>Counterparty</div><div>${esc(d.counterparty)}</div><div>Amount</div><div>${money(d.amount_cents, d.currency)}</div>
    <div>Account</div><div>${esc(d.account_number)} ${d.account_redacted ? '<span class="tiny muted">(redacted by server for your role)</span>' : ""}</div>
    <div>Status</div><div><span class="pill ${esc(d.status)}">${esc(d.status)}</span></div>`;
  const k = d.risk;
  $("risk").innerHTML = k.status === "available"
    ? `<div>Score <b class="${esc(k.band)}">${k.score}/100 (${esc(k.band)} risk)</b> <span class="tiny muted">· ${esc(k.source)}, model ${esc(k.model)}</span></div><ul>${k.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`
    : `<div class="err"><b>Risk score unavailable.</b> ${esc(k.message)}</div><div class="tiny muted">${esc(k.detail)}</div>`;
  if (d.status !== "open") $("decision").innerHTML = `<p class="muted">Already ${esc(d.status)} — no further decision possible.</p>`;
  else if (!ME.can_decide) $("decision").innerHTML = `<p class="muted">View only. Your role (${esc(ME.role_label)}) cannot approve or reject; the server would refuse it (403).</p>`;
  else {
    $("decision").innerHTML = `<textarea id="reason" rows="2" placeholder="Reason (required, at least 5 characters)"></textarea><br><br>
      <button class="primary" id="approve">Approve</button> <button class="danger" id="reject">Reject</button>
      <span class="tiny muted">Records a decision only — no money moves.</span><div id="decErr" class="err"></div>`;
    $("approve").onclick = () => decide(d.id, "approve"); $("reject").onclick = () => decide(d.id, "reject");
  }
  await loadHistory(id);
  return d;
}

async function decide(id, action) {
  const r = await api(`/api/exceptions/${encodeURIComponent(id)}/decision`, {method: "POST", body: JSON.stringify({action, reason: $("reason").value})});
  if (r.status !== 200) { $("decErr").textContent = r.body.detail?.[0]?.msg || r.body.detail || "Failed"; return; }
  await openDetail(id);
}

async function loadHistory(id) {
  const r = await api(`/api/exceptions/${encodeURIComponent(id)}/history`); if (r.status !== 200) return;
  $("history").innerHTML = r.body.items.length ? `<ul>${r.body.items.map((h) => `<li><b>${esc(h.action === "approve" ? "Approved" : "Rejected")}</b> by ${esc(h.actor)} · ${esc(new Date(h.at).toLocaleString())}<br><span class="muted">“${esc(h.reason)}”</span></li>`).join("")}</ul>` : `<p class="muted">No decisions yet.</p>`;
}

async function loadIntegration() {
  const r = await api("/api/integration"); if (r.status !== 200) return;
  const g = r.body; $("connPill").className = `pill ${g.state}`; $("connPill").textContent = g.state === "connected" ? "Connected" : "Unavailable";
  $("integration").innerHTML = `<div class="kv"><div>Service</div><div>${esc(g.vendor)}</div><div>Endpoint</div><div>${esc(g.endpoint)} (fixed in server config)</div>
    <div>Auth</div><div>${esc(g.auth)}</div><div>Client secret</div><div>${g.credentials_configured ? "Configured on server [REDACTED]" : "Not configured"}</div>
    <div>Access token</div><div>${g.token_cached ? `Cached on server [REDACTED], ~${g.token_seconds_left}s left` : "None"}</div>
    ${g.last_error ? `<div>Last error</div><div class="err">${esc(g.last_error)}</div>` : ""}</div>
    <h3>How this integration works</h3><ol>${g.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
    <button id="recheck">Re-check connection</button>`;
  $("recheck").onclick = loadIntegration;
}
$("runIntegrationDemo").addEventListener("click", async () => {
  const button = $("runIntegrationDemo"), proof = $("integrationProof");
  const first = document.querySelector("tr.row");
  if (!first || !ME) { proof.textContent = "Sign in and load your queue first."; return; }
  button.disabled = true;
  proof.textContent = "Requesting a risk result through the backend…";
  try {
    const record = await openDetail(first.dataset.id);
    await loadIntegration();
    proof.textContent = record?.risk?.status === "available"
      ? `Live check passed for ${record.id}: the backend received a risk score of ${record.risk.score}/100 from the simulated vendor over HTTP. The vendor token stays on the server and may have been reused from cache. See the exception details below.`
      : "The check could not return a risk result. Check your sign-in and the vendor connection below; no success result has been substituted.";
  } catch {
    proof.textContent = "Connection check failed. Check that the app and simulated vendor are running, then try again.";
  } finally { button.disabled = false; }
});
boot();
