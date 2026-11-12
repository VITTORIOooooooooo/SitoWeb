/* =====================================================================
   gestione_prodotti.js — CRUD dei prodotti (solo gestori)
   CREATE  → POST   /api/prodotti
   READ    → GET    /api/prodotti?filtri
   UPDATE  → PUT    /api/prodotti/<id>
   DELETE  → DELETE /api/prodotti/<id>
   ===================================================================== */
let prodotti = [];
let inModifica = null;   // null = sto creando, altrimenti il prodotto che sto modificando

const dialogo = document.getElementById('dialogo-prodotto');
const form = document.getElementById('form-prodotto');

async function carica() {
    try {
        const risposta = await api('/api/prodotti?' + Filtri.query());
        prodotti = risposta.dati;
        document.getElementById('conteggio').textContent = `${prodotti.length} prodotti`;
        mostraTabella();
    } catch (e) {
        document.getElementById('conteggio').textContent = 'Errore: ' + e.message;
    }
}

function mostraTabella() {
    const tbody = document.getElementById('tabella');
    const q = Filtri.termine();
    tbody.replaceChildren();
    if (prodotti.length === 0) {
        tbody.append(el('tr', {}, el('td', { colspan: 10, classe: 'vuoto', testo: 'Nessun prodotto trovato.' })));
        return;
    }
    for (const p of prodotti) {
        tbody.append(el('tr', {},
            el('td', {}, evidenzia(p.id, q)),
            el('td', {}, el('strong', {}, evidenzia(p.nome, q))),
            el('td', {}, evidenzia(p.categoria, q)),
            el('td', {}, evidenzia(p.referente, q)),
            el('td', { testo: euro(p.prezzo) }),
            el('td', { testo: p.quantita }),
            el('td', {}, el('span', { classe: 'badge ' + classeDisponibilita(p.disponibilita), testo: p.disponibilita })),
            el('td', { testo: dataIt(p.data_uscita) }),
            el('td', { testo: dataIt(p.modificato_il.split(' ')[0]), title: dataIt(p.modificato_il) }),
            el('td', {}, el('div', { classe: 'azioni' },
                el('button', { classe: 'btn piccolo secondario', title: 'Modifica', 'aria-label': 'Modifica', onclick: () => apriForm(p) }, '✏️'),
                el('button', { classe: 'btn piccolo pericolo', title: 'Elimina', 'aria-label': 'Elimina', onclick: () => elimina(p) }, '🗑'),
            )),
        ));
    }
}

/* ---------- Form crea / modifica ---------- */
function apriForm(p = null) {
    inModifica = p;
    form.reset();
    document.getElementById('errore-form').textContent = '';
    document.getElementById('form-titolo').textContent = p ? `Modifica «${p.nome}»` : 'Nuovo prodotto';

    if (p) {
        form.nome.value = p.nome;
        form.categoria.value = p.categoria;
        form.referente.value = p.referente;
        form.disponibilita.value = p.disponibilita;
        form.prezzo.value = p.prezzo;
        form.quantita.value = p.quantita;
        form.data_produzione.value = p.data_produzione;
        form.data_uscita.value = p.data_uscita;
        form.descrizione.value = p.descrizione || '';
    }
    dialogo.showModal();
}

form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!form.reportValidity()) return;          // controlli base del browser
    const dati = new FormData(form);

    const bottone = document.getElementById('salva');
    bottone.disabled = true;
    try {
        const risposta = inModifica
            ? await api('/api/prodotti/' + inModifica.id, 'PUT', dati)
            : await api('/api/prodotti', 'POST', dati);
        dialogo.close();
        toast(risposta.messaggio);
        carica();
    } catch (err) {
        // i controlli "veri" li fa il server: qui mostriamo il suo messaggio
        document.getElementById('errore-form').textContent = err.message;
    } finally {
        bottone.disabled = false;
    }
});

/* ---------- Eliminazione ---------- */
async function elimina(p) {
    const ok = await conferma(`Eliminare «${p.nome}»?`, `Il prodotto #${p.id} verrà cancellato dal database. L'operazione non si può annullare.`);
    if (!ok) return;
    try {
        const risposta = await api('/api/prodotti/' + p.id, 'DELETE');
        toast(risposta.messaggio);
        carica();
    } catch (e) {
        toast(e.message, 'errore');
    }
}

document.getElementById('nuovo-prodotto').addEventListener('click', () => apriForm());
Filtri.init(carica);
carica();
