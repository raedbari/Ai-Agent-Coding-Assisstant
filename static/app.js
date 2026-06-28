const WorkflowState = {
  INITIAL: "INITIAL",
  PROJECT_SELECTED: "PROJECT_SELECTED",
  SCANNING: "SCANNING",
  SCAN_DONE: "SCAN_DONE",
  ISSUE_SELECTED: "ISSUE_SELECTED",
  PROPOSING_FIX: "PROPOSING_FIX",
  FIX_PROPOSED: "FIX_PROPOSED",
  BUILDING_DIFF: "BUILDING_DIFF",
  DIFF_READY: "DIFF_READY",
  APPLYING_PATCH: "APPLYING_PATCH",
  VERIFY_DONE: "VERIFY_DONE",
  ERROR: "ERROR"
};

const steps = [
  { key: "select", label: "Select project" },
  { key: "scan", label: "Scan project" },
  { key: "issue", label: "Select issue" },
  { key: "fix", label: "Propose fix" },
  { key: "diff", label: "Review diff" },
  { key: "apply", label: "Apply patch" },
  { key: "verify", label: "Verify result" }
];

const INITIAL_LOG_TEXT = "No action started yet.";

const ToolStatus = {
  PASSED: "passed",
  FAILED: "failed",
  INTERRUPTED: "interrupted",
  TOOL_MISSING: "tool_missing",
  NO_TESTS: "no_tests"
};

let state = WorkflowState.INITIAL;
let selectedProjectId = null;
let selectedIssueId = null;
let selectedSonarIssueKey = null;

const currentStatus = document.getElementById("currentStatus");
const workflowSteps = document.getElementById("workflowSteps");

const projectSelect = document.getElementById("projectSelect");
const confirmProjectButton = document.getElementById("confirmProjectButton");
const changeProjectButton = document.getElementById("changeProjectButton");
const scanProjectButton = document.getElementById("scanProjectButton");

const projectSelectionArea = document.getElementById("projectSelectionArea");
const selectedProjectArea = document.getElementById("selectedProjectArea");
const selectedProjectText = document.getElementById("selectedProjectText");

const activityLog = document.getElementById("activityLog");
const toolRunsBox = document.getElementById("toolRunsBox");
const issuesBox = document.getElementById("issuesBox");
const repairPlanBox = document.getElementById("repairPlanBox");
const diffBox = document.getElementById("diffBox");
const finalResultBox = document.getElementById("finalResultBox");

function setState(nextState, statusText) {
  state = nextState;
  currentStatus.textContent = statusText;
  renderWorkflow();
  renderControls();
}

function getStepStatus(index) {
  const currentIndexByState = {
    INITIAL: 0,
    PROJECT_SELECTED: 1,
    SCANNING: 1,
    SCAN_DONE: 2,
    ISSUE_SELECTED: 3,
    PROPOSING_FIX: 3,
    FIX_PROPOSED: 4,
    BUILDING_DIFF: 4,
    DIFF_READY: 5,
    APPLYING_PATCH: 5,
    VERIFY_DONE: 6,
    ERROR: 0
  };

  const activeIndex = currentIndexByState[state] ?? 0;

  if (state === WorkflowState.ERROR && index === activeIndex) {
    return "failed";
  }

  if (index < activeIndex) {
    return "done";
  }

  if (index === activeIndex) {
    return "active";
  }

  return "locked";
}

function renderWorkflow() {
  workflowSteps.innerHTML = "";

  steps.forEach((step, index) => {
    const div = document.createElement("div");
    div.className = `step ${getStepStatus(index)}`;
    div.textContent = `${index + 1}. ${step.label}`;
    workflowSteps.appendChild(div);
  });
}

