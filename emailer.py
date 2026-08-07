import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_report(html_content: str) -> None:
    """Port of the "Send a message" (Gmail) node, using SMTP + an App Password."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Techmeme Signals and AI recommendations as of {date.today().isoformat()}"
    message["From"] = config.GMAIL_ADDRESS
    message["To"] = config.RECIPIENT_EMAIL
    message.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_ADDRESS, [config.RECIPIENT_EMAIL], message.as_string())
