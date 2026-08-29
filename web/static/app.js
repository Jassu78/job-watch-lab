(() => {
  const LIST_KEYS = [
    "title_any",
    "title_exclude",
    "keywords_any",
    "keywords_all",
    "keywords_exclude",
    "locations_any",
  ];

  const state = {
    token: localStorage.getItem("jw_desk_token") || "",
    filters: null,
    sources: [],
    bootstrap: null,
    jobsPage: 1,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2200);
  }

  function tokenFromUrl() {
    const u = new URL(location.href);
    return u.searchParams.get("k") || "";
  }

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    const res = await fetch(path, { ...opts, headers });
    if (res.status === 401) throw new Error("unauthorized");
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function ensureList(key) {
    if (!state.filters[key]) state.filters[key] = [];
    return state.filters[key];
  }

  function renderChips() {
    LIST_KEYS.forEach((key) => {
      const box = $(`.chips[data-key="${key}"]`);
      if (!box) return;
      const items = ensureList(key);
      box.innerHTML = "";
      items.forEach((term, idx) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `<span></span><button type="button" aria-label="remove">×</button>`;
        chip.querySelector("span").textContent = term;
        chip.querySelector("button").onclick = () => {
          items.splice(idx, 1);
          renderChips();
          syncRaw();
        };
        box.appendChild(chip);
      });
    });
  }

  function addTerm(key, value) {
    const v = (value || "").trim();
    if (!v) return;
    const list = ensureList(key);
    if (list.some((x) => x.toLowerCase() === v.toLowerCase())) return;
    list.push(v);
    renderChips();
    syncRaw();
  }

  function syncRaw() {
    $("#rawJson").value = JSON.stringify(state.filters, null, 2);
  }

  function readFormIntoFilters() {
    const maxDays = $("#maxDays").value;
    state.filters.max_days_old = maxDays === "" ? null : Number(maxDays);
    state.filters.max_per_source = Number($("#maxPer").value || 5);
    state.filters.sources = {
      companies: $("#srcCompanies").checked,
      aggregators: $("#srcAggregators").checked,
    };
  }

  function fillFilterForm() {
    $("#maxDays").value =
      state.filters.max_days_old == null ? "" : state.filters.max_days_old;
    $("#maxPer").value = state.filters.max_per_source ?? 5;
    $("#srcCompanies").checked = !!(state.filters.sources || {}).companies;
    $("#srcAggregators").checked = !!(state.filters.sources || {}).aggregators;
    renderChips();
    syncRaw();
  }

  function renderJobs(payload) {
    const box = $("#jobList");
    const jobs = payload.jobs || [];
    const total = payload.total ?? jobs.length;
    const from = payload.from || 0;
    const to = payload.to || 0;
    const page = payload.page || 1;
    const pages = payload.pages || 1;
    state.jobsPage = page;

    $("#jobPageLabel").textContent = total
      ? `${from}–${to} of ${total} jobs`
      : "0 jobs";
    const short = $("#jobPageShort");
    if (short) short.textContent = `${page} / ${pages}`;
    $("#jobPrev").disabled = page <= 1;
    $("#jobNext").disabled = page >= pages;
    const pager = $("#jobPager");
    if (pager) pager.hidden = total === 0;

    if (!jobs.length) {
      box.innerHTML = `<div class="job">No jobs in history for this view.</div>`;
      return;
    }
    const base = from || 1;
    box.innerHTML = jobs
      .map((j, i) => {
        const n = base + i;
        const title = escapeHtml(j.title || "");
        const co = escapeHtml(j.company || "");
        const loc = escapeHtml(j.location || "");
        const sid = escapeHtml(j.source_id || "");
        const url = j.url
          ? `<div><a href="${escapeAttr(j.url)}" target="_blank" rel="noopener">open listing</a></div>`
          : "";
        return `<article class="job"><div><span class="num">${n}.</span><span class="co">[${co}]</span> ${title}</div><div class="meta">${sid}${loc ? " · " + loc : ""}</div>${url}</article>`;
      })
      .join("");
  }

  async function loadJobs(page) {
    if (page != null) state.jobsPage = page;
    const q = encodeURIComponent($("#jobQ").value || "");
    const source = encodeURIComponent($("#jobSource").value || "");
    const pageSize = encodeURIComponent($("#jobPageSize").value || "10");
    const data = await api(
      `/api/jobs?q=${q}&source=${source}&page=${state.jobsPage}&page_size=${pageSize}`
    );
    renderJobs(data);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function renderSources() {
    const q = ($("#srcFilter").value || "").toLowerCase();
    const box = $("#sourceList");
    box.innerHTML = "";
    state.sources
      .filter((s) => !q || `${s.id} ${s.name} ${s.type}`.toLowerCase().includes(q))
      .forEach((s) => {
        const el = document.createElement("label");
        el.className = "source-item";
        el.innerHTML = `<input type="checkbox" ${s.enabled ? "checked" : ""} /><div><div class="id">${escapeHtml(s.id)}</div><div class="type">${escapeHtml(s.type)} · ${escapeHtml(s.bucket)}</div></div>`;
        el.querySelector("input").onchange = (e) => {
          s.enabled = e.target.checked;
        };
        box.appendChild(el);
      });
  }

  async function loadHealth() {
    const data = await api("/api/status");
    const rows = data.sources || [];
    if (!rows.length) {
      $("#healthWrap").innerHTML = `<p class="hint">No scan history yet.</p>`;
      return;
    }
    $("#healthWrap").innerHTML = `<table class="status-table"><thead><tr><th>source</th><th>last check</th><th>fetch</th><th>match</th><th>seen</th></tr></thead><tbody>${rows
      .map((r) => {
        const lc = (r.last_check || "—").toString().slice(0, 19).replace("T", " ");
        return `<tr><td>${escapeHtml(r.id)}</td><td>${escapeHtml(lc)}</td><td>${r.last_fetch_count ?? "—"}</td><td>${r.last_match_count ?? "—"}</td><td>${r.seen ?? "—"}</td></tr>`;
      })
      .join("")}</tbody></table>`;
  }

  async function boot() {
    const data = await api("/api/bootstrap");
    state.bootstrap = data;
    state.filters = data.filters || {};
    LIST_KEYS.forEach((k) => ensureList(k));
    state.sources = data.sources || [];
    $("#muted").checked = !!(data.prefs || {}).muted;
    $("#liveState").textContent = (data.prefs || {}).muted ? "alerts paused" : "alerts on";
    $("#statCheck").textContent = `last check ${(data.status.last_check || "—").toString().slice(0, 19).replace("T", " ")}`;
    $("#statRecent").textContent = `history ${data.status.recent_count || 0}`;
    fillFilterForm();
    const sel = $("#jobSource");
    const cur = sel.value;
    sel.innerHTML = `<option value="">all sources</option>` +
      [...new Set(state.sources.map((s) => s.id))]
        .map((id) => `<option value="${escapeAttr(id)}">${escapeHtml(id)}</option>`)
        .join("");
    sel.value = cur;
    renderSources();
    await loadJobs();
  }

  function showApp() {
    $("#gate").hidden = true;
    $("#app").hidden = false;
  }
  function showGate() {
    $("#gate").hidden = false;
    $("#app").hidden = true;
  }

  async function enter(token) {
    state.token = (token || "").trim();
    if (!state.token) return;
    localStorage.setItem("jw_desk_token", state.token);
    try {
      await boot();
      showApp();
      if (tokenFromUrl()) {
        history.replaceState({}, "", "/");
      }
      const tg = window.Telegram && window.Telegram.WebApp;
      if (tg) {
        tg.ready();
        tg.expand();
        try {
          tg.setHeaderColor("#0c0f0c");
          tg.setBackgroundColor("#070908");
        } catch (_) {}
      }
    } catch (e) {
      localStorage.removeItem("jw_desk_token");
      state.token = "";
      showGate();
      toast("Access denied — open via Telegram Catalog");
    }
  }

  async function authTelegramWebApp() {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg || !tg.initData) return false;
    tg.ready();
    tg.expand();
    const res = await fetch("/api/auth/telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initData: tg.initData }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.token) {
      throw new Error(data.error || "telegram auth failed");
    }
    await enter(data.token);
    return true;
  }

  async function bootAuth() {
    try {
      if (await authTelegramWebApp()) return;
    } catch (e) {
      console.warn(e);
      const hint = $("#gateHint");
      if (hint) {
        hint.textContent =
          "Telegram sign-in failed. Use /desk fallback key on the same host network.";
      }
    }
    const fromUrl = tokenFromUrl();
    if (fromUrl) {
      await enter(fromUrl);
      return;
    }
    if (state.token) {
      await enter(state.token);
      return;
    }
    showGate();
  }

  function wire() {
    $$(".tab").forEach((btn) => {
      btn.onclick = async () => {
        $$(".tab").forEach((b) => b.setAttribute("aria-selected", "false"));
        btn.setAttribute("aria-selected", "true");
        $$(".panel").forEach((p) => p.classList.remove("active"));
        $(`#tab-${btn.dataset.tab}`).classList.add("active");
        if (btn.dataset.tab === "jobs") await loadJobs();
        if (btn.dataset.tab === "health") await loadHealth();
      };
    });

    LIST_KEYS.forEach((key) => {
      const input = $(`input[data-add="${key}"]`);
      const btn = $(`button[data-addbtn="${key}"]`);
      const add = () => {
        addTerm(key, input.value);
        input.value = "";
        input.focus();
      };
      if (btn) btn.onclick = add;
      if (input) {
        input.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            add();
          }
        });
      }
    });

    $("#saveFilters").onclick = async () => {
      readFormIntoFilters();
      await api("/api/filters", { method: "PUT", body: JSON.stringify(state.filters) });
      await api("/api/prefs", {
        method: "PUT",
        body: JSON.stringify({ muted: $("#muted").checked }),
      });
      $("#liveState").textContent = $("#muted").checked ? "alerts paused" : "alerts on";
      toast("Filters saved");
      syncRaw();
    };

    $("#reloadFilters").onclick = async () => {
      const data = await api("/api/filters");
      state.filters = data;
      fillFilterForm();
      toast("Reloaded");
    };

    $("#muted").onchange = async () => {
      await api("/api/prefs", {
        method: "PUT",
        body: JSON.stringify({ muted: $("#muted").checked }),
      });
      $("#liveState").textContent = $("#muted").checked ? "alerts paused" : "alerts on";
      toast($("#muted").checked ? "Alerts paused" : "Alerts on");
    };

    $("#bulkMerge").onclick = () => {
      const key = $("#bulkTarget").value;
      const lines = $("#bulkText").value.split(/\n/).map((x) => x.trim()).filter(Boolean);
      lines.forEach((t) => addTerm(key, t));
      toast(`Merged ${lines.length} into ${key}`);
    };
    $("#bulkReplace").onclick = () => {
      const key = $("#bulkTarget").value;
      const lines = $("#bulkText").value.split(/\n/).map((x) => x.trim()).filter(Boolean);
      state.filters[key] = [];
      lines.forEach((t) => addTerm(key, t));
      toast(`Replaced ${key}`);
    };
    $("#rawApply").onclick = () => {
      try {
        state.filters = JSON.parse($("#rawJson").value);
        LIST_KEYS.forEach((k) => ensureList(k));
        fillFilterForm();
        toast("JSON applied (not saved yet)");
      } catch {
        toast("Invalid JSON");
      }
    };
    $("#exportJson").onclick = () => {
      readFormIntoFilters();
      const blob = new Blob([JSON.stringify(state.filters, null, 2)], {
        type: "application/json",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "filters.json";
      a.click();
    };
    $("#importJson").onchange = async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      try {
        state.filters = JSON.parse(await file.text());
        LIST_KEYS.forEach((k) => ensureList(k));
        fillFilterForm();
        toast("Imported (not saved yet)");
      } catch {
        toast("Import failed");
      }
    };

    $("#jobRefresh").onclick = () => loadJobs(1);
    $("#jobQ").addEventListener("keydown", (e) => {
      if (e.key === "Enter") loadJobs(1);
    });
    $("#jobSource").onchange = () => loadJobs(1);
    $("#jobPageSize").onchange = () => loadJobs(1);
    $("#jobPrev").onclick = () => loadJobs(Math.max(1, state.jobsPage - 1));
    $("#jobNext").onclick = () => loadJobs(state.jobsPage + 1);

    $("#srcFilter").oninput = renderSources;
    $("#srcAllOn").onclick = () => {
      state.sources.forEach((s) => (s.enabled = true));
      renderSources();
    };
    $("#srcAllOff").onclick = () => {
      state.sources.forEach((s) => (s.enabled = false));
      renderSources();
    };
    $("#saveSources").onclick = async () => {
      await api("/api/sources", {
        method: "PUT",
        body: JSON.stringify({
          items: state.sources.map((s) => ({ id: s.id, enabled: s.enabled })),
        }),
      });
      toast("Sources saved");
    };

    $("#gateGo").onclick = () => enter($("#gateKey").value);
    $("#gateKey").addEventListener("keydown", (e) => {
      if (e.key === "Enter") enter($("#gateKey").value);
    });
  }

  wire();
  bootAuth();
})();