function renderControls() {
  const projectChosen = Boolean(selectedProjectId);
  const busyStates = [
    WorkflowState.SCANNING,
    WorkflowState.PROPOSING_FIX,
    WorkflowState.BUILDING_DIFF,
    WorkflowState.APPLYING_PATCH
  ];

  projectSelectionArea.classList.toggle("hidden", projectChosen);
  selectedProjectArea.classList.toggle("hidden", !projectChosen);

  confirmProjectButton.disabled = state !== WorkflowState.INITIAL;
  scanProjectButton.disabled = ![
    WorkflowState.PROJECT_SELECTED,
    WorkflowState.SCAN_DONE
  ].includes(state);

  changeProjectButton.disabled = busyStates.includes(state);
}

function addLog(message) {
  const now = new Date().toLocaleTimeString("en-GB");
  const previous = activityLog.textContent.trim();
  const line = `[${now}] ${message}`;

  activityLog.textContent =
    previous === INITIAL_LOG_TEXT ? line : `${activityLog.textContent}\n${line}`;

  activityLog.scrollTop = activityLog.scrollHeight;
}

function setBox(element, content, kind = "muted") {
  element.className = `box ${kind}`;
  element.textContent = content;
}

function clearBox(element, kind = "") {
  element.className = kind ? `box ${kind}` : "box";
  element.innerHTML = "";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json; charset=utf-8"
    },
    ...options
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text);
  }

  return response.json();
}

async function loadProjects() {
  try {
    addLog("Loading projects...");
    const projects = await api("/projects");

    projectSelect.innerHTML = "";

    for (const project of projects) {
      const option = document.createElement("option");
      option.value = project.id;
      option.textContent = `${project.name} (${project.id})`;
      projectSelect.appendChild(option);
    }

    addLog("Projects loaded.");
    setState(WorkflowState.INITIAL, "Select a project");
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to load projects");
    setBox(issuesBox, `Failed to load projects:\n${error.message}`, "error");
    addLog("Failed to load projects.");
  }
}
function confirmProject() {
  selectedProjectId = projectSelect.value;
  selectedIssueId = null;
  selectedSonarIssueKey = null;

  selectedProjectText.textContent = selectedProjectId;

  setBox(repairPlanBox, "No fix has been proposed yet.", "muted");
  setBox(diffBox, "No diff has been built yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  if (selectedProjectId === "sonar_demo") {
    scanProjectButton.classList.add("hidden");
    scanProjectButton.disabled = true;

    setBox(
      toolRunsBox,
      "This project uses SonarQube results. Internal scan is disabled for this demo.",
      "muted"
    );

    renderSonarEntryPoint();
    addLog(`Selected SonarQube project: ${selectedProjectId}`);
    setState(WorkflowState.PROJECT_SELECTED, "SonarQube project ready");
    return;
  }

  scanProjectButton.classList.remove("hidden");
  scanProjectButton.disabled = false;

  setBox(toolRunsBox, "No internal scan has been run yet.", "muted");
  setBox(issuesBox, "Run the internal scan to detect issues.", "muted");

  addLog(`Selected project: ${selectedProjectId}`);
  setState(WorkflowState.PROJECT_SELECTED, "Project ready to scan");
}

function changeProject() {
  selectedProjectId = null;
  selectedIssueId = null;
  selectedSonarIssueKey = null;

  scanProjectButton.classList.remove("hidden");
  scanProjectButton.disabled = false;

  addLog("Returned to project selection.");
  setState(WorkflowState.INITIAL, "Select a project");
}

function statusDisplayName(status) {
  const names = {
    passed: "Passed",
    failed: "Failed",
    interrupted: "Interrupted",
    tool_missing: "Tool missing",
    no_tests: "No tests"
  };

  return names[status] || status;
}

function statusKind(status) {
  if (status === ToolStatus.PASSED) {
    return "success";
  }

  if ([ToolStatus.INTERRUPTED, ToolStatus.NO_TESTS].includes(status)) {
    return "warning";
  }

  return "error";
}

function isBlockingToolRun(run) {
  return [ToolStatus.FAILED, ToolStatus.TOOL_MISSING].includes(run.status);
}

