/* =====================================================================
   gestione_utenti.js — gestione degli utenti (solo gestori)
   ===================================================================== */
let mioId = null;

async function carica() {
    const parametri = new URLSearchParams({
        q: document.getElementById('u-cerca').value.trim(),
        ruolo: document.getElementById('u-ruolo').value,
    });
    try {
        const risposta = await api('/api/utenti?' + parametri);
        mioId = risposta.io;
        document.getElementById('conteggio').textContent = `${risposta.dati.length} utenti`;
        mostra(risposta.dati);
    } catch (e) {
        document.getElementById('conteggio').textContent = 'Errore: ' + e.message;
    }
}

function mostra(utenti) {
    const tbody = document.getElementById('tabella');
    tbody.replaceChildren();
    if (utenti.length === 0) {
        tbody.append(el('tr', {}, el('td', { colspan: 8, classe: 'vuoto', testo: 'Nessun utente trovato.' })));
        return;
    }
    for (const u of utenti) {
        const sonoIo = u.id === mioId;

        const selectRuolo = el('select', { disabled: sonoIo, style: 'width:auto;padding:6px 10px',
            onchange: e => aggiorna(u, { ruolo: e.target.value }) },
            el('option', { value: 'base', selected: u.ruolo === 'base', testo: 'Base' }),
            el('option', { value: 'gestore', selected: u.ruolo === 'gestore', testo: 'Gestore' }),
        );
        const interruttore = el('label', { classe: 'switch', title: u.attivo ? 'Attivo' : 'Non attivo' },
            el('input', { type: 'checkbox', checked: !!u.attivo, disabled: sonoIo,
                onchange: e => aggiorna(u, { attivo: e.target.checked ? '1' : '0' }) }),
            el('span'),
        );

        tbody.append(el('tr', { classe: sonoIo ? 'io' : '' },
            el('td', { testo: u.id }),
            el('td', {}, el('div', { style: 'display:flex;gap:10px;align-items:center' },
                el('span', { classe: 'avatar', testo: u.username.slice(0, 2) }),
                el('strong', { testo: u.username + (sonoIo ? ' (tu)' : '') }))),
            el('td', { testo: u.email }),
            el('td', {}, selectRuolo),
            el('td', {}, interruttore, ' ', u.attivo ? '' : el('span', { classe: 'badge esaurito', testo: 'disattivato' })),
            el('td', { testo: dataIt(u.ultimo_accesso) }),
            el('td', { testo: dataIt(u.creato_il) }),
            el('td', {}, el('button', { classe: 'btn piccolo pericolo', disabled: sonoIo, onclick: () => elimina(u) }, '🗑 Elimina')),
        ));
    }
}

async function aggiorna(u, modifiche) {
    const dati = new FormData();
    dati.set('ruolo', modifiche.ruolo ?? u.ruolo);
    dati.set('attivo', modifiche.attivo ?? (u.attivo ? '1' : '0'));
    try {
        const risposta = await api('/api/utenti/' + u.id, 'PUT', dati);
        toast(`${u.username}: ${risposta.messaggio.toLowerCase()}`);
    } catch (e) {
        toast(e.message, 'errore');
    }
    carica();
}

async function elimina(u) {
    if (!await conferma(`Eliminare «${u.username}»?`, 'L\'account verrà cancellato definitivamente dal database.')) return;
    try {
        const risposta = await api('/api/utenti/' + u.id, 'DELETE');
        toast(risposta.messaggio);
        carica();
    } catch (e) { toast(e.message, 'errore'); }
}

/* Nuovo utente */
const dialogo = document.getElementById('dialogo-utente');
const form = document.getElementById('form-utente');
document.getElementById('nuovo-utente').addEventListener('click', () => {
    form.reset();
    document.getElementById('errore-utente').textContent = '';
    dialogo.showModal();
});
form.addEventListener('submit', async e => {
    e.preventDefault();
    try {
        const risposta = await api('/api/utenti', 'POST', new FormData(form));
        dialogo.close();
        toast(risposta.messaggio);
        carica();
    } catch (err) {
        document.getElementById('errore-utente').textContent = err.message;
    }
});

document.getElementById('u-cerca').addEventListener('input', ritarda(carica));
document.getElementById('u-ruolo').addEventListener('change', carica);
carica();
