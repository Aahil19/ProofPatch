const $ = (selector) => document.querySelector(selector);
const pct = (value) => `${Math.round(value * 100)}%`;
const status = (value) => `<span class="outcome ${value}">${value}</span>`;

let data;
let filtered = [];

function setText(selector, value) { $(selector).textContent = value; }

function renderSummary() {
  const { summary } = data;
  const supervisor = summary.supervisor;
  const baseline = summary.single_agent;
  setText("#metric-supervisor", pct(supervisor.verified_rate));
  setText("#metric-delta", `+${Math.round((supervisor.verified_rate - baseline.verified_rate) * 100)} percentage points vs baseline`);
  setText("#metric-cases", summary.scenarios);
  setText("#metric-coverage", pct(Math.min(summary.reproduction_coverage, summary.trace_coverage)));
  setText("#metric-false", summary.false_verified);
  for (const [prefix, system] of [["supervisor", supervisor], ["baseline", baseline]]) {
    setText(`#${prefix}-rate`, pct(system.verified_rate));
    setText(`#${prefix}-verified`, `${system.verified} / ${summary.scenarios}`);
    setText(`#${prefix}-escalated`, system.escalated);
    setText(`#${prefix}-latency`, `${(system.median_latency_ms / 1000).toFixed(2)}s`);
    $(`#${prefix}-bar`).style.width = pct(system.verified_rate);
  }
  setText("#generated-at", `Snapshot ${new Date(data.generated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}`);
}

function traceFor(caseData) {
  const steps = [
    ["Reproducer", `${caseData.supervisor.baseline_failures} failure observed and reproduced`, "pass"],
    ["Investigator", caseData.description, "pass"],
    ["Repair agent", `Candidate 1 ${caseData.supervisor.attempts > 1 ? "failed verification" : "proposed"}`, caseData.supervisor.attempts > 1 ? "retry" : "pass"],
  ];
  if (caseData.supervisor.attempts > 1) steps.push(["Repair agent", "Candidate 2 proposed from verification feedback", caseData.supervisor.status]);
  steps.push(["Verifier", caseData.supervisor.status === "verified" ? "Focused and regression evidence passed" : "Evidence insufficient; escalated to a human", caseData.supervisor.status]);
  return steps;
}

function selectCase(caseData) {
  document.querySelectorAll("tbody tr").forEach((row) => row.classList.toggle("selected", row.dataset.id === caseData.id));
  setText("#detail-title", caseData.id);
  setText("#detail-description", caseData.description);
  $("#detail-trace").innerHTML = traceFor(caseData).map(([agent, message, result]) => `<li><strong>${agent}</strong><span>${message}</span><span class="mono">${result}</span></li>`).join("");
  $("#detail-grid").innerHTML = `
    <div><span>Project</span><strong>${caseData.project}</strong></div>
    <div><span>Category</span><strong>${caseData.category}</strong></div>
    <div><span>Attempts</span><strong>${caseData.supervisor.attempts} / 2</strong></div>
    <div><span>Regression</span><strong>${caseData.supervisor.regression_passes} / 10</strong></div>`;
}

function renderCases() {
  const project = $("#project-filter").value;
  const outcome = $("#outcome-filter").value;
  filtered = data.cases.filter((item) => (project === "all" || item.project === project) && (outcome === "all" || item.supervisor.status === outcome));
  $("#case-table").innerHTML = filtered.map((item) => `<tr data-id="${item.id}">
    <td class="mono">${item.id}</td><td>${item.project}</td><td>${status(item.supervisor.status)}</td>
    <td>${item.supervisor.attempts}</td><td>${status(item.single_agent.status)}</td></tr>`).join("");
  document.querySelectorAll("#case-table tr").forEach((row) => row.addEventListener("click", () => selectCase(data.cases.find((item) => item.id === row.dataset.id))));
  if (filtered.length) selectCase(filtered[0]);
}

function setupFilters() {
  const projects = [...new Set(data.cases.map((item) => item.project))];
  $("#project-filter").insertAdjacentHTML("beforeend", projects.map((project) => `<option value="${project}">${project}</option>`).join(""));
  $("#project-filter").addEventListener("change", renderCases);
  $("#outcome-filter").addEventListener("change", renderCases);
}

const demoEvents = [
  ["01", "Failure reproduced", "The same pytest node fails twice before source code is touched."],
  ["02", "First candidate rejected", "The focused test still fails. ProofPatch records the diff and feeds the exact evidence into one bounded retry."],
  ["03", "Second candidate verified", "The former failure passes and all ten selected regression tests retain their identities."],
  ["✓", "Review-ready, not auto-merged", "The verified patch waits behind an explicit human approval gate."],
];
let demoTimer;
function playDemo() {
  clearInterval(demoTimer);
  $("#demo-overlay").hidden = false;
  let index = 0;
  const show = () => {
    const [icon, title, copy] = demoEvents[index];
    $("#demo-stage").innerHTML = `<div class="demo-event"><div class="icon">${icon}</div><div><h3>${title}</h3><p>${copy}</p></div></div>`;
    $("#demo-progress").style.width = `${((index + 1) / demoEvents.length) * 100}%`;
    index = (index + 1) % demoEvents.length;
  };
  show();
  demoTimer = setInterval(show, 2600);
}

$("#play-demo").addEventListener("click", playDemo);
$("#close-demo").addEventListener("click", () => { clearInterval(demoTimer); $("#demo-overlay").hidden = true; });
$("#demo-overlay").addEventListener("click", (event) => { if (event.target === $("#demo-overlay")) $("#close-demo").click(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("#demo-overlay").hidden) $("#close-demo").click(); });

fetch("data/benchmark-results.json")
  .then((response) => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
  .then((payload) => { data = payload; renderSummary(); setupFilters(); renderCases(); })
  .catch((error) => { setText("#metric-delta", `Could not load results: ${error.message}`); });
