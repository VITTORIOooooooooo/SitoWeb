"""
init_db.py
Prepara il database: crea le tabelle, carica i 30 prodotti di esempio
e crea un account di prova.

    python init_db.py          → chiede conferma prima di cancellare i dati
    python init_db.py --si     → nessuna domanda

ATTENZIONE: cancella e ricrea le tabelle utenti e prodotti.
"""
import json
import os
import sys

import pymysql

import config
import DB_tool
import sicurezza

CARTELLA_DATI = os.path.join(config.CARTELLA, "dati_iniziali")

UTENTI_DEMO = [
    # username, email, password
    ("utente", "utente@voltaria.example", "Utente2026!"),
]


def main():
    print(f"Database: {config.DB_USER}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    if "--si" not in sys.argv:
        risposta = input("Le tabelle del progetto verranno cancellate e ricreate. Continuare? [s/N] ")
        if risposta.strip().lower() not in ("s", "si", "sì", "y"):
            print("Operazione annullata.")
            return

    try:
        DB_tool.crea_database_se_manca()
    except pymysql.MySQLError:
        pass  # sul server della scuola non abbiamo il permesso, ma il database esiste già

    try:
        DB_tool.elimina_tabelle()
        DB_tool.crea_tabelle()
    except pymysql.MySQLError as errore:
        print(f"❌ Errore di connessione al database: {errore}")
        print("   Controlla i dati DB_... nel file .env (e di essere sulla rete della scuola).")
        sys.exit(1)
    print("✅ Tabelle create")

    with open(os.path.join(CARTELLA_DATI, "prodotti.json"), encoding="utf-8") as f:
        prodotti = json.load(f)
    for p in prodotti:
        DB_tool.crea_prodotto(p)
    print(f"✅ {len(prodotti)} prodotti inseriti")

    for username, email, password in UTENTI_DEMO:
        DB_tool.crea_utente(username, email, sicurezza.hash_password(password), attivo=True)
        print(f"✅ Utente di prova →  username: {username}  password: {password}")

    print("\nFatto! Ora avvia il sito con:  python main.py")


if __name__ == "__main__":
    main()
