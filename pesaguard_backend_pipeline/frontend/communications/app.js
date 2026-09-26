"use strict";

/*
 * PesaGuard communications console.
 *
 * Security invariants this file must keep:
 *   - The access token lives only in the `state` object in memory for this
 *     tab. It is never written to any browser storage, never put in a URL or
 *     query string, and never logged.
 *   - Every render replaces DOM content with createElement/textContent only,
 *     so a value from the API (a recipient, a template body) can never be
 *     interpreted as markup.
 *   - This console is read-only: it never calls the export endpoint. Use the
 *     audited export API directly if you hold the export permission.
 */

const DEV_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

const state = {
  baseUrl: "",
  token: "",
  tenant: "",
};

const els = {
  apiBase: document.getElementById("api-base"),
  token: document.getElementById("token"),
  connect: document.getElementById("connect"),
  disconnect: document.getElementById("disconnect"),
  clearToken: document.getElementById("clear-token"),
  search: document.getElementById("search"),
  status: document.getElementById("status"),
  refresh: document.getElementById("refresh"),
  reload: document.getElementById("reload"),
  loadTemplates: document.getElementById("load-templates"),
  results: document.getElementById("results"),
  tenantBanner: document.getElementById("tenant-banner"),
  sessionState: document.getElementById("session-state"),
  connectionError: document.getElementById("connection-error"),
};

function isSecureApi(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  if (parsed.protocol === "https:") return true;
  // Plain http is only acceptable against a local dev backend, never a real host.
  return parsed.protocol === "http:" && DEV_HOSTS.includes(parsed.hostname);
}

// Reads the tenant_id claim out of the JWT payload purely for display in the
// banner. This is not a trust boundary: every request is still scoped to the
// caller's tenant on the server (see communications/product_routes.py, which
// filters every query with filter_by(tenant_id=...)).
function decodeTenant(token) {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    const claims = JSON.parse(json);
    return claims.tenant_id || claims.tenant || "";
  } catch {
    return "";
  }
}

// Redacts a phone number or email to a non-identifying fragment for display.
// e.g. "254712345678" -> "2547***5678", "jane@example.com" -> "j***@example.com".
function maskRecipient(recipient) {
  const value = String(recipient || "");
  const at = value.indexOf("@");
  if (at > 0) {
    const name = value.slice(0, at);
    const domain = value.slice(at);
    return `${name[0]}***${domain}`;
  }
  if (value.length > 7) {
    return `${value.slice(0, 4)}***${value.slice(-4)}`;
  }
  return "***";
}

function setConnectionError(message) {
  els.connectionError.textContent = message || "";
}

function setSessionState(text) {
  els.sessionState.textContent = text;
}

function clearChildren(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function connect() {
  const url = els.apiBase.value.trim();
  const token = els.token.value.trim();
  if (!isSecureApi(url)) {
    setConnectionError("Refusing to connect: the API URL must be https, or http on localhost only.");
    return;
  }
  if (!token) {
    setConnectionError("Enter an access token first.");
    return;
  }
  state.baseUrl = url.replace(/\/+$/, "");
  state.token = token; // kept only on this object, for this tab, for this page load
  state.tenant = decodeTenant(token);
  setConnectionError("");
  setSessionState("connected");
  clearChildren(els.tenantBanner);
  if (state.tenant) {
    els.tenantBanner.appendChild(document.createTextNode(`Tenant: ${state.tenant}`));
  }
  loadMessages();
}

function disconnect() {
  state.baseUrl = "";
  state.token = "";
  state.tenant = "";
  setSessionState("disconnected");
  clearChildren(els.tenantBanner);
  clearChildren(els.results);
}

function clearToken() {
  // Defensive cleanup only: this app never writes pg_token to localStorage,
  // but an older build might have, so proactively remove any leftover value.
  localStorage.removeItem('pg_token');
  els.token.value = "";
  state.token = "";
  setSessionState(state.baseUrl ? "connected, no token" : "disconnected");
}

async function api(path, { params } = {}) {
  if (!isSecureApi(state.baseUrl)) {
    throw new Error("not connected to a secure API base URL");
  }
  const url = new URL(state.baseUrl + path);
  for (const [key, value] of Object.entries(params || {})) {
    if (value) url.searchParams.set(key, value);
  }
  let response;
  try {
    response = await fetch(url.toString(), {
      method: "GET",
      credentials: "omit",
      headers: { Authorization: `Bearer ${state.token}` },
    });
  } catch {
    throw new Error("network error reaching the API");
  }
  if (response.status === 401) {
    disconnect();
    throw new Error("session expired (401) — reconnect with a fresh token");
  }
  if (response.status === 403) {
    throw new Error("you do not have permission for this action (403)");
  }
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    throw new Error(`rate limited (429) — try again${retryAfter ? ` in ${retryAfter}s` : ""}`);
  }
  if (!response.ok) {
    throw new Error(`request failed (${response.status})`);
  }
  return response.json();
}

function renderMessagesTable(messages) {
  clearChildren(els.results);
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.textContent = `${messages.length} message${messages.length === 1 ? "" : "s"}`;
  table.appendChild(caption);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Recipient", "Channel", "Status", "Provider", "Created"].forEach((label) => {
    const th = document.createElement("th");
    th.setAttribute("scope", "col");
    th.textContent = label;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const message of messages) {
    const row = document.createElement("tr");
    const cells = [
      maskRecipient(message.recipient),
      message.channel || "",
      message.status || "",
      message.provider || "",
      message.created_at || "",
    ];
    for (const value of cells) {
      const td = document.createElement("td");
      td.textContent = value;
      row.appendChild(td);
    }
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  els.results.appendChild(table);
}

function renderTemplatesList(templates) {
  clearChildren(els.results);
  const heading = document.createElement("h3");
  heading.textContent = `${templates.length} template${templates.length === 1 ? "" : "s"}`;
  els.results.appendChild(heading);
  const list = document.createElement("ul");
  for (const template of templates) {
    const item = document.createElement("li");
    item.textContent = `${template.slug} (v${template.version}, ${template.channel})`;
    list.appendChild(item);
  }
  els.results.appendChild(list);
}

async function loadMessages(all = false) {
  els.results.setAttribute("aria-busy", "true");
  setConnectionError("");
  try {
    const params = all
      ? {}
      : {
          recipient: els.search.value.trim() || undefined,
          status: els.status.value || undefined,
          limit: "50",
        };
    const data = await api("/api/v1/communications/messages", { params });
    renderMessagesTable(data.messages || []);
  } catch (err) {
    setConnectionError(err.message);
  } finally {
    els.results.setAttribute("aria-busy", "false");
  }
}

async function loadTemplates() {
  els.results.setAttribute("aria-busy", "true");
  setConnectionError("");
  try {
    const data = await api("/api/v1/communications/templates");
    renderTemplatesList(Array.isArray(data) ? data : []);
  } catch (err) {
    setConnectionError(err.message);
  } finally {
    els.results.setAttribute("aria-busy", "false");
  }
}

els.connect.addEventListener("click", connect);
els.disconnect.addEventListener("click", disconnect);
els.clearToken.addEventListener("click", clearToken);
els.refresh.addEventListener("click", () => loadMessages(false));
els.reload.addEventListener("click", () => loadMessages(true));
els.loadTemplates.addEventListener("click", loadTemplates);

setSessionState("disconnected");
