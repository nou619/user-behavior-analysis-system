import json
import os
from statistics import mean

import requests


QC_FACULTIES = ["FMM", "FMT", "FMSF", "FMSO"]


def _num(value, default=0):
    try:
        return int(float(value or 0))
    except Exception:
        return default


def _pct(part: int, total: int) -> float:
    if not total:
        return 0.0
    return round((part / total) * 100, 1)


def _leaderboard_to_dicts(leaderboard) -> tuple[list[dict], list[dict]]:
    score_rows = []
    streak_rows = []

    for entry in leaderboard:
        row = {
            "rank": _num(getattr(entry, "rank", 0)),
            "student": getattr(entry, "user_fullname", ""),
            "faculty": getattr(entry, "faculte", ""),
            "level": getattr(entry, "niveau", ""),
            "value": _num(getattr(entry, "value", 0)),
        }
        category = str(getattr(entry, "category", "")).lower()
        if category == "score":
            score_rows.append(row)
        elif category == "streak":
            streak_rows.append(row)

    score_rows.sort(key=lambda x: x["rank"] or 999)
    streak_rows.sort(key=lambda x: x["rank"] or 999)
    return score_rows[:5], streak_rows[:5]


def build_platform_kpis(overview, leaderboard) -> dict:
    total = _num(getattr(overview, "total_students", 0))
    active = _num(getattr(overview, "active_this_week", 0))
    inactive = _num(getattr(overview, "inactive", 0))
    new_students = _num(getattr(overview, "new_this_week", 0))

    faculty = {
        "FMM": _num(getattr(overview, "count_fmm", 0)),
        "FMT": _num(getattr(overview, "count_fmt", 0)),
        "FMSF": _num(getattr(overview, "count_fmsf", 0)),
        "FMSO": _num(getattr(overview, "count_fmso", 0)),
    }

    score_rows, streak_rows = _leaderboard_to_dicts(leaderboard)
    avg_score = round(mean([r["value"] for r in score_rows]), 1) if score_rows else 0
    avg_streak = round(mean([r["value"] for r in streak_rows]), 1) if streak_rows else 0

    active_rate = _pct(active, total)
    new_rate = _pct(new_students, total)
    inactive_rate = _pct(inactive, total)

    momentum = round(active_rate * 2 + new_rate)
    momentum = max(0, min(100, momentum))

    if momentum >= 80:
        label = "Excellent"
    elif momentum >= 60:
        label = "Sain"
    elif momentum >= 35:
        label = "Stable"
    else:
        label = "À surveiller"

    return {
        "overview": {
            "total_students": total,
            "active_this_week": active,
            "inactive": inactive,
            "new_this_week": new_students,
        },
        "rates": {
            "active_rate": active_rate,
            "new_student_rate": new_rate,
            "inactive_rate": inactive_rate,
        },
        "faculty_distribution": faculty,
        "leaderboards": {
            "top_scores": score_rows,
            "top_streaks": streak_rows,
        },
        "computed": {
            "learning_momentum_index": momentum,
            "platform_health_label": label,
            "avg_top_score": avg_score,
            "avg_top_streak": avg_streak,
        },
    }


def _fallback_ai(kpis: dict) -> dict:
    ov = kpis["overview"]
    rates = kpis["rates"]
    computed = kpis["computed"]
    faculty = kpis["faculty_distribution"]
    top_faculty = max(faculty.items(), key=lambda x: x[1])[0] if faculty else "FMM"

    return {
        "executive_brief": (
            f"La dynamique de la plateforme demande une attention ciblée avec un Learning Momentum de "
            f"{computed['learning_momentum_index']}/100. Sur {ov['total_students']} étudiants, "
            f"{ov['active_this_week']} ont été actifs cette semaine, soit {rates['active_rate']}% d’engagement. "
            f"La croissance reste visible avec {ov['new_this_week']} nouveaux étudiants, tandis que {top_faculty} "
            f"concentre la plus forte présence étudiante."
        ),
        "recommended_actions": [
            {
                "title": "Réactiver les inactifs",
                "text": "Envoyer des rappels ciblés aux étudiants inactifs et pousser les parcours à forte valeur pour relancer l’engagement.",
            },
            {
                "title": "Renforcer le premier engagement",
                "text": "Encourager chaque nouvel étudiant à terminer un premier quiz dès la première session pour créer une habitude.",
            },
            {
                "title": "Capitaliser sur les leaders",
                "text": "Utiliser les meilleurs scores et streaks comme signaux marketing pour valoriser les parcours les plus attractifs.",
            },
        ],
    }


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return {}
    return {}


