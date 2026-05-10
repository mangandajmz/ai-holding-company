const state = {
  snapshot: null,
  currentView: "today",
  selectedPersona: "chief-of-staff",
  personaMessages: [],
};

const titles = {
  today: "Today",
  approvals: "Approvals",
  memory: "Memory",
  personas: "Personas",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pill(status) {
  const clean = escapeHtml(status || "UNKNOWN");
  return `<span class="pill ${clean}">${clean}</span>`;
}

function renderToday(view) {
  const items = view.items || [];
  return `
    <article class="card">
      <h2>Company Opening</h2>
      <p>${pill(view.status)} The first screen is a deterministic digest from local artifacts.</p>
    </article>
    ${items.map((item) => `
      <article class="card">
        <div class="row">
          <div>
            <h3>${escapeHtml(item.skill)}</h3>
            <p>${escapeHtml(item.brief)}</p>
            <p class="muted"><code>${escapeHtml(item.source)}</code></p>
          </div>
          ${pill(item.status)}
        </div>
      </article>
    `).join("")}
  `;
}

function renderApprovals(view) {
  const pending = view.pending || [];
  if (!pending.length) {
    return `<article class="card"><h2>No Pending Approvals</h2><p class="muted">No approval items were found in local state.</p></article>`;
  }
  return `
    <article class="card"><h2>${pending.length} Pending Approval${pending.length === 1 ? "" : "s"}</h2></article>
    ${pending.map((item) => `
      <article class="card">
        <h3>${escapeHtml(item.topic)}</h3>
        <p>${escapeHtml(item.decision)}</p>
        <p class="muted"><code>${escapeHtml(item.approval_id)}</code></p>
        ${pill(item.priority)}
      </article>
    `).join("")}
  `;
}

function renderMemory(view) {
  const samples = view.samples || [];
  if (!samples.length) {
    return `<article class="card"><h2>No Memory Samples</h2><p class="muted">No local memory rows were available for this snapshot.</p></article>`;
  }
  return samples.map((item) => `
    <article class="card">
      <p>${escapeHtml(item.text)}</p>
      <p class="muted">${escapeHtml(JSON.stringify(item.metadata || {}))}</p>
    </article>
  `).join("");
}

function renderPersonas(view) {
  const personas = view.personas || [];
  const selected = personas.find((persona) => persona.slug === state.selectedPersona) || personas[0] || {};
  const transcript = state.personaMessages.length
    ? state.personaMessages.map((item) => `
      <div class="message ${escapeHtml(item.role)}">
        <p>${escapeHtml(item.text)}</p>
        ${item.evidence?.length ? `
          <details class="evidence-details">
            <summary>Evidence (${item.evidence.length})</summary>
            <div class="evidence-list">
            ${item.evidence.map((evidence) => `
              <div class="evidence-item">
                <strong>${escapeHtml(evidence.status)} ${escapeHtml(evidence.skill)}</strong>
                <span>${escapeHtml(evidence.brief)}</span>
                <code>${escapeHtml(evidence.source)}</code>
              </div>
            `).join("")}
            </div>
          </details>
        ` : ""}
        ${item.shadow ? `
          <p class="shadow-status">
            Shadow: ${escapeHtml(item.shadow.enabled === false ? "disabled" : item.shadow.accepted ? "accepted" : item.shadow.reason || "pending")}
          </p>
          ${item.shadow.answer ? `<p class="shadow-answer">${escapeHtml(item.shadow.answer)}</p>` : ""}
        ` : ""}
        ${item.sources?.length ? `<details class="source-details"><summary>Source paths</summary><p>${item.sources.map(escapeHtml).join(", ")}</p></details>` : ""}
      </div>
    `).join("")
    : `<p class="muted">Ask any natural question. The reply is grounded against local org truth, not chat memory.</p>`;
  return `
    <section class="persona-layout">
      <aside class="persona-list" aria-label="Employees">
        ${personas.map((persona) => `
          <button class="persona-button ${persona.slug === state.selectedPersona ? "is-active" : ""}" data-persona="${escapeHtml(persona.slug)}" type="button">
            <span>${escapeHtml(persona.name)}</span>
            ${pill(persona.status)}
          </button>
        `).join("")}
      </aside>
      <article class="card chat-panel">
        <div class="chat-header">
          <div>
            <h2>${escapeHtml(selected.name || "Persona")}</h2>
            <p class="muted"><code>${escapeHtml(selected.contract || "")}</code></p>
          </div>
          <div class="chat-actions">
            <span class="truth-badge">Truth-first</span>
            <button id="shadow-write" class="secondary-button" type="button">Run Shadow</button>
          </div>
        </div>
        <div id="persona-transcript" class="transcript">${transcript}</div>
        <form id="persona-chat-form" class="chat-form">
          <textarea id="persona-message" name="message" rows="3" placeholder="Talk naturally. The employee will answer from stored truth." required></textarea>
          <button type="submit">Send</button>
        </form>
      </article>
    </section>
  `;
}

function render() {
  const root = document.querySelector("#view-root");
  const title = document.querySelector("#view-title");
  title.textContent = titles[state.currentView] || "Operating Room";
  if (!state.snapshot) {
    root.innerHTML = `<article class="card"><h2>Snapshot Missing</h2><p>Run <code>python scripts/operating_room_snapshot.py</code>.</p></article>`;
    return;
  }
  const view = state.snapshot.views[state.currentView] || {};
  if (state.currentView === "today") root.innerHTML = renderToday(view);
  if (state.currentView === "approvals") root.innerHTML = renderApprovals(view);
  if (state.currentView === "memory") root.innerHTML = renderMemory(view);
  if (state.currentView === "personas") root.innerHTML = renderPersonas(view);
  bindPersonaControls();
}

function bindPersonaControls() {
  document.querySelectorAll(".persona-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedPersona = button.dataset.persona;
      state.personaMessages = [];
      render();
    });
  });
  const form = document.querySelector("#persona-chat-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector("#persona-message");
    const message = input.value.trim();
    if (!message) return;
    state.personaMessages.push({ role: "owner", text: message, sources: [], evidence: [] });
    input.value = "";
    render();
    try {
      const response = await fetch("/api/persona-chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ persona: state.selectedPersona, message }),
      });
      const payload = await response.json();
      state.personaMessages.push({
        role: "persona",
        text: payload.answer || payload.error || "No answer returned.",
        sources: payload.sources || [],
        evidence: payload.evidence || [],
        shadow: payload.shadow_verbalizer || null,
      });
    } catch (_error) {
      state.personaMessages.push({
        role: "persona",
        text: "Start the local server with python scripts/operating_room_server.py to chat here.",
        sources: [],
        evidence: [],
        shadow: null,
      });
    }
    render();
  });
  const shadowButton = document.querySelector("#shadow-write");
  if (shadowButton) {
    shadowButton.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/nanoclaw-shadow-write", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: "{}",
        });
        const payload = await response.json();
        state.personaMessages.push({
          role: "persona",
          text: payload.ok
            ? "Shadow candidate written. Ask the same question again to compare it."
            : `Shadow writer did not run: ${payload.error || "unknown reason"}.`,
          sources: [],
          evidence: [],
          shadow: null,
        });
      } catch (_error) {
        state.personaMessages.push({
          role: "persona",
          text: "Shadow writer is unavailable from this local server.",
          sources: [],
          evidence: [],
          shadow: null,
        });
      }
      render();
    });
  }
}

async function loadSnapshot() {
  try {
    const response = await fetch("snapshot.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.snapshot = await response.json();
    document.querySelector("#generated-at").textContent = `Generated ${state.snapshot.generated_at_utc}`;
  } catch (_error) {
    state.snapshot = null;
  }
  render();
}

document.querySelectorAll(".nav").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav").forEach((node) => node.classList.remove("is-active"));
    button.classList.add("is-active");
    state.currentView = button.dataset.view;
    render();
  });
});

loadSnapshot();
