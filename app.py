# Name: Aryan Zope
# PRN: 26070122053
"""TrustLearn prototype: a privacy-first AI learning layer for colleges.

Run:  pip install -r requirements.txt && python app.py   (then open http://127.0.0.1:5000)
All data is synthetic and kept in memory. The "AI tutor" is a rule-based stub standing in
for a local model (for example Ollama) that would run on the college's own server.
"""
import hashlib
import hmac
import os
import random
import statistics
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("TRUSTLEARN_SECRET", "dev-only-secret")
SALT = os.environ.get("TRUSTLEARN_SALT", "dev-only-salt").encode()

QUESTIONS = {
    1: {"q": "What does len([1, 2, 3] * 2) return?", "ans": "6",
        "hints": ["Multiplying a list repeats its items.", "[1, 2, 3] * 2 becomes [1, 2, 3, 1, 2, 3]."]},
    2: {"q": "What is the value of 7 // 2 ?", "ans": "3",
        "hints": ["// is floor division.", "7 / 2 is 3.5. Floor means round down."]},
    3: {"q": "How many numbers does range(2, 10, 3) produce?", "ans": "3",
        "hints": ["The third argument is the step.", "List them: 2, 5, 8. What would come next?"]},
}
STUDENTS, AUDIT, DECISIONS = {}, [], {}
ATTRS = {"Department": "dept", "Gender": "gender", "Language background": "lang", "Rural or urban": "area"}


def pseudonymize(student_id):
    """One-way keyed hash: the real ID never enters the learning data."""
    return hmac.new(SALT, student_id.encode(), hashlib.sha256).hexdigest()[:10]


def log(actor, action, detail=""):
    AUDIT.insert(0, {"time": datetime.now().strftime("%d %b %H:%M:%S"),
                     "actor": actor, "action": action, "detail": detail})


def make_event(qid, hints, revealed, days_ago):
    score = 0 if revealed else max(0, 1 - 0.35 * hints)  # fewer hints = more self-reliant
    return {"qid": qid, "hints": hints, "revealed": revealed, "days_ago": days_ago, "score": round(score, 2)}


def seed():
    """Create one demo student plus 60 synthetic students (rural students get less steady activity)."""
    rnd = random.Random(42)
    demo = pseudonymize("DEMO-001")
    STUDENTS[demo] = {"dept": "CSE", "gender": "Female", "lang": "English-medium", "area": "Urban",
                      "track": True, "share": True, "events": []}
    for i in range(1, 61):
        rural, track = rnd.random() < 0.4, rnd.random() < 0.9
        s = {"dept": rnd.choice(["CSE", "ENTC", "Mechanical"]),
             "gender": rnd.choices(["Female", "Male", "Non-binary"], [45, 45, 10])[0],
             "lang": rnd.choice(["English-medium", "Marathi-medium", "Hindi-medium"]),
             "area": "Rural" if rural else "Urban",
             "track": track, "share": track and rnd.random() < 0.85, "events": []}
        if track:
            last = rnd.randint(0, 12 if rural else 8)
            days = [last] + [last + rnd.randint(1, 10) for _ in range(rnd.randint(2, 7))]
            for d in days:
                s["events"].append(make_event(rnd.randint(1, 3), rnd.choice([0, 0, 1, 2]), rnd.random() < 0.1, d))
        STUDENTS[pseudonymize(f"STU-{i:03d}")] = s
    return demo


DEMO_PID = seed()


def reliance_score(s):
    """Self-reliance score (0-100): average of per-question scores, None if nothing recorded."""
    return round(100 * statistics.mean(e["score"] for e in s["events"])) if s["events"] else None


def alert_reasons(s):
    """Plain-language reasons for a support alert. Only students who opted in to sharing are checked."""
    if not s["share"] or not s["events"]:
        return []
    ev, reasons = s["events"], []
    idle = min(e["days_ago"] for e in ev)
    if idle >= 7:
        reasons.append(f"No practice for {idle} days")
    if len(ev) >= 3:
        if reliance_score(s) < 50:
            reasons.append(f"Self-reliance score is {reliance_score(s)}, below 50")
        shown = sum(e["revealed"] for e in ev)
        if shown / len(ev) >= 0.3:
            reasons.append(f"Answer revealed on {shown} of {len(ev)} questions")
    return reasons


