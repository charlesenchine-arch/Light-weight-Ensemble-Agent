"use strict";

const repositoryUrl =
  "https://github.com/charlesenchine-arch/Light-weight-Ensemble-Agent";

const elements = {
  form: document.querySelector("#calculator-form"),
  scenario: document.querySelector("#scenario"),
  baseline: document.querySelector("#baseline"),
  budget: document.querySelector("#budget"),
  copy: document.querySelector("#copy-result"),
  resultKicker: document.querySelector("#result-kicker"),
  leaCost: document.querySelector("#lea-cost"),
  baselineLabel: document.querySelector("#baseline-label"),
  baselineCost: document.querySelector("#baseline-cost"),
  leaBar: document.querySelector("#lea-bar"),
  baselineBar: document.querySelector("#baseline-bar"),
  savingValue: document.querySelector("#saving-value"),
  savingLabel: document.querySelector("#saving-label"),
  budgetAnswer: document.querySelector("#budget-answer"),
  catalogDate: document.querySelector("#catalog-date"),
  routeList: document.querySelector("#route-list"),
  dataError: document.querySelector("#data-error"),
  headlineSaving: document.querySelector("#headline-saving"),
  disclaimer: document.querySelector("#disclaimer"),
  sources: document.querySelector("#source-links"),
};

let catalog;

