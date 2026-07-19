from collections import defaultdict
import json
import re
import requests

from shared.types import SheetAlert
import os

AI_TIMEOUT_SECONDS = int(os.environ.get("AI_TIMEOUT_SECONDS", "25"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", str(AI_TIMEOUT_SECONDS)))

INSTANT_GROQ_API_KEY = os.environ.get("INSTANT_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
INSTANT_GROQ_MODEL = os.environ.get("INSTANT_GROQ_MODEL") or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
INSTANT_OPENAI_API_KEY = os.environ.get("INSTANT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
INSTANT_OPENAI_MODEL = os.environ.get("INSTANT_OPENAI_MODEL", "gpt-4.1-mini")

WEEKLY_GROQ_API_KEY = os.environ.get("WEEKLY_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
WEEKLY_GROQ_MODEL = os.environ.get("WEEKLY_GROQ_MODEL") or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


ORTHOGRAPHE_TYPES = {"erreur d'orthographe", "faute d'orthographe"}

HIGH_SCORE_TYPES = {
    "la question est fausse": 4,
    "aucune proposition est correcte": 4,
    "la réponse est fausse": 4,
}


def rule_score(alert: SheetAlert, same_question_count: int) -> int:
    t = alert.alert_type.strip().lower()
    details = (alert.details or "").strip()

    if not details:
        return 0

    if t in ORTHOGRAPHE_TYPES:
        return 1

    if t in HIGH_SCORE_TYPES:
        base = HIGH_SCORE_TYPES[t]
    else:
        base = 2

    if same_question_count >= 3:
        base += 1

    return min(base, 5)


def classify_alerts(alerts: list[SheetAlert]) -> list[dict]:
    question_counts = defaultdict(int)
    for a in alerts:
        question_counts[a.question_description] += 1

    results = []

    for a in alerts:
        count = question_counts[a.question_description]
        t = a.alert_type.strip().lower()

        if not a.details or not a.details.strip():
            score = 0
            is_critical = False
        elif t in ORTHOGRAPHE_TYPES:
            score = 1
            is_critical = False
        else:
            score = rule_score(a, count)
            is_critical = score >= 4 and t in HIGH_SCORE_TYPES

        results.append({
            "alert_id": a.alert_id,
            "created_at": a.created_at,
            "status": a.status,
            "alert_type": a.alert_type,
            "details": a.details,
            "user_fullname": a.user_fullname,
            "user_email": a.user_email,
            "user_faculte": a.user_faculte,
            "user_niveau": a.user_niveau,
            "question_description": a.question_description,
            "question_responses": a.question_responses,
            "question_correct_response": a.question_correct_response,
            "matiere_title": a.matiere_title,
            "cours_title": a.cours_title,
            "certif_title": a.certif_title,
            "question_times_answered": a.question_times_answered,
            "alert_count_same_question": count,
            "score": score,
            "is_critical": is_critical,

            "llm_justification_groq": "",
            "llm_confidence_groq": "",
            "student_intent_groq": "",
            "alert_verdict_groq": "",
            "why_verdict_groq": "",
            "medical_analysis_groq": "",
            "recommended_correction_groq": "",
            "admin_action_groq": "",

            "llm_justification_gemini": "",
            "llm_confidence_gemini": "",

            "llm_justification_openai": "",
            "llm_confidence_openai": "",
            "student_intent_openai": "",
            "alert_verdict_openai": "",
            "why_verdict_openai": "",
            "medical_analysis_openai": "",
            "recommended_correction_openai": "",
            "admin_action_openai": "",

            "llm_justification": "",
            "llm_confidence": "",
        })

    results.sort(key=lambda x: (x["score"], x.get("created_at", "")), reverse=True)
    return results


def build_alert_investigation_prompt(alert: dict) -> str:
    return f"""
Tu es un reviewer médical senior pour QCMed.

Objectif: produire une analyse normale, utile et lisible pour un admin.
Pas une réponse trop courte. Pas un roman.

Tu dois faire exactement ceci:
1. Comprendre ce que l'étudiant veut probablement dire.
2. Comparer son alerte avec la question, les propositions et la réponse officielle.
3. Dire clairement si l'étudiant est correct ou incorrect.
4. Expliquer pourquoi avec assez de détails pour que l'admin comprenne sans ouvrir Gemini.
5. Proposer l'action exacte à faire côté admin.

Règles de longueur:
- why_verdict: 2 phrases normales, pas plus.
- medical_analysis: 2 à 3 phrases normales.
- recommended_correction: 1 phrase claire.
- Le total doit être utile, mais compact.

Règles importantes:
- Ne répète pas seulement le commentaire étudiant.
- Si l'étudiant écrit seulement une lettre comme "D", déduis ce qu'il veut probablement dire à partir du contexte.
- Si l'étudiant est incorrect, explique d'abord pourquoi sa proposition est incorrecte.
- Si l'étudiant est correct, explique d'abord pourquoi la réponse officielle est fausse ou incomplète.
- Si tu n'as pas assez d'informations pour trancher, choisis MANUAL_REVIEW.
- N'invente pas de faits médicaux.
- Ne donne pas une confiance de 0 si tu as réellement donné un verdict. Utilise 70-95 quand le verdict est clair, 50-69 si incertain, moins de 50 seulement si MANUAL_REVIEW.

Retourne UNIQUEMENT un JSON valide en français. Pas de markdown.

Format exact:
{{
  "student_intent": "Ce que l'étudiant voulait probablement dire, en une phrase.",
  "alert_verdict": "VALID_ALERT ou INVALID_ALERT ou MANUAL_REVIEW",
  "why_verdict": "Explique d'abord si l'étudiant est correct ou incorrect, puis pourquoi, en comparant avec la réponse officielle.",
  "medical_analysis": "Analyse médicale/pédagogique en 2 à 3 phrases normales.",
  "recommended_correction": "Correction exacte si nécessaire, sinon: Aucune correction nécessaire.",
  "admin_action": "Accepter l'alerte ou Rejeter l'alerte ou Revue manuelle",
  "confidence": 0
}}

Question:
{alert.get("question_description", "")}

Propositions:
{alert.get("question_responses", "")}

Réponse officielle:
{alert.get("question_correct_response", "")}

Type d'alerte:
{alert.get("alert_type", "")}

Commentaire étudiant:
{alert.get("details", "")}

Matière / cours:
{alert.get("matiere_title", "")} — {alert.get("cours_title", "")}
""".strip()

def build_weekly_alert_prompt(alert: dict) -> str:
    return f"""
Tu es un reviewer médical QCMed. Réponds en français avec une analyse de longueur moyenne.

But: aider l'admin à décider rapidement, sans bullshit.
Ne fais pas une phrase ridicule. Ne fais pas un paragraphe long.

Tu dois:
1. dire ce que l'étudiant veut probablement dire;
2. dire si son alerte est correcte ou incorrecte;
3. expliquer pourquoi en comparant question, propositions et réponse officielle;
4. donner la correction ou l'action admin.

Règles de longueur:
- why_verdict: exactement 2 phrases.
- recommended_correction: 1 phrase.
- student_intent: 1 phrase courte.
- Pas de paragraphes longs.

Confiance:
- Si le verdict est clair, donne 75-95.
- Si c'est incertain, 50-69 et MANUAL_REVIEW.
- Ne mets jamais 0 sauf si tu n'as vraiment aucune analyse possible.

Retourne UNIQUEMENT ce JSON valide:
{{
  "student_intent": "1 phrase courte",
  "alert_verdict": "VALID_ALERT ou INVALID_ALERT ou MANUAL_REVIEW",
  "why_verdict": "2 phrases: étudiant correct/incorrect + raison exacte",
  "recommended_correction": "Correction exacte ou Aucune correction nécessaire.",
  "admin_action": "Accepter l'alerte ou Rejeter l'alerte ou Revue manuelle",
  "confidence": 0
}}

Question:
{alert.get("question_description", "")}

Propositions:
{alert.get("question_responses", "")}

Réponse officielle:
{alert.get("question_correct_response", "")}

Type d'alerte:
{alert.get("alert_type", "")}

Commentaire étudiant:
{alert.get("details", "")}
""".strip()

def build_gemini_review_prompt(alert: dict) -> str:
    return build_alert_investigation_prompt(alert)


def _extract_json(text: str) -> dict:
    if not text:
        return {}

    text = text.strip().replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clean_value(value) -> str:
    return str(value or "").strip()


def _clip(value: str, limit: int) -> str:
    value = str(value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


def _format_review(data: dict) -> str:
    if not data:
        return ""

    intent = _clip(data.get('student_intent', 'Non déterminée.'), 230)
    verdict = _clip(data.get('alert_verdict', 'MANUAL_REVIEW'), 80)
    why = _clip(data.get('why_verdict', 'Revue manuelle recommandée.'), 420)
    analysis = _clip(data.get('medical_analysis', ''), 420)
    correction = _clip(data.get('recommended_correction', 'Revue manuelle requise.'), 300)
    action = _clip(data.get('admin_action', 'Revue manuelle'), 120)
    confidence = _safe_int(data.get('confidence', 0))

    return "\n".join([
        f"Intention: {intent}",
        f"Verdict: {verdict}",
        f"Pourquoi: {why}",
        f"Analyse: {analysis}",
        f"Correction: {correction}",
        f"Action: {action} · Confiance {confidence}%",
    ])

def _format_weekly_review(data: dict) -> str:
    if not data:
        return ""

    intent = _clip(data.get("student_intent", "Non déterminée."), 190)
    verdict = _clip(data.get("alert_verdict", "MANUAL_REVIEW"), 50)
    why = _clip(data.get("why_verdict", "Revue manuelle recommandée."), 330)
    correction = _clip(data.get("recommended_correction", "Revue manuelle requise."), 220)
    action = _clip(data.get("admin_action", "Revue manuelle"), 90)
    confidence = _safe_int(data.get("confidence", 0))

    return "\n".join([
        f"Intention: {intent}",
        f"Verdict: {verdict}",
        f"Pourquoi: {why}",
        f"Correction: {correction}",
        f"Action: {action} · Confiance {confidence}%",
    ])

def _normalize_review(data: dict, weekly: bool = False) -> tuple[str, str, dict]:
    formatted = _format_weekly_review(data) if weekly else _format_review(data)
    confidence = data.get("confidence", "") if data else ""
    confidence = f"{_safe_int(confidence)}%" if confidence != "" else ""
    return formatted, confidence, data or {}


def _call_groq_json(prompt: str, api_key: str | None, model: str, timeout: int = AI_TIMEOUT_SECONDS, max_tokens: int = 600) -> dict:
    if not api_key:
        return {}

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "Tu réponds uniquement en JSON valide, en français, sans markdown."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.05,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )

    if response.status_code == 429:
        raise RuntimeError("GROQ_RATE_LIMIT")

    if response.status_code >= 400:
        print(f"Groq failed: HTTP {response.status_code} - {response.text[:700]}")
        return {}

    data = response.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _extract_json(text)


def _call_openai_json(prompt: str, api_key: str | None, model: str, timeout: int = AI_TIMEOUT_SECONDS) -> dict:
    if not api_key:
        return {}

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "Tu réponds uniquement en JSON valide, en français, sans markdown."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.05,
            "max_completion_tokens": 700,
        },
        timeout=timeout,
    )

    if response.status_code == 429:
        raise RuntimeError("OPENAI_RATE_LIMIT")

    if response.status_code >= 400:
        print(f"OpenAI failed: HTTP {response.status_code} - {response.text[:700]}")
        return {}

    data = response.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _extract_json(text)


def generate_gemini_justification(alert: dict) -> tuple[str, str, dict]:
    if not GEMINI_API_KEY:
        return "", "", {}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    prompt = build_alert_investigation_prompt(alert)

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.05, "topP": 0.95, "maxOutputTokens": 800},
    }

    try:
        response = requests.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=GEMINI_TIMEOUT_SECONDS)

        if response.status_code == 429:
            raise RuntimeError("GEMINI_RATE_LIMIT")

        if response.status_code >= 400:
            print(f"Gemini failed: HTTP {response.status_code} - {response.text[:700]}")
            return "", "", {}

        data = response.json()
        raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return _normalize_review(_extract_json(raw))

    except RuntimeError:
        raise
    except Exception as exc:
        print(f"Gemini failed: {type(exc).__name__}")
        return "", "", {}


