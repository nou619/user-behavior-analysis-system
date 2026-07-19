from datetime import datetime, timedelta
from html import escape

from services.sheets import load_sheet
from services.classifier import (
    classify_alerts,
    enrich_alerts_with_instant_llms,
    build_alert_investigation_prompt,
)
from services.email import send_email
from weasyprint import HTML
from zoneinfo import ZoneInfo
import os


TUNIS_TZ = ZoneInfo("Africa/Tunis")


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


def compact(value: str, limit: int = 1800) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


def is_today_or_yesterday(created_at: str) -> bool:
    dt = parse_alert_datetime(created_at)
    if not dt:
        return False

    today = now_local().date()
    yesterday = today - timedelta(days=1)
    return dt.date() in {today, yesterday}


def get_today_yesterday_critical_alerts(classified: list[dict]) -> list[dict]:
    selected = [a for a in classified if a.get("is_critical") and is_today_or_yesterday(a.get("created_at", ""))]

    selected.sort(
        key=lambda a: parse_alert_datetime(a.get("created_at", "")) or datetime.min,
        reverse=True,
    )

    return selected


def provider_review_html(a: dict, provider: str, title: str) -> str:
    review = a.get(f"llm_justification_{provider}") or ""
    confidence = a.get(f"llm_confidence_{provider}") or "N/A"
    verdict = a.get(f"alert_verdict_{provider}") or "Non généré"
    action = a.get(f"admin_action_{provider}") or "En attente"

    if review:
        body = html_lines(review)
    else:
        body = "Analyse non générée pour ce provider. Vérifiez la clé API ou la limite de quota."

    return f"""
    <div class="ai-block {provider}">
      <div class="ai-head">
        <div>
          <div class="mini-label">{safe(title)}</div>
          <strong>{safe(verdict)}</strong>
        </div>
        <div class="confidence">{safe(confidence)}</div>
      </div>
      <div class="ai-body">{body}</div>
      <div class="action-chip">Action admin: {safe(action)}</div>
    </div>
    """


