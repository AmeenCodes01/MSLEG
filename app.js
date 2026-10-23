const profile = {
  mission: "",
  exclusions: new Set(),
  flags: new Set(),
  esg: "",
  risk: "",
  attachments: [],
};

const exclusionOptions = [
  ["fossil fuel", "Fossil fuel expansion"],
  ["coal", "Fossil fuel expansion"],
  ["oil and gas", "Fossil fuel expansion"],
  ["weapons", "Weapons & defence"],
  ["armaments", "Weapons & defence"],
  ["tobacco", "Tobacco"],
  ["gambling", "Gambling"],
  ["alcohol", "Alcohol"],
  ["animal testing", "Animal testing"],
  ["adult entertainment", "Adult entertainment"],
  ["nuclear", "Nuclear energy"],
];

const flagOptions = [
  ["greenwashing", "Greenwashing"],
  ["labor", "Workers’ rights"],
  ["workers", "Workers’ rights"],
  ["human rights", "Human rights"],
  ["modern slavery", "Modern slavery"],
  ["deforestation", "Deforestation & biodiversity"],
  ["biodiversity", "Deforestation & biodiversity"],
  ["indigenous", "Indigenous rights"],
  ["water scarcity", "Water stewardship"],
  ["water use", "Water stewardship"],
  ["pollution", "Pollution & product harms"],
  ["corruption", "Corruption & tax conduct"],
  ["tax avoidance", "Corruption & tax conduct"],
  ["privacy", "Privacy & surveillance"],
  ["surveillance", "Privacy & surveillance"],
  ["governance", "Governance & lobbying"],
  ["lobbying", "Governance & lobbying"],
  ["controversies", "Material controversies"],
  ["animal welfare", "Animal welfare"],
];

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
  reviewButton: document.querySelector("#review-button"),
  reviewHint: document.querySelector(".review-hint"),
  dialog: document.querySelector("#review-dialog"),
  summary: document.querySelector("#review-summary"),
  consent: document.querySelector("#consent-checkbox"),
  confirm: document.querySelector("#confirm-button"),
};

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function addMessage(text, role = "assistant") {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  const safeText = escapeHtml(text).replace(/\n/g, "<br>");
  article.innerHTML = role === "user"
    ? `<div class="message-avatar" aria-hidden="true">NC</div><div class="message-body"><div class="message-author">You <time>Just now</time></div><div class="message-bubble"><p>${safeText}</p></div></div>`
    : `<div class="message-avatar" aria-hidden="true">✳</div><div class="message-body"><div class="message-author">Ethos <time>Just now</time></div><div class="message-bubble"><p>${safeText}</p></div></div>`;
  elements.messages.insertBefore(article, elements.typing);
  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function chooseTerms(text, options) {
  const lower = text.toLowerCase();
  return options.filter(([term]) => lower.includes(term)).map(([, label]) => label);
}

function updateProfile(message) {
  const lower = message.toLowerCase();
  const exclusions = chooseTerms(lower, exclusionOptions);
  const flags = chooseTerms(lower, flagOptions);
  exclusions.forEach((item) => profile.exclusions.add(item));
  flags.forEach((item) => profile.flags.add(item));

  if (/(mission|charity|trust|community|values|principles|impact|care about|stand for)/i.test(message)
      && !profile.mission) {
    profile.mission = message.trim();
  }

  const esgMatch = lower.match(/(?:esg(?: score)?|minimum(?: score)?|threshold)[^\d]{0,20}(\d{1,3})|(\d{1,3})\s*(?:\/\s*100|out of 100)/);
  if (esgMatch) {
    const score = Number(esgMatch[1] || esgMatch[2]);
    if (score <= 100) profile.esg = `${score}/100`;
  } else if (/(high|strict|strong)\s+(?:minimum\s+)?esg|high esg/i.test(lower)) {
    profile.esg = "70/100 (suggested)";
  }

  if (/\b(conservative|low)\s+risk\b/.test(lower)) profile.risk = "Conservative";
  else if (/\b(moderate|balanced|medium)\s+risk\b/.test(lower)) profile.risk = "Balanced";
  else if (/\b(aggressive|high)\s+risk\b/.test(lower)) profile.risk = "Growth-oriented";

  renderProfile();
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

  const hasCriteria = Boolean(profile.mission || profile.exclusions.size || profile.flags.size
    || profile.esg || profile.risk || profile.attachments.length);
  elements.reviewButton.disabled = !hasCriteria;
  elements.reviewHint.textContent = hasCriteria
    ? "You can review and edit your brief before analysis."
    : "Add at least one value or criterion to continue.";
}

function assistantReply(message) {
  const lower = message.toLowerCase();
  const missing = [];
  if (!profile.exclusions.size) missing.push("any industries your charity wants to exclude");
  if (!profile.flags.size) missing.push("controversies you want us to flag");
  if (!profile.esg) missing.push("a minimum ESG score (if you use one)");
  if (!profile.risk) missing.push("your preferred risk level");
  if (missing.length) {
    return `I’ve added what I could identify to your draft. To make the brief more useful, would you like to tell me ${missing.join(", ")}? You can leave any of these unset and review the brief whenever you’re ready.`;
  }
  if (lower.includes("greenwashing")) {
    return "Greenwashing is on your flag list. A useful screen can compare marketing claims with emissions data, transition plans, capital spending, regulatory findings, and credible third-party reporting. I’ve captured that as a flag, not a proven finding.";
  }
  return "Thanks, I’ve updated the draft profile on the right. Please check whether I interpreted your criteria correctly. When you’re ready, choose “Review analysis brief” to see the exact data categories and approve the demo analysis.";
}

function handleMessage(message) {
  addMessage(message, "user");
  updateProfile(message);
  elements.suggestions.hidden = true;
  elements.typing.hidden = false;
  window.setTimeout(() => {
    elements.typing.hidden = true;
    addMessage(assistantReply(message));
  }, 550);
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

function showReview() {
  const rows = [
    ["Mission & principles", profile.mission || "Not specified"],
    ["Industry exclusions", [...profile.exclusions].join(", ") || "None specified"],
    ["Controversy flags", [...profile.flags].join(", ") || "None specified"],
    ["Minimum ESG score", profile.esg || "Not specified"],
    ["Risk tolerance", profile.risk || "Not specified"],
    ["Attachments", profile.attachments.map((file) => file.name).join(", ") || "None"],
  ];
  elements.summary.replaceChildren();
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "summary-row";
    const heading = document.createElement("strong");
    heading.textContent = label;
    const content = document.createElement("span");
    content.className = label === "Attachments" ? "summary-files" : "";
    content.textContent = value;
    row.append(heading, content);
    elements.summary.append(row);
  });
  elements.consent.checked = false;
  elements.confirm.disabled = true;
  elements.dialog.showModal();
}

function showDemoResult() {
  elements.dialog.close();
  addMessage("Your brief is confirmed. This prototype has not sent your criteria or attachments to a backend, and it has not fetched live market, ESG, economic, news, or sentiment data. In the connected product, this is where sourced analysis and uncertainty would be returned for your review.");
  const recommendation = document.createElement("article");
  recommendation.className = "demo-result";
  recommendation.innerHTML = `<div class="result-label"><span>✳</span> DEMO RESPONSE · NO LIVE DATA</div><strong>Analysis is ready to connect</strong><p>Connect a backend to evaluate securities against your approved criteria. Any future recommendations should include dated data sources, model uncertainty, controversy evidence, and a clear explanation of why an investment fits—or fails—your charity’s policy.</p><div class="result-footer">No investment recommendation has been generated.</div>`;
  elements.messages.insertBefore(recommendation, elements.typing);
  elements.messages.scrollTop = elements.messages.scrollHeight;
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

elements.reviewButton.addEventListener("click", showReview);
elements.consent.addEventListener("change", () => {
  elements.confirm.disabled = !elements.consent.checked;
});
elements.confirm.addEventListener("click", showDemoResult);

renderProfile();
