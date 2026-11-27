# ⚡ Voltaria — Gestionale del catalogo prodotti

Applicazione web in **Python + Flask + MySQL** per un'azienda (di fantasia) di elettronica di consumo.
Gli utenti si registrano con **conferma via email**, hanno **ruoli diversi** (base e gestore), consultano
un catalogo letto **dal database**, lo **selezionano e lo aggiungono al carrello** fino alla conferma dell'ordine,
e i gestori possono **creare, modificare ed eliminare** prodotti, immagini e utenti.

---

## Funzionalità

### Requisiti richiesti
| Requisito | Come è stato realizzato |
|---|---|
| Registrazione con email di conferma | `/registrati` crea l'utente **non attivo** e invia un link `/conferma/<token>` (scade dopo 24 h, usabile una sola volta). Senza conferma il login è bloccato. |
| Utenti con privilegi diversi | Campo `ruolo` (`base` / `gestore`). I decoratori `@login_richiesto` e `@solo_gestori` proteggono pagine e API. |
| Password crittografata | **PBKDF2-HMAC-SHA256** con *sale* casuale per utente e 260.000 iterazioni (`sicurezza.py`). |
| Protezione da SQL injection | Tutte le query usano **parametri `%s`** di PyMySQL; per `ORDER BY` c'è una **lista bianca** di colonne (`DB_tool.py`). |
| Dashboard con dati dal database | `/dashboard`: ricerca, filtri e ordinamento eseguiti **dalla query SQL** (`GET /api/prodotti?...`). |
| Endpoint riservato ai gestori con CRUD | `/gestione`: crea / modifica / elimina prodotti tramite API REST (`POST`, `PUT`, `DELETE`). |
| Salvataggio di immagini nel database | Colonna `MEDIUMBLOB`; le immagini vengono verificate, ridimensionate e convertite in WebP con Pillow, poi servite da `/immagine/prodotto/<id>`. |
| Modulo separato `DB_tool.py` | Tutto l'SQL è in `DB_tool.py`; `main.py` chiama solo le sue funzioni. |
| Pagina di riepilogo dell'azienda con navbar | `/azienda`: pagina lunga con navbar fissa che evidenzia la sezione corrente e barra di avanzamento della lettura. |

### Funzionalità aggiuntive
- **Carrello e ordini**: dal catalogo si possono selezionare più prodotti (anche "seleziona tutti") o aggiungerne uno
  con la quantità scelta. Il carrello è salvato nel database (tabella `carrello`), con contatore nella barra in alto.
  La conferma dell'ordine avviene in una **transazione** (`BEGIN` → `SELECT ... FOR UPDATE` → `COMMIT`/`ROLLBACK`):
  controlla la disponibilità, crea l'ordine, scala il magazzino (a 0 pezzi il prodotto diventa "Esaurito") e svuota
  il carrello. Spedizione gratuita sopra i 49 €. Storico ordini per l'utente e pagina **Ordini** per i gestori.
- **Gestione utenti** per i gestori: cambio ruolo, attivazione manuale, creazione ed eliminazione.
- **Recupero password** via email con link a scadenza (30 minuti).
- **Cambio password** dal profilo, con indicatore di robustezza.
- **Registro attività**: ogni login, creazione, modifica ed eliminazione viene salvata nel database.
- **Modulo contatti** nella pagina azienda: i messaggi finiscono nel database e li leggono i gestori.
- **Statistiche** calcolate con `COUNT`, `SUM`, `AVG` e `GROUP BY` (grafico a barre per categoria).
- **Esportazione CSV** del catalogo (si apre con Excel).
- Vista a **griglia o tabella**, evidenziazione dei risultati di ricerca, dettaglio prodotto.
- **Tema chiaro / scuro**, layout responsive per smartphone.
- Sicurezza extra: **token anti-CSRF**, cookie `HttpOnly` + `SameSite`, rigenerazione della sessione al login,
  protezione da *open redirect*, header di sicurezza, protezione **XSS** (testo inserito con `textContent`).
- **Modalità sviluppo**: se l'email non è configurata il link di conferma viene mostrato a schermo e nel terminale.

---

## Tecnologie
- **Backend:** Python 3, Flask, PyMySQL, Pillow, python-dotenv
- **Database:** MySQL / MariaDB
- **Frontend:** HTML (template Jinja2), CSS, JavaScript (fetch API), nessuna libreria esterna

