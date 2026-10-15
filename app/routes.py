import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from .assistant import respond
from .db import get_db

api = Blueprint("api", __name__, url_prefix="/api")
log = logging.getLogger("jarvis")


class Bad(ValueError):
    pass


@api.errorhandler(Bad)
def bad(e):
    return jsonify(error=str(e)), 400


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise Bad("Request body must be a JSON object")
    return d


def text(d, k, mx, req=False, cur=""):
    v = d.get(k, cur)
    v = "" if v is None else v
    if not isinstance(v, str):
        raise Bad(f"{k} must be text")
    v = v.strip()
    if req and not v:
        raise Bad(f"{k} is required")
    if len(v) > mx:
        raise Bad(f"{k} must be at most {mx} characters")
    return v


def when(v, fmt, label, req=False):
    if v in (None, ""):
        if req:
            raise Bad(f"{label} is required")
        return None
    try:
        datetime.strptime(v, fmt)
    except (TypeError, ValueError):
        raise Bad(f"{label} is invalid")
    return v


def flag(d, k, c):
    v = d.get(k, c.get(k, 0))
    if not isinstance(v, (bool, int)):
        raise Bad(f"{k} must be true or false")
    return int(bool(v))


def v_task(d, c):
    pr = d.get("priority", c.get("priority", "medium"))
    if pr not in ("low", "medium", "high"):
        raise Bad("priority must be low, medium or high")
    return dict(title=text(d, "title", 100, True, c.get("title", "")),
                description=text(d, "description", 500, cur=c.get("description", "")),
                priority=pr, due_date=when(d.get("due_date", c.get("due_date")), "%Y-%m-%d", "due_date"),
                completed=flag(d, "completed", c))


def v_rem(d, c):
    return dict(title=text(d, "title", 100, True, c.get("title", "")),
                description=text(d, "description", 500, cur=c.get("description", "")),
                remind_at=when(d.get("remind_at", c.get("remind_at")), "%Y-%m-%dT%H:%M", "remind_at", True),
                done=flag(d, "done", c))


def v_note(d, c):
    return dict(title=text(d, "title", 100, True, c.get("title", "")),
                content=text(d, "content", 5000, cur=c.get("content", "")))


def f_task(a):
    s = a.get("status")
    return (["completed=0"], []) if s == "pending" else (["completed=1"], []) if s == "completed" else ([], [])


def f_note(a):
    q = (a.get("q") or "").strip()[:100]
    if not q:
        return [], []
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return ["(title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"], [like, like]


def resource(name, validate, order, filters=lambda a: ([], [])):
    label = name[:-1].title()

    def get(i):
        r = get_db().execute(f"SELECT * FROM {name} WHERE id=?", (i,)).fetchone()
        return dict(r) if r else None

    def lst():
        cl, pa = filters(request.args)
        sql = f"SELECT * FROM {name}" + (" WHERE " + " AND ".join(cl) if cl else "") + f" ORDER BY {order}"
        return jsonify(items=[dict(r) for r in get_db().execute(sql, pa)])

    def create():
        vals = validate(body(), {})
        db = get_db()
        cur = db.execute(f"INSERT INTO {name} ({','.join(vals)}) VALUES ({','.join('?' * len(vals))})", list(vals.values()))
        db.commit()
        return jsonify(item=get(cur.lastrowid)), 201

    def one(id):
        r = get(id)
        return (jsonify(item=r), 200) if r else (jsonify(error=f"{label} not found"), 404)

    def update(id):
        cur = get(id)
        if not cur:
            return jsonify(error=f"{label} not found"), 404
        vals = validate(body(), cur)
        db = get_db()
        db.execute(f"UPDATE {name} SET {','.join(k + '=?' for k in vals)}, updated_at=datetime('now','localtime') WHERE id=?",
                   [*vals.values(), id])
        db.commit()
        return jsonify(item=get(id))

    def delete(id):
        db = get_db()
        n = db.execute(f"DELETE FROM {name} WHERE id=?", (id,)).rowcount
        db.commit()
        return (jsonify(message="Deleted"), 200) if n else (jsonify(error=f"{label} not found"), 404)

    u = f"/{name}"
    api.add_url_rule(u, f"{name}_list", lst)
    api.add_url_rule(u, f"{name}_create", create, methods=["POST"])
    api.add_url_rule(u + "/<int:id>", f"{name}_one", one)
    api.add_url_rule(u + "/<int:id>", f"{name}_update", update, methods=["PUT", "PATCH"])
    api.add_url_rule(u + "/<int:id>", f"{name}_delete", delete, methods=["DELETE"])


resource("tasks", v_task, "completed ASC, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id DESC", f_task)
resource("reminders", v_rem, "done ASC, remind_at ASC")
resource("notes", v_note, "updated_at DESC, id DESC", f_note)


@api.post("/chat")
def chat():
    msg = text(body(), "message", 500, True)
    db = get_db()
    res = respond(msg, db)
    db.execute("INSERT INTO chat (role, content) VALUES ('user', ?)", (msg,))
    db.execute("INSERT INTO chat (role, content) VALUES ('assistant', ?)", (res["reply"],))
    db.commit()
    return jsonify(res)


@api.get("/chat/history")
def history():
    rows = get_db().execute("SELECT role, content, created_at FROM chat ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify(items=[dict(r) for r in reversed(rows)])


@api.post("/chat/clear")
def clear():
    db = get_db()
    db.execute("DELETE FROM chat")
    db.commit()
    return jsonify(message="Chat history cleared")


@api.get("/dashboard/stats")
def stats():
    db = get_db()
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    n = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    rows = lambda sql, *a: [dict(r) for r in db.execute(sql, a)]
    total, done = n("SELECT COUNT(*) FROM tasks"), n("SELECT COUNT(*) FROM tasks WHERE completed=1")
    return jsonify(
        total_tasks=total, completed_tasks=done, pending_tasks=total - done,
        completion_percent=round(done * 100 / total) if total else 0,
        upcoming_reminders=n("SELECT COUNT(*) FROM reminders WHERE done=0 AND remind_at>=?", now),
        overdue_reminders=n("SELECT COUNT(*) FROM reminders WHERE done=0 AND remind_at<?", now),
        next_reminders=rows("SELECT id,title,remind_at FROM reminders WHERE done=0 ORDER BY remind_at LIMIT 5"),
        recent_notes=rows("SELECT id,title,updated_at FROM notes ORDER BY updated_at DESC, id DESC LIMIT 5"))
