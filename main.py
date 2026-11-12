"""
main.py
Applicazione web Flask: contiene le pagine (endpoint) e le API JSON.
L'accesso al database è tutto nel modulo DB_tool.py.

Avvio:  python main.py   →   http://localhost:3000
"""
import secrets
import sys
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)

import config
import DB_tool
import email_tool
import sicurezza

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,      # JavaScript non può leggere il cookie di sessione
    SESSION_COOKIE_SAMESITE="Lax",     # il cookie non parte da form di altri siti
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)


# =====================================================================
#  UTENTE CORRENTE E PROTEZIONE CSRF
# =====================================================================

@app.before_request
def prima_di_ogni_richiesta():
    if request.endpoint == "static":
        return

    # 1) Carico l'utente loggato (se c'è) leggendo il suo id dalla sessione
    g.utente = None
    if "utente_id" in session:
        utente = DB_tool.trova_utente_per_id(session["utente_id"])
        if utente and utente["attivo"]:
            g.utente = utente
        else:                      # utente eliminato o non più attivo
            session.pop("utente_id", None)

    # 2) Token anti-CSRF: un valore segreto per sessione che deve accompagnare ogni POST/PUT/DELETE
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method in ("POST", "PUT", "DELETE"):
        inviato = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(inviato, session["csrf"]):
            abort(400, "Sessione scaduta o richiesta non valida: ricarica la pagina e riprova.")


@app.context_processor
def variabili_template():
    """Variabili disponibili in tutti i template HTML."""
    return {
        "utente": g.get("utente"),
        "csrf_token": session.get("csrf", ""),
        "azienda": config.AZIENDA,
        "anno": datetime.now().year,
    }


def e_api():
    return request.path.startswith("/api/")


def login_richiesto(funzione):
    """Decoratore: la pagina è visibile solo agli utenti loggati."""
    @wraps(funzione)
    def controllo(*args, **kwargs):
        if g.utente is None:
            if e_api():
                return jsonify(successo=False, errore="Non autenticato"), 401
            flash("Accedi per vedere questa pagina.", "info")
            return redirect(url_for("login", next=request.path))
        return funzione(*args, **kwargs)
    return controllo


def solo_gestori(funzione):
    """Decoratore: la pagina è riservata agli utenti con ruolo 'gestore'."""
    @wraps(funzione)
    @login_richiesto
    def controllo(*args, **kwargs):
        if g.utente["ruolo"] != "gestore":
            if e_api():
                return jsonify(successo=False, errore="Permesso negato: operazione riservata ai gestori"), 403
            abort(403)
        return funzione(*args, **kwargs)
    return controllo


def link_sicuro(destinazione):
    """Evita i redirect verso siti esterni (accetta solo percorsi interni tipo /dashboard)."""
    if destinazione and destinazione.startswith("/") and not destinazione.startswith("//") \
            and not urlparse(destinazione).netloc:
        return destinazione
    return url_for("dashboard")


# =====================================================================
#  HOME
# =====================================================================

@app.get("/")
def home():
    return redirect(url_for("dashboard"))


# =====================================================================
#  REGISTRAZIONE E CONFERMA EMAIL
# =====================================================================

def manda_link_conferma(utente_id, username, email):
    """Crea un nuovo token, lo salva (in hash) e manda il link. Ritorna il link se l'email non è partita."""
    token = sicurezza.genera_token()
    scadenza = datetime.now() + timedelta(hours=config.ORE_VALIDITA_CONFERMA)
    DB_tool.imposta_token_conferma(utente_id, sicurezza.hash_token(token), scadenza)
    link = url_for("conferma", token=token, _external=True)
    if email_tool.invia_conferma(email, username, link):
        return None
    print(f"\n[MODALITÀ SVILUPPO] Link di conferma per {username}: {link}\n")
    return link