function isWarningToolRun(run) {
  return [ToolStatus.INTERRUPTED, ToolStatus.NO_TESTS].includes(run.status);
}

function compactToolFallback(run) {
  const output = run.output || run.raw_output || "";

  if (run.status === ToolStatus.PASSED) {
    return `${toolDisplayName(run.tool)} passed.`;
  }

  if (run.status === ToolStatus.NO_TESTS) {
    return "No tests were collected.";
  }

  if (run.status === ToolStatus.INTERRUPTED) {
    return `${toolDisplayName(run.tool)} did not complete.`;
  }

  if (output.includes("SyntaxError")) {
    return "Python syntax error found.";
  }

  if (output.includes("invalid-syntax")) {
    return "Invalid Python syntax found.";
  }

  if (output.includes("No module named")) {
    return `${toolDisplayName(run.tool)} is not installed in the active environment.`;
  }

  return `${toolDisplayName(run.tool)} ${statusDisplayName(run.status).toLowerCase()}.`;
}
function renderBadge(text, kind = "") {
  const badge = document.createElement("span");
  badge.className = kind ? `badge ${kind}` : "badge";
  badge.textContent = text;
  return badge;
}

function renderTechnicalDetails({ command, exitCode, rawText }) {
  const details = document.createElement("details");
  details.className = "technical-details";

  const summary = document.createElement("summary");
  summary.textContent = "Details";

  const pre = document.createElement("pre");
  pre.textContent = [
    command ? `Command: ${command}` : null,
    Number.isInteger(exitCode) ? `Exit code: ${exitCode}` : null,
    "",
    rawText || "No technical output."
  ].filter(Boolean).join("\n");

  details.appendChild(summary);
  details.appendChild(pre);

  return details;
}

function hasUsefulRawText(rawText, visibleText) {
  if (!rawText) {
    return false;
  }

  return rawText.trim() !== visibleText.trim();
}

function createToolRunCard(run, options = {}) {
  const showDetails = options.showDetails ?? false;
  const showAction = options.showAction ?? true;

  const card = document.createElement("div");
  card.className = `issue-card status-${statusKind(run.status)}`;

  const title = document.createElement("h3");
  title.textContent = `${toolDisplayName(run.tool)} — ${statusDisplayName(run.status)}`;

  const summary = document.createElement("p");
  summary.textContent = run.summary || compactToolFallback(run);

  card.appendChild(title);
  card.appendChild(summary);

  if (showAction && run.suggested_action) {
    const action = document.createElement("p");
    action.className = "action-text";
    action.textContent = `Action: ${run.suggested_action}`;
    card.appendChild(action);
  }

  const rawText = run.raw_output || run.output || "";

  if (showDetails && hasUsefulRawText(rawText, summary.textContent)) {
    card.appendChild(
      renderTechnicalDetails({
        command: run.command,
        exitCode: run.exit_code,
        rawText
      })
    );
  }

  return card;
}

function issueKind(issue) {
  if (issue.severity === "high") {
    return "error";
  }

  if (issue.severity === "medium") {
    return "warning";
  }

  return "muted";
}

function createIssueCard(issue, options = {}) {
  const showProposeButton = options.showProposeButton ?? true;
  const showDetails = options.showDetails ?? false;

  const card = document.createElement("div");
  card.className = `issue-card status-${issueKind(issue)}`;

  const title = document.createElement("h3");
  title.textContent = issue.summary || issue.title;

  const badges = document.createElement("div");
  badges.className = "badges";
  badges.appendChild(renderBadge(`Tool: ${toolDisplayName(issue.tool)}`));
  badges.appendChild(renderBadge(`Severity: ${issue.severity}`));

  if (issue.location) {
    badges.appendChild(renderBadge(`Location: ${issue.location}`));
  }

  card.appendChild(title);
  card.appendChild(badges);

  if (issue.suggested_action) {
    const action = document.createElement("p");
    action.className = "action-text";
    action.textContent = `Action: ${issue.suggested_action}`;
    card.appendChild(action);
  }

  const rawDetails = issue.raw_details || issue.details || "";

  if (showDetails && hasUsefulRawText(rawDetails, issue.summary || issue.title)) {
    card.appendChild(
      renderTechnicalDetails({
        command: issue.command,
        exitCode: null,
        rawText: rawDetails
      })
    );
  }

  if (showProposeButton) {
    const actions = document.createElement("div");
    actions.className = "action-row";

    const proposeButton = document.createElement("button");
    proposeButton.textContent = "Propose fix";
    proposeButton.onclick = () => selectIssueAndProposeFix(issue.id);

    actions.appendChild(proposeButton);
    card.appendChild(actions);
  }

  return card;
}

