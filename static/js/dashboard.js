/* =====================================================================
   dashboard.js — catalogo prodotti (visibile a tutti gli utenti loggati)
   Da qui si possono selezionare i prodotti e aggiungerli al carrello.
   ===================================================================== */
let prodotti = [];
let vista = 'griglia';
const selezionati = new Set();        // id dei prodotti selezionati
try { vista = localStorage.getItem('vista') || 'griglia'; } catch {}

const acquistabile = p => p.disponibilita === 'Disponibile' && p.quantita > 0;

async function carica() {
    const inizio = performance.now();
    try {
        const risposta = await api('/api/prodotti?' + Filtri.query());
        prodotti = risposta.dati;
        const ms = Math.round(performance.now() - inizio);
        document.getElementById('conteggio').textContent =
            `${prodotti.length} prodott${prodotti.length === 1 ? 'o' : 'i'} trovat${prodotti.length === 1 ? 'o' : 'i'} · risposta del database in ${ms} ms`;
        mostra();
        aggiornaRiassunto();
    } catch (e) {
        document.getElementById('conteggio').textContent = 'Errore: ' + e.message;
    }
}

function mostra() {
    document.getElementById('griglia').classList.toggle('nascosto', vista !== 'griglia');
    document.getElementById('contenitore-tabella').classList.toggle('nascosto', vista !== 'tabella');
    document.querySelectorAll('[data-vista]').forEach(b => b.classList.toggle('attivo', b.dataset.vista === vista));
    vista === 'griglia' ? mostraGriglia() : mostraTabella();
    aggiornaSelezione();
}

function foto(p, classe = '') {
    return p.immagine_url
        ? el('img', { src: p.immagine_url, alt: p.nome, loading: 'lazy', classe })
        : el('div', { classe: 'senza-foto ' + classe, testo: '📦' });
}

function badge(p) {
    return el('span', { classe: 'badge ' + classeDisponibilita(p.disponibilita), testo: p.disponibilita });
}

/* ---------- Selezione dei prodotti ---------- */
function casellaSelezione(p) {
    return el('input', {
        type: 'checkbox', classe: 'seleziona', 'data-id': p.id,
        checked: selezionati.has(p.id), disabled: !acquistabile(p),
        title: acquistabile(p) ? 'Seleziona' : 'Non acquistabile', 'aria-label': 'Seleziona ' + p.nome,
        onclick: e => e.stopPropagation(),
        onchange: e => {
            e.target.checked ? selezionati.add(p.id) : selezionati.delete(p.id);
            aggiornaSelezione();
        },
    });
}

function aggiornaSelezione() {
    // tolgo dalla selezione i prodotti che non sono più visibili (es. dopo un filtro)
    const visibili = new Set(prodotti.filter(acquistabile).map(p => p.id));
    for (const id of [...selezionati]) if (!visibili.has(id)) selezionati.delete(id);

    document.querySelectorAll('input.seleziona').forEach(c => {
        c.checked = selezionati.has(Number(c.dataset.id));
        c.closest('.prodotto, tr')?.classList.toggle('selezionato', c.checked);
    });
    document.getElementById('n-selezionati').textContent = selezionati.size;
    document.getElementById('barra-selezione').classList.toggle('visibile', selezionati.size > 0);
    const tutti = document.getElementById('seleziona-tutti');
    tutti.checked = visibili.size > 0 && selezionati.size === visibili.size;
}

function bottoneCarrello(p, piccolo = true) {
    return el('button', {
        classe: 'btn ' + (piccolo ? 'piccolo ' : '') + 'aggiungi', disabled: !acquistabile(p),
        title: acquistabile(p) ? 'Aggiungi al carrello' : 'Non acquistabile',
        onclick: async e => {
            e.stopPropagation();
            const b = e.currentTarget;
            b.disabled = true;
            if (await aggiungiAlCarrello([p.id])) { b.textContent = '✓ Aggiunto'; setTimeout(() => { b.textContent = '🛒 Aggiungi'; }, 1500); }
            b.disabled = false;
        },
    }, acquistabile(p) ? '🛒 Aggiungi' : (p.disponibilita === 'In arrivo' ? 'In arrivo' : 'Esaurito'));
}

