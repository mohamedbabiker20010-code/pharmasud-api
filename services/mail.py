"""Provider-neutral transactional mail transport for activation and recovery."""

from dataclasses import dataclass
from email.message import EmailMessage
import html
import os
import smtplib
import ssl
from typing import Protocol


@dataclass(frozen=True)
class MailMessage:
    recipient: str
    subject: str
    text: str
    html: str


class MailTransport(Protocol):
    def send(self, message: MailMessage) -> None: ...


class SMTPMailTransport:
    def __init__(self):
        self.host = os.environ["MAIL_HOST"]
        self.port = int(os.getenv("MAIL_PORT", "587"))
        self.username = os.getenv("MAIL_USERNAME", "")
        self.password = os.getenv("MAIL_PASSWORD", "")
        self.from_address = os.environ["MAIL_FROM_ADDRESS"]
        self.from_name = os.getenv("MAIL_FROM_NAME", "PharmaSUD")

    def send(self, message: MailMessage) -> None:
        email = EmailMessage()
        email["From"] = f"{self.from_name} <{self.from_address}>"
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.text)
        email.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(self.host, self.port, timeout=20) as client:
            client.starttls(context=ssl.create_default_context())
            if self.username:
                client.login(self.username, self.password)
            client.send_message(email)


class CapturedMailTransport:
    """Test transport; never performs network delivery."""
    def __init__(self):
        self.messages: list[MailMessage] = []

    def send(self, message: MailMessage) -> None:
        self.messages.append(message)


def get_mail_transport() -> MailTransport:
    return SMTPMailTransport()


def _base_url() -> str:
    return os.environ["APP_BASE_URL"].rstrip("/")


def activation_message(*, recipient: str, pharmacy: str, owner: str, secret: str, expires_hours: int) -> MailMessage:
    link = f"{_base_url()}/owner-activation#token={secret}"
    safe_pharmacy, safe_owner, safe_link = map(html.escape, (pharmacy, owner, link))
    return MailMessage(
        recipient=recipient,
        subject="PharmaSUD — حساب صيدليتك جاهز",
        text=(f"مرحباً {owner}، حساب {pharmacy} جاهز. افتح رابط التفعيل خلال {expires_hours} ساعة:\n{link}\n"
              "إذا لم تتوقع هذه الرسالة فتجاهلها."),
        html=(f'<div dir="rtl"><h2>PharmaSUD</h2><p>مرحباً {safe_owner}،</p>'
              f'<p>حساب صيدلية <strong>{safe_pharmacy}</strong> جاهز.</p>'
              f'<p><a href="{safe_link}">اختيار كلمة المرور وتفعيل الحساب</a></p>'
              f'<p>ينتهي الرابط خلال {expires_hours} ساعة. تجاهل الرسالة إذا لم تتوقعها.</p></div>'),
    )


def reset_message(*, recipient: str, secret: str, expires_minutes: int) -> MailMessage:
    link = f"{_base_url()}/reset-password#token={secret}"
    safe_link = html.escape(link)
    return MailMessage(
        recipient=recipient,
        subject="PharmaSUD — إعادة تعيين كلمة المرور",
        text=(f"استخدم الرابط خلال {expires_minutes} دقيقة لإعادة تعيين كلمة المرور:\n{link}\n"
              "إذا لم تطلب ذلك فتجاهل الرسالة."),
        html=(f'<div dir="rtl"><h2>PharmaSUD</h2><p>تلقينا طلب إعادة تعيين كلمة المرور.</p>'
              f'<p><a href="{safe_link}">إعادة تعيين كلمة المرور</a></p>'
              f'<p>ينتهي الرابط خلال {expires_minutes} دقيقة. تجاهل الرسالة إذا لم تطلب ذلك.</p></div>'),
    )
