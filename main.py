"""
main.py
Applicazione web Flask: contiene le pagine (endpoint) e le API JSON.
L'accesso al database è tutto nel modulo DB_tool.py.

Avvio:  python main.py   →   http://localhost:3000
"""
import io
import secrets
import sys
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, Response, abort, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from PIL import Image, ImageOps, UnidentifiedImageError

import config
import DB_tool
import sicurezza

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    MAX_CONTENT_LENGTH=(config.MAX_MB_IMMAGINE + 1) * 1024 * 1024,  # limite dimensione richieste
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
        else:                      # utente eliminato o disattivato da un gestore
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
#  REGISTRAZIONE
# =====================================================================

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

    DB_tool.crea_utente(dati["username"], dati["email"], sicurezza.hash_password(password), attivo=True)
    flash("Account creato! Ora puoi accedere.", "successo")
    return redirect(url_for("login"))


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
        flash("Questo account è stato disattivato da un gestore.", "errore")
        return render_template("auth/login.html", credenziale=credenziale), 403

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


@app.get("/gestione/utenti")
@solo_gestori
def gestione_utenti():
    return render_template("gestione/utenti.html")


# =====================================================================
#  IMMAGINI SALVATE NEL DATABASE
# =====================================================================

FORMATI_AMMESSI = {"JPEG", "PNG", "WEBP", "GIF"}


def elabora_immagine(file):
    """
    Controlla che il file sia davvero un'immagine (non basta l'estensione!),
    la raddrizza, la ridimensiona e la converte in WebP per occupare poco spazio nel database.
    Restituisce (byte, tipo_mime).
    """
    try:
        img = Image.open(file.stream)
        formato = img.format
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ValueError("Il file caricato non è un'immagine valida.")
    if formato not in FORMATI_AMMESSI:
        raise ValueError("Formato non supportato: usa JPG, PNG, WEBP o GIF.")

    img = ImageOps.exif_transpose(img)  # gira le foto scattate col telefono
    img.thumbnail((config.LATO_MAX_IMMAGINE, config.LATO_MAX_IMMAGINE))
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="WEBP", quality=82)
    return buffer.getvalue(), "image/webp"


@app.get("/immagine/prodotto/<int:prodotto_id>")
def immagine_prodotto(prodotto_id):
    riga = DB_tool.recupera_immagine(prodotto_id)
    if riga is None:
        abort(404)
    risposta = Response(riga["immagine"], mimetype=riga["immagine_tipo"])
    risposta.headers["Cache-Control"] = "public, max-age=86400"  # il browser la tiene in cache per un giorno
    return risposta


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


def con_url_immagine(p):
    if p["ha_immagine"]:
        # ?v=... cambia quando il prodotto viene modificato, così il browser scarica la nuova immagine
        versione = p["modificato_il"].replace(" ", "").replace(":", "").replace("-", "")
        p["immagine_url"] = url_for("immagine_prodotto", prodotto_id=p["id"], v=versione)
    else:
        p["immagine_url"] = None
    return p


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
    return jsonify(successo=True, dati=[con_url_immagine(p) for p in prodotti])


@app.get("/api/prodotti/<int:prodotto_id>")
@login_richiesto
def api_prodotto(prodotto_id):
    p = DB_tool.recupera_prodotto(prodotto_id)
    if p is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    return jsonify(successo=True, dati=con_url_immagine(p))


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


def leggi_immagine_dal_form():
    """Restituisce (byte, tipo) se è stata caricata un'immagine, altrimenti (None, None)."""
    file = request.files.get("immagine")
    if file is None or file.filename == "":
        return None, None
    return elabora_immagine(file)


@app.post("/api/prodotti")
@solo_gestori
def api_crea_prodotto():
    dati, errori = valida_prodotto(request.form)
    try:
        immagine, tipo = leggi_immagine_dal_form()
    except ValueError as e:
        errori.append(str(e))
    if errori:
        return jsonify(successo=False, errore=" ".join(errori)), 400

    nuovo_id = DB_tool.crea_prodotto(dati, immagine, tipo)
    return jsonify(successo=True, messaggio="Prodotto creato", id=nuovo_id), 201