function getBlockingIssues(issues) {
  return issues.filter(issue => issue.severity === "high");
}

function getWarningIssues(issues) {
  return issues.filter(issue => issue.severity !== "high");
}

function getVerificationLevel(result) {
  const blockingIssues = getBlockingIssues(result.issues || []);
  const hasToolMissing = result.tool_runs.some(run => run.status === ToolStatus.TOOL_MISSING);
  const hasInterrupted = result.tool_runs.some(run => run.status === ToolStatus.INTERRUPTED);
  const hasNoTests = result.tool_runs.some(run => run.status === ToolStatus.NO_TESTS);
  const hasFailedCompile = result.tool_runs.some(run => {
    return run.tool === "compileall" && run.status === ToolStatus.FAILED;
  });

  if (hasFailedCompile || hasToolMissing || blockingIssues.length > 0) {
    return "error";
  }

  if (hasInterrupted || hasNoTests || result.issues.length > 0) {
    return "warning";
  }

  return "success";
}
function getVerificationTitle(level) {
  if (level === "success") {
    return "Patch applied successfully";
  }

  if (level === "warning") {
    return "Patch applied, review recommended";
  }

  return "Patch applied, but blocking checks failed";
}

function getVerificationMessage(result, level) {
  if (level === "success") {
    return "All configured verification checks passed.";
  }

  if (level === "warning") {
    return "The patch was applied. Some checks produced warnings or non-blocking findings.";
  }

  const blockingIssues = getBlockingIssues(result.issues || []);

  if (blockingIssues.length) {
    return blockingIssues[0].summary || blockingIssues[0].title;
  }

  const failedRun = result.tool_runs.find(isBlockingToolRun);

  if (failedRun) {
    return failedRun.summary || compactToolFallback(failedRun);
  }

  return "A blocking verification problem was detected.";
}

function getNextAction(result, level) {
  if (level === "success") {
    return "No action required.";
  }

  const compileRun = result.tool_runs.find(run => run.tool === "compileall");

  if (compileRun && compileRun.status === ToolStatus.FAILED) {
    return compileRun.suggested_action || "Fix the Python compile error, then scan again.";
  }

  const ruffIssue = (result.issues || []).find(issue => issue.tool === "ruff");

  if (ruffIssue) {
    return ruffIssue.suggested_action || "Review the Ruff issue and apply the suggested cleanup.";
  }

  const pytestRun = result.tool_runs.find(run => run.tool === "pytest");

  if (pytestRun && pytestRun.status === ToolStatus.NO_TESTS) {
    return "Add tests or confirm that this project intentionally has no tests.";
  }

  const interruptedRun = result.tool_runs.find(run => run.status === ToolStatus.INTERRUPTED);

  if (interruptedRun) {
    return interruptedRun.suggested_action || "Run verification again.";
  }

  if (level === "warning") {
    return "Review the warning, then decide whether another fix is needed.";
  }

  return "Review the blocking check before continuing.";
}

function renderVerificationSummary(result) {
  const list = document.createElement("ul");
  list.className = "compact-list";

  for (const run of result.tool_runs) {
    const item = document.createElement("li");
    item.textContent = `${toolDisplayName(run.tool)}: ${statusDisplayName(run.status)}`;
    list.appendChild(item);
  }

  return list;
}