def _apply_provider_fields(alert: dict, provider: str, review: str, confidence: str, parsed: dict) -> None:
    alert[f"llm_justification_{provider}"] = review
    alert[f"llm_confidence_{provider}"] = confidence
    alert[f"student_intent_{provider}"] = _clean_value(parsed.get("student_intent"))
    alert[f"alert_verdict_{provider}"] = _clean_value(parsed.get("alert_verdict"))
    alert[f"why_verdict_{provider}"] = _clean_value(parsed.get("why_verdict"))
    alert[f"medical_analysis_{provider}"] = _clean_value(parsed.get("medical_analysis"))
    alert[f"recommended_correction_{provider}"] = _clean_value(parsed.get("recommended_correction"))
    alert[f"admin_action_{provider}"] = _clean_value(parsed.get("admin_action"))


def generate_instant_groq_review(alert: dict) -> tuple[str, str, dict]:
    parsed = _call_groq_json(build_alert_investigation_prompt(alert), INSTANT_GROQ_API_KEY, INSTANT_GROQ_MODEL, AI_TIMEOUT_SECONDS, 800)
    return _normalize_review(parsed)


def generate_instant_openai_review(alert: dict) -> tuple[str, str, dict]:
    parsed = _call_openai_json(build_alert_investigation_prompt(alert), INSTANT_OPENAI_API_KEY, INSTANT_OPENAI_MODEL, AI_TIMEOUT_SECONDS)
    return _normalize_review(parsed)