@app.put("/api/prodotti/<int:prodotto_id>")
@solo_gestori
def api_modifica_prodotto(prodotto_id):
    if DB_tool.recupera_prodotto(prodotto_id) is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    dati, errori = valida_prodotto(request.form)
    try:
        immagine, tipo = leggi_immagine_dal_form()
    except ValueError as e:
        errori.append(str(e))
    if errori:
        return jsonify(successo=False, errore=" ".join(errori)), 400

    DB_tool.aggiorna_prodotto(prodotto_id, dati, immagine, tipo,
                              rimuovi_immagine=request.form.get("rimuovi_immagine") == "1")
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
#  API JSON: UTENTI (solo gestori)
# =====================================================================

@app.get("/api/utenti")
@solo_gestori
def api_utenti():
    return jsonify(successo=True, dati=DB_tool.elenco_utenti(
        cerca=request.args.get("q", "").strip() or None,
        ruolo=request.args.get("ruolo") or None,
    ), io=g.utente["id"])


@app.post("/api/utenti")
@solo_gestori
def api_crea_utente():
    """Un gestore può creare direttamente un nuovo utente, già attivo."""
    f = request.form
    username, email, password = f.get("username", "").strip(), f.get("email", "").strip().lower(), f.get("password", "")
    ruolo = f.get("ruolo", "base")
    errori = []
    if not sicurezza.valida_username(username):
        errori.append("Username non valido (3-30 caratteri: lettere, numeri, . e _).")
    elif DB_tool.esiste_username(username):
        errori.append("Username già in uso.")
    if not sicurezza.valida_email(email):
        errori.append("Email non valida.")
    elif DB_tool.esiste_email(email):
        errori.append("Email già registrata.")
    if sicurezza.errori_password(password):
        errori.append("Password debole: servono 8 caratteri con maiuscola, minuscola e numero.")
    if ruolo not in ("base", "gestore"):
        errori.append("Ruolo non valido.")
    if errori:
        return jsonify(successo=False, errore=" ".join(errori)), 400

    nuovo_id = DB_tool.crea_utente(username, email, sicurezza.hash_password(password), ruolo, attivo=True)
    return jsonify(successo=True, messaggio="Utente creato", id=nuovo_id), 201


@app.put("/api/utenti/<int:utente_id>")
@solo_gestori
def api_modifica_utente(utente_id):
    if utente_id == g.utente["id"]:
        return jsonify(successo=False, errore="Non puoi modificare il tuo ruolo o disattivarti da solo."), 400
    bersaglio = DB_tool.trova_utente_per_id(utente_id)
    if bersaglio is None:
        return jsonify(successo=False, errore="Utente non trovato"), 404
    ruolo = request.form.get("ruolo", bersaglio["ruolo"])
    attivo = request.form.get("attivo", str(bersaglio["attivo"])) == "1"
    if ruolo not in ("base", "gestore"):
        return jsonify(successo=False, errore="Ruolo non valido"), 400

    DB_tool.aggiorna_utente(utente_id, ruolo, attivo)
    return jsonify(successo=True, messaggio="Utente aggiornato")


@app.delete("/api/utenti/<int:utente_id>")
@solo_gestori
def api_elimina_utente(utente_id):
    if utente_id == g.utente["id"]:
        return jsonify(successo=False, errore="Non puoi eliminare il tuo stesso account."), 400
    bersaglio = DB_tool.trova_utente_per_id(utente_id)
    if bersaglio is None:
        return jsonify(successo=False, errore="Utente non trovato"), 404
    DB_tool.elimina_utente(utente_id)
    return jsonify(successo=True, messaggio="Utente eliminato")


# =====================================================================
#  PAGINE DI ERRORE
# =====================================================================

MESSAGGI_ERRORE = {
    400: "Richiesta non valida.",
    403: "Questa pagina è riservata agli utenti gestori.",
    404: "La pagina che cerchi non esiste.",
    413: f"File troppo grande: il limite è {config.MAX_MB_IMMAGINE} MB.",
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
    print(f"✅ Server avviato su http://localhost:{config.PORTA}")
    app.run(host="0.0.0.0", port=config.PORTA, debug=config.DEBUG)