function renderVerificationDetails(result) {
  const details = document.createElement("details");
  details.className = "technical-details";

  const summary = document.createElement("summary");
  summary.textContent = "Details";

  const pre = document.createElement("pre");

  const toolRunsText = result.tool_runs.map(run => {
    return [
      `${toolDisplayName(run.tool)} — ${statusDisplayName(run.status)}`,
      run.command ? `Command: ${run.command}` : null,
      Number.isInteger(run.exit_code) ? `Exit code: ${run.exit_code}` : null,
      run.raw_output || run.output || "No output."
    ].filter(Boolean).join("\n");
  }).join("\n\n---\n\n");

  const issuesText = (result.issues || []).map(issue => {
    return [
      `${issue.summary || issue.title}`,
      issue.location ? `Location: ${issue.location}` : null,
      issue.suggested_action ? `Action: ${issue.suggested_action}` : null,
      issue.raw_details || issue.details || ""
    ].filter(Boolean).join("\n");
  }).join("\n\n---\n\n");

  pre.textContent = [
    "Tool runs:",
    toolRunsText || "None.",
    "",
    "Issues:",
    issuesText || "None."
  ].join("\n");

  details.appendChild(summary);
  details.appendChild(pre);

  return details;
}

function renderFinalResult(result) {
  finalResultBox.innerHTML = "";

  const level = getVerificationLevel(result);
  finalResultBox.className = `box ${level}`;

  const title = document.createElement("h3");
  title.textContent = getVerificationTitle(level);
  finalResultBox.appendChild(title);

  const files = document.createElement("p");
  files.textContent = `Modified files: ${result.applied_files.join(", ") || "None"}`;
  finalResultBox.appendChild(files);

  const message = document.createElement("p");
  message.textContent = getVerificationMessage(result, level);
  finalResultBox.appendChild(message);

  const summaryTitle = document.createElement("h3");
  summaryTitle.textContent = "Verification summary";
  finalResultBox.appendChild(summaryTitle);

  finalResultBox.appendChild(renderVerificationSummary(result));

  const nextAction = document.createElement("p");
  nextAction.className = "action-text";
  nextAction.textContent = `Next action: ${getNextAction(result, level)}`;
  finalResultBox.appendChild(nextAction);

  finalResultBox.appendChild(renderVerificationDetails(result));
}

function renderToolRuns(toolRuns) {
  toolRunsBox.innerHTML = "";

  if (!toolRuns.length) {
    setBox(toolRunsBox, "No scan tools were executed.", "muted");
    return;
  }

  const hasBlockingFailure = toolRuns.some(isBlockingToolRun);
  const hasWarning = toolRuns.some(isWarningToolRun);

  if (hasBlockingFailure) {
    toolRunsBox.className = "box error";
  } else if (hasWarning) {
    toolRunsBox.className = "box warning";
  } else {
    toolRunsBox.className = "box success";
  }

  for (const run of toolRuns) {
    toolRunsBox.appendChild(
      createToolRunCard(run, {
        showDetails: false,
        showAction: true
      })
    );
  }
}

function renderIssues(issues) {
  issuesBox.innerHTML = "";

  if (!issues.length) {
    issuesBox.className = "box success";
    issuesBox.textContent = "No issues found.";
    return;
  }

  const blockingIssues = getBlockingIssues(issues);
  issuesBox.className = blockingIssues.length ? "box error" : "box warning";

  for (const issue of issues) {
    issuesBox.appendChild(
      createIssueCard(issue, {
        showProposeButton: true,
        showDetails: false
      })
    );
  }
}


function renderSonarEntryPoint() {
  issuesBox.innerHTML = "";
  issuesBox.className = "box";

  const text = document.createElement("p");
  text.textContent = "You can scan this project with the internal tools, or load existing SonarQube issues.";
  issuesBox.appendChild(text);

  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const button = document.createElement("button");
  button.textContent = "Load Sonar issues";
  button.onclick = loadSonarIssues;

  wrapper.appendChild(button);
  issuesBox.appendChild(wrapper);
}


