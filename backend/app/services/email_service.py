"""
Email delivery service.

No SMTP provider is configured by default (same philosophy as the payment/
delivery gateways: the system works out of the box without real credentials,
and real sending is layered in via settings without code changes).

In development (no SMTP_HOST configured), emails are logged to stdout instead
of sent, which keeps password-reset and other email flows fully testable
without a mail server.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("marketplace.email")


async def send_email(to: str, subject: str, body: str) -> None:
    """
    Generic email sender. In dev (no SMTP_HOST) logs instead of sending, so
    notification emails are fully testable without a mail server.
    """
    smtp_host = getattr(settings, "SMTP_HOST", "")
    if not smtp_host:
        logger.info("SMTP not configured — email NOT sent to %s. Subject: %s", to, subject)
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = getattr(settings, "SMTP_FROM", "no-reply@marketplace.com")
    msg["To"] = to
    with smtplib.SMTP(smtp_host, getattr(settings, "SMTP_PORT", 587)) as server:
        server.starttls()
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], [to], msg.as_string())


async def send_password_reset_email(to_email: str, reset_token: str, frontend_url: str) -> None:
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    subject = "Восстановление пароля — Marketplace"
    body = (
        f"Здравствуйте!\n\n"
        f"Вы запросили восстановление пароля. Перейдите по ссылке, чтобы задать новый пароль:\n"
        f"{reset_link}\n\n"
        f"Ссылка действительна в течение 1 часа. Если вы не запрашивали восстановление, "
        f"просто проигнорируйте это письмо.\n"
    )

    smtp_host = getattr(settings, "SMTP_HOST", "")
    if not smtp_host:
        # Dev mode: no mail server configured. Log instead of sending so the
        # flow remains fully testable (the link can be copied from logs/console).
        logger.warning(
            "SMTP not configured — password reset email NOT sent. "
            "Reset link for %s: %s", to_email, reset_link,
        )
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = getattr(settings, "SMTP_FROM", "no-reply@marketplace.com")
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, getattr(settings, "SMTP_PORT", 587)) as server:
        server.starttls()
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], [to_email], msg.as_string())


async def send_verification_code_email(to_email: str, code: str) -> None:
    """Send an email-confirmation code to a newly registered user."""
    subject = "Подтверждение email — код"
    body = (
        f"Здравствуйте!\n\n"
        f"Ваш код подтверждения email: {code}\n\n"
        f"Код действует 15 минут. Если вы не регистрировались, проигнорируйте это письмо."
    )
    await send_email(to_email, subject, body)
