# Jarvis AI — Offline Personal Assistant Dashboard

A full-stack **local, single-user** app: Flask (Python) backend, SQLite database, HTML/CSS/JS frontend.
**No cloud, no AI API, no internet needed** after installing Flask. No login (single-user, local only).

> The assistant is a **rule-based local engine** (pattern matching), not an AI language model. The UI says so.

## Features
Dashboard (live stats from the database, progress bar, animated SVG robot) · Assistant chat (quick actions, loading dots,
history, confirm-before-create task, optional spoken replies via the Mac's built-in voice) · Task Planner (add/edit/delete/complete,
priority, due date, filters, counters) · Reminders (overdue/upcoming, in-app alert while the page is open) · Notes (CRUD, search, timestamps) · Settings.
Voice *input* is omitted on purpose: browser speech recognition uploads audio to online servers.

## Setup on macOS (VS Code)
1. Check Python: open Terminal, run `python3 --version`. If missing, install from https://www.python.org/downloads/ (or `brew install python`).
2. Unzip, then in VS Code: **File → Open Folder…** → select `jarvis-ai`. Open the terminal with **Ctrl+`**.
3. Create and activate a virtual environment (run in the VS Code terminal, inside `jarvis-ai`):
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies: `pip install -r requirements.txt`
5. Start the app: `python app.py` (database `instance/jarvis.db` is created automatically).
6. Open **http://127.0.0.1:5000** in your browser (served by Flask; don't open index.html directly).
7. Stop with **Ctrl+C**.

No `.env` is required. Optional: `export SECRET_KEY="any-long-random-text"` before step 5.

**Reset the database:** stop the app, run `rm instance/jarvis.db`, start again.

## Test plan
| Test | Steps | Expected |
|---|---|---|
| Startup / DB | `python app.py` | Server on :5000, `instance/jarvis.db` exists |
| Tasks | Add, edit, tick, filter, delete | List and counters update after each action |
| Reminders | Add one 1–2 min ahead, keep page open | Toast appears; Dismiss moves it to Done |
| Overdue | Add a reminder in the past | Listed under Overdue |
| Notes | Create, edit, search, delete | Timestamps shown; search filters live |
| Dashboard | Open after changes | Numbers match your data |
| Chat | "What can you do?", "Create a task Buy milk" → Confirm, "Show my tasks" | Replies; task appears in Task Planner |
| Persistence | Stop and restart Flask | All data still there |
| Mobile | Narrow the browser below 800px | Bottom navigation bar, stacked cards |
| Errors | Stop Flask, then click Save | Red error toast, nothing shown as saved |

Sample API calls (CSRF token is required for POST/PUT/PATCH/DELETE, so use the browser UI for writes). Reads work directly:
```
curl http://127.0.0.1:5000/api/tasks             # 200 {"items":[...]}
curl http://127.0.0.1:5000/api/tasks/999         # 404 {"error":"Task not found"}
curl http://127.0.0.1:5000/api/dashboard/stats   # 200 {"total_tasks":..., "completion_percent":...}
curl -X POST http://127.0.0.1:5000/api/tasks     # 403 {"error":"Invalid or missing CSRF token..."}
```
Invalid input returns 400 with `{"error": "..."}`.

## Troubleshooting
- `command not found: python3` → install Python (step 1).
- `No module named flask` → activate the venv (`source venv/bin/activate`) and rerun `pip install -r requirements.txt`.
- `Address already in use` → port 5000 is busy (macOS AirPlay can use it). Change `port=5000` in `app.py` to `5001`.
- "Invalid CSRF token" → reload the page (the server was restarted).

## Architecture & database
Browser (HTML/CSS/JS, `fetch`) → Flask REST API (`app/routes.py`, validation, CSRF) → SQLite (`app/db.py`). Assistant logic: `app/assistant.py`.
Tables: `tasks(id,title,description,priority,due_date,completed,created_at,updated_at)`, `reminders(id,title,description,remind_at,done,…)`,
`notes(id,title,content,created_at,updated_at)`, `chat(id,role,content,created_at)`.
Security: parameterized SQL, server-side validation and length limits, CSRF token, HTML-escaped rendering, safe calculator (no `eval`), localhost-only binding.

## Demo sequence for judges
Dashboard → Assistant: "What can you do?" → "Create a task Present Jarvis" → Confirm → Task Planner: tick it complete → Reminders: add one due in 1 minute → Dashboard: show updated stats.

## 2-minute script
"Hi judges, this is Jarvis AI, a personal productivity dashboard that runs fully on your own computer. Many assistants send your data to the cloud; Jarvis doesn't. Everything is stored in a local SQLite database, and nothing leaves the machine. Here is the dashboard: these numbers are live from the database. I'll ask the assistant what it can do. It's an honest, rule-based engine, not a language model, and it says so. I'll tell it to create a task. It asks me to confirm before touching my data. Now in the Task Planner I'll mark it complete. I'll add a reminder for one minute from now; it will alert us here while the app is open. Back on the dashboard, the progress bar and counters have updated. Under the hood: Flask REST API, SQLite, validation, CSRF protection and escaped rendering. Limitations: single user, no login, reminders only while the page is open, and commands are fixed. Future work: a local language model, calendar sync and multi-user accounts. Thank you."

## Limitations
Local single-user, no authentication; reminders only while the page is open; the assistant understands fixed commands only.
