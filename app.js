const profile = {
  mission: "",
  exclusions: new Set(),
  flags: new Set(),
  esg: "",
  risk: "",
  attachments: [],
};

const elements = {
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  messages: document.querySelector("#message-list"),
  suggestions: document.querySelector("#suggestions"),
  typing: document.querySelector("#typing-indicator"),
  fileInput: document.querySelector("#file-input"),
  attachButton: document.querySelector("#attach-button"),
  attachmentList: document.querySelector("#attachment-list"),
  mission: document.querySelector("#mission-value"),
  exclusions: document.querySelector("#exclusion-tags"),
  flags: document.querySelector("#flag-tags"),
  esg: document.querySelector("#esg-value"),
  risk: document.querySelector("#risk-value"),
};

function renderInlineMarkdown(text, parent, depth = 0) {
  if (depth > 8) {
    parent.append(document.createTextNode(text));
    return;
  }

  const tokenPattern = /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|~~[^~\n]+~~|\*[^*\n]+\*|_[^_\n]+_|\[[^\]\n]+\]\((?:https?:\/\/|\/)[^)\s]*\))/g;
  let lastIndex = 0;
  let match;

  while ((match = tokenPattern.exec(text)) !== null) {
    parent.append(document.createTextNode(text.slice(lastIndex, match.index)));
    const token = match[0];
    let element;

    if (token.startsWith("`")) {
      element = document.createElement("code");
      element.textContent = token.slice(1, -1);
    } else if (token.startsWith("**") || token.startsWith("__")) {
      element = document.createElement("strong");
      renderInlineMarkdown(token.slice(2, -2), element, depth + 1);
    } else if (token.startsWith("~~")) {
      element = document.createElement("del");
      renderInlineMarkdown(token.slice(2, -2), element, depth + 1);
    } else if (token.startsWith("*") || token.startsWith("_")) {
      element = document.createElement("em");
      renderInlineMarkdown(token.slice(1, -1), element, depth + 1);
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]*)\)$/);
      const href = linkMatch?.[2];
      if (!linkMatch || !isSafeMarkdownUrl(href)) {
        parent.append(document.createTextNode(token));
        lastIndex = tokenPattern.lastIndex;
        continue;
      }
      element = document.createElement("a");
      element.href = href;
      element.target = "_blank";
      element.rel = "noopener noreferrer";
      renderInlineMarkdown(linkMatch[1], element, depth + 1);
    }

    parent.append(element);
    lastIndex = tokenPattern.lastIndex;
  }

  parent.append(document.createTextNode(text.slice(lastIndex)));
}