async function loadSonarIssues() {
  selectedSonarIssueKey = null;

  setState(WorkflowState.SCANNING, "Loading Sonar issues");
  addLog("Loading SonarQube issues.");
  setBox(issuesBox, "Loading SonarQube issues...", "muted");
  setBox(repairPlanBox, "No Sonar prompt has been built yet.", "muted");
  setBox(diffBox, "No diff has been built yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(
  `/sonar/demo/issues?project_id=${encodeURIComponent(selectedProjectId)}`
);

    addLog(`${result.total} SonarQube issue(s) loaded.`);
    renderSonarIssues(result.issues || []);

    if (result.issues && result.issues.length) {
      setState(WorkflowState.SCAN_DONE, "Select a Sonar issue");
    } else {
      setState(WorkflowState.VERIFY_DONE, "No Sonar issues found");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to load Sonar issues");
    setBox(issuesBox, `Failed to load Sonar issues:\n${error.message}`, "error");
    addLog("Failed to load SonarQube issues.");
  }
}


function renderSonarIssues(issues) {
  issuesBox.innerHTML = "";

  if (!issues.length) {
    issuesBox.className = "box success";
    issuesBox.textContent = "No SonarQube issues found.";
    return;
  }

  const hasCritical = issues.some((issue) => issue.severity === "CRITICAL" || issue.severity === "BLOCKER");
  issuesBox.className = hasCritical ? "box error" : "box warning";

  const title = document.createElement("h3");
  title.textContent = "SonarQube issues";
  issuesBox.appendChild(title);

  for (const issue of issues) {
    issuesBox.appendChild(createSonarIssueCard(issue));
  }
}


function createSonarIssueCard(issue) {
  const card = document.createElement("div");
  card.className = "issue-card";

  const title = document.createElement("h4");
  title.textContent = `${issue.severity || "UNKNOWN"} · ${issue.rule_id || "unknown rule"}`;
  card.appendChild(title);

  const message = document.createElement("p");
  message.textContent = issue.message || "No message.";
  card.appendChild(message);

  const file = document.createElement("p");
  file.textContent = `File: ${issue.file_path || "Unknown file"}:${issue.line || issue.start_line || "?"}`;
  card.appendChild(file);

  const type = document.createElement("p");
  type.textContent = `Type: ${issue.type || "Unknown"} · Source: SonarQube`;
  card.appendChild(type);

  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const button = document.createElement("button");
  button.textContent = "Build Sonar prompt";
  button.onclick = () => buildSonarPrompt(issue.issue_key);

  wrapper.appendChild(button);
  card.appendChild(wrapper);

  return card;
}


async function buildSonarPrompt(issueKey) {
  selectedSonarIssueKey = issueKey;

  setState(WorkflowState.PROPOSING_FIX, "Building Sonar prompt");
  addLog(`Selected Sonar issue: ${issueKey}`);
  setBox(repairPlanBox, "Building Sonar prompt...", "muted");
  setBox(diffBox, "No diff has been built yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(`/sonar/demo/issues/${issueKey}/prompt`);

    addLog("Sonar prompt built.");
    renderSonarPrompt(result.issue, result.prompt);

    setState(WorkflowState.FIX_PROPOSED, "Sonar prompt ready");
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to build Sonar prompt");
    setBox(repairPlanBox, `Failed to build Sonar prompt:\n${error.message}`, "error");
    addLog("Failed to build Sonar prompt.");
  }
}


function renderSonarPrompt(issue, prompt) {
  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = "Sonar repair prompt";
  repairPlanBox.appendChild(title);

  const meta = document.createElement("p");
  meta.textContent = `${issue.severity || "UNKNOWN"} · ${issue.rule_id || "unknown rule"} · ${issue.file_path || "unknown file"}`;
  repairPlanBox.appendChild(meta);

  const pre = document.createElement("pre");
  pre.textContent = prompt;
  repairPlanBox.appendChild(pre);
}



