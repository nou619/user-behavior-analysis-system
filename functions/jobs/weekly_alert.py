from datetime import datetime, timedelta
from html import escape
from collections import Counter

from services.sheets import load_sheet
from services.classifier import classify_alerts, enrich_alerts_with_weekly_groq
from services.email import send_email
from weasyprint import HTML
from zoneinfo import ZoneInfo
import os


TUNIS_TZ = ZoneInfo("Africa/Tunis")
WEEKLY_MAX_LLM_ALERTS = int(os.environ.get("WEEKLY_MAX_LLM_ALERTS", "8"))
WEEKLY_MAX_REPORT_ALERTS = int(os.environ.get("WEEKLY_MAX_REPORT_ALERTS", "20"))


def now_local() -> datetime:
    return datetime.now(TUNIS_TZ).replace(tzinfo=None)


QC_NAVY = "#0D1B3E"
QC_BLUE = "#185FA5"
QC_RED = "#C0392B"
QC_BG = "#F4F7FB"
QC_LINE = "#DCE4EF"
QC_TEXT = "#172033"
QC_MUTED = "#667085"


def safe(value) -> str:
    return escape(str(value or ""))


def html_lines(value) -> str:
    return safe(value).replace("\n", "<br>")


def parse_alert_datetime(value: str):
    try:
        return datetime.strptime(str(value or "").strip(), "%d/%m/%Y %H:%M")
    except Exception:
        return None


def compact(value: str, limit: int = 900) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


def get_this_week_alerts(alerts):
    now = now_local()
    week_ago = now - timedelta(days=7)
    result = []

    for alert in alerts:
        dt = parse_alert_datetime(alert.created_at)
        if dt and dt >= week_ago:
            result.append(alert)

    return result


def week_range() -> str:
    now = now_local()
    start = now - timedelta(days=7)
    return f"{start.strftime('%d/%m/%Y')} – {now.strftime('%d/%m/%Y')}"


def build_summary(classified: list[dict]) -> dict:
    critical = [a for a in classified if a.get("is_critical")]
    non_critical = [a for a in classified if not a.get("is_critical")]
    unique_questions = len(set(a.get("question_description", "") for a in classified))
    reviewed = len([a for a in critical if a.get("llm_justification_groq")])
    alert_types = Counter(a.get("alert_type", "Non spécifié") for a in classified)
    courses = Counter(a.get("matiere_title", "Non spécifié") for a in classified)

    return {
        "total": len(classified),
        "critical": len(critical),
        "non_critical": len(non_critical),
        "unique_questions": unique_questions,
        "reviewed": reviewed,
        "top_types": alert_types.most_common(4),
        "top_courses": courses.most_common(4),
    }


def mini_rows(items: list[tuple[str, int]]) -> str:
    if not items:
        return '<tr><td class="muted">Aucune donnée</td><td>0</td></tr>'

    rows = ""
    for name, count in items:
        rows += f"""
        <tr>
          <td>{safe(name)}</td>
          <td>{count}</td>
        </tr>
        """
    return rows


def ai_review_block(alert: dict) -> str:
    review = alert.get("llm_justification_groq") or "Analyse non générée."
    confidence = alert.get("llm_confidence_groq") or "N/A"

    return f"""
    <div class="ai-box">
      <div class="label">Analyse IA · Confiance {safe(confidence)}</div>
      <p>{html_lines(compact(review, 900))}</p>
    </div>
    """


