import os
import tempfile
from collections.abc import Callable

from firebase_functions import scheduler_fn
from firebase_functions.params import SecretParam


# Shared Firebase-managed secrets
SERVICE_ACCOUNT_JSON = SecretParam("SERVICE_ACCOUNT_JSON")
RECIPIENT_EMAIL = SecretParam("RECIPIENT_EMAIL")
SHEET_ID = SecretParam("SHEET_ID")
SHEET_TAB = SecretParam("SHEET_TAB")

# Brevo transactional-email configuration
BREVO_API_KEY = SecretParam("BREVO_API_KEY")
BREVO_SENDER_EMAIL = SecretParam("BREVO_SENDER_EMAIL")

# Report-specific Groq credentials and model IDs
INSTANT_GROQ_API_KEY = SecretParam("INSTANT_GROQ_API_KEY")
INSTANT_GROQ_MODEL = SecretParam("INSTANT_GROQ_MODEL")

WEEKLY_GROQ_API_KEY = SecretParam("WEEKLY_GROQ_API_KEY")
WEEKLY_GROQ_MODEL = SecretParam("WEEKLY_GROQ_MODEL")

GENERAL_GROQ_API_KEY = SecretParam("GENERAL_GROQ_API_KEY")
GENERAL_GROQ_MODEL = SecretParam("GENERAL_GROQ_MODEL")


BASE_SECRETS = [
    SERVICE_ACCOUNT_JSON,
    RECIPIENT_EMAIL,
    SHEET_ID,
    SHEET_TAB,
    BREVO_API_KEY,
    BREVO_SENDER_EMAIL,
]

INSTANT_SECRETS = BASE_SECRETS + [
    INSTANT_GROQ_API_KEY,
    INSTANT_GROQ_MODEL,
]

WEEKLY_SECRETS = BASE_SECRETS + [
    WEEKLY_GROQ_API_KEY,
    WEEKLY_GROQ_MODEL,
]

GENERAL_SECRETS = BASE_SECRETS + [
    GENERAL_GROQ_API_KEY,
    GENERAL_GROQ_MODEL,
]


def _load_service_account() -> str:
    payload = SERVICE_ACCOUNT_JSON.value

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )
    try:
        temp_file.write(payload)
        temp_file.flush()
        return temp_file.name
    finally:
        temp_file.close()


def _inject_base_env() -> None:
    os.environ["RECIPIENT_EMAIL"] = RECIPIENT_EMAIL.value
    os.environ["SHEET_ID"] = SHEET_ID.value
    os.environ["SHEET_TAB"] = SHEET_TAB.value

    os.environ["BREVO_API_KEY"] = BREVO_API_KEY.value
    os.environ["BREVO_SENDER_EMAIL"] = BREVO_SENDER_EMAIL.value
    os.environ["BREVO_SENDER_NAME"] = "QCMed Alert System"

    os.environ["AI_TIMEOUT_SECONDS"] = "25"


def _inject_instant_env() -> None:
    _inject_base_env()
    os.environ["INSTANT_GROQ_API_KEY"] = INSTANT_GROQ_API_KEY.value
    os.environ["INSTANT_GROQ_MODEL"] = INSTANT_GROQ_MODEL.value


def _inject_weekly_env() -> None:
    _inject_base_env()
    os.environ["WEEKLY_GROQ_API_KEY"] = WEEKLY_GROQ_API_KEY.value
    os.environ["WEEKLY_GROQ_MODEL"] = WEEKLY_GROQ_MODEL.value

    # Existing report limits remain unchanged.
    os.environ["WEEKLY_MAX_LLM_ALERTS"] = "8"
    os.environ["WEEKLY_MAX_REPORT_ALERTS"] = "20"


def _inject_general_env() -> None:
    _inject_base_env()
    os.environ["GENERAL_GROQ_API_KEY"] = GENERAL_GROQ_API_KEY.value
    os.environ["GENERAL_GROQ_MODEL"] = GENERAL_GROQ_MODEL.value


def _run_job(job_module: str, inject_env: Callable[[], None]) -> None:
    inject_env()

    service_account_path = _load_service_account()
    os.environ["SERVICE_ACCOUNT_FILE"] = service_account_path

    try:
        module = __import__(job_module, fromlist=["main"])
        module.main()
    finally:
        try:
            os.unlink(service_account_path)
        except FileNotFoundError:
            pass


@scheduler_fn.on_schedule(
    schedule="0 8 * * *",
    timezone="UTC",
    memory=512,
    timeout_sec=540,
    secrets=INSTANT_SECRETS,
)
def instant_alert(event) -> None:
    _run_job("jobs.instant_alert", _inject_instant_env)


@scheduler_fn.on_schedule(
    schedule="0 8 * * 5",
    timezone="UTC",
    memory=512,
    timeout_sec=540,
    secrets=WEEKLY_SECRETS,
)
def weekly_alert(event) -> None:
    _run_job("jobs.weekly_alert", _inject_weekly_env)


@scheduler_fn.on_schedule(
    schedule="0 19 * * 1",
    timezone="UTC",
    memory=512,
    timeout_sec=540,
    secrets=GENERAL_SECRETS,
)
def general_report(event) -> None:
    _run_job("jobs.general_report", _inject_general_env)
