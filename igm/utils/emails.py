from .log import logger
from email.message import EmailMessage
import smtplib
import traceback
from ..core.config import Config

'''
Works only with localhost for now. Using other smtp will require to setup the connection, with its own security issues
        "smtp" : {
            "label" : "SMTP server",
            "dtype" : "str",
            "role" : "optional-input",
            "blank": true,
            "description" : "SMTP server to use. If not specified, localhost is used"
        }
'''

def send_email(to, sender=None, smtpserver='localhost', subject="", content=""):
    try:
        if isinstance(to, (Config, dict)):
            cfg = to
            to = cfg['address']
            sender = cfg.get('from', sender)
            smtpserver = cfg.get('smtp', smtpserver)
        msg = EmailMessage()
        msg.set_content(content)
        msg['Subject'] = subject
        if sender is None:
            sender = to
        msg['From'] = sender
        msg['To'] = to
        with smtplib.SMTP(smtpserver) as s:
            s.send_message(msg)

    except:
        logger.error('Cannot send email')
        logger.error(traceback.format_exc())
