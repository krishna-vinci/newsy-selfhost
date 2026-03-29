const root = document.documentElement;
const themeToggle = document.querySelector("[data-theme-toggle]");
const themeKey = "rss-gen-theme";

const form = document.querySelector("[data-resolver-form]");
const queryInput = document.getElementById("query");
const redditLimitInput = document.getElementById("reddit-limit");
const includePreviewInput = document.getElementById("include-preview");

const loadingBox = document.querySelector("[data-loading]");
const errorBox = document.querySelector("[data-error]");
const resultsSection = document.querySelector("[data-results]");

const sourceBadge = document.querySelector("[data-source-badge]");
const entityName = document.querySelector("[data-entity-name]");
const entityLink = document.querySelector("[data-entity-link]");
const resultSubtitle = document.querySelector("[data-result-subtitle]");
const feedCount = document.querySelector("[data-feed-count]");
const feedList = document.querySelector("[data-feed-list]");
const formatToggle = document.querySelector("[data-format-toggle]");
const formatButtons = document.querySelectorAll("[data-format]");

const previewPanel = document.querySelector("[data-preview-panel]");
const previewLabel = document.querySelector("[data-preview-label]");
const previewList = document.querySelector("[data-preview-list]");

const attributionPanel = document.querySelector("[data-attribution-panel]");
const attributionCopy = document.querySelector("[data-attribution-copy]");

const optionsToggle = document.querySelector("[data-options-toggle]");
const formOptions = document.querySelector("[data-form-options]");
const kbdHint = document.querySelector("[data-kbd-hint]");

let currentPayload = null;
let currentFormat = "rss";

/* ── Theme ─────────────────────────────────────────────── */

function applyTheme(theme) {
  root.setAttribute("data-theme", theme);
  themeToggle.textContent = theme === "dark" ? "☀" : "☾";
}

function initializeTheme() {
  const savedTheme = localStorage.getItem(themeKey);
  applyTheme(savedTheme || "dark");
}

/* ── UI helpers ────────────────────────────────────────── */

function showLoading(show) {
  loadingBox.classList.toggle("hidden", !show);
}

function showError(message = "") {
  errorBox.textContent = message;
  errorBox.classList.toggle("hidden", !message);
}

function hideResults() {
  resultsSection.classList.add("hidden");
}

function setEntityLink(url, source) {
  if (!url) {
    entityLink.classList.add("hidden");
    entityLink.removeAttribute("href");
    return;
  }
  entityLink.href = url;
  entityLink.textContent = `Open ${source} ↗`;
  entityLink.classList.remove("hidden");
}

function createButton({ label, className, onClick }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

async function copyToClipboard(value, button) {
  const succeed = () => {
    button.textContent = "Copied ✓";
    button.classList.add("copied");
    window.setTimeout(() => {
      button.textContent = "Copy";
      button.classList.remove("copied");
    }, 1400);
  };
  const fail = () => {
    button.textContent = "Failed";
    window.setTimeout(() => { button.textContent = "Copy"; }, 1400);
  };

  // Modern API (requires HTTPS or localhost)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      succeed();
      return;
    } catch {
      // fall through to legacy method
    }
  }

  // Fallback for HTTP / non-secure contexts
  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) { succeed(); } else { fail(); }
  } catch {
    fail();
  }
}

/* ── Feed format ───────────────────────────────────────── */

function getFeedUrl(feed) {
  if (currentPayload?.source === "reddit" && currentFormat === "atom") {
    return feed.url.replace(/\.rss(\?|$)/, ".atom$1");
  }
  return feed.url;
}

function syncFormatToggle() {
  formatButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.format === currentFormat);
  });
}

/* ── Render feeds ──────────────────────────────────────── */

function renderFeeds(feeds) {
  feedList.replaceChildren();
  feedCount.textContent = `${feeds.length} feed${feeds.length === 1 ? "" : "s"}`;

  feeds.forEach((feed) => {
    const item = document.createElement("article");
    item.className = "feed-item";

    const topRow = document.createElement("div");
    topRow.className = "feed-top-row";

    const headingWrap = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = feed.label;
    headingWrap.appendChild(title);

    if (feed.description) {
      const description = document.createElement("p");
      description.className = "feed-description";
      description.textContent = feed.description;
      headingWrap.appendChild(description);
    }

    topRow.appendChild(headingWrap);

    const badges = document.createElement("div");
    badges.style.cssText = "display:flex;gap:6px;align-items:center;flex-shrink:0";

    if (feed.is_podcast) {
      const podBadge = document.createElement("span");
      podBadge.className = "podcast-badge";
      podBadge.textContent = "🎙 Podcast";
      badges.appendChild(podBadge);
    }

    if (feed.count !== null && feed.count !== undefined) {
      const countBadge = document.createElement("span");
      countBadge.className = "count-badge";
      countBadge.textContent = `${feed.count} items`;
      badges.appendChild(countBadge);
    }

    if (badges.hasChildNodes()) topRow.appendChild(badges);

    item.appendChild(topRow);

    const feedUrl = getFeedUrl(feed);
    const urlLink = document.createElement("a");
    urlLink.className = "feed-url";
    urlLink.href = feedUrl;
    urlLink.target = "_blank";
    urlLink.rel = "noreferrer";
    urlLink.textContent = feedUrl;
    item.appendChild(urlLink);

    const actions = document.createElement("div");
    actions.className = "feed-actions";

    const copyButton = createButton({
      label: "Copy",
      className: "copy-button",
      onClick: () => copyToClipboard(feedUrl, copyButton),
    });
    actions.appendChild(copyButton);

    const openLink = document.createElement("a");
    openLink.className = "open-button";
    openLink.href = feedUrl;
    openLink.target = "_blank";
    openLink.rel = "noreferrer";
    openLink.textContent = feed.external ? "Open feed ↗" : "Open XML ↗";
    actions.appendChild(openLink);

    item.appendChild(actions);
    feedList.appendChild(item);
  });
}

