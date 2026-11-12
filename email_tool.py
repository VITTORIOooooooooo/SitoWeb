"""
email_tool.py
Invio delle email (conferma account e recupero password) tramite SMTP.
Se l'SMTP non è configurato nel file .env, le funzioni restituiscono False
e il link viene stampato nel terminale: così l'app funziona anche senza email.
"""
import smtplib
import ssl
from email.message import EmailMessage

import config


def email_configurata():
    return bool(config.MAIL_USERNAME and config.MAIL_PASSWORD)


def invia_email(destinatario, oggetto, testo, html):
    """Invia una email in formato testo + HTML. Restituisce True se è partita."""
    if not email_configurata():
        return False

    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = f"{config.AZIENDA['nome']} <{config.MAIL_MITTENTE}>"
    msg["To"] = destinatario
    msg.set_content(testo)                 # versione solo testo
    msg.add_alternative(html, subtype="html")  # versione grafica

    contesto = ssl.create_default_context()
    try:
        if config.MAIL_PORT == 465:
            with smtplib.SMTP_SSL(config.MAIL_SERVER, config.MAIL_PORT, context=contesto, timeout=15) as smtp:
                smtp.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT, timeout=15) as smtp:
                smtp.starttls(context=contesto)
                smtp.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
                smtp.send_message(msg)
        return True
    except Exception as errore:
        print(f"[EMAIL] Invio non riuscito a {destinatario}: {errore}")
        return False


def _html(titolo, saluto, paragrafo, testo_bottone, link, nota):
    """Modello HTML comune a tutte le email."""
    nome = config.AZIENDA["nome"]
    return f"""
    <div style="font-family:Arial,sans-serif;background:#f3f6fc;padding:30px">
      <div style="max-width:520px;margin:auto;background:#fff;border-radius:14px;padding:32px;border:1px solid #e5e7eb">
        <h2 style="color:#4f46e5;margin-top:0">⚡ {nome}</h2>
        <h3 style="color:#26324b">{titolo}</h3>
        <p style="color:#26324b">{saluto}</p>
        <p style="color:#26324b">{paragrafo}</p>
        <p style="text-align:center;margin:28px 0">
          <a href="{link}" style="background:#4f46e5;color:#fff;padding:13px 24px;border-radius:9px;text-decoration:none;font-weight:bold">{testo_bottone}</a>
        </p>
        <p style="color:#64748b;font-size:13px">{nota}</p>
        <p style="color:#64748b;font-size:12px;word-break:break-all">Se il pulsante non funziona copia questo link: {link}</p>
      </div>
    </div>"""


def invia_conferma(destinatario, username, link):
    oggetto = f"Conferma il tuo account {config.AZIENDA['nome']}"
    testo = (f"Ciao {username},\nper attivare il tuo account apri questo link:\n{link}\n\n"
             f"Il link scade tra {config.ORE_VALIDITA_CONFERMA} ore.")
    html = _html("Attiva il tuo account", f"Ciao <b>{username}</b>,",
                 "grazie per esserti registrato! Clicca il pulsante qui sotto per confermare la tua email e attivare l'account.",
                 "Attiva account", link,
                 f"Il link scade tra {config.ORE_VALIDITA_CONFERMA} ore. Se non sei stato tu, ignora questa email.")
    return invia_email(destinatario, oggetto, testo, html)

