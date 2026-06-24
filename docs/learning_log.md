# AI Coding Assistant - Learning Log

## Goal
Build an AI Coding Assistant that scans a selected project, detects issues, proposes safe fixes, shows diffs, waits for developer approval, applies fixes, and verifies the result.

## Learning Items

| Topic | Why we need it | Estimated learning time | Status |
|---|---|---:|---|
| LangGraph State, Nodes, Edges | Build the workflow engine | 2 hours | In progress |
| LangGraph Conditional Edges | Decide next step based on scan result or approval | 1 hour | Later |
| LangGraph Interrupts | Stop before applying code changes and wait for human approval | 1.5 hours | Later |
| LangGraph Persistence | Save graph state and resume later | 1.5 hours | Later |
| LangGraph Streaming | Show progress in the website while the agent works | 1.5 hours | Later |
| FastAPI endpoints | Expose scan, issues, propose-fix, apply, verify APIs | 1.5 hours | In progress |
| Ruff basics | Run lint checks and detect style/code issues | 1 hour | In progress |
| Pytest basics | Detect failing tests and no-test situations | 1 hour | In progress |
| Python AST basics | Parse code safely for structural analysis | 1 hour | Later |
| Diff/Patch basics | Show proposed changes before applying them | 1.5 hours | Later |
| Project path security | Prevent arbitrary file access | 1 hour | In progress |
| Project-scoped context collection | The agent must read files from the selected target project, not from the assistant's own source code | 1 hour | Done |
| Pytest failure interpretation | Read failing test output and map it to source/test files | 45 minutes | Done |
| Ruff basics | Run `ruff check` and distinguish tool-missing from lint failures | 1 hour | Done |
| Unified diff generation | Show the developer exactly what will change before applying a fix | 1 hour | Done |
| AST-based function replacement | Safely replace a target function by name when the LLM proposes a function snippet | 1 hour | Done |
| Human approval flow | Enforce that patches are only applied after the developer reviews the diff | 45 minutes | In progress |



<div dir="rtl">

## فصل التحليل

### ١. تحديد مدخلات النظام

* اختيار المشروع.
* قراءة بنية المشروع.
* استقبال رسالة المستخدم.
* استقبال نتائج الفحص أو الاختبار.
* تحديد الملفات المرتبطة بالمشكلة.

---

### ٢. تحديد ما يجب حفظه أثناء التنفيذ

يتم حفظ المعلومات داخل **الحالة (State)**، مثل:

* المشروع المختار.
* الملفات التي تم فحصها.
* الأخطاء المكتشفة.
* الملف المستهدف.
* تحليل المشكلة.
* خطة الإصلاح.
* نتيجة الاختبار.
* حالة موافقة المستخدم.

---

### ٣. تحديد القرارات المطلوبة

يجب أن يقرر النظام:

* هل المشروع صالح للفحص؟
* هل توجد أخطاء؟
* هل نحتاج قراءة ملفات إضافية؟
* هل المشكلة واضحة؟
* هل التعديل آمن؟
* هل نحتاج موافقة المستخدم؟
* هل نجحت الاختبارات؟
* هل نعيد المحاولة أو نتوقف؟

---

### ٤. تحديد الأدوات المسموح استخدامها

الأدوات المسموحة:

* قراءة الملفات المسموحة.
* البحث داخل المشروع.
* تحليل الكود.
* تشغيل الاختبارات.
* اقتراح الإصلاح.
* تطبيق التعديل بعد الموافقة.
* إعادة الفحص بعد التعديل.

---

### ٥. تحديد الملفات الممنوع قراءتها

يمنع قراءة:

* ملفات البيئة.
* ملفات الأسرار.
* مفاتيح الواجهة البرمجية.
* مجلد Git.
* بيئة العمل.
* ملفات البناء.
* الملفات الكبيرة أو غير المرتبطة بالمشكلة.

---

### ٦. تحديد متى يتوقف النظام

يتوقف النظام عندما:

* لا توجد أخطاء.
* تم إصلاح المشكلة بنجاح.
* فشلت الاختبارات بعد الإصلاح.
* يحتاج موافقة المستخدم.
* الملف غير مسموح قراءته.
* لا توجد معلومات كافية.
* المستخدم أوقف العملية.

---

### ٧. تحويل التحليل إلى لانجراف

في **لانجراف (LangGraph)** نحول التحليل إلى:

* **حالة مشتركة (State)** لحفظ البيانات.
* **عُقد (Nodes)** لتنفيذ الخطوات.
* **انتقالات (Edges)** للانتقال بين الخطوات.
* **انتقالات شرطية (Conditional Edges)** لاتخاذ القرارات.

---

### ٨. تقسيم المهمة إلى خطوات

الخطوات الأساسية:

