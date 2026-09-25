const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  view: "browse",
  subscriptions: [],
  history: [],
  settings: { use_ytdlp: true },
  currentVideo: null,
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function setView(name, title) {
  state.view = name;
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#view-title").textContent = title || name[0].toUpperCase() + name.slice(1);
}

function cardHtml(item) {
  const thumb = item.thumbnail
    ? `<img src="${escapeAttr(item.thumbnail)}" alt="">`
    : "";
  return `
    <article class="card" data-url="${escapeAttr(item.url)}">
      <div class="thumb">${thumb}<span class="dur">${escapeHtml(item.duration || "")}</span></div>
      <div class="meta">
        <h3>${escapeHtml(item.title || "Untitled")}</h3>
        <p>${escapeHtml(item.channel || "")} ${item.views ? "· " + escapeHtml(item.views) : ""}</p>
      </div>
    </article>`;
}

function escapeHtml(s) {
  return String(s || "")
    .replaceAll("&", "&")
    .replaceAll("<", "<")
    .replaceAll(">", ">")
    .replaceAll('"', """);
}
function escapeAttr(s) {
  return escapeHtml(s).replaceAll("'", "&#39;");
}

function showError(err) {
  $("#content").innerHTML = `<div class="error">${escapeHtml(err.message || err)}</div>`;
}

async function loadState() {
  const data = await api("/api/state");
  state.subscriptions = data.subscriptions || [];
  state.history = data.history || [];
  state.settings = data.settings || state.settings;
}

async function loadFeed(kind, q = "") {
  setView(kind === "search" ? "search" : kind, kind === "browse" ? "Browse Rumble" : undefined);
  $("#content").innerHTML = `<div class="empty">Loading…</div>`;
  try {
    const data = await api(`/api/feed?kind=${encodeURIComponent(kind)}&q=${encodeURIComponent(q)}`);
    if (kind === "channel") $("#view-title").textContent = data.title || "Channel";
    renderGrid(data.items || [], data);
  } catch (err) {
    showError(err);
  }
}

function renderGrid(items, extra = {}) {
  if (!items.length) {
    $("#content").innerHTML = `<div class="empty">Nothing here yet. ${escapeHtml(extra.title || "")}</div>`;
    return;
  }
  $("#content").innerHTML = `<div class="grid">${items.map(cardHtml).join("")}</div>`;
  $$(".card").forEach((el) => el.addEventListener("click", () => openVideo(el.dataset.url)));
}

async function doSearch(query) {
  setView("search", `Search: ${query}`);
  $("#content").innerHTML = `<div class="empty">Searching…</div>`;
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
    const channels = (data.channels || [])
      .map((c) => `<button class="chip" data-channel="${escapeAttr(c.url)}">${escapeHtml(c.name)}</button>`)
      .join("");
    $("#content").innerHTML = `
      ${channels ? `<div class="row">${channels}</div>` : ""}
      <div class="grid">${(data.videos || []).map(cardHtml).join("")}</div>`;
    $$(".card").forEach((el) => el.addEventListener("click", () => openVideo(el.dataset.url)));
    $$("[data-channel]").forEach((el) =>
      el.addEventListener("click", () => loadFeed("channel", el.dataset.channel))
    );
  } catch (err) {
    showError(err);
  }
}

async function openVideo(url) {
  setView("watch", "Now playing");
  $("#content").innerHTML = `<div class="empty">Resolving stream…</div>`;
  try {
    const info = await api(`/api/video?url=${encodeURIComponent(url)}`);
    state.currentVideo = info;
    const formats = info.formats || [];
    const options = formats
      .map((f, i) => `<option value="${i}">${escapeHtml(String(f.height || f.type || "stream"))}${f.type === "hls" ? " HLS" : ""}</option>`)
      .join("");
    const subscribed = state.subscriptions.some((s) => s.url === info.channel_url);
    $("#content").innerHTML = `
      <div class="player-wrap">
        <div>
          <video id="player" controls autoplay playsinline poster="${escapeAttr(info.thumbnail || "")}"></video>
          <div class="player-info">
            <h3>${escapeHtml(info.title)}</h3>
            <div class="row">
              <button class="chip" id="open-channel">${escapeHtml(info.channel || "Channel")}</button>
              <button class="${subscribed ? "danger" : "primary"}" id="sub-btn">${subscribed ? "Unsubscribe" : "Subscribe"}</button>
              <select class="quality" id="quality">${options}</select>
              <a class="ghost" href="${escapeAttr(info.watch_url)}" target="_blank" rel="noreferrer">Open on Rumble</a>
            </div>
            <p>${escapeHtml(info.description || "")}</p>
            <p class="hint">Resolved via ${escapeHtml(info.resolver || "unknown")}</p>
          </div>
        </div>
      </div>`;
    attachPlayer(info, 0);
    $("#open-channel")?.addEventListener("click", () => {
      if (info.channel_url) loadFeed("channel", info.channel_url);
    });
    $("#sub-btn")?.addEventListener("click", () => toggleSub(info));
    $("#quality")?.addEventListener("change", (e) => attachPlayer(info, Number(e.target.value)));
    loadState();
  } catch (err) {
    showError(err);
  }
}

function attachPlayer(info, index) {
  const video = $("#player");
  const fmt = (info.formats || [])[index] || { url: info.best_url, type: "mp4" };
  if (!fmt?.url) return;
  if (String(fmt.type).includes("hls") || String(fmt.url).includes(".m3u8")) {
    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls();
      hls.loadSource(fmt.url);
      hls.attachMedia(video);
    } else {
      video.src = fmt.url;
    }
  } else {
    video.src = fmt.url;
  }
  video.play().catch(() => {});
}

async function toggleSub(info) {
  if (!info.channel_url) return;
  const exists = state.subscriptions.some((s) => s.url === info.channel_url);
  if (exists) {
    state.subscriptions = await api("/api/subscriptions/remove", {
      method: "POST",
      body: JSON.stringify({ url: info.channel_url }),
    });
  } else {
    state.subscriptions = await api("/api/subscriptions/add", {
      method: "POST",
      body: JSON.stringify({ name: info.channel, url: info.channel_url, handle: info.channel }),
    });
  }
  openVideo(info.watch_url);
}

async function showSubscriptions() {
  setView("subscriptions", "Subscriptions");
  await loadState();
  if (!state.subscriptions.length) {
    $("#content").innerHTML = `<div class="empty">No subscriptions yet. Open a video and hit Subscribe.</div>`;
    return;
  }
  $("#content").innerHTML = `<div class="empty">Loading subscription feeds…</div>`;
  const all = [];
  for (const sub of state.subscriptions) {
    try {
      const data = await api(`/api/feed?kind=channel&q=${encodeURIComponent(sub.url)}`);
      all.push(...(data.items || []).map((i) => ({ ...i, channel: i.channel || sub.name })));
    } catch {}
  }
  renderGrid(all);
}

async function showHistory() {
  setView("history", "History");
  await loadState();
  if (!state.history.length) {
    $("#content").innerHTML = `<div class="empty">Watched videos will show up here. History never leaves this computer.</div>`;
    return;
  }
  $("#content").innerHTML = `<div class="list">${state.history.map((h) => `
      <div class="list-item" data-url="${escapeAttr(h.url)}">
        <img src="${escapeAttr(h.thumbnail || "")}" alt="">
        <div><h3>${escapeHtml(h.title || "")}</h3><p class="hint">${escapeHtml(h.channel || "")}</p></div>
      </div>`).join("")}</div>`;
  $$(".list-item").forEach((el) => el.addEventListener("click", () => openVideo(el.dataset.url)));
}

function showSettings() {
  setView("settings", "Settings");
  $("#content").innerHTML = `
    <div class="settings">
      <label><input type="checkbox" id="use-ytdlp" ${state.settings.use_ytdlp ? "checked" : ""}>
        Use yt-dlp as fallback resolver (recommended)</label>
      <p class="hint">Data lives in <code>~/.local/share/freerumble</code> on Linux. Nothing is uploaded.</p>
      <p class="hint">Paste any rumble.com video URL into search to open it directly.</p>
    </div>`;
  $("#use-ytdlp").addEventListener("change", async (e) => {
    state.settings = await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({ use_ytdlp: e.target.checked }),
    });
  });
}

function routeFromSearch(value) {
  const v = value.trim();
  if (!v) return loadFeed("browse");
  if (v.includes("rumble.com/v") || v.startsWith("/v")) return openVideo(v);
  if (v.includes("rumble.com/c/") || v.includes("rumble.com/user/")) return loadFeed("channel", v);
  return doSearch(v);
}

function bind() {
  $$(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      if (view === "browse") loadFeed("browse");
      else if (view === "live") loadFeed("live");
      else if (view === "subscriptions") showSubscriptions();
      else if (view === "history") showHistory();
      else if (view === "settings") showSettings();
    });
  });
  $("#search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") routeFromSearch(e.target.value);
  });
  $("#search-btn").addEventListener("click", () => routeFromSearch($("#search").value));
}

bind();
loadState().then(() => loadFeed("browse")).catch((err) => showError(err));