def _limit_words(text: str, max_words: int) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def generate_platform_ai(kpis: dict) -> dict:
    api_key = os.getenv("GENERAL_GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    model = os.getenv("GENERAL_GROQ_MODEL") or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
    timeout = int(os.getenv("AI_TIMEOUT_SECONDS", "25"))

    fallback = _fallback_ai(kpis)
    if not api_key:
        return fallback

    prompt = f"""
Tu écris pour un rapport exécutif QCMed utilisé aussi comme support marketing.
Tu dois écrire en français uniquement.
Tu dois copier exactement ce ton: premium, direct, positif mais crédible, comme un rapport préparé pour direction/partenaires.
Le texte doit tenir dans un PDF de 2 pages.

Contraintes strictes:
- executive_brief: 45 à 65 mots maximum.
- recommended_actions: exactement 3 actions.
- Chaque action: title très court + text entre 14 et 24 mots.
- Ne mentionne jamais les limites des données.
- N’écris jamais de roman.
- N’invente aucun KPI non fourni.
- Interprète les chiffres au lieu de les répéter mécaniquement.
- Pas de markdown.
- Réponds uniquement en JSON valide.

Style cible:
"La dynamique de la plateforme reste lisible et exploitable pour la direction. L’activité étudiante, la croissance récente et les signaux de classement indiquent où concentrer les efforts marketing et pédagogiques cette semaine."

JSON attendu:
{{
  "executive_brief": "...",
  "recommended_actions": [
    {{"title": "...", "text": "..."}},
    {{"title": "...", "text": "..."}},
    {{"title": "...", "text": "..."}}
  ]
}}

KPIs:
{json.dumps(kpis, ensure_ascii=False)}
""".strip()

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un analyste exécutif français spécialisé en intelligence plateforme, marketing SaaS et éducation médicale.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.25,
                "max_completion_tokens": 520,
            },
            timeout=timeout,
        )

        if response.status_code >= 400:
            print(f"General AI failed: HTTP {response.status_code}")
            return fallback

        text = response.json()["choices"][0]["message"]["content"]
        parsed = _extract_json(text)
        if not parsed:
            return fallback

        brief = _limit_words(str(parsed.get("executive_brief", "")).strip(), 65) or fallback["executive_brief"]
        actions = parsed.get("recommended_actions") or fallback["recommended_actions"]
        actions = actions[:3]
        while len(actions) < 3:
            actions.append(fallback["recommended_actions"][len(actions)])

        cleaned_actions = []
        for idx, action in enumerate(actions[:3]):
            fallback_action = fallback["recommended_actions"][idx]
            cleaned_actions.append(
                {
                    "title": _limit_words(action.get("title") or fallback_action["title"], 5),
                    "text": _limit_words(action.get("text") or fallback_action["text"], 24),
                }
            )

        return {
            "executive_brief": brief,
            "recommended_actions": cleaned_actions,
        }

    except Exception as exc:
        print(f"General AI failed: {type(exc).__name__}")
        return fallback


from datetime import datetime, timedelta
from html import escape

from services.sheets import load_overview, load_leaderboards
from services.email import send_email
from weasyprint import HTML
from zoneinfo import ZoneInfo


TUNIS_TZ = ZoneInfo("Africa/Tunis")


def now_local() -> datetime:
    return datetime.now(TUNIS_TZ).replace(tzinfo=None)


QC_NAVY = "#0D1B3E"
QC_RED = "#C8392E"
QC_BLUE = "#185FA5"
QC_BG = "#F5F8FC"
QC_LINE = "#DCE4EF"
QC_TEXT = "#172033"
QC_MUTED = "#667085"


def safe(value) -> str:
    return escape(str(value or ""))


