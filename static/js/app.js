/* =====================================================================
   app.js — funzioni JavaScript comuni a tutte le pagine
   ===================================================================== */

const CSRF = document.querySelector('meta[name="csrf-token"]').content;

/* ---------- Tema chiaro / scuro ---------- */
function cambiaTema() {
    const scuro = document.documentElement.dataset.tema === 'scuro';
    if (scuro) delete document.documentElement.dataset.tema;
    else document.documentElement.dataset.tema = 'scuro';
    try { localStorage.setItem('tema', scuro ? 'chiaro' : 'scuro'); } catch {}
}

/* ---------- Chiamate alle API del server ----------
   Invia sempre il token CSRF nell'header e trasforma gli errori in eccezioni. */
async function api(url, metodo = 'GET', corpo = null) {
    const opzioni = { method: metodo, headers: { 'X-CSRF-Token': CSRF } };
    if (corpo) opzioni.body = corpo;            // FormData (testo + file)

    const r = await fetch(url, opzioni);
    let risposta;
    try { risposta = await r.json(); }
    catch { risposta = { successo: false, errore: 'Risposta non valida dal server' }; }

    if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); }
    if (!r.ok) throw new Error(risposta.errore || 'Errore ' + r.status);
    return risposta;
}

/* ---------- Creazione sicura di elementi HTML ----------
   Usiamo textContent e non innerHTML: se un utente scrive <script> nel nome
   di un prodotto, viene mostrato come testo e non eseguito (protezione XSS). */
function el(tag, attributi = {}, ...figli) {
    const nodo = document.createElement(tag);
    for (const [chiave, valore] of Object.entries(attributi)) {
        if (valore === null || valore === undefined || valore === false) continue;
        if (chiave === 'testo') nodo.textContent = valore;
        else if (chiave.startsWith('on')) nodo.addEventListener(chiave.slice(2), valore);
        else nodo.setAttribute(chiave === 'classe' ? 'class' : chiave, valore === true ? '' : valore);
    }
    for (const figlio of figli.flat()) {
        if (figlio === null || figlio === undefined || figlio === false) continue;
        nodo.append(figlio instanceof Node ? figlio : document.createTextNode(String(figlio)));
    }
    return nodo;
}

/* Evidenzia (con <mark>) le parti di testo che corrispondono alla ricerca */
function evidenzia(testo, termine) {
    const frammento = document.createDocumentFragment();
    testo = String(testo ?? '');
    if (!termine) { frammento.append(testo); return frammento; }
    const sicuro = termine.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    testo.split(new RegExp('(' + sicuro + ')', 'gi')).forEach((parte, i) => {
        if (parte === '') return;
        frammento.append(i % 2 === 1 ? el('mark', { testo: parte }) : parte);
    });
    return frammento;
}

/* ---------- Formattazione ---------- */
const euro = n => Number(n).toLocaleString('it-IT', { style: 'currency', currency: 'EUR' });
function dataIt(iso) {
    if (!iso) return '—';
    const [data, ora] = iso.split(' ');
    const [a, m, g] = data.split('-');
    return `${g}/${m}/${a}` + (ora ? ' ' + ora : '');
}
function classeDisponibilita(d) {
    return d === 'Disponibile' ? 'disponibile' : d === 'Esaurito' ? 'esaurito' : 'in-arrivo';
}

/* ---------- Notifiche "toast" in basso a destra ---------- */
function toast(messaggio, tipo = 'successo') {
    const t = el('div', { classe: 'toast ' + tipo, testo: messaggio });
    document.getElementById('toast-zona').append(t);
    setTimeout(() => t.remove(), 4000);
}

/* Ritarda una funzione finché l'utente non smette di scrivere (meno query al database) */
function ritarda(funzione, ms = 250) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => funzione(...args), ms); };
}

/* Chiude le finestre modali cliccando sullo sfondo scuro */
document.querySelectorAll('dialog').forEach(d =>
    d.addEventListener('click', e => { if (e.target === d) d.close(); }));

/* ---------- Campi password: occhio "mostra" + barra di robustezza ---------- */
document.querySelectorAll('[data-mostra-password]').forEach(bottone => {
    bottone.addEventListener('click', () => {
        const input = bottone.previousElementSibling;
        input.type = input.type === 'password' ? 'text' : 'password';
        bottone.textContent = input.type === 'password' ? '👁️' : '🙈';
    });
});

document.querySelectorAll('[data-robustezza]').forEach(input => {
    const box = document.getElementById(input.dataset.robustezza);
    const barra = box.querySelector('.forza span');
    const regole = {
        lunghezza: v => v.length >= 8,
        maiuscola: v => /[A-Z]/.test(v),
        minuscola: v => /[a-z]/.test(v),
        numero: v => /[0-9]/.test(v),
    };
    input.addEventListener('input', () => {
        let punti = 0;
        for (const [nome, regola] of Object.entries(regole)) {
            const ok = regola(input.value);
            box.querySelector(`[data-regola="${nome}"]`).classList.toggle('ok', ok);
            if (ok) punti++;
        }
        if (input.value.length >= 12 && /[^A-Za-z0-9]/.test(input.value)) punti++;
        const colori = ['#ef4444', '#ef4444', '#f59e0b', '#eab308', '#22c55e', '#16a34a'];
        barra.style.width = (punti / 5 * 100) + '%';
        barra.style.background = colori[punti];
    });
});