function isSafeMarkdownUrl(href) {
  try {
    const url = new URL(href, window.location.origin);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function parseMarkdownTableRow(line) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function isMarkdownTableDivider(line, columnCount) {
  const cells = parseMarkdownTableRow(line);
  return cells.length === columnCount && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdownTable(lines, parent) {
  const headers = parseMarkdownTableRow(lines[0]);
  const dividers = parseMarkdownTableRow(lines[1]);
  const wrapper = document.createElement("div");
  wrapper.className = "markdown-table-scroll";
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");

  headers.forEach((label, index) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.style.textAlign = getTableAlignment(dividers[index]);
    renderInlineMarkdown(label, cell);
    headRow.append(cell);
  });
  head.append(headRow);
  table.append(head);

  const body = document.createElement("tbody");
  lines.slice(2).forEach((line) => {
    const values = parseMarkdownTableRow(line);
    const row = document.createElement("tr");
    headers.forEach((_, index) => {
      const cell = document.createElement("td");
      cell.style.textAlign = getTableAlignment(dividers[index]);
      if (values[index]) renderInlineMarkdown(values[index], cell);
      row.append(cell);
    });
    body.append(row);
  });
  table.append(body);
  wrapper.append(table);
  parent.append(wrapper);
}

function getTableAlignment(divider) {
  const left = divider.startsWith(":");
  const right = divider.endsWith(":");
  if (left && right) return "center";
  if (right) return "right";
  return "left";
}

function renderMarkdown(text, parent) {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (/^```/.test(line.trim())) {
      const language = line.trim().slice(3).trim().split(/\s/, 1)[0];
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^```\s*$/.test(lines[index].trim())) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      if (/^[\w+-]+$/.test(language)) code.className = `language-${language}`;
      code.textContent = codeLines.join("\n");
      pre.append(code);
      parent.append(pre);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const element = document.createElement(`h${heading[1].length}`);
      renderInlineMarkdown(heading[2], element);
      parent.append(element);
      index += 1;
      continue;
    }

    if (/^\s*(---+|___+|\*\*\*+)\s*$/.test(line)) {
      parent.append(document.createElement("hr"));
      index += 1;
      continue;
    }

    if (line.includes("|") && index + 1 < lines.length) {
      const headers = parseMarkdownTableRow(line);
      if (headers.length > 1 && isMarkdownTableDivider(lines[index + 1], headers.length)) {
        const tableLines = [line, lines[index + 1]];
        index += 2;
        while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
          tableLines.push(lines[index]);
          index += 1;
        }
        renderMarkdownTable(tableLines, parent);
        continue;
      }
    }

    if (/^\s*>/.test(line)) {
      const quoteLines = [];
      while (index < lines.length && /^\s*>/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      const quote = document.createElement("blockquote");
      renderMarkdown(quoteLines.join("\n"), quote);
      parent.append(quote);
      continue;
    }

    const listMatch = line.match(/^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/);
    if (listMatch) {
      const ordered = Boolean(listMatch[2]);
      const list = document.createElement(ordered ? "ol" : "ul");
      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*(?:([-+*])|(\d+)\.)\s+(.+)$/);
        if (!itemMatch || Boolean(itemMatch[2]) !== ordered) break;
        const item = document.createElement("li");
        renderInlineMarkdown(itemMatch[3], item);
        list.append(item);
        index += 1;
      }
      parent.append(list);
      continue;
    }

    const paragraphLines = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim()
      && !/^(#{1,6})\s+/.test(lines[index])
      && !/^```/.test(lines[index].trim())
      && !/^\s*>/.test(lines[index])
      && !/^\s*(?:[-+*]|\d+\.)\s+/.test(lines[index])
      && !(lines[index].includes("|") && index + 1 < lines.length
        && parseMarkdownTableRow(lines[index]).length > 1
        && isMarkdownTableDivider(lines[index + 1], parseMarkdownTableRow(lines[index]).length))
      && !/^\s*(---+|___+|\*\*\*+)\s*$/.test(lines[index])) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = document.createElement("p");
    renderInlineMarkdown(paragraphLines.join(" "), paragraph);
    parent.append(paragraph);
  }
}

function addMessage(text, role = "assistant") {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "NC" : "✳";

  const body = document.createElement("div");
  body.className = "message-body";
  const author = document.createElement("div");
  author.className = "message-author";
  author.append(document.createTextNode(role === "user" ? "You " : "Ethos "));
  const time = document.createElement("time");
  time.textContent = "Just now";
  author.append(time);

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  if (role === "user") {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    bubble.append(paragraph);
  } else {
    bubble.classList.add("markdown-body");
    renderMarkdown(text, bubble);
  }
  body.append(author, bubble);
  article.append(avatar, body);
  elements.messages.insertBefore(article, elements.typing);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return bubble;
}

function renderTags(container, items, className) {
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("span");
    empty.className = "empty-tag";
    empty.textContent = "None selected";
    container.append(empty);
    return;
  }
  items.forEach((item) => {
    const tag = document.createElement("span");
    tag.className = `tag ${className}`;
    tag.textContent = item;
    container.append(tag);
  });
}

function renderProfile() {
  elements.mission.textContent = profile.mission || "Not added yet";
  elements.mission.classList.toggle("empty-copy", !profile.mission);
  renderTags(elements.exclusions, [...profile.exclusions], "exclusion");
  renderTags(elements.flags, [...profile.flags], "flag");
  elements.esg.textContent = profile.esg || "Not set";
  elements.risk.textContent = profile.risk || "Not set";
}

function fillProfile(policy) {
  profile.mission = policy.mission || "";
  profile.exclusions = new Set(policy.exclude_tags || []);
  profile.esg = "Not used (no ESG data)";
  profile.risk = policy.risk ? `${policy.risk[0].toUpperCase()}${policy.risk.slice(1)}` : "";
  renderProfile();
}

function handleMessage(message) {
  addMessage(message, "user");
  elements.suggestions.hidden = true;
  runAnalysis(message);
}

function renderAttachments() {
  elements.attachmentList.replaceChildren();
  profile.attachments.forEach((file, index) => {
    const pill = document.createElement("span");
    pill.className = "attachment-pill";
    const fileLabel = document.createElement("span");
    fileLabel.textContent = `${file.name} · ${formatBytes(file.size)}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${file.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      profile.attachments.splice(index, 1);
      renderAttachments();
      renderProfile();
    });
    pill.append(fileLabel, remove);
    elements.attachmentList.append(pill);
  });
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

