(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const nf = new Intl.NumberFormat("en-US");
  const POLL_MS = 5000;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const thisHost = document.querySelector(".shell").dataset.host;

  // ---------- helpers ----------

  const hue = (str) => {
    let h = 2166136261; // FNV-1a, then golden-ratio spread for distinct hues
    for (const c of str) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
    return Math.round(((h * 0.618033988749895) % 1) * 360);
  };
  const hostColor = (host) => `hsl(${hue(host)} 80% 62%)`;

  const ordinal = (n) => {
    const s = ["th", "st", "nd", "rd"], v = n % 100;
    return nf.format(n) + (s[(v - 20) % 10] || s[v] || s[0]);
  };

  const ago = (iso) => {
    const sec = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (sec < 5) return "just now";
    if (sec < 60) return `${sec}s ago`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
  };

  const duration = (s) => {
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${m}m`;
    if (m) return `${m}m`;
    return `${s}s`;
  };

  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "style") Object.assign(node.style, v);
      else if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    for (const c of children) node.append(c);
    return node;
  };

  function countTo(node, to, format = (n) => nf.format(n)) {
    const from = Number(node.dataset.value || 0);
    node.dataset.value = to;
    if (reducedMotion || from === to) { node.textContent = format(to); return; }
    const start = performance.now(), dur = 900;
    const step = (t) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(2, -10 * p);
      node.textContent = format(Math.round(from + (to - from) * eased));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function setStatus(state, text) {
    $("#status").dataset.state = state;
    $("#status-text").textContent = text;
  }

  async function call(method, url) {
    const t0 = performance.now();
    const res = await fetch(url, { method, headers: { Accept: "application/json" }, credentials: "same-origin" });
    const ms = Math.round(performance.now() - t0);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), ms };
  }

  // ---------- renderers ----------

  function renderChart(hourly) {
    const chart = $("#chart");
    const max = Math.max(1, ...hourly.map((h) => h.count));
    const peak = hourly.reduce((a, b) => (b.count > a.count ? b : a), hourly[0]);

    if (chart.children.length !== hourly.length) {
      chart.replaceChildren(...hourly.map(() => el("div", { class: "bar" })));
    }
    hourly.forEach((h, i) => {
      const bar = chart.children[i];
      const label = new Date(h.hour).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      bar.style.height = `${Math.max(2, (h.count / max) * 100)}%`;
      bar.dataset.tip = `${label} · ${nf.format(h.count)}`;
      bar.classList.toggle("empty", h.count === 0);
      bar.classList.toggle("now", i === hourly.length - 1);
    });

    const fmt = (iso) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    $("#chart-axis").replaceChildren(
      ...[0, 6, 12, 18].map((i) => el("span", {}, fmt(hourly[i].hour))),
      el("span", {}, "now"),
    );
    $("#peak").textContent = peak.count ? `peak ${nf.format(peak.count)} at ${fmt(peak.hour)}` : "no traffic yet";
  }

  function renderReplicas(servedBy, currentHost) {
    const list = $("#replicas");
    const total = servedBy.reduce((s, r) => s + r.count, 0) || 1;
    $("#replica-count").textContent = `${servedBy.length} ${servedBy.length === 1 ? "instance" : "instances"}`;

    if (!servedBy.length) {
      list.replaceChildren(el("li", { class: "empty-state" }, "No traffic yet."));
      return;
    }
    list.replaceChildren(
      ...servedBy.map((r) => {
        const pct = (r.count / total) * 100;
        const color = hostColor(r.host);
        const name = el("span", { class: "replica-name" },
          el("span", { class: "swatch", style: { background: color } }),
          el("span", { class: "n", title: r.host }, r.host),
        );
        if (r.host === currentHost) name.append(el("span", { class: "you" }, "you"));
        const fill = el("div", { class: "fill", style: { width: "0%", background: color } });
        requestAnimationFrame(() => (fill.style.width = `${pct}%`));
        return el("li", {},
          el("div", { class: "replica-row" }, name,
            el("span", { class: "replica-num" }, `${nf.format(r.count)} · ${pct.toFixed(0)}%`)),
          el("div", { class: "track" }, fill),
        );
      }),
    );
  }

  function renderRecent(recent) {
    const list = $("#recent");
    if (!recent.length) {
      list.replaceChildren(el("li", { class: "empty-state" }, "Waiting for the first visitor…"));
      return;
    }
    list.replaceChildren(
      ...recent.map((v) =>
        el("li", {},
          el("span", { class: "n" }, `#${nf.format(v.n)}`),
          el("span", { class: "meta" },
            el("span", { class: "swatch", style: { background: hostColor(v.host) } }),
            el("code", { title: v.host }, v.host),
            el("span", { class: "who" }, `visitor ${v.visitor}`),
          ),
          el("time", { datetime: v.at, title: new Date(v.at).toLocaleString() }, ago(v.at)),
        ),
      ),
    );
  }

  function render(s) {
    countTo($("#s-total"), s.total);
    countTo($("#s-today"), s.today);
    countTo($("#s-unique"), s.unique);
    countTo($("#s-instances"), s.served_by.length);
    $("#uptime").textContent = duration(s.instance.uptime_seconds);
    $("#served-host").textContent = s.instance.host;

    if (s.you) {
      const big = $("#you-number");
      countTo(big, s.you.number, ordinal);
      big.classList.remove("bump"); void big.offsetWidth; big.classList.add("bump");
      $("#greeting").textContent = s.you.returning ? "Welcome back" : "Hello there";
    }

    renderChart(s.hourly);
    renderReplicas(s.served_by, s.instance.host);
    renderRecent(s.recent);
  }

  // ---------- actions ----------

  async function visit() {
    const btn = $("#visit-btn");
    btn.disabled = true;
    try {
      const { data, ms } = await call("POST", "/api/visit");
      render(data);
      setStatus("live", `Live · ${ms} ms`);
    } catch (e) {
      setStatus("down", "Redis unavailable");
    } finally {
      btn.disabled = false;
    }
  }

  async function refresh() {
    if (document.hidden) return;
    try {
      const { data, ms } = await call("GET", "/api/stats");
      render(data);
      setStatus("live", `Live · ${ms} ms`);
    } catch (e) {
      setStatus("down", "Redis unavailable");
    }
  }

  $("#visit-btn").addEventListener("click", visit);
  document.addEventListener("visibilitychange", () => !document.hidden && refresh());
  document.addEventListener("keydown", (e) => {
    if (e.key === "+" && !e.metaKey && !e.ctrlKey) visit();
  });

  visit();
  setInterval(refresh, POLL_MS);
  console.info(`[visit-counter] page served by ${thisHost}`);
})();