def week_range() -> str:
    now = now_local()
    start = now - timedelta(days=7)
    return f"Semaine du {start.strftime('%d/%m/%Y')} au {now.strftime('%d/%m/%Y')}"


def pct(part: int, total: int) -> float:
    return round((part / total) * 100, 1) if total else 0.0


def bar(value, color=QC_BLUE) -> str:
    value = max(0, min(100, float(value or 0)))
    return f'<div class="mini-bar"><div class="mini-fill" style="width:{value}%;background:{color};"></div></div>'


def faculty_table(faculty: dict, total: int) -> str:
    rows = ""
    max_value = max(faculty.values()) if faculty else 1
    for name, count in faculty.items():
        share = pct(count, total)
        weight = round((count / max_value) * 100, 1) if max_value else 0
        rows += f"""
        <tr>
          <td>{safe(name)}</td>
          <td>{safe(count)}</td>
          <td>{safe(share)}%</td>
          <td>{bar(weight)}</td>
        </tr>
        """
    return rows


def leader_rows(rows: list[dict], unit: str) -> str:
    html = ""
    for row in rows[:5]:
        html += f"""
        <tr>
          <td class="rank">#{safe(row.get('rank'))}</td>
          <td>
            <strong>{safe(row.get('student'))}</strong>
            <span>{safe(row.get('faculty'))} · {safe(row.get('level'))}</span>
          </td>
          <td class="value"><strong>{safe(row.get('value'))}</strong><span>{safe(unit)}</span></td>
        </tr>
        """
    return html


def action_cards(actions: list[dict]) -> str:
    html = ""
    for index, item in enumerate(actions[:3], start=1):
        html += f"""
        <div class="action">
          <div class="action-number">{index}</div>
          <p><strong>{safe(item.get('title'))} :</strong> {safe(item.get('text'))}</p>
        </div>
        """
    return html


def build_html(overview, leaderboard, kpis: dict, ai: dict) -> str:
    generated_at = now_local().strftime("%d/%m/%Y %H:%M")
    period = week_range()

    ov = kpis["overview"]
    rates = kpis["rates"]
    computed = kpis["computed"]
    faculty = kpis["faculty_distribution"]
    top_scores = kpis["leaderboards"]["top_scores"]
    top_streaks = kpis["leaderboards"]["top_streaks"]

    momentum = computed["learning_momentum_index"]
    health = computed["platform_health_label"]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page {{ size: A4; margin: 10mm; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; color: {QC_TEXT}; background: white; font-size: 11px; line-height: 1.38; }}
