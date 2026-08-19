"""Email sending service.

If SMTP is configured (SMTP_HOST set), sends a real email via smtplib.
Otherwise falls back to sandbox mode: the message is only stored in the
email_messages table with status 'sent' (dev/demo behaviour).
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST)


def send_email_smtp(to_email: str, subject: str, body: str) -> None:
    """Send a real email over SMTP. Raises on failure so callers can mark failed."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.FROM_NAME, settings.FROM_EMAIL))
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.FROM_EMAIL, [to_email], msg.as_string())
