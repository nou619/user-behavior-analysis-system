<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0D1B3E,100:185FA5&height=200&section=header&text=User%20Behavior%20Analysis%20System&fontSize=38&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Automated%20Analytics%20%26%20Alert%20Intelligence%20Pipeline&descAlignY=55&descSize=16" width="100%"/>

<a href="#"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&duration=3000&pause=800&color=185FA5&center=true&vCenter=true&width=650&lines=Automated+Weekly+%2F+Instant+Alert+Reports;AI-Powered+Alert+Classification+%26+Scoring;PDF+Generation+%2B+Transactional+Email+Delivery;Built+during+a+Data%2FBackend+Internship" alt="Typing SVG" /></a>

<br/>

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Status-Internship_Project-C0392B?style=for-the-badge)
![Data](https://img.shields.io/badge/User_Data-Anonymized-0D1B3E?style=for-the-badge&logo=shieldsdotio&logoColor=white)
![Snapshot](https://img.shields.io/badge/Repo-Single_Commit_Snapshot-orange?style=for-the-badge&logo=git&logoColor=white)
![License](https://img.shields.io/badge/License-Private-lightgrey?style=for-the-badge)

</div>

---

## 🔒 A note before you scroll

> This repository is a **portfolio copy** of an internal analytics system I built during a backend/data internship.
> The **company name, real user data, and any identifying information have been redacted or anonymized**. Screenshots below have sensitive numbers (student counts, names, emails) **blurred**. Any brand names left inside the code/templates (colors, PDF headers, etc.) are internal placeholders and do **not** represent the actual client.
>
> **Why this repo has a single commit:** this is a **snapshot copy-paste** of the original codebase, published here purely to showcase the work. The real project lives in a **private company repository** with a full commit history built over time across **multiple contributors** on the team. This copy intentionally does not reflect that history.

---

## 📖 Overview

This system automates **behavioral analytics and quality-alert reporting** for an e-learning platform (quiz/course based). It reads raw activity & alert data from a data source (Google Sheets, fed by the platform's backend), runs it through a **rule-based + LLM classification pipeline**, and produces polished **PDF reports** that are emailed automatically to stakeholders — no manual work required.

Three independent scheduled jobs cover three different reporting needs:

| Job | Frequency | Purpose |
|---|---|---|
| ⚡ **Instant Alert Report** | Daily / on-demand | Surfaces **critical, unresolved alerts** from today & yesterday, cross-checked by multiple LLM providers for a fast triage view |
| 📅 **Weekly Alert Report** | Weekly | Deep-dive PDF on the week's critical alerts, with AI-written justifications, KPIs, and breakdowns by type/course |
| 📊 **General Platform Report** | Weekly | Executive-style **platform health report**: engagement, growth, faculty distribution, leaderboards, and an AI-generated executive brief with recommended actions |

---

## ✨ Key Features

- 🧠 **Hybrid classification engine** — deterministic rule scoring first, then selective LLM enrichment only on the alerts that actually need deeper judgment (cost-efficient)
- 🤝 **Multi-provider AI cross-validation** — Gemini, Groq (Llama), and OpenAI are used side-by-side on instant alerts to reduce single-model bias
- 🖨️ **Dynamic PDF generation** — HTML/CSS reports rendered to PDF with WeasyPrint, styled like real executive dashboards (KPI cards, mini bar charts, leaderboards, ranked case studies)
- 📧 **Automated transactional email delivery** — reports + attachments sent via the Brevo (Sendinblue) API
- 🕰️ **Timezone-safe scheduling logic** — all "this week" / "today or yesterday" windows are computed in local time before comparison
- 🧩 **Clean modular architecture** — shared `types`, `services` (sheets, classifier, email) reused across all three jobs
- 🛡️ **Fail-soft design** — malformed rows are skipped and logged instead of crashing the pipeline; AI failures gracefully fall back to a deterministic French-language summary

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph SRC[" 📄 Data Layer "]
        direction TB
        A[Google Sheets]
    end

    subgraph PROC[" ⚙️ Processing "]
        direction TB
        B[Load & validate records]
        C[Rule-based scoring]
        D{Critical alert?}
        B --> C --> D
    end

    subgraph AI[" 🧠 AI Enrichment "]
        direction LR
        E1[Gemini]
        E2[Groq · Llama 3.3]
        E3[OpenAI]
    end

    subgraph JOBS[" ⏱️ Scheduled Jobs "]
        direction TB
        G[instant_alert.py]
        H[weekly_alert.py]
        I[general_report.py]
    end

    subgraph OUT[" 📤 Output "]
        direction TB
        J[HTML → PDF via WeasyPrint]
        K[Brevo Email API]
    end

    L[("📬 Stakeholder Inbox")]

    SRC --> PROC
    D -- Yes --> AI
    D -- No --> H
    AI --> E1 & E2 & E3
    E1 & E2 & E3 --> G
    E1 & E2 & E3 --> H
    B --> I
    G --> J
    H --> J
    I --> J
    J --> K --> L

    classDef srcStyle fill:#0D1B3E,color:#fff,stroke:#0D1B3E
    classDef procStyle fill:#F4F7FB,color:#172033,stroke:#DCE4EF
    classDef aiStyle fill:#185FA5,color:#fff,stroke:#185FA5
    classDef jobStyle fill:#F4F7FB,color:#172033,stroke:#185FA5
    classDef outStyle fill:#C0392B,color:#fff,stroke:#C0392B
    classDef inboxStyle fill:#0D1B3E,color:#fff,stroke:#0D1B3E

    class A srcStyle
    class B,C,D procStyle
    class E1,E2,E3 aiStyle
    class G,H,I jobStyle
    class J,K outStyle
    class L inboxStyle
```

---

## 🛠️ Tech Stack

<div align="center">

<img src="https://skillicons.dev/icons?i=python,gcp,vscode,git,github,githubactions&theme=dark" />

</div>

<div align="center">

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Data Source** | Google Sheets API (`gspread` + Service Account) |
| **AI / LLM Providers** | Google Gemini, Groq (Llama 3.3), OpenAI |
| **PDF Rendering** | WeasyPrint (HTML/CSS → PDF) |
| **Email Delivery** | Brevo (Sendinblue) Transactional Email API |
| **Config Management** | `python-dotenv` |
| **Scheduling** | Cron / scheduled cloud job (daily & weekly triggers) |
| **Data Modeling** | Python `dataclasses` (typed `SheetAlert`, `User`, `LeaderboardEntry`...) |

</div>

---

## 📂 Project Structure

```
user-behavior-analysis-system/
├── functions/
│   ├── jobs/
│   │   ├── general_report.py      # Weekly executive platform report
│   │   ├── instant_alert.py       # Daily critical-alert triage report
│   │   └── weekly_alert.py        # Weekly deep-dive alert report
│   ├── services/
│   │   ├── classifier.py          # Rule engine + multi-LLM enrichment
│   │   ├── email.py                # Brevo email delivery
│   │   └── sheets.py               # Google Sheets data access layer
│   └── shared/
│       └── types.py                # Typed dataclasses (Alert, User, etc.)
├── src/shared/
│   └── config.py                   # Environment-based configuration
├── test_brevo.py                   # Manual email delivery smoke test
├── requirements.txt
└── README.md
```

---

## 📸 Screenshots

> All figures below (student counts, names, emails, scores) are **blurred** to protect real user data.
> Replace the placeholders below with your own blurred screenshots.

<div align="center">

<!-- 🖼️ Screenshot 1 — General Platform Report (page 1: KPIs + AI Executive Brief) -->
<img src="https://via.placeholder.com/850x480/0D1B3E/FFFFFF?text=Screenshot+1+%E2%80%94+Platform+Report+%28blur+numbers%29" width="80%"/>

<br/><br/>

<!-- 🖼️ Screenshot 2 — Weekly Alert Report (critical case card) -->
<img src="https://via.placeholder.com/850x480/185FA5/FFFFFF?text=Screenshot+2+%E2%80%94+Weekly+Alert+Report+%28blur+names%29" width="80%"/>

<br/><br/>

<!-- 🖼️ Screenshot 3 — Instant Alert Report (multi-LLM verdicts) -->
<img src="https://via.placeholder.com/850x480/C0392B/FFFFFF?text=Screenshot+3+%E2%80%94+Instant+Alert+Report" width="80%"/>

<br/><br/>

<!-- 🖼️ Screenshot 4 — Email delivery / inbox view -->
<img src="https://via.placeholder.com/850x480/667085/FFFFFF?text=Screenshot+4+%E2%80%94+Email+Delivery+%28blur+addresses%29" width="80%"/>

<br/><br/>

<!-- 🖼️ Screenshot 5 — Google Sheet data source (blur all rows) -->
<img src="https://via.placeholder.com/850x480/DCE4EF/172033?text=Screenshot+5+%E2%80%94+Raw+Data+Source+%28fully+blurred%29" width="80%"/>

</div>

---

## ⚙️ Environment Variables

> No real values are shown here — only the variable names your `.env` needs.

```env
# Google Sheets
SERVICE_ACCOUNT_FILE=
SHEET_ID=
SHEET_TAB=

# AI Providers
GEMINI_API_KEY=
GEMINI_MODEL=
GROQ_API_KEY=
GROQ_MODEL=
INSTANT_GROQ_API_KEY=
INSTANT_OPENAI_API_KEY=
INSTANT_OPENAI_MODEL=
WEEKLY_GROQ_API_KEY=
GENERAL_GROQ_API_KEY=
AI_TIMEOUT_SECONDS=

# Email (Brevo)
BREVO_API_KEY=
BREVO_SENDER_EMAIL=
BREVO_SENDER_NAME=
RECIPIENT_EMAIL=

# Report Tuning
WEEKLY_MAX_LLM_ALERTS=
WEEKLY_MAX_REPORT_ALERTS=
```

---

## 🚀 Running Locally

```bash
# 1. Clone & enter the project
git clone <this-repo>
cd user-behavior-analysis-system

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env   # then fill in your own values

# 5. Run any of the three jobs
python -m functions.jobs.instant_alert
python -m functions.jobs.weekly_alert
python -m functions.jobs.general_report
```

---

## 🎓 What I Learned

- Designing a **cost-aware AI pipeline**: only escalating to LLMs when a deterministic rule engine flags something as worth reviewing
- Building **production-style HTML → PDF reports** with real design systems (color tokens, spacing scale, componentized cards)
- Handling **multi-provider LLM orchestration** with graceful fallbacks when an API fails or times out
- Structuring a small Python codebase with **clear service boundaries** (`sheets`, `classifier`, `email`) that stay reusable across multiple jobs
- Thinking about **data confidentiality** end-to-end, from raw data handling to what ends up in a portfolio repo

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:185FA5,100:0D1B3E&height=120&section=footer&animation=fadeIn" width="100%"/>

*Built as part of a data/backend internship — shared here with all company & user identifiers removed.*

</div>
