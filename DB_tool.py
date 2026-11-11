"""
DB_tool.py
Modulo che contiene TUTTE le funzioni di accesso al database MySQL.
main.py non scrive mai SQL: chiama solo le funzioni di questo file.

PROTEZIONE DA SQL INJECTION
Ogni valore che arriva dall'utente viene passato a cursor.execute() come
PARAMETRO (i segnaposto %s), mai concatenato dentro la stringa SQL.
È PyMySQL a fare l'escape dei caratteri pericolosi (', ", ;, --, ...).
Dove non si possono usare i parametri (il nome della colonna in ORDER BY)
usiamo una "lista bianca" di valori ammessi.
"""
from datetime import date, datetime
from decimal import Decimal

import pymysql
import pymysql.cursors

import config

TABELLE = ["prodotti", "utenti"]


# =====================================================================
#  CONNESSIONE E FUNZIONI DI SUPPORTO
# =====================================================================

def get_connection():
    """Apre una connessione al database MySQL usando i dati del file .env."""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,  # ogni riga arriva come dizionario
        connect_timeout=5,
    )


def _pulisci(riga):
    """Converte Decimal e date in tipi che si possono mandare in JSON."""
    if riga is None:
        return None
    for chiave, valore in riga.items():
        if isinstance(valore, Decimal):
            riga[chiave] = float(valore)
        elif isinstance(valore, datetime):
            riga[chiave] = valore.strftime("%Y-%m-%d %H:%M")
        elif isinstance(valore, date):
            riga[chiave] = valore.isoformat()
    return riga


def leggi(query, parametri=(), uno=False):
    """Esegue una SELECT e restituisce una lista di righe (o una sola riga se uno=True)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, parametri)
            if uno:
                return cursor.fetchone()
            return cursor.fetchall()
    finally:
        conn.close()


def scrivi(query, parametri=()):
    """Esegue INSERT / UPDATE / DELETE, salva (commit) e restituisce l'id inserito o le righe toccate."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            righe = cursor.execute(query, parametri)
            conn.commit()
            return cursor.lastrowid if query.lstrip().upper().startswith("INSERT") else righe
    finally:
        conn.close()


# =====================================================================
#  CREAZIONE DEL DATABASE E DELLE TABELLE
# =====================================================================