def build_pdf_html(alerts: list[dict]) -> str:
    generated_at = now_local().strftime("%d/%m/%Y %H:%M")
    reviewed_groq = len([a for a in alerts if a.get("llm_justification_groq")])
    reviewed_openai = len([a for a in alerts if a.get("llm_justification_openai")])
    unique_questions = len(set(a.get("question_description", "") for a in alerts))

    cards = ""

    for i, a in enumerate(alerts, start=1):
        cards += f"""
        <section class="case">
          <div class="case-head">
            <div>
              <div class="case-label">Cas critique #{i}</div>
              <h2>{safe(a.get("alert_type"))}</h2>
              <div class="meta">
                {safe(a.get("created_at"))} · {safe(a.get("user_fullname"))} · {safe(a.get("user_faculte"))} {safe(a.get("user_niveau"))}
              </div>
            </div>
            <div class="score">{safe(a.get("score"))}/5</div>
          </div>

          <div class="two">
            <div class="box student">
              <div class="label">Commentaire étudiant</div>
              <p>{html_lines(compact(a.get("details"), 700))}</p>
            </div>

            <div class="box answer">
              <div class="label">Réponse officielle</div>
              <p>{html_lines(compact(a.get("question_correct_response"), 900))}</p>
            </div>
          </div>

          <div class="box">
            <div class="label">Question</div>
            <p>{html_lines(compact(a.get("question_description"), 1500))}</p>
          </div>

          <div class="box">
            <div class="label">Propositions disponibles</div>
            <p>{html_lines(compact(a.get("question_responses"), 1300))}</p>
          </div>

          <div class="two">
            <div class="box ai-cell">
              {provider_review_html(a, "groq", "Analyse Groq")}
            </div>
            <div class="box ai-cell">
              {provider_review_html(a, "openai", "Analyse OpenAI")}
            </div>
          </div>
        </section>
        """

    if not cards:
        cards = """
        <section class="empty">
          Aucun cas critique trouvé pour aujourd'hui et hier.
        </section>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
@page {{
  size: A4;
  margin: 14mm;
}}

body {{
  font-family: Arial, sans-serif;
  color: {QC_TEXT};
  font-size: 11.8px;
  line-height: 1.55;
  margin: 0;
}}

.cover {{
  border-bottom: 4px solid {QC_RED};
  padding-bottom: 16px;
  margin-bottom: 20px;
}}

.brand {{
  color: {QC_RED};
  text-transform: uppercase;
  letter-spacing: .12em;
  font-size: 9px;
  font-weight: 800;
}}

h1 {{
  color: {QC_NAVY};
  font-size: 24px;
  margin: 7px 0 5px;
  line-height: 1.15;
}}

.subtitle {{
  color: {QC_MUTED};
  font-size: 12px;
}}

.kpis {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 8px;
  margin: 15px -8px 0;
}}

.kpi {{
  background: {QC_BG};
  border: 1px solid {QC_LINE};
  border-radius: 12px;
  padding: 11px;
}}

.kpi small {{
  color: {QC_MUTED};
  text-transform: uppercase;
  font-size: 8.5px;
  font-weight: 800;
}}

.kpi strong {{
  display: block;
  color: {QC_NAVY};
  font-size: 19px;
  margin-top: 4px;
}}

.case {{
  page-break-inside: avoid;
  border: 1px solid {QC_LINE};
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 13px;
}}

.case-head {{
  background: {QC_NAVY};
  color: white;
  padding: 12px;
  display: table;
  width: 100%;
}}

.case-head > div {{
  display: table-cell;
  vertical-align: middle;
}}

.case-label {{
  color: #AFC4DE;
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: 8.5px;
  font-weight: 800;
}}

h2 {{
  margin: 3px 0;
  font-size: 14px;
  line-height: 1.25;
}}

.meta {{
  color: #AFC4DE;
  font-size: 9.8px;
}}

.score {{
  text-align: right;
  font-size: 16px;
  font-weight: 800;
  color: white;
}}

.two {{
  display: table;
  width: 100%;
}}

.two .box {{
  display: table-cell;
  width: 50%;
}}

.box {{
  padding: 10px 12px;
  border-bottom: 1px solid #EEF2F6;
  vertical-align: top;
}}

.label, .mini-label {{
  color: {QC_MUTED};
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: 8.5px;
  font-weight: 800;
  margin-bottom: 5px;
}}

.box p {{
  margin: 0;
  line-height: 1.6;
  word-break: break-word;
}}

.student {{
  background: #FFF5F4;
  color: #7A271A;
}}

.answer {{
  background: #F0F9FF;
  color: #0B4A6F;
}}

.ai-cell {{
  background: #FAFCFF;
}}

.ai-block {{
  border-radius: 11px;
  border: 1px solid #B9E6FE;
  border-left: 4px solid {QC_BLUE};
  padding: 10px;
  background: #F1F7FF;
}}

.ai-block.openai {{
  border-color: #D0D5DD;
  border-left-color: #101828;
  background: #FAFAFA;
}}

.ai-head {{
  display: table;
  width: 100%;
  margin-bottom: 7px;
}}

.ai-head > div {{
  display: table-cell;
  vertical-align: middle;
}}

.ai-head strong {{
  color: {QC_NAVY};
}}

.confidence {{
  text-align: right;
  font-weight: 800;
  color: {QC_RED};
  white-space: nowrap;
}}

.ai-body {{
  white-space: normal;
  word-break: break-word;
}}

.action-chip {{
  margin-top: 8px;
  color: {QC_NAVY};
  font-weight: 800;
}}

.empty {{
  border: 1px solid {QC_LINE};
  border-radius: 14px;
  padding: 18px;
  color: {QC_MUTED};
  background: {QC_BG};
}}
</style>
</head>
<body>

<div class="cover">
  <div class="brand">QCMed AI Alert Review</div>
  <h1>Alertes critiques — aujourd'hui et hier</h1>
  <div class="subtitle">
    Rapport instantané limité aux alertes critiques créées aujourd'hui ou hier. Chaque cas inclut une analyse structurée en français pour guider la décision admin.
  </div>

  <table class="kpis">
    <tr>
      <td class="kpi"><small>Alertes critiques</small><strong>{len(alerts)}</strong></td>
      <td class="kpi"><small>Questions uniques</small><strong>{unique_questions}</strong></td>
      <td class="kpi"><small>Groq analysées</small><strong>{reviewed_groq}</strong></td>
      <td class="kpi"><small>OpenAI analysées</small><strong>{reviewed_openai}</strong></td>
      <td class="kpi"><small>Généré</small><strong style="font-size:13px">{generated_at}</strong></td>
    </tr>
  </table>
</div>

{cards}

</body>
</html>"""