/* ---------- Griglia ---------- */
function mostraGriglia() {
    const griglia = document.getElementById('griglia');
    const q = Filtri.termine();
    griglia.replaceChildren();
    if (prodotti.length === 0) {
        griglia.append(el('p', { classe: 'card vuoto', style: 'grid-column:1/-1', testo: 'Nessun prodotto corrisponde alla ricerca.' }));
        return;
    }
    for (const p of prodotti) {
        griglia.append(el('article', { classe: 'card prodotto' + (acquistabile(p) ? '' : ' non-acquistabile') },
            el('button', { classe: 'apri', 'aria-label': 'Dettagli di ' + p.nome, onclick: () => dettaglio(p) },
                el('div', { classe: 'foto' }, foto(p), badge(p)),
                el('div', { classe: 'corpo' },
                    el('span', { classe: 'categoria' }, evidenzia(p.categoria, q)),
                    el('h3', {}, evidenzia(p.nome, q)),
                    el('span', { classe: 'prezzo', testo: euro(p.prezzo) }),
                    el('span', { classe: 'meta' }, '👤 ', evidenzia(p.referente, q), ` · ${p.quantita} pz`),
                ),
            ),
            el('label', { classe: 'angolo-selezione', title: 'Seleziona' }, casellaSelezione(p)),
            el('div', { classe: 'piede-card' }, bottoneCarrello(p)),
        ));
    }
}

/* ---------- Tabella ---------- */
function mostraTabella() {
    const tbody = document.getElementById('tabella');
    const q = Filtri.termine();
    tbody.replaceChildren();
    if (prodotti.length === 0) {
        tbody.append(el('tr', {}, el('td', { colspan: 12, classe: 'vuoto', testo: 'Nessun prodotto corrisponde alla ricerca.' })));
        return;
    }
    for (const p of prodotti) {
        tbody.append(el('tr', { style: 'cursor:pointer', onclick: () => dettaglio(p) },
            el('td', {}, casellaSelezione(p)),
            el('td', { classe: 'miniatura' }, foto(p)),
            el('td', {}, evidenzia(p.id, q)),
            el('td', {}, el('strong', {}, evidenzia(p.nome, q))),
            el('td', {}, evidenzia(p.categoria, q)),
            el('td', {}, evidenzia(p.referente, q)),
            el('td', { testo: euro(p.prezzo) }),
            el('td', { testo: p.quantita }),
            el('td', {}, badge(p)),
            el('td', { testo: dataIt(p.data_uscita) }),
            el('td', { testo: dataIt(p.data_produzione) }),
            el('td', {}, bottoneCarrello(p)),
        ));
    }
}

function aggiornaRiassunto() {
    const conta = d => prodotti.filter(p => p.disponibilita === d).length;
    const somma = prodotti.reduce((t, p) => t + p.prezzo, 0);
    const valore = prodotti.reduce((t, p) => t + p.prezzo * p.quantita, 0);
    document.getElementById('stat-totale').textContent = prodotti.length;
    document.getElementById('stat-disp').textContent = conta('Disponibile');
    document.getElementById('stat-arrivo').textContent = conta('In arrivo');
    document.getElementById('stat-esau').textContent = conta('Esaurito');
    document.getElementById('stat-medio').textContent = prodotti.length ? euro(somma / prodotti.length) : '—';
    document.getElementById('stat-valore').textContent = euro(valore);
}

