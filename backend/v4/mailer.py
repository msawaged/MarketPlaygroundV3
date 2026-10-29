"""
Sending email (verification links, password resets). Plain SMTP, so it works with a Gmail
account + app password today, and any email service later (they all offer SMTP).

Env:
  MP_SMTP_HOST      e.g. smtp.gmail.com
  MP_SMTP_PORT      587 (STARTTLS, default) or 465 (SSL)
  MP_SMTP_USER      the sending account, e.g. hello.marketplayground@gmail.com
  MP_SMTP_PASSWORD  app password (Gmail: Google Account -> Security -> App passwords)
  MP_MAIL_FROM      optional display, default "MarketPlayground <MP_SMTP_USER>"
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

_sent_for_tests: list = []


def configured() -> bool:
    return bool(os.getenv("MP_SMTP_HOST") and os.getenv("MP_SMTP_USER") and os.getenv("MP_SMTP_PASSWORD"))


def send(to: str, subject: str, text: str, html: str = "") -> None:
    if os.getenv("MP_MAIL_TEST_SINK"):
        _sent_for_tests.append({"to": to, "subject": subject, "text": text})
        return
    if not configured():
        raise RuntimeError("email is not configured (MP_SMTP_*)")
    user = os.environ["MP_SMTP_USER"]
    msg = EmailMessage()
    msg["From"] = os.getenv("MP_MAIL_FROM") or f"MarketPlayground <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    host, port = os.environ["MP_SMTP_HOST"], int(os.getenv("MP_SMTP_PORT", "587"))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=20) as s:
            s.login(user, os.environ["MP_SMTP_PASSWORD"]); s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=ctx); s.login(user, os.environ["MP_SMTP_PASSWORD"]); s.send_message(msg)


def button_html(title: str, lead: str, url: str, label: str, foot: str) -> str:
    site = (os.getenv("MP_SITE_URL") or "https://marketplayground-web.onrender.com").rstrip("/")
    return f"""<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#0f172a">
<img src="{site}/icon-192.png" width="44" height="44" alt="MarketPlayground" style="border-radius:12px;border:1px solid #e2e8f0;display:block">
<h1 style="font-size:22px;margin:20px 0 8px">{title}</h1>
<p style="font-size:15px;line-height:1.5;color:#334155">{lead}</p>
<p style="margin:24px 0"><a href="{url}" style="background:#2563eb;color:#fff;text-decoration:none;font-weight:700;padding:12px 20px;border-radius:12px;display:inline-block">{label}</a></p>
<p style="font-size:12px;color:#64748b;line-height:1.5">{foot}<br>Or paste this link: {url}</p>
</div>"""
