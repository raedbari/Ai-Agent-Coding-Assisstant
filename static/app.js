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
  { key: "select", label: "اختيار المشروع" },
  { key: "scan", label: "فحص المشروع" },
  { key: "issue", label: "اختيار مشكلة" },
  { key: "fix", label: "اقتراح الإصلاح" },
  { key: "diff", label: "عرض الفرق" },
  { key: "apply", label: "تطبيق التعديل" },
  { key: "verify", label: "التحقق النهائي" }
];

let state = WorkflowState.INITIAL;
let selectedProjectId = null;
let selectedIssueId = null;

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

  projectSelectionArea.classList.toggle("hidden", projectChosen);
  selectedProjectArea.classList.toggle("hidden", !projectChosen);

  confirmProjectButton.disabled = state !== WorkflowState.INITIAL;
  scanProjectButton.disabled = state !== WorkflowState.PROJECT_SELECTED && state !== WorkflowState.SCAN_DONE;
  changeProjectButton.disabled = state === WorkflowState.SCANNING || state === WorkflowState.PROPOSING_FIX || state === WorkflowState.BUILDING_DIFF || state === WorkflowState.APPLYING_PATCH;
}

function addLog(message) {
  const now = new Date().toLocaleTimeString("en-GB");
  const previous = activityLog.textContent.trim();

  const line = `[${now}] ${message}`;

  if (previous === "لم يبدأ أي إجراء بعد.") {
    activityLog.textContent = line;
  } else {
    activityLog.textContent += `\n${line}`;
  }

  activityLog.scrollTop = activityLog.scrollHeight;
}

function setBox(element, content, kind = "muted") {
  element.className = `box ${kind}`;
  element.textContent = content;
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
    addLog("تحميل قائمة المشاريع...");
    const projects = await api("/projects");

    projectSelect.innerHTML = "";

    for (const project of projects) {
      const option = document.createElement("option");
      option.value = project.id;
      option.textContent = `${project.name} (${project.id})`;
      projectSelect.appendChild(option);
    }

    addLog("تم تحميل المشاريع.");
    setState(WorkflowState.INITIAL, "اختر مشروعًا");
  } catch (error) {
    setState(WorkflowState.ERROR, "فشل تحميل المشاريع");
    setBox(issuesBox, `فشل تحميل المشاريع:\n${error.message}`, "error");
    addLog("فشل تحميل المشاريع.");
  }
}

function confirmProject() {
  selectedProjectId = projectSelect.value;
  selectedIssueId = null;

  selectedProjectText.textContent = selectedProjectId;

  setBox(toolRunsBox, "لم يتم الفحص بعد.", "muted");
  setBox(issuesBox, "اضغط على زر فحص المشروع.", "muted");
  setBox(repairPlanBox, "لم يتم اقتراح إصلاح بعد.", "muted");
  setBox(diffBox, "لم يتم بناء الفرق بعد.", "muted");
  setBox(finalResultBox, "لم يتم تطبيق أي تعديل بعد.", "muted");

  addLog(`تم اختيار المشروع: ${selectedProjectId}`);
  setState(WorkflowState.PROJECT_SELECTED, "المشروع جاهز للفحص");
}

function changeProject() {
  selectedProjectId = null;
  selectedIssueId = null;

  addLog("تم الرجوع إلى اختيار المشروع.");
  setState(WorkflowState.INITIAL, "اختر مشروعًا");
}

function renderToolRuns(toolRuns) {
  if (!toolRuns.length) {
    setBox(toolRunsBox, "لم يتم تشغيل أدوات فحص.", "muted");
    return;
  }

  const text = toolRuns.map(run => {
    return [
      `الأداة (Tool): ${run.tool}`,
      `الحالة (Status): ${run.status}`,
      `كود الخروج (Exit Code): ${run.exit_code}`,
      `الأمر (Command): ${run.command}`,
      run.output ? `المخرجات (Output):\n${run.output}` : "المخرجات (Output): فارغة"
    ].join("\n");
  }).join("\n\n--------------------\n\n");

  setBox(toolRunsBox, text, "success");
}