/* Grafico a barre: i numeri arrivano da una query con GROUP BY categoria */
async function caricaGrafico() {
    try {
        const { dati } = await api('/api/statistiche');
        const barre = document.getElementById('barre');
        const massimo = Math.max(...dati.per_categoria.map(c => c.numero), 1);
        document.getElementById('stat-su').textContent = `su ${dati.totali.prodotti} totali`;
        barre.replaceChildren(...dati.per_categoria.map(c => {
            const riempimento = el('div', { classe: 'riempimento' });
            requestAnimationFrame(() => { riempimento.style.width = (c.numero / massimo * 100) + '%'; });
            return el('div', { classe: 'barra' },
                el('button', { testo: c.categoria, title: 'Filtra: ' + c.categoria, onclick: () => Filtri.impostaCategoria(c.categoria, carica) }),
                el('div', { classe: 'traccia' }, riempimento),
                el('strong', { testo: c.numero }),
            );
        }));
    } catch (e) { /* il grafico è un extra: se fallisce la pagina funziona lo stesso */ }
}

/* ---------- Dettaglio con scelta della quantità ---------- */
function dettaglio(p) {
    const massimo = Math.min(p.quantita, 10);
    const quantita = el('input', { type: 'number', min: 1, max: massimo, value: 1, 'aria-label': 'Quantità', classe: 'campo-quantita' });
    const acquisto = acquistabile(p)
        ? el('div', { classe: 'acquisto' },
            quantita,
            el('button', { classe: 'btn', onclick: async () => {
                const n = Math.max(1, Math.min(massimo, parseInt(quantita.value) || 1));
                if (await aggiungiAlCarrello([p.id], n)) document.getElementById('dialogo-dettaglio').close();
            } }, '🛒 Aggiungi al carrello'))
        : el('p', { classe: 'muto', testo: p.disponibilita === 'In arrivo' ? 'Prodotto in arrivo: non ancora acquistabile.' : 'Prodotto esaurito.' });

    document.getElementById('dettaglio-titolo').textContent = p.nome;
    document.getElementById('dettaglio-corpo').replaceChildren(
        el('div', { classe: 'dettaglio' },
            foto(p),
            el('div', {},
                el('span', { classe: 'muto', testo: p.categoria.toUpperCase() }),
                el('div', { classe: 'prezzo', style: 'font-size:30px;font-weight:900;color:var(--primario)', testo: euro(p.prezzo) }),
                badge(p),
                el('p', { testo: p.descrizione || 'Nessuna descrizione.' }),
                acquisto,
                el('dl', {},
                    el('dt', { testo: 'Codice' }), el('dd', { testo: '#' + p.id }),
                    el('dt', { testo: 'Referente' }), el('dd', { testo: p.referente }),
                    el('dt', { testo: 'In magazzino' }), el('dd', { testo: p.quantita + ' pezzi' }),
                    el('dt', { testo: 'Produzione' }), el('dd', { testo: dataIt(p.data_produzione) }),
                    el('dt', { testo: 'Uscita' }), el('dd', { testo: dataIt(p.data_uscita) }),
                    el('dt', { testo: 'Ultima modifica' }), el('dd', { testo: dataIt(p.modificato_il) }),
                ),
            ),
        ),
    );
    document.getElementById('dialogo-dettaglio').showModal();
}

/* ---------- Eventi ---------- */
document.querySelectorAll('[data-vista]').forEach(b => b.addEventListener('click', () => {
    vista = b.dataset.vista;
    try { localStorage.setItem('vista', vista); } catch {}
    mostra();
}));

document.getElementById('seleziona-tutti').addEventListener('change', e => {
    prodotti.filter(acquistabile).forEach(p => e.target.checked ? selezionati.add(p.id) : selezionati.delete(p.id));
    aggiornaSelezione();
});
document.getElementById('annulla-selezione').addEventListener('click', () => { selezionati.clear(); aggiornaSelezione(); });
document.getElementById('aggiungi-selezionati').addEventListener('click', async e => {
    const bottone = e.currentTarget;     // va salvato subito: dopo un await currentTarget diventa null
    bottone.disabled = true;
    if (await aggiungiAlCarrello([...selezionati])) { selezionati.clear(); aggiornaSelezione(); }
    bottone.disabled = false;
});

Filtri.init(carica);
carica();
caricaGrafico();
