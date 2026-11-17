# ⚡ Voltaria — Gestionale del catalogo prodotti

Applicazione web in **Python + Flask + MySQL** per un'azienda (di fantasia) di elettronica di consumo.
Gli utenti si registrano, hanno **ruoli diversi** (base e gestore), consultano un catalogo letto
**dal database** e i gestori possono **creare, modificare ed eliminare** prodotti, immagini e utenti.

---

## Funzionalità
| Requisito | Come è stato realizzato |
|---|---|
| Registrazione utenti | `/registrati` controlla username, email e robustezza della password e crea l'account nel database. |
| Utenti con privilegi diversi | Campo `ruolo` (`base` / `gestore`). I decoratori `@login_richiesto` e `@solo_gestori` proteggono pagine e API. |
| Password crittografata | **PBKDF2-HMAC-SHA256** con *sale* casuale per utente e 260.000 iterazioni (`sicurezza.py`). |
| Protezione da SQL injection | Tutte le query usano **parametri `%s`** di PyMySQL; per `ORDER BY` c'è una **lista bianca** di colonne (`DB_tool.py`). |
| Dashboard con dati dal database | `/dashboard`: ricerca, filtri e ordinamento eseguiti **dalla query SQL** (`GET /api/prodotti?...`). |
| Endpoint riservato ai gestori con CRUD | `/gestione`: crea / modifica / elimina prodotti tramite API REST (`POST`, `PUT`, `DELETE`). |
| Salvataggio di immagini nel database | Colonna `MEDIUMBLOB`; le immagini vengono verificate, ridimensionate e convertite in WebP con Pillow, poi servite da `/immagine/prodotto/<id>`. |
| Modulo separato `DB_tool.py` | Tutto l'SQL è in `DB_tool.py`; `main.py` chiama solo le sue funzioni. |

### In più
- **Gestione utenti** per i gestori: cambio ruolo, attivazione/disattivazione degli account, creazione ed eliminazione.
- **Statistiche** calcolate con `COUNT`, `SUM`, `AVG` e `GROUP BY` (grafico a barre per categoria).
- Vista a **griglia o tabella**, evidenziazione dei risultati di ricerca, dettaglio prodotto.
- **Tema chiaro / scuro**, layout responsive per smartphone.
- Sicurezza: **token anti-CSRF**, cookie `HttpOnly` + `SameSite`, rigenerazione della sessione al login,
  protezione da *open redirect* e da **XSS** (testo inserito con `textContent`).

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
├── sicurezza.py         # hash password e validazioni
├── config.py            # legge le impostazioni dal file .env
├── init_db.py           # crea le tabelle e carica i dati di esempio
├── requirements.txt     # librerie Python necessarie
├── .env.example         # modello del file di configurazione
├── dati_iniziali/       # 30 prodotti di esempio + le loro immagini
├── templates/           # pagine HTML (Jinja2)
│   ├── base.html        # struttura comune (barra in alto, footer)
│   ├── auth/            # login e registrazione
│   ├── gestione/        # area riservata ai gestori
│   └── dashboard.html, errore.html
└── static/
    ├── stile.css
    └── js/              # app.js (comune), filtri, dashboard, gestione prodotti e utenti
```

## Database
- **utenti**: `id, username, email, password_hash, ruolo, attivo, ultimo_accesso, creato_il`
- **prodotti**: `id, nome, categoria, referente, descrizione, prezzo, quantita, disponibilita, data_uscita, data_produzione, immagine (MEDIUMBLOB), immagine_tipo, creato_il, modificato_il`

## Installazione
```bash
git clone <url-della-repo>
cd SVILUPPO_WEB
python -m venv venv
# Windows:  venv\Scripts\activate      macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # poi inserisci i dati del database
python init_db.py           # crea le tabelle e i dati di esempio
python main.py              # → http://localhost:3000
```

### Account di prova (creati da `init_db.py`)
| Ruolo | Username | Password |
|---|---|---|
| Gestore | `admin` | `Admin2026!` |
| Base | `utente` | `Utente2026!` |

## Endpoint principali
| Metodo | URL | Accesso | Descrizione |
|---|---|---|---|
| GET/POST | `/registrati`, `/login` | pubblico | Registrazione e accesso |
| GET | `/dashboard` | utenti loggati | Catalogo con ricerca e filtri |
| GET | `/gestione`, `/gestione/utenti` | gestori | Area di amministrazione |
| GET | `/api/prodotti` | utenti loggati | Elenco filtrato (JSON) |
| POST / PUT / DELETE | `/api/prodotti[/<id>]` | gestori | Crea / modifica / elimina |
| GET / POST / PUT / DELETE | `/api/utenti[/<id>]` | gestori | Gestione utenti |
| GET | `/immagine/prodotto/<id>` | pubblico | Immagine letta dal database |