def build_pdf_html(classified: list[dict]) -> str:
    summary = build_summary(classified)
    critical = [a for a in classified if a.get("is_critical")]
    critical.sort(
        key=lambda a: (
            a.get("score", 0),
            parse_alert_datetime(a.get("created_at", "")) or datetime.min,
        ),
        reverse=True,
    )
    displayed_critical = critical[:WEEKLY_MAX_REPORT_ALERTS]
    generated_at = now_local().strftime("%d/%m/%Y %H:%M")

    cards = ""
    for i, a in enumerate(displayed_critical, start=1):
        cards += f"""
        <section class="case">
          <div class="case-head">
            <div>
              <div class="case-label">Cas critique #{i}</div>
              <h2>{safe(a.get('alert_type'))}</h2>
              <div class="meta">{safe(a.get('created_at'))} · {safe(a.get('user_fullname'))} · {safe(a.get('user_faculte'))} {safe(a.get('user_niveau'))}</div>
            </div>
            <div class="score">{safe(a.get('score'))}/5</div>
          </div>

          <div class="two">
            <div class="box student">
              <div class="label">Commentaire étudiant</div>
              <p>{html_lines(compact(a.get('details'), 520))}</p>
            </div>
            <div class="box answer">
              <div class="label">Réponse officielle</div>
              <p>{html_lines(compact(a.get('question_correct_response'), 650))}</p>
            </div>
          </div>

          <div class="box">
            <div class="label">Question</div>
            <p>{html_lines(compact(a.get('question_description'), 1000))}</p>
          </div>

          <div class="box">
            <div class="label">Propositions</div>
            <p>{html_lines(compact(a.get('question_responses'), 850))}</p>
          </div>

          <div class="box no-border">
            {ai_review_block(a)}
          </div>
        </section>
        """

    if not cards:
        cards = '<section class="empty">Aucune alerte critique cette semaine.</section>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page {{ size: A4; margin: 13mm; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: Arial, sans-serif; color:{QC_TEXT}; background:white; font-size:11.6px; line-height:1.52; }}