@app.route("/registrati", methods=["GET", "POST"])
def registrati():
    if g.utente:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return render_template("auth/registrati.html", dati={})

    dati = {
        "username": request.form.get("username", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
    }
    password = request.form.get("password", "")
    conferma = request.form.get("conferma", "")

    errori = []
    if not sicurezza.valida_username(dati["username"]):
        errori.append("Lo username deve avere 3-30 caratteri: lettere, numeri, punto o underscore.")
    elif DB_tool.esiste_username(dati["username"]):
        errori.append("Questo username è già in uso.")
    if not sicurezza.valida_email(dati["email"]):
        errori.append("Inserisci un indirizzo email valido.")
    elif DB_tool.esiste_email(dati["email"]):
        errori.append("Esiste già un account con questa email.")
    mancanti = sicurezza.errori_password(password)
    if mancanti:
        errori.append("La password deve contenere " + ", ".join(mancanti) + ".")
    if password != conferma:
        errori.append("Le due password non coincidono.")

    if errori:
        for e in errori:
            flash(e, "errore")
        return render_template("auth/registrati.html", dati=dati), 400

    utente_id = DB_tool.crea_utente(dati["username"], dati["email"], sicurezza.hash_password(password))
    link_sviluppo = manda_link_conferma(utente_id, dati["username"], dati["email"])
    return render_template("auth/controlla_email.html", email=dati["email"], link_sviluppo=link_sviluppo,
                           tipo="conferma", email_attiva=email_tool.email_configurata())


@app.get("/conferma/<token>")
def conferma(token):
    utente = DB_tool.trova_utente_per_token_conferma(sicurezza.hash_token(token))
    if utente is None:
        flash("Link di conferma non valido o già utilizzato.", "errore")
    elif utente["scadenza_conferma"] < datetime.now():
        flash("Il link di conferma è scaduto: richiedine uno nuovo qui sotto.", "errore")
        return redirect(url_for("reinvia_conferma"))
    else:
        DB_tool.attiva_utente(utente["id"])
        flash("Email confermata! Ora puoi accedere.", "successo")
    return redirect(url_for("login"))


@app.route("/reinvia-conferma", methods=["GET", "POST"])
def reinvia_conferma():
    if request.method == "GET":
        return render_template("auth/email_form.html", tipo="conferma")
    email = request.form.get("email", "").strip().lower()
    utente = DB_tool.trova_utente_per_email(email)
    link_sviluppo = None
    if utente and not utente["attivo"]:
        link_sviluppo = manda_link_conferma(utente["id"], utente["username"], utente["email"])
    # Messaggio sempre uguale: non riveliamo se l'email è registrata
    return render_template("auth/controlla_email.html", email=email, link_sviluppo=link_sviluppo,
                           tipo="conferma", email_attiva=email_tool.email_configurata())


# =====================================================================
#  LOGIN / LOGOUT
# =====================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.utente:
        return redirect(url_for("dashboard"))
    if request.method == "GET":
        return render_template("auth/login.html")

    credenziale = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    utente = DB_tool.trova_utente_per_login(credenziale) if credenziale else None

    if utente is None or not sicurezza.verifica_password(password, utente["password_hash"]):
        flash("Username/email o password errati.", "errore")
        return render_template("auth/login.html", credenziale=credenziale), 401
    if not utente["attivo"]:
        flash("Account non ancora attivo: conferma la tua email (controlla anche lo spam).", "errore")
        return render_template("auth/login.html", credenziale=credenziale, non_attivo=True), 403

    # Nuova sessione pulita (evita il "session fixation"), poi salvo solo l'id dell'utente
    csrf = session.get("csrf")
    session.clear()
    session["utente_id"] = utente["id"]
    session["csrf"] = csrf or secrets.token_hex(16)
    session.permanent = request.form.get("ricordami") == "on"

    DB_tool.aggiorna_ultimo_accesso(utente["id"])
    flash(f"Bentornato, {utente['username']}!", "successo")
    return redirect(link_sicuro(request.args.get("next")))


@app.post("/logout")
def logout():
    session.clear()
    flash("Sei uscito dal tuo account.", "info")
    return redirect(url_for("login"))


# =====================================================================
#  AREA RISERVATA: DASHBOARD (tutti gli utenti)
# =====================================================================

@app.get("/dashboard")
@login_richiesto
def dashboard():
    return render_template("dashboard.html", categorie=DB_tool.elenco_categorie(),
                           disponibilita=DB_tool.DISPONIBILITA)


# =====================================================================
#  AREA GESTORI: PAGINE
# =====================================================================

@app.get("/gestione")
@solo_gestori
def gestione_prodotti():
    return render_template("gestione/prodotti.html", categorie=DB_tool.elenco_categorie(),
                           disponibilita=DB_tool.DISPONIBILITA)


# =====================================================================
#  API JSON: PRODOTTI
# =====================================================================

def numero_o_none(valore):
    try:
        return float(valore.replace(",", ".")) if valore not in (None, "") else None
    except ValueError:
        return None


def data_o_none(valore):
    try:
        return datetime.strptime(valore, "%Y-%m-%d").date().isoformat() if valore else None
    except ValueError:
        return None


@app.get("/api/prodotti")
@login_richiesto
def api_prodotti():
    a = request.args
    prodotti = DB_tool.recupera_prodotti(
        cerca=a.get("q", "").strip() or None,
        categoria=a.get("categoria") or None,
        disponibilita=a.get("disponibilita") or None,
        prezzo_min=numero_o_none(a.get("prezzo_min")),
        prezzo_max=numero_o_none(a.get("prezzo_max")),
        uscita_da=data_o_none(a.get("uscita_da")),
        uscita_a=data_o_none(a.get("uscita_a")),
        ordina=a.get("ordina", "id"),
        direzione=a.get("direzione", "asc"),
    )
    return jsonify(successo=True, dati=prodotti)


@app.get("/api/prodotti/<int:prodotto_id>")
@login_richiesto
def api_prodotto(prodotto_id):
    p = DB_tool.recupera_prodotto(prodotto_id)
    if p is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    return jsonify(successo=True, dati=p)


@app.get("/api/statistiche")
@login_richiesto
def api_statistiche():
    return jsonify(successo=True, dati=DB_tool.statistiche())


def valida_prodotto(form):
    """Controlla i campi del form prodotto. Restituisce (dati_puliti, lista_errori)."""
    errori = []
    dati = {
        "nome": form.get("nome", "").strip()[:100],
        "categoria": form.get("categoria", "").strip()[:50],
        "referente": form.get("referente", "").strip()[:100],
        "descrizione": form.get("descrizione", "").strip()[:2000],
        "disponibilita": form.get("disponibilita", ""),
        "data_uscita": data_o_none(form.get("data_uscita")),
        "data_produzione": data_o_none(form.get("data_produzione")),
    }
    for campo in ("nome", "categoria", "referente"):
        if not dati[campo]:
            errori.append(f"Il campo «{campo}» è obbligatorio.")

    prezzo = numero_o_none(form.get("prezzo"))
    if prezzo is None or prezzo < 0 or prezzo > 99_999_999:
        errori.append("Il prezzo deve essere un numero positivo.")
    dati["prezzo"] = round(prezzo or 0, 2)

    try:
        dati["quantita"] = int(form.get("quantita", "0") or 0)
        if dati["quantita"] < 0:
            raise ValueError
    except ValueError:
        errori.append("La quantità deve essere un numero intero positivo.")

    if dati["disponibilita"] not in DB_tool.DISPONIBILITA:
        errori.append("Disponibilità non valida.")
    if not dati["data_uscita"] or not dati["data_produzione"]:
        errori.append("Inserisci data di produzione e data di uscita.")
    elif dati["data_produzione"] > dati["data_uscita"]:
        errori.append("La data di produzione non può essere successiva alla data di uscita.")
    return dati, errori


@app.post("/api/prodotti")
@solo_gestori
def api_crea_prodotto():
    dati, errori = valida_prodotto(request.form)
    if errori:
        return jsonify(successo=False, errore=" ".join(errori)), 400

    nuovo_id = DB_tool.crea_prodotto(dati)
    return jsonify(successo=True, messaggio="Prodotto creato", id=nuovo_id), 201


@app.put("/api/prodotti/<int:prodotto_id>")
@solo_gestori
def api_modifica_prodotto(prodotto_id):
    if DB_tool.recupera_prodotto(prodotto_id) is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    dati, errori = valida_prodotto(request.form)
    if errori:
        return jsonify(successo=False, errore=" ".join(errori)), 400

    DB_tool.aggiorna_prodotto(prodotto_id, dati)
    return jsonify(successo=True, messaggio="Prodotto aggiornato")


@app.delete("/api/prodotti/<int:prodotto_id>")
@solo_gestori
def api_elimina_prodotto(prodotto_id):
    p = DB_tool.recupera_prodotto(prodotto_id)
    if p is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    DB_tool.elimina_prodotto(prodotto_id)
    return jsonify(successo=True, messaggio="Prodotto eliminato")


# =====================================================================
#  PAGINE DI ERRORE
# =====================================================================

MESSAGGI_ERRORE = {
    400: "Richiesta non valida.",
    403: "Questa pagina è riservata agli utenti gestori.",
    404: "La pagina che cerchi non esiste.",
    500: "Errore interno del server.",
}


def gestisci_errore(errore):
    codice = getattr(errore, "code", 500)
    descrizione = getattr(errore, "description", None)
    messaggio = descrizione if codice == 400 and descrizione else MESSAGGI_ERRORE.get(codice, "Errore")
    if e_api():
        return jsonify(successo=False, errore=messaggio), codice
    return render_template("errore.html", codice=codice, messaggio=messaggio), codice


for _codice in MESSAGGI_ERRORE:
    app.register_error_handler(_codice, gestisci_errore)


# =====================================================================
#  AVVIO
# =====================================================================

if __name__ == "__main__":
    problema = DB_tool.verifica_struttura()
    if problema:
        print(f"\n❌ {problema}\n   Esegui prima:  python init_db.py\n")
        sys.exit(1)
    if not email_tool.email_configurata():
        print("ℹ️  Email non configurata nel file .env: i link di conferma verranno stampati qui.")
    print(f"✅ Server avviato su http://localhost:{config.PORTA}")
    app.run(host="0.0.0.0", port=config.PORTA, debug=config.DEBUG)
