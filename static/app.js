const WorkflowState = {
  INITIAL: "INITIAL",
  PROJECT_SELECTED: "PROJECT_SELECTED",
  STARTING_AGENT: "STARTING_AGENT",
  REVIEW_REQUIRED: "REVIEW_REQUIRED",
  RESUMING_AGENT: "RESUMING_AGENT",
  COMPLETED_PUSHED: "COMPLETED_PUSHED",
  COMPLETED_REJECTED: "COMPLETED_REJECTED",
  NO_ACTIONABLE_ISSUES: "NO_ACTIONABLE_ISSUES",
  COMPLETED: "COMPLETED",
  ERROR: "ERROR"
};

const steps = [
  { key: "select", label: "Select project" },
  { key: "start", label: "Start agent" },
  { key: "analyze", label: "Analyze issues" },
  { key: "review", label: "Human review" },
  { key: "apply", label: "Apply patch" },
  { key: "deploy", label: "CI/CD deploy" }
];

const INITIAL_LOG_TEXT = "No action started yet.";

let state = WorkflowState.INITIAL;
let selectedProjectId = null;
let currentThreadId = null;
let currentReviewPayload = null;
let currentAgentOutput = null;
let currentStreamController = null;

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
  if (state === WorkflowState.ERROR) {
    return index === 0 ? "failed" : "locked";
  }

  if (state === WorkflowState.NO_ACTIONABLE_ISSUES) {
    if (index <= 2) {
      return "done";
    }

    return "locked";
  }

  if (state === WorkflowState.COMPLETED_REJECTED) {
    if (index <= 3) {
      return "done";
    }

    return "locked";
  }

  const currentIndexByState = {
    INITIAL: 0,
    PROJECT_SELECTED: 1,
    STARTING_AGENT: 1,
    REVIEW_REQUIRED: 3,
    RESUMING_AGENT: 4,
    COMPLETED_PUSHED: 5,
    COMPLETED: 5
  };

  const activeIndex = currentIndexByState[state] ?? 0;

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
    WorkflowState.STARTING_AGENT,
    WorkflowState.RESUMING_AGENT
  ];

  projectSelectionArea.classList.toggle("hidden", projectChosen);
  selectedProjectArea.classList.toggle("hidden", !projectChosen);

  confirmProjectButton.disabled = state !== WorkflowState.INITIAL;

  scanProjectButton.disabled =
    !projectChosen ||
    busyStates.includes(state) ||
    state === WorkflowState.REVIEW_REQUIRED;

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