/* ── Render preview ────────────────────────────────────── */

function renderPreviewItems(previewItems, label) {
  previewList.replaceChildren();

  if (!previewItems.length) {
    previewPanel.classList.add("hidden");
    return;
  }

  previewLabel.textContent = label || "Recent entries";
  previewPanel.classList.remove("hidden");

  previewItems.forEach((item) => {
    const previewItem = document.createElement("article");
    previewItem.className = "preview-item";

    const title = document.createElement("a");
    title.className = "preview-title";
    title.href = item.url || "#";
    title.target = "_blank";
    title.rel = "noreferrer";
    title.textContent = item.title || "Untitled";
    previewItem.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "preview-meta";
    const bits = [item.author, item.published].filter(Boolean);
    meta.textContent = bits.join(" · ") || "";
    if (bits.length) previewItem.appendChild(meta);

    if (item.badge) {
      const badge = document.createElement("span");
      badge.className = "preview-badge";
      badge.textContent = item.badge;
      meta.prepend(badge);
      if (!meta.parentElement) previewItem.appendChild(meta);
    }

    previewList.appendChild(previewItem);
  });
}

/* ── Render attribution ────────────────────────────────── */

function renderAttribution(attribution) {
  if (!attribution) {
    attributionPanel.classList.add("hidden");
    attributionCopy.textContent = "";
    return;
  }
  attributionPanel.classList.remove("hidden");
  attributionCopy.innerHTML = `${attribution.label} · <a href="${attribution.url}" target="_blank" rel="noreferrer">${attribution.url}</a>`;
}

/* ── Render results ────────────────────────────────────── */

function renderResults(payload) {
  currentPayload = payload;
  currentFormat = "rss";
  formatToggle.classList.toggle("hidden", payload.source !== "reddit");
  syncFormatToggle();
  sourceBadge.textContent = payload.source;
  entityName.textContent = payload.entity_name;
  resultSubtitle.textContent = `Input: ${payload.input}`;
  setEntityLink(payload.entity_url, payload.source);
  renderFeeds(payload.feeds || []);
  renderPreviewItems(payload.preview_items || [], payload.preview_feed_label || "");
  renderAttribution(payload.attribution || null);
  resultsSection.classList.remove("hidden");

  requestAnimationFrame(() => {
    resultsSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}

/* ── Resolve ───────────────────────────────────────────── */

async function resolveFeeds(event) {
  event.preventDefault();
  const query = queryInput.value.trim();

  if (!query) {
    showError("Enter a YouTube channel, subreddit, or website.");
    hideResults();
    return;
  }

  hideResults();
  showError("");
  showLoading(true);

  const params = new URLSearchParams({
    query,
    reddit_limit: redditLimitInput.value,
    include_preview: String(includePreviewInput.checked),
  });

  try {
    const response = await fetch(`/api/v1/resolve?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Could not resolve feed options.");
    }
    renderResults(payload);
  } catch (error) {
    showError(error.message || "Could not resolve feed options.");
  } finally {
    showLoading(false);
  }
}

/* ── Init ──────────────────────────────────────────────── */

initializeTheme();

themeToggle.addEventListener("click", () => {
  const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
  localStorage.setItem(themeKey, nextTheme);
  applyTheme(nextTheme);
});

formatButtons.forEach((button) => {
  button.addEventListener("click", () => {
    currentFormat = button.dataset.format || "rss";
    syncFormatToggle();
    if (currentPayload) {
      renderFeeds(currentPayload.feeds || []);
    }
  });
});

form.addEventListener("submit", resolveFeeds);

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.example || "";
    form.requestSubmit();
  });
});

/* ── Options collapse ──────────────────────────────────── */

optionsToggle.addEventListener("click", () => {
  const isCollapsed = formOptions.classList.toggle("collapsed");
  optionsToggle.classList.toggle("open", !isCollapsed);
});

/* ── Keyboard shortcut: / or Ctrl+K to focus search ──── */

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
  if (e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) {
    e.preventDefault();
    queryInput.focus();
    queryInput.select();
  }
});

queryInput.addEventListener("focus", () => {
  if (kbdHint) kbdHint.classList.add("hide");
});

queryInput.addEventListener("blur", () => {
  if (kbdHint && !queryInput.value) kbdHint.classList.remove("hide");
});