.page {{ page-break-after: always; position: relative; min-height: 276mm; padding-bottom: 18px; }}
.page:last-child {{ page-break-after: auto; }}
.hero {{ background: {QC_NAVY}; color: white; border-radius: 18px; padding: 24px 28px; margin: 4px 0 14px; position: relative; overflow: hidden; }}
.hero:after {{ content: ""; position: absolute; right: -34px; top: -58px; width: 150px; height: 150px; border-radius: 50%; background: rgba(200,57,46,.46); }}
.eyebrow {{ color: #9FB8D8; letter-spacing: .16em; font-size: 8px; text-transform: uppercase; font-weight: 900; }}
h1 {{ margin: 8px 0 4px; font-size: 25px; line-height: 1.05; color: white; letter-spacing: -.5px; }}
.hero p {{ margin: 0; color: #C9D8EA; font-size: 11.5px; max-width: 610px; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; margin-bottom: 14px; }}
.kpi {{ background: {QC_BG}; border: 1px solid {QC_LINE}; border-radius: 14px; padding: 13px 13px; min-height: 83px; }}
.kpi-label {{ color: {QC_MUTED}; text-transform: uppercase; letter-spacing: .08em; font-weight: 900; font-size: 7.8px; }}
.kpi-value {{ color: {QC_NAVY}; font-size: 25px; font-weight: 900; margin-top: 8px; }}
.kpi-note {{ color: {QC_MUTED}; font-size: 9px; margin-top: 6px; }}
.title {{ font-size: 16px; color: {QC_NAVY}; font-weight: 900; margin: 14px 0 8px; }}
.brief {{ background: #F0F7FF; border: 1px solid #CFE4FF; border-left: 4px solid {QC_BLUE}; border-radius: 14px; padding: 13px 15px; font-size: 11.3px; line-height: 1.48; margin-bottom: 15px; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.card {{ border: 1px solid {QC_LINE}; border-radius: 15px; padding: 16px; background: white; overflow: hidden; }}
.card h2 {{ color: {QC_NAVY}; margin: 0 0 12px; font-size: 16px; }}
.health {{ display: grid; grid-template-columns: 132px 1fr; gap: 16px; align-items: center; min-height: 180px; }}
.ring {{ width: 126px; height: 126px; border-radius: 50%; border: 12px solid {QC_RED}; display: flex; flex-direction: column; align-items: center; justify-content: center; color: {QC_NAVY}; }}
.ring strong {{ font-size: 31px; line-height: 1; }}
.ring span {{ color: {QC_MUTED}; text-transform: uppercase; font-size: 8px; font-weight: 900; margin-top: 6px; }}
.pill {{ display: inline-block; background: {QC_RED}; color: white; border-radius: 99px; padding: 5px 11px; font-size: 9px; font-weight: 900; margin-bottom: 8px; }}
.health p {{ color: {QC_MUTED}; font-size: 11px; margin: 0 0 9px; }}
.metric-line {{ margin-top: 6px; }}
.metric-line strong {{ color: {QC_NAVY}; display: block; font-size: 10px; }}
.mini-bar {{ width: 100%; height: 7px; background: #EDF2F7; border-radius: 999px; overflow: hidden; }}
.mini-fill {{ height: 100%; border-radius: 999px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: {QC_NAVY}; color: #AFC4DE; text-transform: uppercase; letter-spacing: .08em; font-size: 7.5px; text-align: left; padding: 10px; }}
td {{ border-bottom: 1px solid #EEF2F6; padding: 10px; vertical-align: middle; }}
.faculty td {{ font-size: 11px; }}
.action {{ display: grid; grid-template-columns: 38px 1fr; gap: 11px; align-items: start; padding: 9px 0; border-bottom: 1px solid #EEF2F6; }}
.action:last-child {{ border-bottom: none; }}
.action-number {{ width: 30px; height: 30px; background: {QC_RED}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 12px; }}
.action p {{ margin: 0; font-size: 10.8px; color: {QC_TEXT}; }}
.action strong {{ color: {QC_NAVY}; }}
.leader-card {{ border: 1px solid {QC_LINE}; border-radius: 15px; padding: 14px; background: white; }}
.leader-card h2 {{ color: {QC_NAVY}; margin: 0 0 13px; font-size: 16px; }}
.leader-card table {{ border-collapse: separate; border-spacing: 0; overflow: hidden; border-radius: 8px; }}
.leader-card th {{ padding: 10px 13px; }}
.leader-card td {{ padding: 12px 13px; }}
.rank {{ color: {QC_RED}; font-weight: 900; width: 45px; }}
.leader-card td strong {{ color: {QC_NAVY}; display: block; }}
.leader-card td span {{ color: {QC_MUTED}; font-size: 9.4px; }}
.value {{ text-align: right; width: 92px; }}
.value strong {{ font-size: 13px; }}
.footer {{ position: absolute; left: 0; right: 0; bottom: 3px; border-top: 1px solid #E8EDF5; padding-top: 8px; color: #A3ADBA; font-size: 8px; }}
</style>
</head>
<body>

<section class="page">
  <div class="hero">
    <div class="eyebrow">QCMed Platform Intelligence</div>
    <h1>Rapport Général Plateforme</h1>
    <p>{safe(period)} · Généré le {safe(generated_at)} · Activité étudiants, santé d’engagement, momentum d’apprentissage et signaux de classement.</p>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="kpi-label">Étudiants inscrits</div><div class="kpi-value">{safe(ov['total_students'])}</div><div class="kpi-note">Apprenants enregistrés</div></div>
    <div class="kpi"><div class="kpi-label">Actifs cette semaine</div><div class="kpi-value">{safe(ov['active_this_week'])}</div><div class="kpi-note">{safe(rates['active_rate'])}% d’engagement</div></div>
    <div class="kpi"><div class="kpi-label">Nouveaux étudiants</div><div class="kpi-value">{safe(ov['new_this_week'])}</div><div class="kpi-note">{safe(rates['new_student_rate'])}% de la base</div></div>
    <div class="kpi"><div class="kpi-label">Inactifs</div><div class="kpi-value">{safe(ov['inactive'])}</div><div class="kpi-note">{safe(rates['inactive_rate'])}% inactifs</div></div>
  </div>

  <div class="title">Synthèse Exécutive IA</div>
  <div class="brief">{safe(ai.get('executive_brief'))}</div>

  <div class="title">Santé de la Plateforme</div>
  <div class="card health">
    <div class="ring"><strong>{safe(momentum)}</strong><span>Momentum</span></div>
    <div>
      <span class="pill">{safe(health)}</span>
      <p>L’indice de Learning Momentum combine l’engagement hebdomadaire, l’arrivée de nouveaux étudiants et la pression d’inactivité en un seul signal opérationnel. Il aide la direction à comprendre si la plateforme progresse dans la bonne direction.</p>
      <div class="metric-line"><strong>Engagement</strong>{bar(rates['active_rate'], QC_BLUE)}</div>
      <div class="metric-line"><strong>Croissance</strong>{bar(rates['new_student_rate'], QC_BLUE)}</div>
      <div class="metric-line"><strong>Pression d’inactivité</strong>{bar(rates['inactive_rate'], QC_RED)}</div>
    </div>
  </div>

  <div class="grid2" style="margin-top:13px;">
    <div>
      <div class="title">Répartition par Faculté</div>
      <div class="card" style="padding:12px;">
        <table class="faculty">
          <thead><tr><th>Faculté</th><th>Étudiants</th><th>Part</th><th>Poids</th></tr></thead>
          <tbody>{faculty_table(faculty, ov['total_students'])}</tbody>
        </table>
      </div>
    </div>
    <div>
      <div class="title">Actions Recommandées</div>
      <div class="card">{action_cards(ai.get('recommended_actions', []))}</div>
    </div>
  </div>

  <div class="footer">Rapport Général QCMed · Intelligence plateforme automatisée · Les alertes et la qualité du contenu sont traitées dans le Weekly Alert Report.</div>
</section>

<section class="page">
  <div class="grid2" style="margin-top:28px;">
    <div class="leader-card">
      <h2>Leaders par Score</h2>
      <table>
        <thead><tr><th>#</th><th>Étudiant</th><th style="text-align:right;">Valeur</th></tr></thead>
        <tbody>{leader_rows(top_scores, 'score')}</tbody>
      </table>
    </div>

    <div class="leader-card">
      <h2>Leaders par Streak</h2>
      <table>
        <thead><tr><th>#</th><th>Étudiant</th><th style="text-align:right;">Valeur</th></tr></thead>
        <tbody>{leader_rows(top_streaks, 'jours')}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">Rapport Général QCMed · Intelligence plateforme automatisée · Les alertes et la qualité du contenu sont traitées dans le Weekly Alert Report.</div>
</section>

</body>
</html>"""


def main():
    overview = load_overview()
    leaderboard = load_leaderboards()
    kpis = build_platform_kpis(overview, leaderboard)
    ai = generate_platform_ai(kpis)

    html = build_html(overview, leaderboard, kpis, ai)
    report_date = now_local().strftime("%Y-%m-%d")
    filename = f"QCMed_Rapport_General_Plateforme_{report_date}.pdf"
    pdf_bytes = HTML(string=html).write_pdf()

    recipients = [
        email.strip()
        for email in os.environ["RECIPIENT_EMAIL"].split(",")
        if email.strip()
    ]

    send_email(
        to=recipients,
        subject="QCMed — Rapport Général Plateforme",
        body="""QCMed — Rapport Général Plateforme

Le PDF est attaché.

Généré automatiquement par QCMed Intelligence.
""",
        is_html=False,
        attachment=pdf_bytes,
        attachment_filename=filename,
    )

    print("Rapport général plateforme envoyé avec PDF attaché.")


if __name__ == "__main__":
    main()
