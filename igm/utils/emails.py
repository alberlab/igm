from .log import logger
from email.message import EmailMessage
import smtplib
import traceback
from ..core.config import Config

def send_email(to, sender=None, smtpserver='localhost', subject="", content=""):
    try:
        if isinstance(to, (Config, dict)):
            cfg = to
            to = cfg['to']
            sender = cfg['from']
            smtpserver = cfg['smtp']
        msg = EmailMessage()
        msg.set_content(content)
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to
        s = smtplib.SMTP(smtpserver)
        s.send_message(msg)
        s.quit()
    except:
        logger.error('Cannot send email')
        logger.error(traceback.format_exc())
