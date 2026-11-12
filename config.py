"""
config.py
Legge le impostazioni dal file .env (che NON va su GitHub perché contiene password).
Tutti gli altri moduli importano le costanti da qui, così le impostazioni
stanno in un posto solo.
"""
import os
from dotenv import load_dotenv

# Carica le variabili dal file .env che si trova nella stessa cartella di questo file
CARTELLA = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(CARTELLA, ".env"))

# ---------- Flask ----------
# Chiave usata da Flask per firmare il cookie di sessione (se cambia, tutti vengono sloggati)
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-questa-chiave-segreta")
PORTA = int(os.getenv("PORTA", "3000"))
DEBUG = os.getenv("DEBUG", "0") == "1"

# ---------- Database MySQL ----------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sviluppo_web")

# ---------- Email (SMTP) ----------
# Se MAIL_USERNAME è vuoto l'app funziona in "modalità sviluppo":
# il link di conferma viene stampato nel terminale e mostrato a schermo.
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_MITTENTE = os.getenv("MAIL_MITTENTE", MAIL_USERNAME)

# ---------- Regole dell'applicazione ----------
ORE_VALIDITA_CONFERMA = 24      # il link di conferma scade dopo 24 ore

# ---------- Dati dell'azienda (usati nel titolo delle pagine e nel footer) ----------
AZIENDA = {
    "nome": "Voltaria",
    "ragione_sociale": "Voltaria S.r.l.",
    "slogan": "Tecnologia che si accende.",
    "anno_fondazione": 2009,
    "citta": "Reggio Emilia",
    "indirizzo": "Via dell'Innovazione 12, 42122 Reggio Emilia (RE)",
    "telefono": "+39 0522 000 000",
    "email": "info@voltaria.example",
    "dipendenti": 48,
}