def enrich_alerts_with_instant_llms(classified_alerts: list[dict]) -> list[dict]:
    for alert in classified_alerts:
        try:
            review, confidence, parsed = generate_instant_groq_review(alert)
        except RuntimeError as exc:
            if str(exc) == "GROQ_RATE_LIMIT":
                print("Instant Groq quota reached. Skipping remaining Groq reviews.")
                break
            review, confidence, parsed = "", "", {}
        except Exception:
            review, confidence, parsed = "", "", {}

        _apply_provider_fields(alert, "groq", review, confidence, parsed)

        if review:
            alert["llm_justification"] = review
            alert["llm_confidence"] = confidence

        try:
            openai_review, openai_confidence, openai_parsed = generate_instant_openai_review(alert)
        except RuntimeError as exc:
            if str(exc) == "OPENAI_RATE_LIMIT":
                print("Instant OpenAI quota reached. Skipping remaining OpenAI reviews.")
                continue
            openai_review, openai_confidence, openai_parsed = "", "", {}
        except Exception:
            openai_review, openai_confidence, openai_parsed = "", "", {}

        _apply_provider_fields(alert, "openai", openai_review, openai_confidence, openai_parsed)

    return classified_alerts


def generate_weekly_groq_review(alert: dict) -> tuple[str, str, dict]:
    parsed = _call_groq_json(build_weekly_alert_prompt(alert), WEEKLY_GROQ_API_KEY, WEEKLY_GROQ_MODEL, AI_TIMEOUT_SECONDS, 520)
    return _normalize_review(parsed, weekly=True)