async function scanProject() {
  setState(WorkflowState.SCANNING, "Scanning project");
  addLog("Project scan started.");
  setBox(toolRunsBox, "Running verification tools...", "muted");
  setBox(issuesBox, "Checking for issues...", "muted");

  try {
    const result = await api(`/projects/${selectedProjectId}/scan`, {
      method: "POST"
    });

    addLog("Project scan finished.");
    renderToolRuns(result.tool_runs);
    renderIssues(result.issues);

    if (result.issues.length) {
      addLog(`${result.issues.length} issue(s) found.`);
      setState(WorkflowState.SCAN_DONE, "Select an issue");
    } else {
      addLog("No issues found.");
      setState(WorkflowState.VERIFY_DONE, "No visible issues found");
      setBox(finalResultBox, "Scan completed. No issues found.", "success");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "Scan failed");
    setBox(issuesBox, `Scan failed:\n${error.message}`, "error");
    addLog("Project scan failed.");
  }
}

function renderRepairPlan(plan) {
  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = plan.summary || "Fix proposal";
  repairPlanBox.appendChild(title);

  const firstChange = Array.isArray(plan.proposed_file_changes) && plan.proposed_file_changes.length
    ? plan.proposed_file_changes[0]
    : null;

  if (firstChange) {
    const file = document.createElement("p");
    file.textContent = `File: ${firstChange.file_path || "Unknown file"}`;
    repairPlanBox.appendChild(file);

    const action = document.createElement("p");
    action.textContent = `Change: ${firstChange.instructions || firstChange.reason || "Apply the proposed change."}`;
    repairPlanBox.appendChild(action);

    if (firstChange.old_text !== null && firstChange.old_text !== undefined && firstChange.new_text !== null && firstChange.new_text !== undefined) {
      const replacement = document.createElement("p");
      replacement.textContent = `Replace: ${firstChange.old_text} → ${firstChange.new_text}`;
      repairPlanBox.appendChild(replacement);
    }
  } else {
    const fallback = document.createElement("p");
    fallback.textContent = plan.suspected_root_cause || "No concrete file change was proposed.";
    repairPlanBox.appendChild(fallback);
  }
}
async function selectIssueAndProposeFix(issueId) {
  selectedIssueId = issueId;

  setState(WorkflowState.PROPOSING_FIX, "Proposing fix");
  addLog(`Selected issue: ${issueId}`);
  addLog("Analyzing the issue and creating a repair plan.");

  setBox(repairPlanBox, "Creating repair plan...", "muted");
  setBox(diffBox, "No diff has been built yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${issueId}/propose-fix`,
      { method: "POST" }
    );

    addLog("Repair plan created.");

    const plan = result.repair_plan;

    renderRepairPlan(plan);
    setState(WorkflowState.FIX_PROPOSED, "Fix proposed");

    renderBuildDiffButton();
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to propose fix");
    setBox(repairPlanBox, `Failed to propose fix:\n${error.message}`, "error");
    addLog("Failed to propose fix.");
  }
}

function renderBuildDiffButton() {
  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const button = document.createElement("button");
  button.textContent = "Build diff";
  button.onclick = buildDiff;

  wrapper.appendChild(button);
  repairPlanBox.appendChild(wrapper);
}

function createPatchReviewCard(patch) {
  const card = document.createElement("div");
  card.className = patch.can_apply
    ? "issue-card status-success"
    : "issue-card status-warning";

  const title = document.createElement("h3");
  title.textContent = patch.file_path || "Unknown file";
  card.appendChild(title);

  const badges = document.createElement("div");
  badges.className = "badges";
  badges.appendChild(renderBadge(`Change: ${patch.change_type || "unknown"}`));
  badges.appendChild(renderBadge(patch.can_apply ? "Can apply" : "Cannot apply"));
  card.appendChild(badges);

  const details = document.createElement("details");
  details.open = true;
  details.className = "technical-details";

  const summary = document.createElement("summary");
  summary.textContent = "Diff";

  const pre = document.createElement("pre");
  pre.textContent = patch.diff || "No diff generated.";

  details.appendChild(summary);
  details.appendChild(pre);
  card.appendChild(details);

  return card;
}