function renderIssues(issues) {
  issuesBox.innerHTML = "";

  if (!issues.length) {
    issuesBox.className = "box success";
    issuesBox.textContent = "لم يتم العثور على مشاكل.";
    return;
  }

  issuesBox.className = "box";

  issues.forEach(issue => {
    const card = document.createElement("div");
    card.className = "issue-card";

    const title = document.createElement("h3");
    title.textContent = issue.title;

    const badges = document.createElement("div");
    badges.className = "badges";
    badges.innerHTML = `
      <span class="badge">الأداة (Tool): ${issue.tool}</span>
      <span class="badge">الخطورة (Severity): ${issue.severity}</span>
    `;

    const details = document.createElement("pre");
    details.textContent = issue.details;

    const actions = document.createElement("div");
    actions.className = "action-row";

    const proposeButton = document.createElement("button");
    proposeButton.textContent = "اقترح إصلاحًا";
    proposeButton.onclick = () => selectIssueAndProposeFix(issue.id);

    actions.appendChild(proposeButton);

    card.appendChild(title);
    card.appendChild(badges);
    card.appendChild(details);
    card.appendChild(actions);

    issuesBox.appendChild(card);
  });
}

async function scanProject() {
  setState(WorkflowState.SCANNING, "جاري فحص المشروع");
  addLog("بدأ فحص المشروع.");
  setBox(toolRunsBox, "جاري تشغيل أدوات الفحص...", "muted");
  setBox(issuesBox, "جاري البحث عن المشاكل...", "muted");

  try {
    const result = await api(`/projects/${selectedProjectId}/scan`, {
      method: "POST"
    });

    addLog("انتهى فحص المشروع.");
    renderToolRuns(result.tool_runs);
    renderIssues(result.issues);

    if (result.issues.length) {
      addLog(`تم العثور على ${result.issues.length} مشكلة.`);
      setState(WorkflowState.SCAN_DONE, "اختر مشكلة من القائمة");
    } else {
      addLog("لم يتم العثور على مشاكل.");
      setState(WorkflowState.VERIFY_DONE, "المشروع لا يحتوي على مشاكل ظاهرة");
      setBox(finalResultBox, "تم الفحص بنجاح. لا توجد مشاكل.", "success");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "فشل الفحص");
    setBox(issuesBox, `فشل الفحص:\n${error.message}`, "error");
    addLog("فشل فحص المشروع.");
  }
}