1. اختيار المشروع.
2. فحص المشروع.
3. استخراج الأخطاء.
4. اختيار المشكلة.
5. جمع السياق.
6. تحليل السبب.
7. اقتراح الإصلاح.
8. انتظار موافقة المستخدم.
9. تطبيق الإصلاح.
10. تشغيل الاختبارات.
11. عرض النتيجة النهائية.

</div>

# AI Coding Assistant — Project Documentation

## 1. Project Goal

The goal of this project is to build a local AI-assisted coding repair system.

The system scans a selected Python project, detects common issues, proposes a minimal repair plan using an AI model, shows the generated diff to the developer, and applies the patch only after human approval.

The project is designed around one core principle:

> The AI model should propose a fix, but the system must validate, display, and control the actual file changes.

---

## 2. Main Workflow

The application follows this workflow:

1. Select a local demo project.
2. Scan the project locally.
3. Detect syntax, linting, or test issues.
4. Select one issue.
5. Send only the relevant context to the AI model.
6. Ask the model to return a structured repair plan.
7. Convert the repair plan into a diff.
8. Show the diff to the developer.
9. Apply the patch only after approval.
10. Run verification checks again.

This workflow avoids blindly sending the whole project to the model and avoids applying AI-generated changes without review.

---

## 3. Why Local Scanning Comes Before the AI Model

Before asking the AI model to analyze a problem, the system first runs deterministic local checks.

This is important because many programming errors are simple and should not consume AI tokens. For example, a missing colon in Python can be detected locally without sending code to the model.

Example:

```python
def hello()
    print("hello")
```

This is a syntax error. The system can detect this locally before involving the model.

This design reduces token usage, improves speed, and prevents the AI model from wasting reasoning on basic issues that tools can detect more reliably.

---

## 4. Syntax Checking

### Tool Used: Python syntax parsing / compile check

The system uses local Python syntax checking to detect invalid Python files before running the application.

This helps catch errors such as:

* missing colons
* invalid indentation
* broken function definitions
* malformed Python syntax

The benefit is that syntax errors can be detected without executing the application and without calling the AI model.

### Why this is useful

Syntax checking is fast, local, deterministic, and cheap. It is a good first filter before deeper analysis.

### Limitation

Syntax checking only verifies whether the Python code can be parsed or compiled. It does not detect runtime errors, failed imports, incorrect logic, failing tests, or unused code.

For that reason, the project also uses Ruff and pytest.

---

## 5. Ruff for Linting

### Tool Used: Ruff

Ruff is used to detect linting and style issues in the selected project.

Examples of issues Ruff can detect:

* unused imports
* unused variables
* style violations
* some simple code-quality problems

Example:

```python
import os

def hello():
    print("hello")
```

If `os` is not used, Ruff can report it as an unused import.

### Why Ruff is useful

Ruff is fast and can detect many issues without running the application. It is useful after syntax checking because it can find code-quality problems that are not syntax errors.

### Limitation

Ruff does not prove that the program behaves correctly. A file can pass Ruff and still have broken business logic or failing tests.

For that reason, the system also runs pytest.

---

## 6. pytest for Runtime and Behavior Verification

### Tool Used: pytest

pytest is used to run tests and detect behavior problems.

Examples of issues pytest can detect:

* failed assertions
* import errors
* broken functions
* wrong return values
* test collection errors

### Why pytest is useful

pytest goes beyond syntax and linting. It can detect whether the code actually behaves as expected according to the tests.

### Limitation

pytest only verifies what the tests cover. If the project has no tests or weak tests, pytest cannot guarantee that the application is correct.

---

## 7. subprocess for Running Local Tools

### Tool Used: Python subprocess

The application uses subprocess calls to run local commands such as:

```powershell
python -m compileall -q app
python -m ruff check .
python -m pytest -q
```

This allows the backend to execute external developer tools and capture their output.

The system reads:

* exit code
* stdout
* stderr
* command status
* timeout or interruption

### Why subprocess is useful

It allows the application to integrate with existing CLI tools instead of reimplementing their behavior.

### Limitation

Subprocess commands must be controlled carefully. Commands should have a safe working directory, timeout handling, and predictable arguments.

---

## 8. Context Collection

### Tool Used: Custom Context Collector

The system does not send the entire project to the AI model. Instead, it collects only relevant project context.

The context collector includes:

* files mentioned in the error output
* important project files
* limited file contents
* skipped files
* missing referenced files

### Why context collection is useful

It reduces token usage and gives the model only the information needed to propose a minimal fix.

### Limitation

If the collector does not include the right files, the model may not have enough information. In that case, the repair plan should lower confidence or request human review.

---

## 9. AI Model Role

### Tool Used: Chat model through LangChain

The AI model is not responsible for scanning or directly changing files.

