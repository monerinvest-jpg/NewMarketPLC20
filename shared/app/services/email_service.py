"""
Email delivery service.

In production this talks to Yandex Cloud Postbox over SMTP (STARTTLS on 587):
SMTP_HOST=postbox.cloud.yandex.net, SMTP_USER/SMTP_PASSWORD = a Postbox service
account static access key, SMTP_FROM = a verified sender address.

If SMTP_HOST is empty (local/dev), emails are logged to stdout instead of sent,
keeping confirmation/notification flows fully testable without a mail server.

The actual smtplib calls are blocking, so they run in a worker thread via
asyncio.to_thread — sending never blocks the request event loop, and a delivery
failure is logged rather than raised (email is best-effort, not transactional).
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("marketplace.email")


def _smtp_send(to: str, subject: str, body: str, html: Optional[str]) -> None:
    """Blocking SMTP send. Runs in a thread; callers use send_email()."""
    smtp_host = getattr(settings, "SMTP_HOST", "")
    sender = getattr(settings, "SMTP_FROM", "no-reply@marketplace.com")

    if not smtp_host:
        logger.info("SMTP not configured — email NOT sent to %s. Subject: %s", to, subject)
        return

    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    port = int(getattr(settings, "SMTP_PORT", 587))
    with smtplib.SMTP(smtp_host, port, timeout=15) as server:
        server.ehlo()
        try:
            server.starttls()
            server.ehlo()
        except smtplib.SMTPException:
            pass  # server without STARTTLS (e.g. a local relay)
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_password = getattr(settings, "SMTP_PASSWORD", "")
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.sendmail(sender, [to], msg.as_string())


async def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> None:
    """
    Generic best-effort email sender. Non-blocking (runs SMTP in a thread) and
    never raises: a delivery error is logged so it can't break the caller's flow.
    """
    try:
        await asyncio.to_thread(_smtp_send, to, subject, body, html)
    except Exception as exc:  # noqa: BLE001 — email must never break a request
        logger.warning("Email to %s failed: %s", to, exc)


def _wrap_html(title: str, lines: list[str], cta: Optional[tuple[str, str]] = None) -> str:
    """Minimal branded HTML wrapper (warm craft palette). cta = (label, url)."""
    body = "".join(f'<p style="margin:0 0 12px;color:#44403c;font-size:15px;line-height:1.5">{ln}</p>' for ln in lines)
    button = ""
    if cta:
        label, url = cta
        button = (
            f'<a href="{url}" style="display:inline-block;margin-top:8px;background:#b45309;'
            f'color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600">{label}</a>'
        )
    return (
        f'<div style="max-width:520px;margin:0 auto;font-family:Segoe UI,Arial,sans-serif;'
        f'background:#fffaf3;border:1px solid #efe6d8;border-radius:14px;overflow:hidden">'
        f'<div style="background:#7c4a21;padding:18px 24px"><span style="color:#fde9cf;'
        f'font-size:18px;font-weight:700">🪵 Маркетплейс</span></div>'
        f'<div style="padding:24px">'
        f'<h2 style="margin:0 0 16px;color:#7c4a21;font-size:20px">{title}</h2>'
        f'{body}{button}</div>'
        f'<div style="padding:14px 24px;color:#a8a29e;font-size:12px;border-top:1px solid #efe6d8">'
        f'Это письмо отправлено автоматически, отвечать на него не нужно.</div></div>'
    )


async def send_password_reset_email(to_email: str, reset_token: str, frontend_url: str) -> None:
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    subject = "Восстановление пароля — Маркетплейс"
    body = (
        "Вы запросили восстановление пароля. Перейдите по ссылке, чтобы задать новый пароль:\n"
        f"{reset_link}\n\n"
        "Ссылка действительна в течение 1 часа. Если вы не запрашивали восстановление, "
        "просто проигнорируйте это письмо."
    )
    html = _wrap_html(
        "Восстановление пароля",
        ["Вы запросили восстановление пароля. Нажмите кнопку, чтобы задать новый.",
         "Ссылка действительна 1 час. Если это были не вы — проигнорируйте письмо."],
        cta=("Задать новый пароль", reset_link),
    )
    await send_email(to_email, subject, body, html)


async def send_verification_code_email(to_email: str, code: str) -> None:
    """Send an email-confirmation code to a newly registered user."""
    subject = "Подтверждение email — код"
    body = (
        f"Ваш код подтверждения email: {code}\n\n"
        "Код действует 15 минут. Если вы не регистрировались, проигнорируйте это письмо."
    )
    html = _wrap_html(
        "Подтверждение email",
        ["Ваш код подтверждения:",
         f'<span style="font-size:28px;font-weight:700;letter-spacing:4px;color:#7c4a21">{code}</span>',
         "Код действует 15 минут."],
    )
    await send_email(to_email, subject, body, html)
