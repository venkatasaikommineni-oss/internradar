"""Email service: send OTPs and notification emails via SMTP."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings

log = logging.getLogger("internradar.email")

_OTP_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 0; }}
    .container {{ max-width: 520px; margin: 40px auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
    .header {{ background: #0f172a; border-bottom: 2px solid #2563eb; padding: 24px 32px; text-align: left; }}
    .header h1 {{ margin: 0; color: #ffffff; font-size: 20px; font-weight: 600; letter-spacing: -0.02em; }}
    .body {{ padding: 32px; }}
    .otp-box {{ background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; text-align: center; padding: 20px; margin: 24px 0; }}
    .otp {{ font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #1e40af; font-family: monospace; }}
    .note {{ color: #64748b; font-size: 13px; line-height: 1.5; }}
    .footer {{ border-top: 1px solid #e2e8f0; padding: 16px 32px; color: #94a3b8; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>InternRadar</h1></div>
    <div class="body">
      <p>Hello,</p>
      <p>Please use the following single-use verification code to confirm your email address. This code expires in <strong>{expires_min} minutes</strong>.</p>
      <div class="otp-box"><div class="otp">{otp}</div></div>
      <p class="note">If you did not request this verification, you can safely disregard this email.</p>
    </div>
    <div class="footer">InternRadar &middot; Internship Discovery & Career Platform</div>
  </div>
</body>
</html>
"""


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    if not settings.smtp_host:
        log.warning("SMTP not configured; notification for %s not sent via email", to_email)
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    ctx = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            # SSL connection (Brevo / SendinBlue and some providers use port 465)
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=15) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(settings.smtp_from, to_email, msg.as_string())
        else:
            # STARTTLS connection (port 587 – most common, including Brevo default)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ctx)
                smtp.ehlo()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(settings.smtp_from, to_email, msg.as_string())
        log.info("✅ Email sent to %s via %s:%d", to_email, settings.smtp_host, settings.smtp_port)
    except smtplib.SMTPAuthenticationError:
        log.error("❌ SMTP authentication failed for %s – check SMTP_USER and SMTP_PASSWORD in .env", settings.smtp_host)
    except smtplib.SMTPRecipientsRefused as exc:
        log.error("❌ Recipient refused: %s – %s", to_email, exc)
    except Exception:
        log.exception("❌ Failed to send email to %s via %s:%d", to_email, settings.smtp_host, settings.smtp_port)


def send_otp_email(to_email: str, otp: str) -> None:
    if not settings.smtp_host:
        log.info("[AUTH] Verification OTP for %s: %s (expires in %d min)", to_email, otp, settings.otp_expire_minutes)
        return
    html = _OTP_HTML.format(otp=otp, expires_min=settings.otp_expire_minutes)
    _send_smtp(to_email, "Your InternRadar verification code", html)


def send_welcome_email(to_email: str, full_name: str) -> None:
    html = f"""
    <!DOCTYPE html><html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#f8fafc; color:#0f172a; padding:40px 20px;">
    <div style="max-width:520px;margin:auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <div style="background:#0f172a;border-bottom:2px solid #2563eb;padding:24px 32px;">
        <h1 style="color:#ffffff;margin:0;font-size:20px;font-weight:600;">InternRadar</h1>
      </div>
      <div style="padding:32px;">
        <p>Dear <strong>{full_name}</strong>,</p>
        <p>Your email has been verified successfully. You can now explore verified internship opportunities and receive customized matching based on your skills and preferences.</p>
        <p style="color:#64748b;font-size:13px;margin-top:24px;">InternRadar Platform</p>
      </div>
    </div>
    </body></html>
    """
    _send_smtp(to_email, "Welcome to InternRadar", html)