.cover {{ background:{QC_NAVY}; color:white; border-radius:20px; padding:22px; margin-bottom:14px; border-bottom:5px solid {QC_RED}; }}
.brand {{ color:#AFC4DE; text-transform:uppercase; letter-spacing:.12em; font-size:9px; font-weight:900; }}
h1 {{ color:white; font-size:24px; margin:7px 0 4px; line-height:1.15; }}
.subtitle {{ color:#D7E3F4; font-size:11.5px; max-width:680px; }}
.kpis {{ display:table; width:100%; border-spacing:8px; margin:14px -8px 0; }}
.kpi {{ display:table-cell; width:20%; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); border-radius:14px; padding:10px; }}
.kpi small {{ display:block; color:#AFC4DE; text-transform:uppercase; font-size:8px; font-weight:900; }}
.kpi strong {{ display:block; color:white; font-size:20px; margin-top:4px; }}
.grid {{ display:table; width:100%; border-spacing:10px; margin:-10px 0 10px -10px; }}
.panel {{ display:table-cell; width:50%; border:1px solid {QC_LINE}; border-radius:16px; overflow:hidden; vertical-align:top; }}
.panel-head {{ background:{QC_BG}; padding:10px 12px; border-bottom:1px solid {QC_LINE}; font-weight:900; color:{QC_NAVY}; }}
table.clean {{ width:100%; border-collapse:collapse; }}
table.clean td {{ padding:8px 11px; border-bottom:1px solid #EEF2F6; }}
table.clean td:last-child {{ text-align:right; font-weight:900; color:{QC_RED}; }}
.case {{ page-break-inside: avoid; border:1px solid {QC_LINE}; border-radius:18px; overflow:hidden; margin-bottom:13px; }}
.case-head {{ display:table; width:100%; background:{QC_NAVY}; color:white; padding:12px 13px; }}
.case-head > div {{ display:table-cell; vertical-align:middle; }}
.case-label {{ color:#AFC4DE; text-transform:uppercase; letter-spacing:.1em; font-size:8px; font-weight:900; }}
h2 {{ color:white; font-size:14.5px; margin:3px 0; line-height:1.2; }}
.meta {{ color:#AFC4DE; font-size:9.8px; }}
.score {{ text-align:right; font-size:17px; font-weight:900; }}
.two {{ display:table; width:100%; }}
.two .box {{ display:table-cell; width:50%; }}
.box {{ padding:10px 12px; border-bottom:1px solid #EEF2F6; vertical-align:top; }}
.no-border {{ border-bottom:none; }}
.label {{ color:{QC_MUTED}; text-transform:uppercase; letter-spacing:.08em; font-size:8.5px; font-weight:900; margin-bottom:4px; }}
p {{ margin:0; word-break:break-word; }}
.student {{ background:#FFF5F4; color:#7A271A; }}
.answer {{ background:#F0F9FF; color:#0B4A6F; }}
.ai-box {{ background:#F1F7FF; border:1px solid #B9D8FF; border-left:4px solid {QC_BLUE}; border-radius:12px; padding:10px 11px; }}
.ai-box p {{ line-height:1.55; }}
.empty {{ border:1px solid {QC_LINE}; border-radius:16px; padding:18px; color:{QC_MUTED}; background:{QC_BG}; }}
.footer {{ margin-top:12px; color:#98A2B3; font-size:9.5px; border-top:1px solid #EAECF0; padding-top:8px; }}
</style>
</head>
<body>

<section class="cover">
  <div class="brand">QCMed Alert Intelligence</div>
  <h1>Rapport hebdomadaire des alertes</h1>
  <div class="subtitle">PDF court, propre et exploitable. Les analyses IA sont calibrées pour être utiles sans devenir longues.</div>
  <div class="kpis">
    <div class="kpi"><small>Période</small><strong style="font-size:13px">{week_range()}</strong></div>
    <div class="kpi"><small>Total</small><strong>{summary['total']}</strong></div>
    <div class="kpi"><small>Critiques</small><strong>{summary['critical']}</strong></div>
    <div class="kpi"><small>Questions</small><strong>{summary['unique_questions']}</strong></div>
    <div class="kpi"><small>IA</small><strong>{summary['reviewed']}</strong></div>
  </div>
</section>

<section class="grid">
  <div class="panel">
    <div class="panel-head">Types d'alertes principaux</div>
    <table class="clean">{mini_rows(summary['top_types'])}</table>
  </div>
  <div class="panel">
    <div class="panel-head">Matières les plus signalées</div>
    <table class="clean">{mini_rows(summary['top_courses'])}</table>
  </div>
</section>

{cards}

<div class="footer">QCMed Alert System · Rapport hebdomadaire PDF uniquement · Généré automatiquement le {generated_at}</div>
</body>
</html>"""


def main():
    all_alerts = load_sheet()
    week_alerts = get_this_week_alerts(all_alerts)
    classified = classify_alerts(week_alerts)
    critical = [a for a in classified if a.get("is_critical")]
    critical.sort(
        key=lambda a: (
            a.get("score", 0),
            parse_alert_datetime(a.get("created_at", "")) or datetime.min,
        ),
        reverse=True,
    )

    if critical:
        enrich_alerts_with_weekly_groq(critical, max_alerts=WEEKLY_MAX_LLM_ALERTS)

    print(f"{len(classified)} alerte(s) cette semaine, {len(critical)} critique(s).")

    report_date = now_local().strftime("%Y-%m-%d")
    pdf_html = build_pdf_html(classified)
    filename = f"QCMed_Rapport_Hebdomadaire_Alertes_{report_date}.pdf"
    pdf_bytes = HTML(string=pdf_html).write_pdf()

    recipients = [
        email.strip()
        for email in os.environ["RECIPIENT_EMAIL"].split(",")
        if email.strip()
    ]

    send_email(
        to=recipients,
        subject=f"QCMed — Rapport hebdomadaire des alertes ({len(critical)} critiques)",
        body=f"""QCMed — Rapport hebdomadaire des alertes

{len(classified)} alerte(s) cette semaine.
{len(critical)} alerte(s) critique(s).

Le PDF est attaché.
""",
        is_html=False,
        attachment=pdf_bytes,
        attachment_filename=filename,
    )

    print("Rapport hebdomadaire envoyé avec le PDF attaché.")


if __name__ == "__main__":
    main()
