(() => {
  const KEY_STORAGE = "signatureManagerApiKey";

  const el = (id) => document.getElementById(id);
  const status = el("status");
  const rows = el("user-rows");
  const filter = el("user-filter");
  const templateSelect = el("template-select");
  const previewFrame = el("preview");
  const buttons = [el("preview-btn"), el("apply-btn")];
  const applyAllBtn = el("apply-all-btn");

  let apiKey = "";
  let users = [];
  let selectedUpn = null;

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle("error", isError);
  }

  function readStoredKey() {
    try { return sessionStorage.getItem(KEY_STORAGE) || ""; } catch { return ""; }
  }

  function storeKey(key) {
    try { sessionStorage.setItem(KEY_STORAGE, key); } catch { /* storage unavailable */ }
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
        ...(options.headers || {}),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || `Request failed (${response.status})`);
    }
    return body;
  }

  function cell(text) {
    const td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  function renderUsers() {
    const term = filter.value.trim().toLowerCase();
    rows.replaceChildren();
    const visible = users.filter((u) =>
      !term ||
      u.displayName.toLowerCase().includes(term) ||
      u.userPrincipalName.toLowerCase().includes(term) ||
      u.mail.toLowerCase().includes(term));

    if (visible.length === 0) {
      const tr = document.createElement("tr");
      const td = cell("No users match.");
      td.colSpan = 5;
      td.className = "muted";
      tr.append(td);
      rows.append(tr);
      return;
    }

    for (const user of visible) {
      const tr = document.createElement("tr");
      tr.dataset.upn = user.userPrincipalName;
      tr.classList.toggle("selected", user.userPrincipalName === selectedUpn);

      const radioCell = document.createElement("td");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "user";
      radio.checked = user.userPrincipalName === selectedUpn;
      radio.setAttribute("aria-label", `Select ${user.displayName}`);
      radioCell.append(radio);

      tr.append(
        radioCell,
        cell(user.displayName),
        cell(user.mail || user.userPrincipalName),
        cell(user.jobTitle),
        cell(user.department),
      );
      tr.addEventListener("click", () => selectUser(user));
      rows.append(tr);
    }
  }

  function selectUser(user) {
    selectedUpn = user.userPrincipalName;
    el("selected-user").textContent = `${user.displayName} (${user.userPrincipalName})`;
    buttons.forEach((b) => { b.disabled = false; });
    renderUsers();
  }

  async function loadUsers() {
    setStatus("Loading users…");
    try {
      const data = await api("/api/users");
      users = data.users;
      filter.disabled = false;
      applyAllBtn.disabled = false;
      renderUsers();
      setStatus(`Loaded ${users.length} users.`);
    } catch (err) {
      setStatus(err.message, true);
    }
  }

  function showPreview(html) {
    // The iframe is sandboxed with no permissions, so scripts never run.
    previewFrame.srcdoc = html;
  }

  async function preview() {
    setStatus("Rendering preview…");
    try {
      const data = await api("/api/signature/preview", {
        method: "POST",
        body: JSON.stringify({ userPrincipalName: selectedUpn, template: templateSelect.value }),
      });
      showPreview(data.signature);
      setStatus("Preview ready.");
    } catch (err) {
      setStatus(err.message, true);
    }
  }

  async function applyToUser() {
    setStatus(`Applying signature to ${selectedUpn}…`);
    try {
      const data = await api("/api/signature", {
        method: "POST",
        body: JSON.stringify({ userPrincipalName: selectedUpn, template: templateSelect.value }),
      });
      showPreview(data.signature);
      setStatus(`Signature updated for ${selectedUpn}.`);
    } catch (err) {
      setStatus(err.message, true);
    }
  }

  async function applyToAll() {
    const template = templateSelect.value;
    if (!confirm(`Overwrite the signature of every mailbox user with the "${template}" template?`)) {
      return;
    }
    applyAllBtn.disabled = true;
    setStatus("Applying to all users. This can take several minutes…");
    try {
      const data = await api("/api/signature/bulk", {
        method: "POST",
        body: JSON.stringify({ template }),
      });
      const failed = data.failed.length;
      setStatus(`${data.succeeded} updated, ${failed} failed.` +
        (failed ? ` First failure: ${data.failed[0].user}: ${data.failed[0].error}` : ""), failed > 0);
    } catch (err) {
      setStatus(err.message, true);
    } finally {
      applyAllBtn.disabled = false;
    }
  }

  el("key-form").addEventListener("submit", (event) => {
    event.preventDefault();
    apiKey = el("api-key").value.trim();
    storeKey(apiKey);
    loadUsers();
  });
  filter.addEventListener("input", renderUsers);
  el("preview-btn").addEventListener("click", preview);
  el("apply-btn").addEventListener("click", applyToUser);
  applyAllBtn.addEventListener("click", applyToAll);

  apiKey = readStoredKey();
  if (apiKey) {
    el("api-key").value = apiKey;
    loadUsers();
  }
})();
