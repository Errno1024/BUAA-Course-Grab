import smtplib as _smtplib
from email.mime.multipart import MIMEBase as _mimebase, MIMEMultipart as _mimemulti
from email.mime.text import MIMEText as _mimetext
from email.header import Header as _header
import re

_smtp_lut = {
	'263.net.cn': '263.net.cn',
	'airmail.net': 'mail.airmail.net',
	'att.net': 'outbound.att.net',
	'bluewin.ch': 'smtpauths.bluewin.ch',
	'btconnect.com': 'mail.btconnect.tom',
	'earthlink.net': 'smtpauth.earthlink.net',
	'gmx.net': 'mail.gmx.net',
	'hotmail.com': 'smtp-mail.outlook.com',
	'hotpop.com': 'mail.hotpop.com',
	'libero.it': 'mail.libero.it',
	'live.com': 'smtp-mail.outlook.com',
	'outlook.com': 'smtp-mail.outlook.com',
	'verizon.net': 'outgoing.verizon.net',
	'vip.21cn.com': 'vip.21cn.com',
	'yahoo.com': 'mail.yahoo.com',
}

def from_mail(mail_address: str) -> str:
    mail = mail_address[mail_address.rfind('@') + 1:]
    return _smtp_lut.get(mail, 'smtp.' + mail)

class login:
    def __init__(self, username, password, server: str, port: int=25, sender=None):
        colon = server.rfind(':')
        if colon >= 0:
            try:
                port = int(server[colon + 1:])
            except: pass
            server = server[:colon]
        self.smtp = _smtplib.SMTP(server, port)
        self.username = username
        self.password = password
        self.sender = sender

    def __enter__(self):
        self.smtp.login(self.username, self.password)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.smtp.quit()

def login_mail(username, password, sender=None, server=None):
    if sender is None:
        at = username.rfind('@')
        if at >= 0:
            sender = username
            username = username[:at]
        else:
            return None
    if server is None:
        server = from_mail(sender)
    return login(username, password, server=server, sender=sender)

def mail(smtp: login, mime: _mimebase, sender=None, receiver=None):
    if sender is None:
        sender = smtp.sender
    if sender is None:
        return False
    if receiver is None:
        receiver = sender
    try:
        Mime = _mimemulti('related')
        Mime.attach(mime)
        subject_ = mime.get('Subject', None)
        subject_ = '' if subject_ is None else subject_
        from_ = mime.get('From', sender)
        from_ = sender if from_ is None else from_
        to = mime.get('To', receiver)
        to = receiver if to is None else to
        Mime['Subject'] = subject_
        Mime['From'] = from_
        Mime['To'] = to
        smtp.smtp.sendmail(sender, receiver, Mime.as_string())
        return True
    except _smtplib.SMTPException:
        return False

def mime_text(subject, text, from_=None, to=None):
    mime = _mimetext(text, 'plain', 'utf-8')
    mime['Subject'] = _header(subject, 'utf-8')
    mime['From'] = from_
    mime['To'] = to
    return mime

def mime_from_file(subject, filename, from_=None, to=None, replace={}):
    with open(filename, 'r') as file:
        html = file.read()
    for pattern, dest in re_replacer(replace).items():
        html = re.sub(pattern, dest, html)
    mime = _mimetext(html, 'html', file.encoding)
    mime['Subject'] = _header(subject, 'utf-8')
    mime['From'] = from_
    mime['To'] = to
    return mime

def mime_html(subject, html, from_=None, to=None):
    mime = _mimetext(html, 'html', 'utf-8')
    mime['Subject'] = _header(subject, 'utf-8')
    mime['From'] = from_
    mime['To'] = to
    return mime

def _re_var_escape(s):
    return re.sub(r'([\.\*\\\+\^\$\(\)\[\]\|\{\}\?])', '\\\\\\1', s)

def re_replacer(variables):
    res = {}
    for k, v in variables.items():
        res['\\{\\{ *%s *\\}\\}' % _re_var_escape(k)] = _re_var_escape(str(v))
    return res
