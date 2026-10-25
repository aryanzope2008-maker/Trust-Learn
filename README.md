# TrustLearn

A prototype of a privacy-first AI learning layer for colleges, built with Python (Flask) and HTML templates.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. All data is synthetic and held in memory, so it resets on restart.

## How it maps to the three concerns

| Concern | In this prototype |
|---|---|
| Data privacy | IDs are pseudonymized with a keyed hash. Students control tracking and sharing, see every record collected, and can delete it. |
| Over-reliance | Hints unlock only after an attempt, answers after two attempts, and a self-reliance score is shown. |
| Bias | The Ethics panel compares alert rates by department, gender, language background and rural or urban, and flags outliers. Each alert lists its reasons. Faculty must record a decision with a note. |

## Not built yet

Real login and roles, a database, a local LLM tutor (for example Ollama), a faculty-student ethics panel workflow, and consent versioning.

## Structure

```
app.py            routes, privacy, scoring, alert and fairness logic
templates/        base.html, student.html, faculty.html, admin.html
requirements.txt
```