def crea_database_se_manca():
    """Utile in locale (XAMPP): crea il database se non esiste. A scuola di solito esiste già."""
    conn = pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                           password=config.DB_PASSWORD, charset="utf8mb4", connect_timeout=5)
    try:
        with conn.cursor() as cursor:
            # il nome del database non può essere un parametro %s: lo "quotiamo" con i backtick
            nome = config.DB_NAME.replace("`", "")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{nome}` CHARACTER SET utf8mb4")
        conn.commit()
    finally:
        conn.close()


def crea_tabelle():
    """Crea le tabelle del progetto (se non esistono già)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS utenti (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(30) NOT NULL UNIQUE,
                    email VARCHAR(120) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    attivo TINYINT(1) NOT NULL DEFAULT 0,
                    ultimo_accesso DATETIME NULL,
                    creato_il DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prodotti (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    categoria VARCHAR(50) NOT NULL,
                    referente VARCHAR(100) NOT NULL,
                    descrizione TEXT NULL,
                    prezzo DECIMAL(10, 2) NOT NULL,
                    quantita INT NOT NULL DEFAULT 0,
                    disponibilita VARCHAR(20) NOT NULL,
                    data_uscita DATE NOT NULL,
                    data_produzione DATE NOT NULL,
                    creato_il DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    modificato_il DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        conn.commit()
    finally:
        conn.close()


def elimina_tabelle():
    """Cancella tutte le tabelle del progetto (usata solo da init_db.py per ripartire da zero)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # disattivo per un attimo i controlli sulle FOREIGN KEY, così l'ordine delle DROP non conta
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for tabella in TABELLE:
                cursor.execute(f"DROP TABLE IF EXISTS {tabella}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()


def verifica_struttura():
    """
    Controlla che il database sia pronto (tabelle create con le colonne giuste).
    Restituisce None se è tutto a posto, altrimenti un messaggio d'errore.
    """
    try:
        righe = leggi(
            "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s",
            (config.DB_NAME,),
        )
    except pymysql.MySQLError as errore:
        return f"Impossibile collegarsi al database: {errore}"

    colonne = {(r["TABLE_NAME"].lower(), r["COLUMN_NAME"].lower()) for r in righe}
    necessarie = [("utenti", "password_hash"), ("prodotti", "categoria")]
    mancanti = [f"{t}.{c}" for t, c in necessarie if (t, c) not in colonne]
    if mancanti:
        return "Struttura del database mancante o vecchia (" + ", ".join(mancanti) + ")."
    return None


# =====================================================================
#  UTENTI
# =====================================================================

CAMPI_UTENTE = "id, username, email, attivo, ultimo_accesso, creato_il"


def crea_utente(username, email, password_hash, attivo=False):
    return scrivi(
        """INSERT INTO utenti (username, email, password_hash, attivo)
           VALUES (%s, %s, %s, %s)""",
        (username, email.lower(), password_hash, int(attivo)),
    )


def trova_utente_per_id(utente_id):
    return _pulisci(leggi(f"SELECT {CAMPI_UTENTE} FROM utenti WHERE id = %s", (utente_id,), uno=True))


def trova_utente_per_login(username_o_email):
    """Usata nel login: restituisce anche l'hash della password per poterlo verificare."""
    return leggi(
        "SELECT * FROM utenti WHERE username = %s OR email = %s",
        (username_o_email, username_o_email.lower()),
        uno=True,
    )


def esiste_username(username):
    return leggi("SELECT id FROM utenti WHERE username = %s", (username,), uno=True) is not None


def esiste_email(email):
    return leggi("SELECT id FROM utenti WHERE email = %s", (email.lower(),), uno=True) is not None


def aggiorna_ultimo_accesso(utente_id):
    scrivi("UPDATE utenti SET ultimo_accesso = NOW() WHERE id = %s", (utente_id,))


# =====================================================================
#  PRODOTTI
# =====================================================================

# Colonne restituite dalle query sui prodotti
CAMPI_PRODOTTO = """id, nome, categoria, referente, descrizione, prezzo, quantita, disponibilita,
                    data_uscita, data_produzione, creato_il, modificato_il"""

# Lista bianca per ORDER BY: i nomi delle colonne non possono essere passati come
# parametri %s, quindi accettiamo SOLO questi valori.
COLONNE_ORDINABILI = {"id", "nome", "categoria", "referente", "prezzo", "quantita",
                      "disponibilita", "data_uscita", "data_produzione", "modificato_il"}

DISPONIBILITA = ["Disponibile", "In arrivo", "Esaurito"]


def recupera_prodotti(cerca=None, categoria=None, disponibilita=None,
                      prezzo_min=None, prezzo_max=None, uscita_da=None, uscita_a=None,
                      ordina="id", direzione="asc"):
    """Ricerca, filtri e ordinamento vengono fatti direttamente dal database con la query SQL."""
    query = f"SELECT {CAMPI_PRODOTTO} FROM prodotti WHERE 1=1"
    parametri = []

    if cerca:
        query += """ AND (nome LIKE %s OR referente LIKE %s OR categoria LIKE %s
                          OR descrizione LIKE %s OR CAST(id AS CHAR) = %s)"""
        like = f"%{cerca}%"
        parametri += [like, like, like, like, cerca]
    if categoria:
        query += " AND categoria = %s"
        parametri.append(categoria)
    if disponibilita:
        query += " AND disponibilita = %s"
        parametri.append(disponibilita)
    if prezzo_min is not None:
        query += " AND prezzo >= %s"
        parametri.append(prezzo_min)
    if prezzo_max is not None:
        query += " AND prezzo <= %s"
        parametri.append(prezzo_max)
    if uscita_da:
        query += " AND data_uscita >= %s"
        parametri.append(uscita_da)
    if uscita_a:
        query += " AND data_uscita <= %s"
        parametri.append(uscita_a)

    if ordina not in COLONNE_ORDINABILI:
        ordina = "id"
    direzione = "DESC" if direzione == "desc" else "ASC"
    query += f" ORDER BY {ordina} {direzione}, id ASC"

    return [_pulisci(r) for r in leggi(query, parametri)]


def recupera_prodotto(prodotto_id):
    return _pulisci(leggi(f"SELECT {CAMPI_PRODOTTO} FROM prodotti WHERE id = %s", (prodotto_id,), uno=True))


def crea_prodotto(dati):
    return scrivi(
        """INSERT INTO prodotti (nome, categoria, referente, descrizione, prezzo, quantita, disponibilita,
                                 data_uscita, data_produzione)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (dati["nome"], dati["categoria"], dati["referente"], dati["descrizione"], dati["prezzo"],
         dati["quantita"], dati["disponibilita"], dati["data_uscita"], dati["data_produzione"]),
    )


def elenco_categorie():
    return [r["categoria"] for r in leggi("SELECT DISTINCT categoria FROM prodotti ORDER BY categoria")]


def statistiche():
    """Numeri calcolati dal database con funzioni di aggregazione (COUNT, SUM, AVG, GROUP BY)."""
    totali = _pulisci(leggi("""
        SELECT COUNT(*) AS prodotti,
               COALESCE(SUM(quantita), 0) AS pezzi,
               COALESCE(SUM(prezzo * quantita), 0) AS valore_magazzino,
               COALESCE(AVG(prezzo), 0) AS prezzo_medio,
               COUNT(DISTINCT categoria) AS categorie,
               SUM(disponibilita = 'Disponibile') AS disponibili,
               SUM(disponibilita = 'Esaurito') AS esauriti,
               SUM(disponibilita = 'In arrivo') AS in_arrivo
        FROM prodotti""", uno=True))
    per_categoria = [_pulisci(r) for r in leggi("""
        SELECT categoria, COUNT(*) AS numero, SUM(quantita) AS pezzi
        FROM prodotti GROUP BY categoria ORDER BY numero DESC, categoria""")]
    utenti = leggi("SELECT COUNT(*) AS n FROM utenti WHERE attivo = 1", uno=True)["n"]

    # SUM su colonne booleane restituisce Decimal o None: li normalizziamo a int
    for chiave in ("disponibili", "esauriti", "in_arrivo", "pezzi"):
        totali[chiave] = int(totali[chiave] or 0)
    for r in per_categoria:
        r["pezzi"] = int(r["pezzi"] or 0)
    totali["utenti_attivi"] = utenti
    return {"totali": totali, "per_categoria": per_categoria}