const money = (n) => `$${Math.round(n).toLocaleString()}`;
const pct = (n) => (n == null ? "–" : `${(n * 100).toFixed(1)}%`);
const cell = (s) => String(s ?? "").replace(/\|/g, "/");

function whyChosen(holding, row) {
  if (!row || row.stage === "fund") return `Fund that gives the portfolio its ${holding.asset_class} share`;
  const news = row.news_checked ? `news OK (${row.news_checked} headlines)` : "no recent news found to check";
  const pick = row.selection_rank
    ? `; final rank #${row.selection_rank} of ${row.selection_of}: calmness ${row.volatility_score}, economy fit ${row.macro_fit_score} (${row.sector})`
    : "";
  return `Top ${row.rank} of ${row.ranked_of} on return per unit of risk; ${news}${pick}`
    + (holding.flagged ? `. Flagged, so held at half weight: ${row.reason}` : "");
}

function macroLine(m) {
  if (m.status !== "available" || m.stale) {
    return `**Economy (World Bank)**: ${m.description || "not available"}. The economy factor was neutral (0.5) for every company.`;
  }
  const c = m.components || {};
  const part = (key, label) => (c[key] ? `${label} ${c[key].raw_value.toFixed(1)}% (${c[key].observation_year})` : null);
  const facts = [part("gdp_growth", "GDP growth"), part("inflation", "inflation"), part("unemployment", "unemployment")]
    .filter(Boolean).join(", ");
  return `**Economy (World Bank, US)**: ${facts}, so the strength score is ${m.score.toFixed(2)} (${m.regime}). `
    + "Final picks weigh calmness (low volatility) and economy fit equally: cyclical sectors such as industrials "
    + "and financials fit a strong economy, defensive ones such as healthcare and utilities fit a weak one. "
    + "*A descriptive rule of thumb, not a forecast, and not backtested.*";
}