def build_interactive_html(alerts: list[dict]) -> str:
    generated_at = now_local().strftime("%d/%m/%Y %H:%M")
    reviewed_groq = len([a for a in alerts if a.get("llm_justification_groq")])
    reviewed_openai = len([a for a in alerts if a.get("llm_justification_openai")])
    unique_questions = len(set(a.get("question_description", "") for a in alerts))

    cards = ""

    for i, a in enumerate(alerts, start=1):
        groq = a.get("llm_justification_groq") or "Analyse Groq non générée."
        groq_conf = a.get("llm_confidence_groq") or "N/A"
        openai = a.get("llm_justification_openai") or "Analyse OpenAI réservée ou non générée."
        openai_conf = a.get("llm_confidence_openai") or "N/A"
        prompt = build_alert_investigation_prompt(a)

        cards += f"""
        <article class="alert-card"
          data-index="{i}"
          data-score="{safe(a.get("score"))}"
          data-type="{safe(a.get("alert_type"))}"
          data-student="{safe(a.get("user_fullname"))}"
          data-faculty="{safe(a.get("user_faculte"))}"
          data-text="{safe(a.get("question_description"))} {safe(a.get("details"))} {safe(a.get("question_responses"))}"
        >
          <div class="card-top">
            <div>
              <div class="case-label">Cas #{i}</div>
              <h2>{safe(a.get("alert_type"))}</h2>
              <div class="meta">
                {safe(a.get("created_at"))} · {safe(a.get("user_fullname"))} · {safe(a.get("user_faculte"))} {safe(a.get("user_niveau"))}
              </div>
            </div>
            <div class="risk">
              <span>{safe(a.get("score"))}/5</span>
              <small>Risque</small>
            </div>
          </div>

          <div class="quick-line">
            <span>Signalée {safe(a.get("alert_count_same_question"))}x</span>
            <span>{safe(a.get("question_times_answered"))} réponses étudiants</span>
            <span>Groq: {safe(groq_conf)}</span>
            <span>OpenAI: {safe(openai_conf)}</span>
          </div>

          <div class="tabs">
            <button class="tab active" onclick="showTab(this, 'review-{i}')">Analyse IA</button>
            <button class="tab" onclick="showTab(this, 'question-{i}')">Question</button>
            <button class="tab" onclick="showTab(this, 'answers-{i}')">Réponses</button>
            <button class="tab" onclick="showTab(this, 'prompt-{i}')">Prompt</button>
          </div>

          <section id="review-{i}" class="tab-panel active">
            <div class="split">
              <div class="panel student">
                <div class="panel-label">Commentaire étudiant</div>
                <p>{safe(compact(a.get("details"), 700))}</p>
              </div>
              <div class="panel ai">
                <div class="panel-label">Analyse Groq</div>
                <p>{safe(groq).replace(chr(10), "<br>")}</p>
              </div>
            </div>
            <div class="panel openai-panel">
              <div class="panel-label">Analyse OpenAI</div>
              <p>{safe(openai).replace(chr(10), "<br>")}</p>
            </div>
          </section>

          <section id="question-{i}" class="tab-panel">
            <div class="panel">
              <div class="panel-label">Question</div>
              <p>{safe(compact(a.get("question_description"), 2600))}</p>
            </div>
          </section>

          <section id="answers-{i}" class="tab-panel">
            <div class="split">
              <div class="panel">
                <div class="panel-label">Propositions disponibles</div>
                <p>{safe(compact(a.get("question_responses"), 2400)).replace(chr(10), "<br>")}</p>
              </div>
              <div class="panel official">
                <div class="panel-label">Réponse officielle</div>
                <p>{safe(compact(a.get("question_correct_response"), 1200)).replace(chr(10), "<br>")}</p>
              </div>
            </div>
          </section>

          <section id="prompt-{i}" class="tab-panel">
            <div class="panel dark">
              <div class="panel-label">Prompt prêt à vérifier</div>
              <pre id="copy-prompt-{i}">{safe(prompt)}</pre>
              <button class="copy-btn" onclick="copyPrompt('copy-prompt-{i}', this)">Copier le prompt</button>
              <a class="gemini-link" href="https://gemini.google.com/app" target="_blank">Ouvrir Gemini</a>
            </div>
          </section>
        </article>
        """

    if not cards:
        cards = """
        <section class="empty-card">
          Aucune alerte critique trouvée pour aujourd'hui et hier.
        </section>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>QCMed Interactive Critical Alerts</title>
<style>
:root {{
  --navy:#0D1B3E;
  --blue:#185FA5;
  --red:#C0392B;
  --bg:#F4F7FB;
  --card:#FFFFFF;
  --text:#172033;
  --muted:#667085;
  --line:#DCE4EF;
}}

* {{ box-sizing:border-box; }}

body {{
  margin:0;
  font-family:Inter, Arial, sans-serif;
  background:linear-gradient(135deg,#F4F7FB,#FFFFFF);
  color:var(--text);
}}

.app {{ max-width:1180px; margin:0 auto; padding:34px 22px 60px; }}

.hero {{
  background:var(--navy);
  color:white;
  border-radius:28px;
  padding:34px;
  box-shadow:0 24px 60px rgba(13,27,62,.18);
  position:relative;
  overflow:hidden;
}}

.hero:after {{
  content:"";
  position:absolute;
  right:-80px;
  top:-80px;
  width:260px;
  height:260px;
  border-radius:50%;
  background:rgba(192,57,43,.35);
}}

.eyebrow {{ color:#9FB8D8; text-transform:uppercase; letter-spacing:.12em; font-size:12px; font-weight:800; }}
h1 {{ margin:10px 0 6px; font-size:42px; line-height:1.05; }}
.hero p {{ color:#D7E3F4; max-width:760px; }}

.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-top:24px; }}
.kpi {{ background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); border-radius:18px; padding:18px; backdrop-filter:blur(8px); }}
.kpi small {{ color:#9FB8D8; text-transform:uppercase; font-weight:800; font-size:11px; }}
.kpi strong {{ display:block; margin-top:6px; font-size:28px; }}

.toolbar {{
  display:flex;
  gap:12px;
  flex-wrap:wrap;
  align-items:center;
  margin:24px 0;
  background:white;
  border:1px solid var(--line);
  border-radius:22px;
  padding:14px;
  position:sticky;
  top:12px;
  z-index:10;
  box-shadow:0 10px 30px rgba(16,24,40,.06);
}}

.search {{ flex:1; min-width:260px; }}
input, select {{ width:100%; border:1px solid var(--line); border-radius:14px; padding:12px 14px; font-size:14px; }}

.alert-card {{ background:var(--card); border:1px solid var(--line); border-radius:26px; margin-bottom:18px; overflow:hidden; box-shadow:0 14px 36px rgba(16,24,40,.07); }}
.card-top {{ display:flex; justify-content:space-between; gap:20px; padding:24px; background:linear-gradient(180deg,#FFFFFF,#F8FAFC); border-bottom:1px solid var(--line); }}
.case-label {{ color:var(--red); text-transform:uppercase; letter-spacing:.1em; font-size:11px; font-weight:900; }}
h2 {{ margin:6px 0; color:var(--navy); font-size:24px; }}
.meta {{ color:var(--muted); font-size:13px; }}
.risk {{ min-width:92px; height:92px; border-radius:24px; background:var(--red); color:white; display:flex; flex-direction:column; justify-content:center; align-items:center; }}
.risk span {{ font-size:26px; font-weight:900; }}
.risk small {{ opacity:.85; text-transform:uppercase; font-weight:800; font-size:11px; }}

.quick-line {{ display:flex; gap:10px; flex-wrap:wrap; padding:14px 24px; border-bottom:1px solid var(--line); }}
.quick-line span {{ background:#EEF4FF; color:#3538CD; padding:7px 11px; border-radius:999px; font-size:12px; font-weight:800; }}
.tabs {{ display:flex; gap:8px; padding:14px 24px 0; }}
.tab {{ border:0; background:#F2F4F7; color:#475467; padding:10px 14px; border-radius:14px 14px 0 0; font-weight:800; cursor:pointer; }}
.tab.active {{ background:var(--navy); color:white; }}
.tab-panel {{ display:none; padding:24px; }}
.tab-panel.active {{ display:block; }}
.split {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.panel {{ border:1px solid var(--line); border-radius:18px; padding:16px; background:#F8FAFC; }}
.panel-label {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:11px; font-weight:900; margin-bottom:8px; }}
.student {{ background:#FFF5F4; border-color:#F4B8B0; }}
.ai {{ background:#EFF8FF; border-color:#B9E6FE; }}
.official {{ background:#ECFDF3; border-color:#ABEFC6; }}
.openai-panel {{ margin-top:16px; background:#FAFAFA; border-style:dashed; }}
.dark {{ background:#101828; color:white; border-color:#101828; }}
.dark .panel-label {{ color:#98A2B3; }}
pre {{ white-space:pre-wrap; word-break:break-word; font-family:Consolas, monospace; font-size:13px; line-height:1.55; }}
.copy-btn, .gemini-link {{ display:inline-block; margin-top:12px; margin-right:8px; background:var(--blue); color:white; border:0; border-radius:12px; padding:11px 14px; font-weight:900; cursor:pointer; text-decoration:none; }}
.empty-card {{ background:white; border:1px solid var(--line); border-radius:22px; padding:30px; color:var(--muted); box-shadow:0 14px 36px rgba(16,24,40,.07); }}
.hidden {{ display:none !important; }}

@media(max-width:900px) {{ .kpis {{ grid-template-columns:1fr 1fr; }} }}
@media(max-width:760px) {{ h1 {{ font-size:32px; }} .split {{ grid-template-columns:1fr; }} .card-top {{ flex-direction:column; }} .risk {{ width:92px; }} }}
</style>
</head>
<body>
<div class="app">

  <section class="hero">
    <div class="eyebrow">QCMed Interactive Review</div>
    <h1>Alertes critiques — aujourd'hui et hier</h1>
    <p>Rapport interactif en français. Il affiche uniquement les alertes critiques créées aujourd'hui ou hier, avec analyse Groq et espace OpenAI séparé.</p>

    <div class="kpis">
      <div class="kpi"><small>Alertes critiques</small><strong>{len(alerts)}</strong></div>
      <div class="kpi"><small>Groq analysées</small><strong>{reviewed_groq}</strong></div>
      <div class="kpi"><small>OpenAI analysées</small><strong>{reviewed_openai}</strong></div>
      <div class="kpi"><small>Questions uniques</small><strong>{unique_questions}</strong></div>
      <div class="kpi"><small>Généré</small><strong style="font-size:17px">{generated_at}</strong></div>
    </div>
  </section>

  <section class="toolbar">
    <div class="search">
      <input id="search" placeholder="Rechercher question, commentaire, étudiant, faculté..." oninput="applyFilters()">
    </div>
    <div>
      <select id="scoreFilter" onchange="applyFilters()">
        <option value="">Tous les scores</option>
        <option value="5">Risque 5/5</option>
        <option value="4">Risque 4/5</option>
      </select>
    </div>
    <div>
      <select id="typeFilter" onchange="applyFilters()">
        <option value="">Tous les types</option>
        <option value="la question est fausse">Question fausse</option>
        <option value="la réponse est fausse">Réponse fausse</option>
        <option value="aucune proposition est correcte">Aucune proposition correcte</option>
      </select>
    </div>
  </section>

  <main id="alerts">{cards}</main>

</div>

<script>
function showTab(button, panelId) {{
  const card = button.closest('.alert-card');
  card.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  card.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  button.classList.add('active');
  card.querySelector('#' + panelId).classList.add('active');
}}

function applyFilters() {{
  const q = document.getElementById('search').value.toLowerCase();
  const score = document.getElementById('scoreFilter').value;
  const type = document.getElementById('typeFilter').value.toLowerCase();

  document.querySelectorAll('.alert-card').forEach(card => {{
    const text = card.dataset.text.toLowerCase();
    const student = card.dataset.student.toLowerCase();
    const faculty = card.dataset.faculty.toLowerCase();
    const cardScore = card.dataset.score;
    const cardType = card.dataset.type.toLowerCase();

    const matchesSearch = !q || text.includes(q) || student.includes(q) || faculty.includes(q);
    const matchesScore = !score || cardScore === score;
    const matchesType = !type || cardType.includes(type);

    card.classList.toggle('hidden', !(matchesSearch && matchesScore && matchesType));
  }});
}}

async function copyPrompt(id, btn) {{
  const text = document.getElementById(id).innerText;
  await navigator.clipboard.writeText(text);
  const old = btn.innerText;
  btn.innerText = 'Copié ✓';
  setTimeout(() => btn.innerText = old, 1200);
}}
</script>
</body>
</html>"""