Its role is to:

* analyze the selected issue
* reason about the likely root cause
* propose a minimal fix
* return a structured repair plan

The model receives a prepared problem statement and selected project context.

### Why the AI model is useful

The AI model can understand error messages, code context, and propose repairs that are harder to detect with simple static tools.

### Limitation

The AI model can be wrong. It may misunderstand context, propose unsafe changes, or generate incomplete output. Therefore, the system validates the response and requires human review before applying changes.

---

## 10. Structured Repair Plan

### Tool Used: Pydantic Schema

The AI model is required to return a structured repair plan instead of free text.

The repair plan includes:

* summary
* suspected root cause
* files to inspect
* repair steps
* proposed file changes
* commands to run
* confidence
* human review flag

### Why structured output is useful

Structured output makes the AI response usable by the application. Instead of parsing random text, the backend can validate the result and convert it into a diff.

### Limitation

Even if the output has the correct structure, the proposed fix may still be logically wrong. Schema validation checks shape, not correctness.

---

## 11. Diff Generation

### Tool Used: Custom Diff Builder

After the repair plan is created, the system converts proposed file changes into a diff.

The diff shows the developer exactly what will change before applying the patch.

### Why diff review is important

A diff gives transparency. The developer can see whether the AI-generated fix is safe and minimal.

### Limitation

The diff builder can only apply changes it understands. If the model proposes vague instructions or unsafe changes, the patch should not be applied automatically.

---

## 12. Human Approval

The system does not automatically modify files after receiving an AI response.

The developer must review the generated diff and click Apply patch.

This makes the system safer because the human remains responsible for final approval.

Future versions can improve this using LangGraph interrupts, where the graph itself pauses execution until a human approves or rejects the proposed change.

---

## 13. LangGraph Workflow

### Tool Used: LangGraph

LangGraph is used to represent the repair process as a stateful workflow.

The current graph contains two main steps:

1. collect context
2. create repair plan

This separates workflow control from individual logic functions.

### Why LangGraph is useful

LangGraph makes the repair process explicit and easier to extend. Future steps can be added, such as:

* human approval interrupt
* retry logic
* patch application node
* verification node
* rollback node

### Limitation

In the current version, the graph is still simple. It does not yet use advanced LangGraph features such as interrupts, checkpointing, or persistence.

---

## 14. FastAPI Backend

### Tool Used: FastAPI

FastAPI provides the backend API used by the frontend.

The frontend calls backend endpoints to:

* list projects
* scan a project
* propose a fix
* build a diff
* apply a patch

### Why FastAPI is useful

FastAPI makes it easy to define API endpoints and return structured JSON responses to the frontend.

### Limitation

The current version uses in-memory storage for scan results, repair plans, and patches. This is acceptable for a prototype, but production systems should use persistent storage.

---

## 15. Frontend

### Tool Used: HTML, CSS, JavaScript

The frontend provides a simple browser interface for the workflow.

It allows the user to:

* select a project
* start a scan
* review detected issues
* request a repair plan
* review the diff
* apply the patch
* view verification results

### Why a simple frontend was used

A simple frontend is enough for the initial version. It keeps the project easy to understand and avoids unnecessary complexity.

### Limitation

The current frontend is not a full IDE. It focuses only on the repair workflow.

---

## 16. Safety Rules

The project follows several safety rules:

* do not send the whole project to the model
* do not apply patches automatically
* validate AI output with a schema
* show diffs before applying changes
* run verification after patching
* avoid modifying files outside the selected project
* prefer local deterministic tools before AI analysis

These rules make the system safer and more predictable.

---

## 17. Current Limitations

The current version is an initial prototype.

Known limitations:

* project state is stored in memory
* only predefined demo projects are supported
* human approval happens in the frontend, not yet inside LangGraph
* no persistent graph checkpointing yet
* no rollback mechanism yet
* test quality depends on the selected project
* the model may still propose incorrect fixes
* patch generation supports only known change patterns

---

## 18. Future Improvements

Possible next improvements:

1. Add custom local project registration.
2. Add LangGraph interrupts for human approval.
3. Add LangGraph persistence and checkpointing.
4. Add rollback support before applying patches.
5. Add better project exclusion rules.
6. Add structured output directly through the model provider.
7. Add persistent storage for issues, plans, and patches.
8. Add better test reporting.
9. Add LangSmith tracing for debugging AI calls.
10. Improve the diff builder to support more edit types.

---

## 19. Summary

This project combines deterministic local developer tools with AI-assisted repair planning.

The local tools detect simple and reliable issues first. The AI model is used only when reasoning is needed. The system validates the model output, shows the diff, waits for human approval, applies the patch, and verifies the result.

The most important design idea is:

> The AI proposes. The system validates. The human approves. The tools verify.