function renderDiffReview(patches) {
  diffBox.innerHTML = "";

  if (!patches || !patches.length) {
    diffBox.className = "box warning";
    diffBox.textContent = "No diff was generated.";
    return false;
  }

  const canApplyAll = patches.every(patch => patch.can_apply);

  diffBox.className = canApplyAll ? "box diff" : "box warning";

  const title = document.createElement("h3");
  title.textContent = canApplyAll
    ? "Diff ready for review"
    : "Diff generated, but not all changes are safely applicable";

  diffBox.appendChild(title);

  for (const patch of patches) {
    diffBox.appendChild(createPatchReviewCard(patch));
  }

  if (!canApplyAll) {
    const warning = document.createElement("p");
    warning.className = "action-text";
    warning.textContent =
      "Review the proposed changes. The patch cannot be applied automatically until all changes are safe.";
    diffBox.appendChild(warning);

    return false;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const applyButton = document.createElement("button");
  applyButton.textContent = "Apply patch";
  applyButton.onclick = applyPatch;

  const rejectButton = document.createElement("button");
  rejectButton.textContent = "Reject";
  rejectButton.onclick = () => {
    addLog("Patch rejected.");
    setState(WorkflowState.DIFF_READY, "Patch rejected");
  };

  wrapper.appendChild(applyButton);
  wrapper.appendChild(rejectButton);

  diffBox.appendChild(wrapper);

  return true;
}

async function buildDiff() {
  setState(WorkflowState.BUILDING_DIFF, "Building diff");
  addLog("Building diff for review.");
  setBox(diffBox, "Building diff...", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${selectedIssueId}/build-diff`,
      { method: "POST" }
    );

    const canApply = renderDiffReview(result.patches || []);

    if (canApply) {
      addLog("Diff is ready. Waiting for developer approval.");
      setState(WorkflowState.DIFF_READY, "Review diff");
    } else {
      addLog("Diff was generated, but it is not fully applicable.");
      setState(WorkflowState.DIFF_READY, "Review diff warnings");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to build diff");
    setBox(diffBox, `Failed to build diff:\n${error.message}`, "error");
    addLog("Failed to build diff.");
  }
}

async function applyPatch() {
  const confirmed = confirm("Apply this patch to the project files?");

  if (!confirmed) {
    addLog("Patch application was cancelled.");
    return;
  }

  setState(WorkflowState.APPLYING_PATCH, "Applying patch and verifying");
  addLog("Applying patch.");
  setBox(finalResultBox, "Applying patch, then running verification checks...", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${selectedIssueId}/apply`,
      { method: "POST" }
    );

    addLog("Patch applied.");
    addLog("Verification scan finished.");

    renderFinalResult(result);

    const verificationLevel = getVerificationLevel(result);

    if (verificationLevel === "success") {
      setState(WorkflowState.VERIFY_DONE, "Patch applied and verification passed");
      addLog("Patch succeeded. All configured checks passed.");
    } else if (verificationLevel === "warning") {
      setState(WorkflowState.VERIFY_DONE, "Patch applied, review recommended");
      addLog("Patch applied, but review is recommended.");
    } else {
      setState(WorkflowState.VERIFY_DONE, "Patch applied, blocking issues remain");
      addLog("Patch applied, but blocking issues remain.");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to apply patch");
    setBox(finalResultBox, `Failed to apply patch:\n${error.message}`, "error");
    addLog("Failed to apply patch.");
  }
}

confirmProjectButton.addEventListener("click", confirmProject);
changeProjectButton.addEventListener("click", changeProject);
scanProjectButton.addEventListener("click", scanProject);

renderWorkflow();
renderControls();
loadProjects();