## Struttura del progetto
```
SVILUPPO_WEB/
├── main.py              # applicazione Flask: pagine, API, permessi
├── DB_tool.py           # tutte le funzioni di accesso al database
├── sicurezza.py         # hash password, token, validazioni
├── email_tool.py        # invio email via SMTP
├── config.py            # legge le impostazioni dal file .env
├── init_db.py           # crea le tabelle e carica i dati di esempio
├── requirements.txt     # librerie Python necessarie
├── .env.example         # modello del file di configurazione
├── dati_iniziali/       # 30 prodotti di esempio + le loro immagini
├── templates/           # pagine HTML (Jinja2)
│   ├── base.html        # struttura comune (barra in alto, footer)
│   ├── auth/            # login, registrazione, conferma, password
│   ├── gestione/        # area riservata ai gestori
│   ├── dashboard.html, carrello.html, azienda.html, profilo.html, errore.html
└── static/
    ├── stile.css
    └── js/              # app.js (comune), dashboard, carrello, gestione, azienda
```

## Database
- **utenti**: `id, username, email, password_hash, ruolo, attivo, token_conferma, scadenza_conferma, token_reset, scadenza_reset, ultimo_accesso, creato_il`
- **prodotti**: `id, nome, categoria, referente, descrizione, prezzo, quantita, disponibilita, data_uscita, data_produzione, immagine (MEDIUMBLOB), immagine_tipo, creato_il, modificato_il`
- **log_attivita**: `id, utente_id (FK → utenti), username, azione, dettaglio, creato_il`
- **messaggi**: `id, nome, email, testo, creato_il`
- **carrello**: `utente_id, prodotto_id` (chiave primaria doppia), `quantita, aggiunto_il`
- **ordini**: `id, utente_id, username, subtotale, spedizione, totale, creato_il`
- **righe_ordine**: `id, ordine_id, prodotto_id, nome_prodotto, prezzo_unitario, quantita` (nome e prezzo copiati: l'ordine non cambia se cambia il prodotto)

Nel database i token delle email sono salvati come hash SHA-256, non in chiaro.

## Installazione
```bash
git clone <url-della-repo>
cd SVILUPPO_WEB
python -m venv venv
# Windows:  venv\Scripts\activate      macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # poi inserisci i dati del database (e, se vuoi, dell'email)
python init_db.py           # crea le tabelle e i dati di esempio
python main.py              # → http://localhost:3000
```

### Account di prova (creati da `init_db.py`)
| Ruolo | Username | Password |
|---|---|---|
| Gestore | `admin` | `Admin2026!` |
| Base | `utente` | `Utente2026!` |

### Configurare l'email (facoltativo)
Con Gmail: attiva la verifica in due passaggi, crea una **password per le app** da
<https://myaccount.google.com/apppasswords> e inseriscila nel file `.env`
(`MAIL_USERNAME` = indirizzo Gmail, `MAIL_PASSWORD` = password per le app di 16 caratteri).

## Endpoint principali
| Metodo | URL | Accesso | Descrizione |
|---|---|---|---|
| GET | `/azienda` | pubblico | Riepilogo dell'azienda con navbar |
| GET/POST | `/registrati`, `/login` | pubblico | Registrazione e accesso |
| GET | `/conferma/<token>` | pubblico | Attivazione dell'account |
| GET | `/dashboard` | utenti loggati | Catalogo con ricerca e filtri |
| GET | `/gestione`, `/gestione/utenti`, `/gestione/attivita` | gestori | Area di amministrazione |
| GET | `/api/prodotti` | utenti loggati | Elenco filtrato (JSON) |
| POST / PUT / DELETE | `/api/prodotti[/<id>]` | gestori | Crea / modifica / elimina |
| GET / POST / PUT / DELETE | `/api/utenti[/<id>]` | gestori | Gestione utenti |
| GET | `/immagine/prodotto/<id>` | pubblico | Immagine letta dal database |
| GET | `/carrello` | utenti loggati | Carrello e storico ordini |
| GET / POST / PUT / DELETE | `/api/carrello[/<id>]` | utenti loggati | Leggi, aggiungi, cambia quantità, rimuovi/svuota |
| POST | `/api/ordini` | utenti loggati | Conferma l'ordine (transazione) |
| GET | `/gestione/ordini` | gestori | Tutti gli ordini ricevuti |