function appendOption(select, value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function formatModel(model) {
  return `${model.id} · ${model.provider_label}`;
}

function formatMoney(value) {
  const digits = value >= 1 ? 2 : 4;
  return `$${value.toFixed(digits)}`;
}

function selectedRows() {
  if (elements.scenario.value === "all") {
    return catalog.scenarios;
  }
  return catalog.scenarios.filter((row) => row.case === elements.scenario.value);
}

function stageCost(model, role) {
  const [inputTokens, outputTokens] = catalog.typical_tokens[role];
  return (
    (inputTokens * model.input_per_m + outputTokens * model.output_per_m) /
    1_000_000
  );
}

function baselineCost(rows, model) {
  return rows.reduce(
    (total, row) =>
      total + row.roles.reduce((sum, role) => sum + stageCost(model, role), 0),
    0,
  );
}

function addText(parent, tagName, text, className) {
  const node = document.createElement(tagName);
  node.textContent = text;
  if (className) {
    node.className = className;
  }
  parent.append(node);
  return node;
}

function renderRoutes(rows) {
  elements.routeList.replaceChildren();

  rows.forEach((row) => {
    const article = document.createElement("article");
    article.className = "route-card";
    const heading = document.createElement("header");
    addText(heading, "strong", row.case);
    const providerLabel = row.providers === 1 ? "provider" : "providers";
    addText(heading, "span", `${row.providers} ${providerLabel} · ${formatMoney(row.lea_usd)}`);
    article.append(heading);

    const stages = document.createElement("div");
    stages.className = "route-steps";
    row.roles.forEach((role, index) => {
      const item = document.createElement("span");
      item.className = "route-step";
      addText(item, "b", role);
      addText(item, "span", `${String(index + 1).padStart(2, "0")} · ${row.route[index]}`);
      stages.append(item);
    });
    article.append(stages);
    elements.routeList.append(article);
  });
}

function syncUrl() {
  const url = new URL(window.location.href);
  const values = {
    scenario: elements.scenario.value,
    baseline: elements.baseline.value,
    budget: elements.budget.value,
  };
  Object.entries(values).forEach(([key, value]) => {
    if (
      (key === "scenario" && value === "all") ||
      (key === "baseline" && value === catalog.default_baseline) ||
      (key === "budget" && Number(value) === 1)
    ) {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });
  window.history.replaceState(null, "", url);
}

function calculate() {
  const rows = selectedRows();
  const model = catalog.models.find((item) => item.id === elements.baseline.value);
  if (!model || rows.length === 0) {
    return;
  }

  const lea = rows.reduce((sum, row) => sum + row.lea_usd, 0);
  const baseline = baselineCost(rows, model);
  const difference = baseline === 0 ? 0 : ((baseline - lea) / baseline) * 100;
  const budget = Math.max(0, Number(elements.budget.value) || 0);
  const scale = Math.max(lea, baseline, 0.000001);
  const runCount = lea > 0 ? Math.floor((budget + Number.EPSILON) / lea) : 0;

  elements.resultKicker.textContent =
    rows.length === catalog.scenarios.length
      ? `All ${catalog.scenarios.length} benchmark scenarios`
      : rows[0].case;
  elements.leaCost.textContent = formatMoney(lea);
  elements.baselineLabel.textContent = `${model.id} baseline`;
  elements.baselineCost.textContent = formatMoney(baseline);
  elements.leaBar.style.width = `${Math.max(2, (lea / scale) * 100)}%`;
  elements.baselineBar.style.width = `${Math.max(2, (baseline / scale) * 100)}%`;

  if (difference >= 0) {
    elements.savingValue.textContent = `${difference.toFixed(1)}%`;
    elements.savingLabel.textContent = "lower estimated catalog cost";
  } else {
    elements.savingValue.textContent = `${Math.abs(difference).toFixed(1)}%`;
    elements.savingLabel.textContent = "higher estimated catalog cost";
  }

  const unit = rows.length === 1 ? "run" : "complete benchmark set";
  const plural = runCount === 1 ? "" : "s";
  const formattedBudget = `$${budget.toFixed(2)}`;
  elements.budgetAnswer.textContent =
    runCount > 0
      ? `A ${formattedBudget} budget fits about ${runCount} ${unit}${plural} at this estimate.`
      : `A ${formattedBudget} budget does not cover one ${unit} at this estimate.`;

  renderRoutes(rows);
  syncUrl();
}

function renderSources() {
  elements.sources.replaceChildren();
  Object.entries(catalog.pricing_sources).forEach(([provider, url]) => {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = `${provider} pricing ↗`;
    elements.sources.append(link);
  });
}

function restoreQuery() {
  const params = new URLSearchParams(window.location.search);
  const scenario = params.get("scenario");
  const baseline = params.get("baseline");
  const budget = Number(params.get("budget"));

  if (scenario && [...elements.scenario.options].some((item) => item.value === scenario)) {
    elements.scenario.value = scenario;
  }
  if (baseline && [...elements.baseline.options].some((item) => item.value === baseline)) {
    elements.baseline.value = baseline;
  }
  if (Number.isFinite(budget) && budget >= 0.01 && budget <= 100) {
    elements.budget.value = budget.toFixed(2);
  }
}

async function copyComparison() {
  const rows = selectedRows();
  const label = rows.length === 1 ? rows[0].case : "four fixed coding scenarios";
  const text = `${elements.savingValue.textContent} ${elements.savingLabel.textContent} for ${label} in the LEA catalog estimate. Explore it: ${window.location.href} — Source: ${repositoryUrl}`;
  try {
    await navigator.clipboard.writeText(text);
    elements.copy.textContent = "Copied — share it";
  } catch (_error) {
    elements.copy.textContent = "Copy unavailable — use the URL";
  }
  window.setTimeout(() => {
    elements.copy.textContent = "Copy this comparison";
  }, 2400);
}

async function initialise() {
  try {
    const response = await fetch("data.json", { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`Benchmark data returned ${response.status}`);
    }
    catalog = await response.json();

    appendOption(elements.scenario, "all", "All four scenarios");
    catalog.scenarios.forEach((row) => appendOption(elements.scenario, row.case, row.case));
    catalog.models
      .slice()
      .sort((left, right) => left.id.localeCompare(right.id))
      .forEach((model) => appendOption(elements.baseline, model.id, formatModel(model)));
    elements.baseline.value = catalog.default_baseline;
    elements.catalogDate.textContent = `Catalog checked ${catalog.catalog_as_of}`;
    elements.headlineSaving.textContent = `${catalog.summary.savings_percent.toFixed(1)}%`;
    elements.disclaimer.textContent = catalog.disclaimer;
    renderSources();
    restoreQuery();
    calculate();

    elements.form.addEventListener("input", calculate);
    elements.form.addEventListener("change", calculate);
    elements.copy.addEventListener("click", copyComparison);
  } catch (error) {
    elements.dataError.hidden = false;
    elements.form.setAttribute("aria-disabled", "true");
    console.error("LEA cost lab data failed to load", error);
  }
}

initialise();
