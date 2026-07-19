import base64
import os
from typing import Iterable

import requests


BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_TIMEOUT_SECONDS = 60


def _normalize_recipients(to: str | list[str]) -> list[str]:
    raw_recipients: Iterable[str]

    if isinstance(to, list):
        raw_recipients = to
    else:
        raw_recipients = to.split(",")

    recipients = [str(email).strip() for email in raw_recipients if str(email).strip()]

    if not recipients:
        raise ValueError("At least one recipient email is required.")

    return recipients


def _normalize_attachments(
    attachment: bytes | None,
    attachment_filename: str | None,
    attachments: list[tuple[str, bytes, str]] | None,
) -> list[tuple[str, bytes, str]]:
    if attachments:
        return attachments

    if attachment is not None and attachment_filename:
        mime_type = (
            "application/pdf"
            if attachment_filename.lower().endswith(".pdf")
            else "application/octet-stream"
        )
        return [(attachment_filename, attachment, mime_type)]

    return []


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    is_html: bool = False,
    attachment: bytes | None = None,
    attachment_filename: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
):
    recipients = _normalize_recipients(to)
    normalized_attachments = _normalize_attachments(
        attachment=attachment,
        attachment_filename=attachment_filename,
        attachments=attachments,
    )

    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    sender_email = os.environ.get("BREVO_SENDER_EMAIL", "").strip()
    sender_name = os.environ.get("BREVO_SENDER_NAME", "QCMed Alert System").strip()

    if not api_key:
        raise RuntimeError("BREVO_API_KEY is missing.")
    if not sender_email:
        raise RuntimeError("BREVO_SENDER_EMAIL is missing.")

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [{"email": email} for email in recipients],
        "subject": subject,
    }

    if is_html:
        payload["htmlContent"] = body
    else:
        payload["textContent"] = body

    if normalized_attachments:
        payload["attachment"] = [
            {
                "name": filename,
                "content": base64.b64encode(
                    data.encode("utf-8") if isinstance(data, str) else data
                ).decode("ascii"),
            }
            for filename, data, _mime_type in normalized_attachments
        ]

    try:
        response = requests.post(
            BREVO_SEND_URL,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=BREVO_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Brevo request failed: {exc}") from exc

    if response.status_code != 201:
        error_body = response.text[:1200]
        raise RuntimeError(
            f"Brevo email failed: HTTP {response.status_code} - {error_body}"
        )

    result = response.json() if response.content else {}
    message_id = result.get("messageId", "unknown")

    print(f"Email sent through Brevo to {recipients}. Message ID: {message_id}")
    return result
