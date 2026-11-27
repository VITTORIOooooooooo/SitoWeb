/* =====================================================================
   carrello.js — pagina del carrello
   GET    /api/carrello          → contenuto e totali (calcolati dal server)
   PUT    /api/carrello/<id>     → cambia la quantità
   DELETE /api/carrello/<id>     → rimuove un prodotto
   DELETE /api/carrello          → svuota
   POST   /api/ordini            → conferma l'ordine
   ===================================================================== */

async function carica() {
    try {
        const r = await api('/api/carrello');
        mostra(r.dati);
    } catch (e) {
        document.getElementById('righe-carrello').replaceChildren(el('p', { classe: 'muto', testo: 'Errore: ' + e.message }));
    }
}

function mostra(c) {
    const contenitore = document.getElementById('righe-carrello');
    aggiornaBadgeCarrello(c.pezzi);
    document.getElementById('pezzi-carrello').textContent = c.pezzi ? `(${c.pezzi} pezz${c.pezzi === 1 ? 'o' : 'i'})` : '';
    document.getElementById('svuota').classList.toggle('nascosto', c.righe.length === 0);

    if (c.righe.length === 0) {
        contenitore.replaceChildren(el('div', { classe: 'carrello-vuoto' },
            el('div', { style: 'font-size:52px', testo: '🛒' }),
            el('p', { testo: 'Il carrello è vuoto.' }),
            el('a', { classe: 'btn', href: '/dashboard', testo: 'Vai al catalogo' })));
    } else {
        contenitore.replaceChildren(...c.righe.map(riga));
    }

    document.getElementById('r-subtotale').textContent = euro(c.subtotale);
    document.getElementById('r-spedizione').textContent = c.righe.length ? (c.spedizione ? euro(c.spedizione) : 'Gratis') : '—';
    document.getElementById('r-totale').textContent = euro(c.totale);
    const mancano = c.soglia - c.subtotale;
    document.getElementById('nota-spedizione').textContent = c.righe.length && mancano > 0
        ? `Aggiungi ancora ${euro(mancano)} per la spedizione gratuita.` : (c.righe.length ? '✅ Hai diritto alla spedizione gratuita.' : '');
    document.getElementById('conferma-ordine').disabled = c.righe.length === 0 || c.righe.some(r => problema(r));
}

/* Avviso se nel frattempo il prodotto è finito o ce ne sono meno pezzi */
function problema(r) {
    if (r.disponibilita !== 'Disponibile') return 'Non più disponibile: rimuovilo per continuare.';
    if (r.quantita > r.in_magazzino) return `Ne sono rimasti solo ${r.in_magazzino}: riduci la quantità.`;
    return null;
}

function riga(r) {
    const massimo = Math.min(r.in_magazzino, 10);
    const avviso = problema(r);
    return el('div', { classe: 'riga-carrello' + (avviso ? ' con-problema' : '') },
        r.immagine_url ? el('img', { src: r.immagine_url, alt: '' }) : el('div', { classe: 'senza-foto', testo: '📦' }),
        el('div', { classe: 'info' },
            el('span', { classe: 'muto', style: 'font-size:12px', testo: r.categoria.toUpperCase() }),
            el('strong', { testo: r.nome }),
            el('span', { classe: 'muto', testo: euro(r.prezzo) + ' cad.' }),
            avviso ? el('span', { classe: 'avviso', testo: '⚠️ ' + avviso }) : null),
        el('div', { classe: 'stepper', role: 'group', 'aria-label': 'Quantità di ' + r.nome },
            el('button', { 'aria-label': 'Diminuisci', disabled: r.quantita <= 1, onclick: () => cambia(r, r.quantita - 1) }, '−'),
            el('span', { testo: r.quantita }),
            el('button', { 'aria-label': 'Aumenta', disabled: r.quantita >= massimo, onclick: () => cambia(r, r.quantita + 1) }, '+')),
        el('strong', { classe: 'subtotale', testo: euro(r.subtotale) }),
        el('button', { classe: 'btn piccolo pericolo', title: 'Rimuovi', 'aria-label': 'Rimuovi ' + r.nome, onclick: () => rimuovi(r) }, '🗑'),
    );
}

async function cambia(r, quantita) {
    const dati = new FormData();
    dati.set('quantita', quantita);
    try { mostra((await api('/api/carrello/' + r.prodotto_id, 'PUT', dati)).dati); }
    catch (e) { toast(e.message, 'errore'); }
}

async function rimuovi(r) {
    try {
        const risposta = await api('/api/carrello/' + r.prodotto_id, 'DELETE');
        mostra(risposta.dati);
        toast(`«${r.nome}» rimosso dal carrello`);
    } catch (e) { toast(e.message, 'errore'); }
}

document.getElementById('svuota').addEventListener('click', async () => {
    if (!await conferma('Svuotare il carrello?', 'Tutti i prodotti verranno tolti dal carrello.', 'Svuota')) return;
    try { mostra((await api('/api/carrello', 'DELETE')).dati); }
    catch (e) { toast(e.message, 'errore'); }
});

document.getElementById('conferma-ordine').addEventListener('click', async e => {
    const bottone = e.currentTarget;     // va salvato subito: dopo un await currentTarget diventa null
    const totale = document.getElementById('r-totale').textContent;
    if (!await conferma('Confermare l\'ordine?', `Totale da pagare: ${totale}. I pezzi verranno scalati dal magazzino.`, 'Conferma ordine')) return;
    bottone.disabled = true;
    try {
        const r = await api('/api/ordini', 'POST');
        toast(r.messaggio);
        setTimeout(() => location.reload(), 900);     // ricarico per vedere l'ordine nello storico
    } catch (err) {
        toast(err.message, 'errore');
        carica();
    }
});

carica();
