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