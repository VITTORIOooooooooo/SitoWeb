/* =====================================================================
   dashboard.js — catalogo prodotti (visibile a tutti gli utenti loggati)
   ===================================================================== */
let prodotti = [];
let vista = 'griglia';
try { vista = localStorage.getItem('vista') || 'griglia'; } catch {}

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
}

function foto(p, classe = '') {
    return p.immagine_url
        ? el('img', { src: p.immagine_url, alt: p.nome, loading: 'lazy', classe })
        : el('div', { classe: 'senza-foto ' + classe, testo: '📦' });
}

function badge(p) {
    return el('span', { classe: 'badge ' + classeDisponibilita(p.disponibilita), testo: p.disponibilita });
}

function mostraGriglia() {
    const griglia = document.getElementById('griglia');
    const q = Filtri.termine();
    griglia.replaceChildren();
    if (prodotti.length === 0) {
        griglia.append(el('p', { classe: 'card vuoto', style: 'grid-column:1/-1', testo: 'Nessun prodotto corrisponde alla ricerca.' }));
        return;
    }
    for (const p of prodotti) {
        griglia.append(el('button', { classe: 'card prodotto', onclick: () => dettaglio(p) },
            el('div', { classe: 'foto' }, foto(p), badge(p)),
            el('div', { classe: 'corpo' },
                el('span', { classe: 'categoria' }, evidenzia(p.categoria, q)),
                el('h3', {}, evidenzia(p.nome, q)),
                el('span', { classe: 'prezzo', testo: euro(p.prezzo) }),
                el('span', { classe: 'meta' }, '👤 ', evidenzia(p.referente, q), ` · ${p.quantita} pz`),
            ),
        ));
    }
}

function mostraTabella() {
    const tbody = document.getElementById('tabella');
    const q = Filtri.termine();
    tbody.replaceChildren();
    if (prodotti.length === 0) {
        tbody.append(el('tr', {}, el('td', { colspan: 10, classe: 'vuoto', testo: 'Nessun prodotto corrisponde alla ricerca.' })));
        return;
    }
    for (const p of prodotti) {
        tbody.append(el('tr', { style: 'cursor:pointer', onclick: () => dettaglio(p) },
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

function dettaglio(p) {
    document.getElementById('dettaglio-titolo').textContent = p.nome;
    document.getElementById('dettaglio-corpo').replaceChildren(
        el('div', { classe: 'dettaglio' },
            foto(p),
            el('div', {},
                el('span', { classe: 'muto', testo: p.categoria.toUpperCase() }),
                el('div', { classe: 'prezzo', style: 'font-size:30px;font-weight:900;color:var(--primario)', testo: euro(p.prezzo) }),
                badge(p),
                el('p', { testo: p.descrizione || 'Nessuna descrizione.' }),
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

document.querySelectorAll('[data-vista]').forEach(b => b.addEventListener('click', () => {
    vista = b.dataset.vista;
    try { localStorage.setItem('vista', vista); } catch {}
    mostra();
}));

Filtri.init(carica);
carica();
caricaGrafico();