def enrich_alerts_with_weekly_groq(classified_alerts: list[dict], max_alerts: int | None = None) -> list[dict]:
    enriched = 0

    for alert in classified_alerts:
        if max_alerts is not None and enriched >= max_alerts:
            break

        try:
            review, confidence, parsed = generate_weekly_groq_review(alert)
        except RuntimeError as exc:
            if str(exc) == "GROQ_RATE_LIMIT":
                print("Weekly Groq quota reached. Skipping remaining weekly reviews.")
                break
            review, confidence, parsed = "", "", {}
        except Exception:
            review, confidence, parsed = "", "", {}

        _apply_provider_fields(alert, "groq", review, confidence, parsed)

        if review:
            alert["llm_justification"] = review
            alert["llm_confidence"] = confidence

        enriched += 1

    return classified_alerts


def enrich_alerts_with_gemini(classified_alerts: list[dict], max_alerts: int = 10) -> list[dict]:
    enriched = 0

    for alert in classified_alerts:
        if enriched >= max_alerts:
            break

        try:
            review, confidence, parsed = generate_gemini_justification(alert)
        except RuntimeError as exc:
            if str(exc) == "GEMINI_RATE_LIMIT":
                print("Gemini quota reached.")
                break
            review, confidence, parsed = "", "", {}
        except Exception:
            review, confidence, parsed = "", "", {}

        alert["llm_justification_gemini"] = review
        alert["llm_confidence_gemini"] = confidence
        alert["llm_justification"] = review
        alert["llm_confidence"] = confidence
        enriched += 1

    return classified_alerts