function resultMarkdown(res) {
  const byTicker = Object.fromEntries(res.screen.map((s) => [s.ticker, s]));
  const count = (status) => res.screen.filter((s) => s.status === status).length;
  const stocks = res.portfolio.filter((h) => byTicker[h.ticker]?.stage !== "fund").length;
  const holdings = res.portfolio.map((h) =>
    `| ${cell(h.name)} (${h.ticker}) | ${h.asset_class} | ${money(h.dollars)} | ${pct(h.annual_return)} | ${pct(h.volatility)} | ${cell(whyChosen(h, byTicker[h.ticker]))} |`);
  const dropped = res.screen.filter((s) => s.status === "excluded" || s.status === "flagged").map((s) =>
    `- **${s.status === "excluded" ? "Excluded" : "Flagged"}: ${cell(s.name)} (${s.ticker})**: ${s.reason}`
    + (s.evidence ? ` Evidence: ${s.url ? `[${s.evidence}](${s.url})` : s.evidence}` : ""));
  const p = res.policy;
  const inferred = (p.inferred_exclusions || []).map((x) => `- **${cell(x.theme)}**: ${x.reason}`);
  return [
    `**How I read your policy**: mission *${cell(p.mission)}*; excluding ${(p.exclude_tags || []).join(", ") || "nothing"}; `
      + `${p.risk} risk; at most ${pct(p.max_position)} in any one company.`,
    ...(inferred.length ? ["", "**Excluded because of your mission** (not stated in your policy):", "", ...inferred] : []),
    ...(res.macro_context ? ["", macroLine(res.macro_context)] : []),
    "",
    `**${res.companies_scanned} companies scanned**: ${count("excluded")} excluded, ${count("flagged")} flagged, `
      + `${count("not_selected")} not chosen, ${stocks} chosen, plus ${res.portfolio.length - stocks} funds.`,
    "",
    "**Where the $100,000 goes, and why**",
    "",
    "| Holding | Type | Amount | Annual return | Volatility | Why chosen |",
    "| :--- | :--- | ---: | ---: | ---: | :--- |",
    ...holdings,
    "",
    "**Excluded or flagged, and why**",
    "",
    ...(dropped.length ? dropped : ["- Nothing was excluded or flagged."]),
    ...(res.notes.length ? ["", ...res.notes.map((n) => `*${n}*`)] : []),
  ].join("\n");
}

function appendNotChosen(bubble, res) {
  const rows = res.screen.filter((s) => s.status === "not_selected");
  if (!rows.length) return;
  const details = document.createElement("details");
  details.className = "result-details";
  const summary = document.createElement("summary");
  summary.textContent = `See why the other ${rows.length} of ${res.companies_scanned} companies weren’t chosen`;
  details.append(summary);
  renderMarkdown([
    "| Company | Step | Reason |",
    "| :--- | :--- | :--- |",
    ...rows.map((s) => `| ${cell(s.name)} (${s.ticker}) | ${cell(s.stage)} | ${cell(s.reason)} |`),
  ].join("\n"), details);
  bubble.append(details);
}

let running = false;

async function runAnalysis(policy) {
  if (running) {
    addMessage("I’m still working on the last policy. Please wait for it to finish.");
    return;
  }
  running = true;
  addMessage("Reading your policy and running the analysis; a live run can take a few minutes.");
  elements.typing.hidden = false;
  try {
    // Open the page with ?sample=1 to get a canned response without API keys.
    const sample = new URLSearchParams(location.search).has("sample") ? "?sample=1" : "";
    const response = await fetch(`/api/run${sample}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policy }),
    });
    const res = await response.json();
    if (!response.ok) throw new Error(res.error || `Server returned ${response.status}`);
    fillProfile(res.policy);
    appendNotChosen(addMessage(resultMarkdown(res)), res);
    addMessage(res.memo);
  } catch (error) {
    addMessage(`The analysis could not run: ${error.message}`);
  } finally {
    elements.typing.hidden = true;
    running = false;
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message) return;
  elements.input.value = "";
  handleMessage(message);
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("[data-prompt]");
  if (!button) return;
  handleMessage(button.dataset.prompt);
});

elements.attachButton.addEventListener("click", () => elements.fileInput.click());
elements.fileInput.addEventListener("change", () => {
  const allowedExtensions = /\.(pdf|docx?|txt|csv)$/i;
  const rejected = [...elements.fileInput.files].filter((file) => !allowedExtensions.test(file.name));
  if (rejected.length) addMessage(`I couldn’t add ${rejected.map((file) => file.name).join(", ")}. Please choose a PDF, DOC, DOCX, TXT, or CSV file.`);
  [...elements.fileInput.files]
    .filter((file) => allowedExtensions.test(file.name))
    .forEach((file) => {
      if (!profile.attachments.some((attached) => attached.name === file.name && attached.size === file.size)) {
        profile.attachments.push(file);
      }
    });
  renderAttachments();
  renderProfile();
  elements.fileInput.value = "";
});

renderProfile();
