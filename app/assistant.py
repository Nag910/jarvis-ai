"""Jarvis local assistant engine.

100% offline and rule-based: it matches your message against known commands
using regular expressions. It is NOT an AI language model, and it never
connects to the internet. Replies are labelled 'Local engine'.
"""
import ast, operator, random, re
from datetime import datetime

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow}
JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "A SQL query walks into a bar, sees two tables and asks: can I join you?",
]
HELP = ("I'm a local, rule-based assistant. Try: 'show my tasks', 'create task Buy milk', "
        "'show reminders', 'show notes', 'stats', 'what time is it', 'calculate 12*(3+4)', or 'tell me a joke'.")


def calc(expr):
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ValueError("too big")
            return OPS[type(n.op)](a, b)
        raise ValueError("unsupported")
    if len(expr) > 60:
        raise ValueError("too long")
    return ev(ast.parse(expr, mode="eval"))


def respond(message, db):
    m = message.strip()
    low = m.lower()
    out = lambda reply, action=None: {"reply": reply, "action": action, "mode": "local"}
    count = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")

    t = re.match(r"^(?:please\s+)?(?:create|add|new)\s+(?:a\s+)?task\s*(?:to|:|called|named)?\s*(.*)$", m, re.I)
    if t:
        title = t.group(1).strip()[:100]
        if not title:
            return out("What should the task be? Example: create task Finish report")
        return out(f"I can create the task \"{title}\". Please confirm.", {"type": "create_task", "title": title})

    expr = re.sub(r"^(?:calc(?:ulate)?|what(?:'s| is))\s*", "", low).rstrip("?= ").replace("^", "**").replace("x", "*")
    if re.fullmatch(r"[0-9+\-*/().% ]+", expr) and re.search(r"\d\s*[-+*/%]", expr):
        try:
            return out(f"{expr} = {round(calc(expr), 6):g}")
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return out("Sorry, I couldn't calculate that expression.")

    if re.search(r"\b(hello|hi|hey|good (morning|evening|afternoon))\b", low):
        return out("Hello! Jarvis online. How can I help you today?")
    if re.search(r"what can you do|help|commands", low):
        return out(HELP)
    if re.search(r"\btime\b", low):
        return out("The time is " + datetime.now().strftime("%I:%M %p") + ".")
    if re.search(r"\b(date|day|today)\b", low) and "task" not in low:
        return out("Today is " + datetime.now().strftime("%A, %d %B %Y") + ".")
    if re.search(r"(show|list|what).*task|my tasks|pending", low):
        rows = db.execute("SELECT title, priority FROM tasks WHERE completed=0 ORDER BY id DESC LIMIT 8").fetchall()
        if not rows:
            return out("You have no pending tasks. Nice work!")
        return out("Pending tasks:\n" + "\n".join(f"• {r['title']} ({r['priority']})" for r in rows))
    if "remind" in low:
        rows = db.execute("SELECT title, remind_at FROM reminders WHERE done=0 ORDER BY remind_at LIMIT 8").fetchall()
        if not rows:
            return out("You have no active reminders.")
        return out("Reminders:\n" + "\n".join(
            f"• {r['title']} at {r['remind_at'].replace('T', ' ')}" + (" (overdue)" if r['remind_at'] < now else "") for r in rows))
    if re.search(r"\bnotes?\b", low):
        rows = db.execute("SELECT title FROM notes ORDER BY updated_at DESC LIMIT 5").fetchall()
        if not rows:
            return out("You have no notes yet.")
        return out("Recent notes:\n" + "\n".join(f"• {r['title']}" for r in rows))
    if re.search(r"stat|progress|summary", low):
        total, done = count("SELECT COUNT(*) FROM tasks"), count("SELECT COUNT(*) FROM tasks WHERE completed=1")
        up = count("SELECT COUNT(*) FROM reminders WHERE done=0 AND remind_at>=?", now)
        return out(f"{total} tasks total, {done} completed ({round(done * 100 / total) if total else 0}%), "
                   f"{up} upcoming reminders, {count('SELECT COUNT(*) FROM notes')} notes.")
    if "joke" in low:
        return out(random.choice(JOKES))
    if re.search(r"who are you|your name|about you", low):
        return out("I'm Jarvis, a local personal assistant. I run entirely on this computer, with no cloud or internet connection.")
    if "thank" in low:
        return out("You're welcome!")
    if re.search(r"\b(bye|goodbye)\b", low):
        return out("Goodbye! Jarvis standing by.")
    return out("I didn't understand that. I only know specific commands. " + HELP)
