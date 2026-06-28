const WorkflowState = {
  INITIAL: "INITIAL",
  PROJECT_SELECTED: "PROJECT_SELECTED",
  LOADING_SONAR_ISSUES: "LOADING_SONAR_ISSUES",
  SONAR_ISSUES_LOADED: "SONAR_ISSUES_LOADED",
  PROPOSING_FIX: "PROPOSING_FIX",
  DIFF_READY: "DIFF_READY",
  APPLYING_PATCH: "APPLYING_PATCH",
  VERIFY_DONE: "VERIFY_DONE",
  ERROR: "ERROR"
};

const steps = [
  { key: "select", label: "Select project" },
  { key: "load", label: "Load SonarQube issues" },
  { key: "fix", label: "Propose fix" },
  { key: "diff", label: "Review diff" },
  { key: "apply", label: "Apply patch" },
  { key: "verify", label: "Verify result" }
];

const INITIAL_LOG_TEXT = "No action started yet.";

let state = WorkflowState.INITIAL;
let selectedProjectId = null;
let latestProjectFixResult = null;
let latestModelOutput = null;

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
    LOADING_SONAR_ISSUES: 1,
    SONAR_ISSUES_LOADED: 2,
    PROPOSING_FIX: 2,
    DIFF_READY: 3,
    APPLYING_PATCH: 4,
    VERIFY_DONE: 5,
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
    WorkflowState.LOADING_SONAR_ISSUES,
    WorkflowState.PROPOSING_FIX,
    WorkflowState.APPLYING_PATCH
  ];

  projectSelectionArea.classList.toggle("hidden", projectChosen);
  selectedProjectArea.classList.toggle("hidden", !projectChosen);

  confirmProjectButton.disabled = state !== WorkflowState.INITIAL;

  scanProjectButton.disabled = ![
    WorkflowState.PROJECT_SELECTED,
    WorkflowState.SONAR_ISSUES_LOADED,
    WorkflowState.DIFF_READY,
    WorkflowState.VERIFY_DONE
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
  latestProjectFixResult = null;
  latestModelOutput = null;

  selectedProjectText.textContent = selectedProjectId;

  scanProjectButton.classList.remove("hidden");
  scanProjectButton.disabled = false;
  scanProjectButton.textContent = "Load SonarQube issues";
  scanProjectButton.onclick = loadSonarIssues;

  setBox(
    toolRunsBox,
    "This workflow uses SonarQube as the source of detected issues.",
    "muted"
  );

  setBox(issuesBox, "Click “Load SonarQube issues” to fetch detected issues.", "muted");
  setBox(repairPlanBox, "No repair prompt has been generated yet.", "muted");
  setBox(diffBox, "No diff has been proposed yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  addLog(`Selected project: ${selectedProjectId}`);
  setState(WorkflowState.PROJECT_SELECTED, "Project ready for SonarQube");
}

function changeProject() {
  selectedProjectId = null;
  latestProjectFixResult = null;
  latestModelOutput = null;

  scanProjectButton.textContent = "Load SonarQube issues";
  scanProjectButton.onclick = loadSonarIssues;

  setBox(toolRunsBox, "No SonarQube issues have been loaded yet.", "muted");
  setBox(issuesBox, "Confirm the project, then load SonarQube issues.", "muted");
  setBox(repairPlanBox, "No repair prompt has been generated yet.", "muted");
  setBox(diffBox, "No diff has been proposed yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  addLog("Returned to project selection.");
  setState(WorkflowState.INITIAL, "Select a project");
}

function renderBadge(text, kind = "") {
  const badge = document.createElement("span");
  badge.className = kind ? `badge ${kind}` : "badge";
  badge.textContent = text;
  return badge;
}

async function loadSonarIssues() {
  if (!selectedProjectId) {
    setBox(issuesBox, "Select a project first.", "error");
    return;
  }

  latestProjectFixResult = null;
  latestModelOutput = null;

  setState(WorkflowState.LOADING_SONAR_ISSUES, "Loading SonarQube issues");
  addLog(`Loading SonarQube issues for project: ${selectedProjectId}`);

  setBox(issuesBox, "Loading SonarQube issues...", "muted");
  setBox(repairPlanBox, "No repair prompt has been generated yet.", "muted");
  setBox(diffBox, "No diff has been proposed yet.", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(
      `/sonar/demo/issues?project_id=${encodeURIComponent(selectedProjectId)}`
    );

    addLog(`${result.total} SonarQube issue(s) loaded.`);
    renderSonarIssues(result.issues || []);

    if (result.issues && result.issues.length) {
      setState(
        WorkflowState.SONAR_ISSUES_LOADED,
        "SonarQube issues loaded"
      );
    } else {
      setState(
        WorkflowState.VERIFY_DONE,
        "No SonarQube issues found"
      );
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to load SonarQube issues");
    setBox(
      issuesBox,
      `Failed to load SonarQube issues:\n${error.message}`,
      "error"
    );
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

  const hasCritical = issues.some(
    (issue) => issue.severity === "CRITICAL" || issue.severity === "BLOCKER"
  );

  issuesBox.className = hasCritical ? "box error" : "box warning";

  const title = document.createElement("h3");
  title.textContent = "SonarQube issues";
  issuesBox.appendChild(title);

  const projectFixWrapper = document.createElement("div");
  projectFixWrapper.className = "action-row";

  const projectFixButton = document.createElement("button");
  projectFixButton.textContent = "Fix project from SonarQube issues";
  projectFixButton.onclick = proposeProjectSonarFix;

  projectFixWrapper.appendChild(projectFixButton);
  issuesBox.appendChild(projectFixWrapper);

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

  return card;
}


async function proposeProjectSonarFix() {
  if (!selectedProjectId) {
    setBox(diffBox, "Select a project first.", "error");
    return;
  }

  latestProjectFixResult = null;
  latestModelOutput = null;

  setState(
    WorkflowState.PROPOSING_FIX,
    "Sending SonarQube project issues to DeepSeek"
  );

  addLog(`Sending SonarQube issues for project: ${selectedProjectId}`);

  setBox(repairPlanBox, "Building dynamic prompt from SonarQube issues...", "muted");
  setBox(diffBox, "Waiting for DeepSeek response...", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(
      `/sonar/demo/projects/${encodeURIComponent(selectedProjectId)}/propose-fix`,
      { method: "POST" }
    );

    latestProjectFixResult = result;
    latestModelOutput = result.model_output || "";

    addLog(
      `DeepSeek returned a project-level fix for ${result.total} SonarQube issue(s).`
    );

    renderProjectSonarPrompt(result);
    renderProjectSonarModelOutput(result);

    setState(WorkflowState.DIFF_READY, "Review DeepSeek output");
  } catch (error) {
    setState(WorkflowState.ERROR, "DeepSeek request failed");
    setBox(diffBox, `DeepSeek request failed:\n${error.message}`, "error");
    addLog("DeepSeek request failed.");
  }
}


function renderProjectSonarPrompt(result) {
  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = "Dynamic SonarQube repair prompt";
  repairPlanBox.appendChild(title);

  const meta = document.createElement("p");
  meta.textContent = `${result.project_id} · ${result.total} SonarQube issue(s)`;
  repairPlanBox.appendChild(meta);

  const pre = document.createElement("pre");
  pre.textContent = result.prompt || "No prompt was generated.";
  repairPlanBox.appendChild(pre);
}


function renderProjectSonarModelOutput(result) {
  diffBox.innerHTML = "";
  diffBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = "DeepSeek proposed project fix";
  diffBox.appendChild(title);

  const meta = document.createElement("p");
  meta.textContent = `${result.project_id} · ${result.total} SonarQube issue(s)`;
  diffBox.appendChild(meta);

  const pre = document.createElement("pre");
  pre.textContent = result.model_output || "DeepSeek returned an empty response.";
  diffBox.appendChild(pre);

  const note = document.createElement("p");
  note.className = "action-text";
  note.textContent = "Review the diff first. Apply patch is the next backend step.";
  diffBox.appendChild(note);
}


async function applyPatch() {
  if (!selectedProjectId) {
    setBox(finalResultBox, "Select a project first.", "error");
    return;
  }

  if (!latestModelOutput) {
    setBox(finalResultBox, "No DeepSeek diff is available to apply.", "error");
    return;
  }

  const confirmed = confirm(
    "Apply this DeepSeek diff to the project files?"
  );

  if (!confirmed) {
    addLog("Patch application was cancelled.");
    return;
  }

  setState(WorkflowState.APPLYING_PATCH, "Applying patch");
  addLog("Applying project-level SonarQube patch.");
  setBox(finalResultBox, "Applying patch...", "muted");

  try {
    const result = await api(
      `/sonar/demo/projects/${encodeURIComponent(selectedProjectId)}/apply-fix`,
      {
        method: "POST",
        body: JSON.stringify({
          model_output: latestModelOutput
        })
      }
    );

    addLog("Patch apply request finished.");
    renderApplyResult(result);

    setState(WorkflowState.VERIFY_DONE, "Patch apply finished");
  } catch (error) {
    setState(WorkflowState.ERROR, "Failed to apply patch");
    setBox(finalResultBox, `Failed to apply patch:\n${error.message}`, "error");
    addLog("Failed to apply patch.");
  }
}


async function proposeProjectSonarFix() {
  if (!selectedProjectId) {
    setBox(diffBox, "Select a project first.", "error");
    return;
  }

  latestProjectFixResult = null;
  latestModelOutput = null;

  setState(
    WorkflowState.PROPOSING_FIX,
    "Sending SonarQube project issues to DeepSeek"
  );

  addLog(`Sending SonarQube issues for project: ${selectedProjectId}`);

  setBox(repairPlanBox, "Building dynamic prompt from SonarQube issues...", "muted");
  setBox(diffBox, "Waiting for DeepSeek response...", "muted");
  setBox(finalResultBox, "No patch has been applied yet.", "muted");

  try {
    const result = await api(
      `/sonar/demo/projects/${encodeURIComponent(selectedProjectId)}/propose-fix`,
      { method: "POST" }
    );

    latestProjectFixResult = result;
    latestModelOutput = result.model_output || "";

    addLog(
      `DeepSeek returned a project-level fix for ${result.total} SonarQube issue(s).`
    );

    renderProjectSonarPrompt(result);
    renderProjectSonarModelOutput(result);

    setState(WorkflowState.DIFF_READY, "Review DeepSeek output");
  } catch (error) {
    setState(WorkflowState.ERROR, "DeepSeek request failed");
    setBox(diffBox, `DeepSeek request failed:\n${error.message}`, "error");
    addLog("DeepSeek request failed.");
  }
}


function renderProjectSonarPrompt(result) {
  repairPlanBox.innerHTML = "";
  repairPlanBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = "Dynamic SonarQube repair prompt";
  repairPlanBox.appendChild(title);

  const meta = document.createElement("p");
  meta.textContent = `${result.project_id} · ${result.total} SonarQube issue(s)`;
  repairPlanBox.appendChild(meta);

  const pre = document.createElement("pre");
  pre.textContent = result.prompt || "No prompt was generated.";
  repairPlanBox.appendChild(pre);
}


function renderProjectSonarModelOutput(result) {
  diffBox.innerHTML = "";
  diffBox.className = "box";

  const title = document.createElement("h3");
  title.textContent = "DeepSeek proposed project fix";
  diffBox.appendChild(title);

  const meta = document.createElement("p");
  meta.textContent = `${result.project_id} · ${result.total} SonarQube issue(s)`;
  diffBox.appendChild(meta);

  const pre = document.createElement("pre");
  pre.textContent = result.model_output || "DeepSeek returned an empty response.";
  diffBox.appendChild(pre);

  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const applyButton = document.createElement("button");
  applyButton.textContent = "Apply patch";
  applyButton.onclick = applyPatch;

  const rejectButton = document.createElement("button");
  rejectButton.textContent = "Reject";
  rejectButton.onclick = () => {
    latestProjectFixResult = null;
    latestModelOutput = null;
    addLog("DeepSeek proposed fix rejected.");
    setBox(finalResultBox, "Patch rejected. No files were changed.", "warning");
    setState(WorkflowState.DIFF_READY, "Patch rejected");
  };

  wrapper.appendChild(applyButton);
  wrapper.appendChild(rejectButton);
  diffBox.appendChild(wrapper);
}


function renderApplyResult(result) {
  finalResultBox.innerHTML = "";

  const success = result.status === "applied" || result.success === true;
  finalResultBox.className = success ? "box success" : "box warning";

  const title = document.createElement("h3");
  title.textContent = success ? "Patch applied" : "Patch apply result";
  finalResultBox.appendChild(title);

  const message = document.createElement("p");
  message.textContent = result.message || "Patch operation finished.";
  finalResultBox.appendChild(message);

  const appliedFiles = Array.isArray(result.applied_files)
    ? result.applied_files
    : [];

  const files = document.createElement("p");
  files.textContent = `Modified files: ${appliedFiles.length ? appliedFiles.join(", ") : "None"}`;
  finalResultBox.appendChild(files);

  if (result.diff) {
    const pre = document.createElement("pre");
    pre.textContent = result.diff;
    finalResultBox.appendChild(pre);
  }
}


confirmProjectButton.addEventListener("click", confirmProject);
changeProjectButton.addEventListener("click", changeProject);
scanProjectButton.onclick = loadSonarIssues;

renderWorkflow();
renderControls();
loadProjects();