def fairness():
    """Alert rate per group. A group is flagged when it has 5+ students and its rate is over 1.25x overall."""
    pool = [s for s in STUDENTS.values() if s["share"] and s["events"]]
    flagged = lambda grp: sum(bool(alert_reasons(s)) for s in grp) / len(grp)
    overall = flagged(pool) if pool else 0
    report = {}
    for label, key in ATTRS.items():
        rows = []
        for g in sorted({s[key] for s in pool}):
            grp = [s for s in pool if s[key] == g]
            rate = flagged(grp)
            rows.append({"group": g, "n": len(grp), "rate": round(rate * 100),
                         "flag": len(grp) >= 5 and overall > 0 and rate > 1.25 * overall})
        report[label] = rows
    return round(overall * 100), report


def finish(s, qid, st, revealed):
    st["done"], st["revealed"] = True, revealed
    if s["track"]:  # with tracking off, nothing is stored
        s["events"].append(make_event(qid, st["hints"], revealed, 0))


@app.route("/")
def home():
    return redirect(url_for("student"))


@app.route("/student")
def student():
    s, states = STUDENTS[DEMO_PID], session.get("st", {})
    blank = {"tries": 0, "hints": 0, "done": False, "revealed": False}
    cards = [{"id": i, **q, "st": states.get(str(i), blank)} for i, q in QUESTIONS.items()]
    return render_template("student.html", s=s, pid=DEMO_PID, cards=cards, score=reliance_score(s))


@app.post("/student/consent")
def consent():
    s = STUDENTS[DEMO_PID]
    s["track"] = "track" in request.form
    s["share"] = s["track"] and "share" in request.form
    log(f"student {DEMO_PID}", "consent updated", f"tracking={s['track']}, share with faculty={s['share']}")
    flash("Your privacy choices are saved.")
    return redirect(url_for("student"))


@app.post("/student/delete")
def delete_data():
    STUDENTS[DEMO_PID]["events"].clear()
    log(f"student {DEMO_PID}", "deleted own activity data")
    flash("All your recorded activity is deleted.")
    return redirect(url_for("student"))


@app.post("/practice/<int:qid>/<action>")
def practice(qid, action):
    q, s = QUESTIONS.get(qid), STUDENTS[DEMO_PID]
    if not q or action not in ("attempt", "hint", "reveal"):
        return redirect(url_for("student"))
    st = session.setdefault("st", {}).setdefault(str(qid), {"tries": 0, "hints": 0, "done": False, "revealed": False})
    if not st["done"]:
        if action == "attempt":
            if request.form.get("answer", "").strip().lower() == q["ans"]:
                finish(s, qid, st, False)
                flash("Correct. You solved it yourself.")
            else:
                st["tries"] += 1
                flash("Not quite. Rethink your approach and try once more.")
        elif action == "hint":
            if st["tries"] < 1:
                flash("Attempt the question first. Hints unlock after one try.")
            elif st["hints"] >= len(q["hints"]):
                flash("No hints left. Try again, or reveal the answer after 2 attempts.")
            else:
                st["hints"] += 1
        elif st["tries"] < 2:
            flash("The answer unlocks after 2 attempts.")
        else:
            finish(s, qid, st, True)
    session.modified = True
    return redirect(url_for("student"))


@app.route("/faculty")
def faculty():
    alerts = [{"pid": p, "dept": s["dept"], "reasons": alert_reasons(s), "decision": DECISIONS.get(p)}
              for p, s in STUDENTS.items() if alert_reasons(s)]
    alerts.sort(key=lambda a: -len(a["reasons"]))
    return render_template("faculty.html", alerts=alerts)


@app.post("/faculty/decide")
def decide():
    pid, choice = request.form.get("pid", ""), request.form.get("decision", "")
    note = request.form.get("note", "").strip()
    if pid not in STUDENTS or choice not in ("Reach out", "Keep monitoring", "Dismiss alert") or not note:
        flash("Choose a decision and add a short note. The AI only suggests; a person decides.")
    else:
        DECISIONS[pid] = {"decision": choice, "note": note}
        log("faculty", f"decision: {choice}", f"student {pid}: {note}")
    return redirect(url_for("faculty"))


@app.route("/admin")
def admin():
    overall, report = fairness()
    return render_template("admin.html", overall=overall, report=report, audit=AUDIT)


if __name__ == "__main__":
    app.run(debug=True)  # local demo only; use a production server and real auth for deployment
