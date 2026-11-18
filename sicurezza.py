"""
sicurezza.py
Funzioni di sicurezza: crittografia delle password, token casuali e validazione dei dati.
"""
import hashlib
import hmac
import re
import secrets

ITERAZIONI = 260_000  # quante volte viene ripetuto SHA-256: rende lentissimi gli attacchi "brute force"


# ======================= PASSWORD =======================

def hash_password(password):
    """
    Trasforma la password in un hash PBKDF2-HMAC-SHA256 con "sale" casuale.
    Nel database salviamo una stringa del tipo:
        pbkdf2_sha256$260000$<sale>$<hash>
    Il sale è diverso per ogni utente: due utenti con la stessa password
    hanno comunque hash diversi.
    """
    sale = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale.encode("utf-8"), ITERAZIONI)
    return f"pbkdf2_sha256${ITERAZIONI}${sale}${digest.hex()}"


def verifica_password(password, hash_salvato):
    """Ricalcola l'hash con lo stesso sale e lo confronta con quello salvato."""
    try:
        algoritmo, iterazioni, sale, digest_salvato = hash_salvato.split("$")
    except (ValueError, AttributeError):
        return False
    if algoritmo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale.encode("utf-8"), int(iterazioni))
    # compare_digest confronta in tempo costante (evita i "timing attack")
    return hmac.compare_digest(digest.hex(), digest_salvato)


# ======================= TOKEN =======================

def genera_token():
    """Token casuale e imprevedibile da mettere nei link inviati per email."""
    return secrets.token_urlsafe(32)


def hash_token(token):
    """
    Nel database salviamo solo lo SHA-256 del token, non il token vero:
    se qualcuno leggesse il database non potrebbe usare i link.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ======================= VALIDAZIONE =======================

REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
REGEX_USERNAME = re.compile(r"^[a-zA-Z0-9_.]{3,30}$")


def valida_email(email):
    return bool(REGEX_EMAIL.match(email or "")) and len(email) <= 120


def valida_username(username):
    return bool(REGEX_USERNAME.match(username or ""))


def errori_password(password):
    """Restituisce la lista dei requisiti che la password NON rispetta (vuota = ok)."""
    errori = []
    if len(password) < 8:
        errori.append("almeno 8 caratteri")
    if not re.search(r"[A-Z]", password):
        errori.append("una lettera maiuscola")
    if not re.search(r"[a-z]", password):
        errori.append("una lettera minuscola")
    if not re.search(r"[0-9]", password):
        errori.append("un numero")
    return errori
