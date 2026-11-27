"""
main.py
Applicazione web Flask: contiene le pagine (endpoint) e le API JSON.
L'accesso al database è tutto nel modulo DB_tool.py.

Avvio:  python main.py   →   http://localhost:3000
"""
import csv
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
import email_tool
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
#  UTENTE CORRENTE, PROTEZIONE CSRF E HEADER DI SICUREZZA
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


@app.after_request
def header_sicurezza(risposta):
    risposta.headers["X-Content-Type-Options"] = "nosniff"
    risposta.headers["X-Frame-Options"] = "DENY"
    risposta.headers["Referrer-Policy"] = "same-origin"
    return risposta


@app.context_processor
def variabili_template():
    """Variabili disponibili in tutti i template HTML."""
    utente = g.get("utente")
    return {
        "utente": utente,
        "csrf_token": session.get("csrf", ""),
        "azienda": config.AZIENDA,
        "anno": datetime.now().year,
        # numero di pezzi nel carrello, mostrato nella barra in alto
        "pezzi_carrello": DB_tool.conta_carrello(utente["id"]) if utente else 0,
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


def log(azione, dettaglio):
    """Scrive un'azione nel registro attività."""
    u = g.get("utente")
    DB_tool.registra_attivita(u["id"] if u else None, u["username"] if u else "anonimo", azione, dettaglio)


def link_sicuro(destinazione):
    """Evita i redirect verso siti esterni (accetta solo percorsi interni tipo /dashboard)."""
    if destinazione and destinazione.startswith("/") and not destinazione.startswith("//") \
            and not urlparse(destinazione).netloc:
        return destinazione
    return url_for("dashboard")


# =====================================================================
#  PAGINE PUBBLICHE: AZIENDA E CONTATTI
# =====================================================================

@app.get("/")
def home():
    return redirect(url_for("azienda"))


@app.get("/azienda")
def azienda():
    return render_template(
        "azienda.html",
        stat=DB_tool.statistiche(),
        in_evidenza=DB_tool.prodotti_in_evidenza(6),
    )


@app.post("/contatti")
def contatti():
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip()
    testo = request.form.get("testo", "").strip()
    if not nome or not sicurezza.valida_email(email) or len(testo) < 10:
        flash("Compila tutti i campi: nome, email valida e un messaggio di almeno 10 caratteri.", "errore")
    else:
        DB_tool.salva_messaggio(nome[:80], email[:120], testo[:3000])
        flash("Messaggio inviato! Ti risponderemo il prima possibile.", "successo")
    return redirect(url_for("azienda") + "#contatti")


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
    DB_tool.registra_attivita(utente_id, dati["username"], "registrazione", "Nuovo account creato")
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
        DB_tool.registra_attivita(utente["id"], utente["username"], "conferma", "Email confermata, account attivo")
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
    DB_tool.registra_attivita(utente["id"], utente["username"], "login", "Accesso effettuato")
    flash(f"Bentornato, {utente['username']}!", "successo")
    return redirect(link_sicuro(request.args.get("next")))


@app.post("/logout")
def logout():
    session.clear()
    flash("Sei uscito dal tuo account.", "info")
    return redirect(url_for("login"))


# =====================================================================
#  PASSWORD DIMENTICATA
# =====================================================================

@app.route("/password-dimenticata", methods=["GET", "POST"])
def password_dimenticata():
    if request.method == "GET":
        return render_template("auth/email_form.html", tipo="reset")
    email = request.form.get("email", "").strip().lower()
    utente = DB_tool.trova_utente_per_email(email)
    link_sviluppo = None
    if utente and utente["attivo"]:
        token = sicurezza.genera_token()
        scadenza = datetime.now() + timedelta(minutes=config.MINUTI_VALIDITA_RESET)
        DB_tool.imposta_token_reset(utente["id"], sicurezza.hash_token(token), scadenza)
        link = url_for("reimposta_password", token=token, _external=True)
        if not email_tool.invia_reset_password(utente["email"], utente["username"], link):
            print(f"\n[MODALITÀ SVILUPPO] Link reset password per {utente['username']}: {link}\n")
            link_sviluppo = link
    return render_template("auth/controlla_email.html", email=email, link_sviluppo=link_sviluppo,
                           tipo="reset", email_attiva=email_tool.email_configurata())


@app.route("/reimposta-password/<token>", methods=["GET", "POST"])
def reimposta_password(token):
    utente = DB_tool.trova_utente_per_token_reset(sicurezza.hash_token(token))
    if utente is None or utente["scadenza_reset"] < datetime.now():
        flash("Link non valido o scaduto: richiedine uno nuovo.", "errore")
        return redirect(url_for("password_dimenticata"))
    if request.method == "GET":
        return render_template("auth/reimposta.html", token=token)

    password = request.form.get("password", "")
    mancanti = sicurezza.errori_password(password)
    if mancanti or password != request.form.get("conferma", ""):
        flash("La password deve contenere " + ", ".join(mancanti) + "." if mancanti
              else "Le due password non coincidono.", "errore")
        return render_template("auth/reimposta.html", token=token), 400

    DB_tool.aggiorna_password(utente["id"], sicurezza.hash_password(password))
    DB_tool.registra_attivita(utente["id"], utente["username"], "password", "Password reimpostata via email")
    flash("Password aggiornata: ora puoi accedere.", "successo")
    return redirect(url_for("login"))


# =====================================================================
#  AREA RISERVATA: DASHBOARD (tutti gli utenti) E PROFILO
# =====================================================================

@app.get("/dashboard")
@login_richiesto
def dashboard():
    return render_template("dashboard.html", categorie=DB_tool.elenco_categorie(),
                           disponibilita=DB_tool.DISPONIBILITA)


@app.route("/profilo", methods=["GET", "POST"])
@login_richiesto
def profilo():
    if request.method == "POST":
        attuale = request.form.get("attuale", "")
        nuova = request.form.get("nuova", "")
        completo = DB_tool.trova_utente_per_login(g.utente["username"])
        mancanti = sicurezza.errori_password(nuova)
        if not sicurezza.verifica_password(attuale, completo["password_hash"]):
            flash("La password attuale non è corretta.", "errore")
        elif mancanti:
            flash("La nuova password deve contenere " + ", ".join(mancanti) + ".", "errore")
        elif nuova != request.form.get("conferma", ""):
            flash("Le due password non coincidono.", "errore")
        else:
            DB_tool.aggiorna_password(g.utente["id"], sicurezza.hash_password(nuova))
            log("password", "Password cambiata dal profilo")
            flash("Password aggiornata.", "successo")
        return redirect(url_for("profilo"))
    return render_template("profilo.html")


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


@app.get("/gestione/attivita")
@solo_gestori
def gestione_attivita():
    return render_template("gestione/attivita.html", attivita=DB_tool.ultime_attivita(100),
                           messaggi=DB_tool.elenco_messaggi())


@app.get("/gestione/ordini")
@solo_gestori
def gestione_ordini():
    return render_template("gestione/ordini.html", ordini=DB_tool.tutti_gli_ordini())


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
    log("crea_prodotto", f"Creato #{nuovo_id} «{dati['nome']}»")
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
    log("modifica_prodotto", f"Modificato #{prodotto_id} «{dati['nome']}»")
    return jsonify(successo=True, messaggio="Prodotto aggiornato")


@app.delete("/api/prodotti/<int:prodotto_id>")
@solo_gestori
def api_elimina_prodotto(prodotto_id):
    p = DB_tool.recupera_prodotto(prodotto_id)
    if p is None:
        return jsonify(successo=False, errore="Prodotto non trovato"), 404
    DB_tool.elimina_prodotto(prodotto_id)
    log("elimina_prodotto", f"Eliminato #{prodotto_id} «{p['nome']}»")
    return jsonify(successo=True, messaggio="Prodotto eliminato")


@app.get("/api/prodotti/export.csv")
@solo_gestori
def api_export_csv():
    """Scarica il catalogo in formato CSV (si apre con Excel)."""
    colonne = ["id", "nome", "categoria", "referente", "prezzo", "quantita",
               "disponibilita", "data_uscita", "data_produzione"]
    buffer = io.StringIO()
    scrittore = csv.writer(buffer, delimiter=";")
    scrittore.writerow(colonne)
    for p in DB_tool.recupera_prodotti():
        scrittore.writerow([str(p[c]).replace(".", ",") if c == "prezzo" else p[c] for c in colonne])
    log("export", "Esportato il catalogo in CSV")
    return Response("﻿" + buffer.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=catalogo.csv"})


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
    """Un gestore può creare direttamente un utente già attivo (senza email di conferma)."""
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
    log("crea_utente", f"Creato utente «{username}» ({ruolo})")
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
    log("modifica_utente", f"«{bersaglio['username']}»: ruolo {ruolo}, {'attivo' if attivo else 'disattivato'}")
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
    log("elimina_utente", f"Eliminato utente «{bersaglio['username']}»")
    return jsonify(successo=True, messaggio="Utente eliminato")


@app.delete("/api/messaggi/<int:messaggio_id>")
@solo_gestori
def api_elimina_messaggio(messaggio_id):
    DB_tool.elimina_messaggio(messaggio_id)
    return jsonify(successo=True, messaggio="Messaggio eliminato")


# =====================================================================
#  CARRELLO E ORDINI (tutti gli utenti loggati)
# =====================================================================

@app.get("/carrello")
@login_richiesto
def carrello():
    return render_template("carrello.html", ordini=DB_tool.ordini_utente(g.utente["id"]),
                           soglia=config.SOGLIA_SPEDIZIONE_GRATIS, costo_spedizione=config.COSTO_SPEDIZIONE)


def riepilogo_carrello():
    """Contenuto del carrello + totali calcolati sul server (il client non decide i prezzi)."""
    righe = [con_url_immagine(r | {"id": r["prodotto_id"]}) for r in DB_tool.carrello_utente(g.utente["id"])]
    subtotale = round(sum(r["subtotale"] for r in righe), 2)
    spedizione = 0 if subtotale >= config.SOGLIA_SPEDIZIONE_GRATIS or not righe else config.COSTO_SPEDIZIONE
    return {
        "righe": righe,
        "pezzi": sum(r["quantita"] for r in righe),
        "subtotale": subtotale,
        "spedizione": spedizione,
        "totale": round(subtotale + spedizione, 2),
        "soglia": config.SOGLIA_SPEDIZIONE_GRATIS,
    }


def controlla_quantita(prodotto, quantita_totale):
    """Restituisce un messaggio d'errore se il prodotto non si può avere in quella quantità."""
    if prodotto["disponibilita"] != "Disponibile":
        return f"«{prodotto['nome']}» non è acquistabile ({prodotto['disponibilita'].lower()})."
    massimo = min(prodotto["quantita"], config.MAX_PEZZI_PER_PRODOTTO)
    if quantita_totale > massimo:
        return f"Puoi avere al massimo {massimo} pezzi di «{prodotto['nome']}»."
    return None


@app.get("/api/carrello")
@login_richiesto
def api_carrello():
    return jsonify(successo=True, dati=riepilogo_carrello())


@app.post("/api/carrello")
@login_richiesto
def api_aggiungi_carrello():
    """Aggiunge uno o più prodotti (selezione multipla: più campi prodotto_id)."""
    try:
        ids = [int(x) for x in request.form.getlist("prodotto_id")]
        quantita = int(request.form.get("quantita", "1"))
    except ValueError:
        return jsonify(successo=False, errore="Dati non validi."), 400
    if not ids or quantita < 1:
        return jsonify(successo=False, errore="Seleziona almeno un prodotto."), 400

    aggiunti, errori = 0, []
    for prodotto_id in dict.fromkeys(ids):           # dict.fromkeys toglie i doppioni
        prodotto = DB_tool.recupera_prodotto(prodotto_id)
        if prodotto is None:
            errori.append(f"Prodotto #{prodotto_id} inesistente.")
            continue
        gia_presenti = DB_tool.quantita_nel_carrello(g.utente["id"], prodotto_id)
        problema = controlla_quantita(prodotto, gia_presenti + quantita)
        if problema:
            errori.append(problema)
            continue
        DB_tool.aggiungi_al_carrello(g.utente["id"], prodotto_id, quantita)
        aggiunti += 1

    pezzi = DB_tool.conta_carrello(g.utente["id"])
    if aggiunti == 0:
        return jsonify(successo=False, errore=" ".join(errori), pezzi=pezzi), 400
    messaggio = "Aggiunto al carrello" if aggiunti == 1 else f"{aggiunti} prodotti aggiunti al carrello"
    return jsonify(successo=True, messaggio=messaggio, avvisi=errori, pezzi=pezzi)


@app.put("/api/carrello/<int:prodotto_id>")
@login_richiesto
def api_modifica_carrello(prodotto_id):
    prodotto = DB_tool.recupera_prodotto(prodotto_id)
    try:
        quantita = int(request.form.get("quantita", ""))
    except ValueError:
        return jsonify(successo=False, errore="Quantità non valida."), 400
    if prodotto is None or DB_tool.quantita_nel_carrello(g.utente["id"], prodotto_id) == 0:
        return jsonify(successo=False, errore="Il prodotto non è nel carrello."), 404
    if quantita < 1:
        return jsonify(successo=False, errore="La quantità minima è 1."), 400
    problema = controlla_quantita(prodotto, quantita)
    if problema:
        return jsonify(successo=False, errore=problema), 400
    DB_tool.imposta_quantita_carrello(g.utente["id"], prodotto_id, quantita)
    return jsonify(successo=True, dati=riepilogo_carrello())


@app.delete("/api/carrello/<int:prodotto_id>")
@login_richiesto
def api_rimuovi_carrello(prodotto_id):
    DB_tool.rimuovi_dal_carrello(g.utente["id"], prodotto_id)
    return jsonify(successo=True, messaggio="Prodotto rimosso", dati=riepilogo_carrello())


@app.delete("/api/carrello")
@login_richiesto
def api_svuota_carrello():
    DB_tool.svuota_carrello(g.utente["id"])
    return jsonify(successo=True, messaggio="Carrello svuotato", dati=riepilogo_carrello())


@app.post("/api/ordini")
@login_richiesto
def api_crea_ordine():
    try:
        ordine_id = DB_tool.crea_ordine(g.utente["id"], g.utente["username"],
                                        config.SOGLIA_SPEDIZIONE_GRATIS, config.COSTO_SPEDIZIONE)
    except ValueError as e:
        return jsonify(successo=False, errore=str(e)), 400
    log("ordine", f"Ordine #{ordine_id} confermato")
    return jsonify(successo=True, messaggio=f"Ordine #{ordine_id} confermato!", id=ordine_id), 201


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
    if not email_tool.email_configurata():
        print("ℹ️  Email non configurata nel file .env: i link di conferma verranno stampati qui.")
    print(f"✅ Server avviato su http://localhost:{config.PORTA}")
    app.run(host="0.0.0.0", port=config.PORTA, debug=config.DEBUG)