function createElement(tag, className = "", text = "") {
  const element = document.createElement(tag);

  if (className) {
    element.className = className;
  }

  if (text) {
    element.textContent = text;
  }

  return element;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...(options.headers || {})
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

async function streamApi(path, body, onEvent) {
  currentStreamController = new AbortController();

  const response = await fetch(path, {
    method: "POST",
    cache: "no-store",
    signal: currentStreamController.signal,
    headers: body
      ? { "Content-Type": "application/json; charset=utf-8" }
      : {},
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Stream request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming response does not contain a readable body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();

      if (!trimmed) {
        continue;
      }

      const event = JSON.parse(trimmed);
      onEvent(event);
    }
  }

  const rest = buffer.trim();

  if (rest) {
    onEvent(JSON.parse(rest));
  }

  currentStreamController = null;
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
  currentThreadId = null;
  currentReviewPayload = null;
  currentAgentOutput = null;

  selectedProjectText.textContent = selectedProjectId;

  scanProjectButton.classList.remove("hidden");
  scanProjectButton.disabled = false;
  scanProjectButton.textContent = "Start agent run";
  scanProjectButton.onclick = startAgentRun;

  setBox(
    toolRunsBox,
    "Agent stream has not started yet.",
    "muted"
  );

  setBox(issuesBox, "Start the agent to collect SonarQube issue context.", "muted");
  setBox(repairPlanBox, "No repair summary yet.", "muted");
  setBox(diffBox, "No diff is waiting for review.", "muted");
  setBox(finalResultBox, "No final result yet.", "muted");

  addLog(`Selected project: ${selectedProjectId}`);
  setState(WorkflowState.PROJECT_SELECTED, "Project ready for agent run");
}

function changeProject() {
  if (currentStreamController) {
    currentStreamController.abort();
    currentStreamController = null;
  }

  selectedProjectId = null;
  currentThreadId = null;
  currentReviewPayload = null;
  currentAgentOutput = null;

  scanProjectButton.textContent = "Start agent run";
  scanProjectButton.onclick = startAgentRun;

  setBox(toolRunsBox, "Agent stream has not started yet.", "muted");
  setBox(issuesBox, "Confirm the project, then start the agent.", "muted");
  setBox(repairPlanBox, "No repair summary yet.", "muted");
  setBox(diffBox, "No diff is waiting for review.", "muted");
  setBox(finalResultBox, "No final result yet.", "muted");

  addLog("Returned to project selection.");
  setState(WorkflowState.INITIAL, "Select a project");
}

function renderBadge(text, kind = "") {
  const badge = document.createElement("span");
  badge.className = kind ? `badge ${kind}` : "badge";
  badge.textContent = text;
  return badge;
}

function resetAgentBoxes() {
  clearBox(toolRunsBox);
  clearBox(issuesBox);
  clearBox(repairPlanBox);
  clearBox(diffBox);
  clearBox(finalResultBox);

  const streamTitle = createElement("h3", "", "Agent execution stream");
  toolRunsBox.appendChild(streamTitle);

  setBox(issuesBox, "Waiting for selected SonarQube issues...", "muted");
  setBox(repairPlanBox, "Waiting for generated repair summary...", "muted");
  setBox(diffBox, "Waiting for human-review diff...", "muted");
  setBox(finalResultBox, "Waiting for final result...", "muted");
}

function appendStreamEvent(message, kind = "muted") {
  if (toolRunsBox.textContent.trim() === "Agent stream has not started yet.") {
    clearBox(toolRunsBox);
  }

  toolRunsBox.className = "box";
  const event = createElement("div", `stream-event ${kind}`, message);
  toolRunsBox.appendChild(event);
  toolRunsBox.scrollTop = toolRunsBox.scrollHeight;
}

function formatNodeMessage(data) {
  const node = data.node || "graph";

  if (data.error) {
    return `${node}: ${data.error}`;
  }

  if (data.selected_issues_count !== undefined) {
    return `${node}: selected ${data.selected_issues_count} actionable issue(s).`;
  }

  if (data.issues_count !== undefined) {
    return `${node}: loaded ${data.issues_count} SonarQube issue(s).`;
  }

  if (data.fix) {
    return `${node}: generated fix summary.`;
  }

  if (data.diff_validation) {
    return `${node}: diff validation ${data.diff_validation.status}.`;
  }

  if (data.approval_status) {
    return `${node}: approval status ${data.approval_status}.`;
  }

  if (data.apply_result) {
    return `${node}: apply result ${data.apply_result.status}.`;
  }

  return `${node}: completed.`;
}

function handleAgentStreamEvent(event) {
  const type = event.event;
  const data = event.data || {};

  if (type === "run_started") {
    currentThreadId = data.thread_id;
    appendStreamEvent(`Run started. Thread: ${currentThreadId}`, "status-muted");
    addLog(`Agent run started: ${currentThreadId}`);
    return;
  }

  if (type === "node_update") {
    appendStreamEvent(formatNodeMessage(data), data.error ? "status-error" : "status-muted");
    renderNodeUpdate(data);
    return;
  }

  if (type === "review_required") {
    currentThreadId = data.thread_id;
    currentReviewPayload = data.review_payload;
    appendStreamEvent("Human review required.", "status-warning");
    addLog("Agent paused for human review.");
    renderReviewPayload(currentReviewPayload);
    setState(WorkflowState.REVIEW_REQUIRED, "Human review required");
    return;
  }

  if (type === "completed") {
    currentThreadId = data.thread_id;
    currentAgentOutput = data.output || {};
    appendStreamEvent("Agent run completed.", "status-success");
    renderCompletedOutput(currentAgentOutput);
    return;
  }

  if (type === "error") {
    appendStreamEvent(`Error: ${data.message}`, "status-error");
    setBox(finalResultBox, `Agent stream failed:\n${data.message}`, "error");
    setState(WorkflowState.ERROR, "Agent failed");
    addLog("Agent stream failed.");
    return;
  }

  if (type === "done") {
    addLog(`Stream closed with status: ${data.status}`);
  }
}

function renderNodeUpdate(data) {
  if (data.selected_issues_count === 0) {
    issuesBox.innerHTML = "";
    issuesBox.className = "box success";

    const title = createElement("h3", "", "No selected issues");
    issuesBox.appendChild(title);

    const message = createElement(
      "p",
      "",
      "The agent checked this project and found no actionable SonarQube issues."
    );
    issuesBox.appendChild(message);
  }

  if (Array.isArray(data.selected_issues) && data.selected_issues.length) {
    renderSelectedIssues(data.selected_issues);
  }

  if (data.fix) {
    renderFixSummary(data.fix);
  }

  if (data.apply_result) {
    renderApplyResult(data.apply_result);
  }

  if (data.diff_validation && data.diff_validation.success === false) {
    setBox(
      diffBox,
      `Diff validation failed before review:\n${data.diff_validation.message || "Unknown validation error."}`,
      "error"
    );
  }

  if (data.error) {
    setBox(finalResultBox, data.error, "error");
  }
}

function renderSelectedIssues(issues) {
  issuesBox.innerHTML = "";
  issuesBox.className = "box warning";

  const title = createElement("h3", "", "Selected SonarQube issues");
  issuesBox.appendChild(title);

  for (const issue of issues) {
    const card = createElement("div", "issue-card");

    const heading = createElement(
      "h4",
      "",
      `${issue.severity || "UNKNOWN"} · ${issue.rule_id || "unknown rule"}`
    );
    card.appendChild(heading);

    const message = createElement("p", "", issue.message || "No message.");
    card.appendChild(message);

    const file = createElement(
      "p",
      "",
      `File: ${issue.file_path || "Unknown file"}:${issue.line || "?"}`
    );
    card.appendChild(file);

    issuesBox.appendChild(card);
  }
}

function renderFixSummary(fix) {
  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box";

  const title = createElement("h3", "", "Repair summary");
  repairPlanBox.appendChild(title);

  const summary = createElement("p", "", fix.summary || "No summary was generated.");
  repairPlanBox.appendChild(summary);

  const badges = createElement("div", "badges");
  badges.appendChild(renderBadge(`Risk: ${fix.risk || "unknown"}`, "status-warning"));

  const files = Array.isArray(fix.changed_files) ? fix.changed_files : [];

  badges.appendChild(renderBadge(`Files: ${files.length}`, "status-muted"));
  repairPlanBox.appendChild(badges);

  if (files.length) {
    const list = createElement("ul", "compact-list");

    for (const file of files) {
      const li = createElement("li", "", file);
      list.appendChild(li);
    }

    repairPlanBox.appendChild(list);
  }
}

function renderReviewPayload(payload) {
  diffBox.innerHTML = "";
  diffBox.className = "box warning";

  const title = createElement("h3", "", "Human diff review required");
  diffBox.appendChild(title);

  const summary = createElement("p", "", payload.summary || "No summary provided.");
  diffBox.appendChild(summary);

  const badges = createElement("div", "badges");
  badges.appendChild(renderBadge(`Project: ${payload.project_id || selectedProjectId}`));
  badges.appendChild(renderBadge(`Risk: ${payload.risk || "unknown"}`, "status-warning"));
  diffBox.appendChild(badges);

  const changedFiles = Array.isArray(payload.changed_files)
    ? payload.changed_files
    : [];

  if (changedFiles.length) {
    const files = createElement("p", "", `Changed files: ${changedFiles.join(", ")}`);
    diffBox.appendChild(files);
  }

  const pre = createElement("pre", "diff");
  pre.textContent = payload.diff || "No diff returned.";
  diffBox.appendChild(pre);

  const wrapper = createElement("div", "action-row");

  const approveButton = createElement("button", "", "Approve and apply patch");
  approveButton.onclick = approveCurrentReview;

  const rejectButton = createElement("button", "secondary-button", "Reject");
  rejectButton.onclick = rejectCurrentReview;

  wrapper.appendChild(approveButton);
  wrapper.appendChild(rejectButton);
  diffBox.appendChild(wrapper);

  setBox(finalResultBox, "Waiting for your approval decision.", "muted");
}

async function startAgentRun() {
  if (!selectedProjectId) {
    setBox(finalResultBox, "Select a project first.", "error");
    return;
  }

  currentThreadId = null;
  currentReviewPayload = null;
  currentAgentOutput = null;

  setState(WorkflowState.STARTING_AGENT, "Starting agent run");
  addLog(`Starting agent run for project: ${selectedProjectId}`);

  resetAgentBoxes();

  try {
    await streamApi(
      `/agent/projects/${encodeURIComponent(selectedProjectId)}/start/stream`,
      null,
      handleAgentStreamEvent
    );
  } catch (error) {
    addLog("Streaming start failed. Falling back to non-streaming endpoint.");
    appendStreamEvent(`Streaming failed: ${error.message}`, "status-warning");
    await startAgentRunWithoutStreaming();
  }
}

async function startAgentRunWithoutStreaming() {
  try {
    const result = await api(
      `/agent/projects/${encodeURIComponent(selectedProjectId)}/start`,
      { method: "POST" }
    );

    currentThreadId = result.thread_id;

    if (result.status === "interrupted") {
      currentReviewPayload = result.review_payload;
      renderReviewPayload(currentReviewPayload);
      setState(WorkflowState.REVIEW_REQUIRED, "Human review required");
      return;
    }

    renderCompletedOutput(result.output || {});
  } catch (error) {
    setState(WorkflowState.ERROR, "Agent start failed");
    setBox(finalResultBox, `Agent start failed:\n${error.message}`, "error");
    addLog("Agent start failed.");
  }
}

async function approveCurrentReview() {
  if (!currentThreadId || !currentReviewPayload) {
    setBox(finalResultBox, "No active review thread is available.", "error");
    return;
  }

  const confirmed = confirm("Approve this diff and apply the patch to GitHub?");

  if (!confirmed) {
    addLog("Approval cancelled.");
    return;
  }

  await resumeAgentRun(true, "Approved from web UI.");
}

async function rejectCurrentReview() {
  if (!currentThreadId || !currentReviewPayload) {
    setBox(finalResultBox, "No active review thread is available.", "error");
    return;
  }

  await resumeAgentRun(false, "Rejected from web UI.");
}

async function resumeAgentRun(approved, reason) {
  setState(
    WorkflowState.RESUMING_AGENT,
    approved ? "Applying approved patch" : "Rejecting proposed patch"
  );

  addLog(approved ? "Approving agent diff." : "Rejecting agent diff.");

  setBox(
    finalResultBox,
    approved
      ? "Applying patch to GitHub and waiting for result..."
      : "Rejecting patch...",
    "muted"
  );

  try {
    await streamApi(
      `/agent/threads/${encodeURIComponent(currentThreadId)}/resume/stream`,
      {
        approved,
        reason
      },
      handleAgentStreamEvent
    );
  } catch (error) {
    addLog("Streaming resume failed. Falling back to non-streaming endpoint.");
    appendStreamEvent(`Resume streaming failed: ${error.message}`, "status-warning");
    await resumeAgentRunWithoutStreaming(approved, reason);
  }
}

async function resumeAgentRunWithoutStreaming(approved, reason) {
  try {
    const result = await api(
      `/agent/threads/${encodeURIComponent(currentThreadId)}/resume`,
      {
        method: "POST",
        body: JSON.stringify({
          approved,
          reason
        })
      }
    );

    renderCompletedOutput(result.output || {});
  } catch (error) {
    setState(WorkflowState.ERROR, "Agent resume failed");
    setBox(finalResultBox, `Agent resume failed:\n${error.message}`, "error");
    addLog("Agent resume failed.");
  }
}

function renderNoActionableIssues() {
  issuesBox.innerHTML = "";
  issuesBox.className = "box success";

  const issuesTitle = createElement("h3", "", "No actionable issues");
  issuesBox.appendChild(issuesTitle);

  const issuesMessage = createElement(
    "p",
    "",
    "The agent did not find SonarQube issues that match this selected project or require a repair."
  );
  issuesBox.appendChild(issuesMessage);

  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box muted";

  const repairTitle = createElement("h3", "", "Repair skipped");
  repairPlanBox.appendChild(repairTitle);

  const repairMessage = createElement(
    "p",
    "",
    "No repair summary was generated because there were no actionable issues."
  );
  repairPlanBox.appendChild(repairMessage);

  diffBox.innerHTML = "";
  diffBox.className = "box muted";

  const diffTitle = createElement("h3", "", "Human review not required");
  diffBox.appendChild(diffTitle);

  const diffMessage = createElement(
    "p",
    "",
    "No diff was generated, so there is nothing to approve or reject."
  );
  diffBox.appendChild(diffMessage);

  finalResultBox.innerHTML = "";
  finalResultBox.className = "box success";

  const finalTitle = createElement("h3", "", "No actionable issues");
  finalResultBox.appendChild(finalTitle);

  const finalMessage = createElement(
    "p",
    "",
    "The agent did not find actionable SonarQube issues for this project."
  );
  finalResultBox.appendChild(finalMessage);

  setState(WorkflowState.NO_ACTIONABLE_ISSUES, "No actionable issues");
  addLog("No actionable issues found.");
}

function renderCompletedOutput(output) {
  currentAgentOutput = output || {};

  if (output.error) {
    setBox(finalResultBox, `Agent completed with error:\n${output.error}`, "error");
    setState(WorkflowState.ERROR, "Agent completed with error");
    return;
  }

  const applyResult = output.apply_result;

  if (applyResult) {
    renderApplyResult(applyResult);

    if (applyResult.success === true) {
      setState(WorkflowState.COMPLETED_PUSHED, "Patch pushed to GitHub");
      addLog("Patch committed and pushed to GitHub.");
    } else {
      setState(WorkflowState.ERROR, "Patch apply failed");
      addLog("Patch apply failed.");
    }

    return;
  }

  if (output.approval_status === "rejected") {
    finalResultBox.innerHTML = "";
    finalResultBox.className = "box warning";

    const title = createElement("h3", "", "Patch rejected");
    finalResultBox.appendChild(title);

    const message = createElement("p", "", "No files were changed.");
    finalResultBox.appendChild(message);

    setState(WorkflowState.COMPLETED_REJECTED, "Patch rejected");
    addLog("Patch rejected.");
    return;
  }

 const fix = output.fix || {};
 const changedFiles = Array.isArray(fix.changed_files) ? fix.changed_files : [];

if (!fix.summary && !changedFiles.length) {
  renderNoActionableIssues();
  return;
}

  finalResultBox.innerHTML = "";
  finalResultBox.className = "box success";

  const title = createElement("h3", "", "Agent completed");
  finalResultBox.appendChild(title);

  const message = createElement("p", "", "The agent run completed.");
  finalResultBox.appendChild(message);

  setState(WorkflowState.COMPLETED, "Agent completed");
}

function renderApplyResult(result) {
  finalResultBox.innerHTML = "";

  const success = result.status === "pushed" || result.success === true;
  finalResultBox.className = success ? "box success" : "box error";

  const title = createElement(
    "h3",
    "",
    success ? "Patch pushed to GitHub" : "Patch apply failed"
  );
  finalResultBox.appendChild(title);

  const message = createElement(
    "p",
    "",
    result.message || "Patch operation finished."
  );
  finalResultBox.appendChild(message);

  if (result.branch) {
    const branch = createElement("p", "", `Branch: ${result.branch}`);
    finalResultBox.appendChild(branch);
  }

  if (result.commit_sha) {
    const commit = createElement("p", "", `Commit: ${result.commit_sha}`);
    finalResultBox.appendChild(commit);
  }

  const appliedFiles = Array.isArray(result.applied_files)
    ? result.applied_files
    : [];

  const files = createElement(
    "p",
    "",
    `Modified files: ${appliedFiles.length ? appliedFiles.join(", ") : "None"}`
  );
  finalResultBox.appendChild(files);

  if (result.diff) {
    const details = createElement("details", "technical-details");
    const summary = createElement("summary", "", "Applied diff");
    details.appendChild(summary);

    const pre = createElement("pre", "diff");
    pre.textContent = result.diff;
    details.appendChild(pre);

    finalResultBox.appendChild(details);
  }
}

confirmProjectButton.addEventListener("click", confirmProject);
changeProjectButton.addEventListener("click", changeProject);
scanProjectButton.onclick = startAgentRun;

renderWorkflow();
renderControls();
loadProjects();