async function selectIssueAndProposeFix(issueId) {
  selectedIssueId = issueId;

  setState(WorkflowState.PROPOSING_FIX, "جاري اقتراح الإصلاح");
  addLog(`تم اختيار المشكلة: ${issueId}`);
  addLog("جاري تحليل المشكلة وإنشاء خطة إصلاح.");

  setBox(repairPlanBox, "جاري إنشاء خطة الإصلاح...", "muted");
  setBox(diffBox, "لم يتم بناء الفرق بعد.", "muted");
  setBox(finalResultBox, "لم يتم تطبيق أي تعديل بعد.", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${issueId}/propose-fix`,
      { method: "POST" }
    );

    addLog("تم إنشاء خطة الإصلاح.");

    const plan = result.repair_plan;

    const readablePlan = [
      `الملخص:\n${plan.summary}`,
      "",
      `السبب المتوقع:\n${plan.suspected_root_cause}`,
      "",
      "الخطوات:",
      ...(plan.steps || []).map((step, index) => {
        return `${index + 1}. ${step.title}\n   ${step.explanation}\n   التعديل المقترح: ${step.suggested_change}`;
      }),
      "",
      "تغييرات الملفات المقترحة:",
      JSON.stringify(plan.proposed_file_changes || [], null, 2)
    ].join("\n");

    setBox(repairPlanBox, readablePlan);
    setState(WorkflowState.FIX_PROPOSED, "تم اقتراح الإصلاح");

    renderBuildDiffButton();
  } catch (error) {
    setState(WorkflowState.ERROR, "فشل اقتراح الإصلاح");
    setBox(repairPlanBox, `فشل اقتراح الإصلاح:\n${error.message}`, "error");
    addLog("فشل اقتراح الإصلاح.");
  }
}

function renderBuildDiffButton() {
  const wrapper = document.createElement("div");
  wrapper.className = "action-row";

  const button = document.createElement("button");
  button.textContent = "ابنِ الفرق (Diff)";
  button.onclick = buildDiff;

  wrapper.appendChild(button);
  repairPlanBox.appendChild(document.createElement("br"));
  repairPlanBox.appendChild(wrapper);
}

async function buildDiff() {
  setState(WorkflowState.BUILDING_DIFF, "جاري بناء الفرق");
  addLog("جاري بناء الفرق قبل التطبيق.");
  setBox(diffBox, "جاري بناء الفرق...", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${selectedIssueId}/build-diff`,
      { method: "POST" }
    );

    if (!result.patches.length) {
      addLog("لم يتم إنشاء أي فرق.");
      setBox(diffBox, "لم يتم إنشاء أي فرق.", "muted");
      return;
    }

    const text = result.patches.map(patch => {
      return [
        `الملف: ${patch.file_path}`,
        `نوع التغيير: ${patch.change_type}`,
        `قابل للتطبيق: ${patch.can_apply}`,
        "",
        patch.diff
      ].join("\n");
    }).join("\n\n--------------------\n\n");

    diffBox.className = "box diff";
    diffBox.textContent = text;

    const wrapper = document.createElement("div");
    wrapper.className = "action-row";

    const applyButton = document.createElement("button");
    applyButton.textContent = "أوافق، طبّق التعديل";
    applyButton.onclick = applyPatch;

    const rejectButton = document.createElement("button");
    rejectButton.textContent = "رفض التعديل";
    rejectButton.onclick = () => {
      addLog("رفض المطور تطبيق التعديل.");
      setState(WorkflowState.DIFF_READY, "تم رفض التطبيق");
    };

    wrapper.appendChild(applyButton);
    wrapper.appendChild(rejectButton);

    diffBox.appendChild(document.createElement("br"));
    diffBox.appendChild(wrapper);

    addLog("تم بناء الفرق. بانتظار موافقة المطور.");
    setState(WorkflowState.DIFF_READY, "راجع الفرق ثم وافق أو ارفض");
  } catch (error) {
    setState(WorkflowState.ERROR, "فشل بناء الفرق");
    setBox(diffBox, `فشل بناء الفرق:\n${error.message}`, "error");
    addLog("فشل بناء الفرق.");
  }
}

async function applyPatch() {
  const confirmed = confirm("هل توافق على تطبيق هذا التعديل على ملفات المشروع؟");

  if (!confirmed) {
    addLog("ألغى المطور تطبيق التعديل.");
    return;
  }

  setState(WorkflowState.APPLYING_PATCH, "جاري تطبيق التعديل والتحقق");
  addLog("بدأ تطبيق التعديل.");
  setBox(finalResultBox, "جاري تطبيق التعديل ثم إعادة الفحص...", "muted");

  try {
    const result = await api(
      `/projects/${selectedProjectId}/issues/${selectedIssueId}/apply`,
      { method: "POST" }
    );

    addLog("تم تطبيق التعديل.");
    addLog("تمت إعادة الفحص.");

    const finalText = [
      `الملفات التي تم تعديلها:\n${result.applied_files.join(", ") || "لا يوجد"}`,
      "",
      "نتائج أدوات الفحص:",
      JSON.stringify(result.tool_runs, null, 2),
      "",
      "المشاكل المتبقية:",
      JSON.stringify(result.issues, null, 2)
    ].join("\n");

    const finalKind = result.issues.length ? "error" : "success";

    setBox(finalResultBox, finalText, finalKind);

    if (result.issues.length) {
      setState(WorkflowState.VERIFY_DONE, "تم التطبيق لكن بقيت مشاكل");
      addLog("انتهى التحقق مع وجود مشاكل متبقية.");
    } else {
      setState(WorkflowState.VERIFY_DONE, "نجح الإصلاح والتحقق");
      addLog("نجح الإصلاح. جميع الفحوصات الأساسية مرّت.");
    }
  } catch (error) {
    setState(WorkflowState.ERROR, "فشل تطبيق التعديل");
    setBox(finalResultBox, `فشل تطبيق التعديل:\n${error.message}`, "error");
    addLog("فشل تطبيق التعديل.");
  }
}

confirmProjectButton.addEventListener("click", confirmProject);
changeProjectButton.addEventListener("click", changeProject);
scanProjectButton.addEventListener("click", scanProject);

renderWorkflow();
renderControls();
loadProjects();