def main():
    all_alerts = load_sheet()
    classified = classify_alerts(all_alerts)
    selected = get_today_yesterday_critical_alerts(classified)
    selected = enrich_alerts_with_instant_llms(selected)

    report_date = now_local().strftime("%Y-%m-%d")
    pdf_html = build_pdf_html(selected)
    interactive_html = build_interactive_html(selected)

    pdf_filename = f"QCMed_Alertes_Critiques_{report_date}.pdf"
    html_filename = f"QCMed_Revue_Interactive_{report_date}.html"
    pdf_bytes = HTML(string=pdf_html).write_pdf()

    recipients = [
        email.strip()
        for email in os.environ["RECIPIENT_EMAIL"].split(",")
        if email.strip()
    ]

    send_email(
        to=recipients,
        subject=f"QCMed Alertes critiques — aujourd'hui + hier ({len(selected)})",
        body=f"""QCMed AI Review

{len(selected)} alerte(s) critique(s) d'aujourd'hui et d'hier incluses.

Pièces jointes :
- PDF : archive officielle
- HTML : revue interactive

Généré automatiquement par QCMed AI.
""",
        is_html=False,
        attachments=[
            (pdf_filename, pdf_bytes, "application/pdf"),
            (html_filename, interactive_html.encode("utf-8"), "text/html"),
        ],
    )

    print(f"{len(selected)} alerte(s) critique(s) d'aujourd'hui et d'hier envoyée(s) avec PDF + HTML.")


if __name__ == "__main__":
    main()
