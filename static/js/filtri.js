/* =====================================================================
   filtri.js — legge ricerca e filtri e costruisce la query string per /api/prodotti.
   La ricerca vera e propria la fa il DATABASE (WHERE ... LIKE ... nella query SQL),
   qui prepariamo solo i parametri da mandare al server.
   ===================================================================== */
const Filtri = {
    campi: ['q', 'categoria', 'prezzo_min', 'prezzo_max', 'uscita_da', 'uscita_a', 'ordina', 'direzione'],
    disponibilita: '',

    valore(id) { return document.getElementById(id).value.trim(); },

    /* Restituisce es. "q=laptop&categoria=Computer&ordina=prezzo&direzione=desc" */
    query() {
        const parametri = new URLSearchParams();
        for (const id of this.campi) {
            const v = this.valore(id);
            if (v !== '') parametri.set(id, v);
        }
        if (this.disponibilita) parametri.set('disponibilita', this.disponibilita);
        return parametri.toString();
    },

    termine() { return this.valore('q'); },

    init(quandoCambia) {
        const aggiorna = ritarda(quandoCambia, 250);
        for (const id of this.campi) {
            document.getElementById(id).addEventListener('input', aggiorna);
        }
        // chip della disponibilità
        document.querySelectorAll('#chips-disponibilita .chip').forEach(chip => {
            chip.addEventListener('click', () => {
                document.querySelectorAll('#chips-disponibilita .chip').forEach(c => c.classList.remove('attivo'));
                chip.classList.add('attivo');
                this.disponibilita = chip.dataset.valore;
                quandoCambia();
            });
        });
        // intestazioni della tabella cliccabili per ordinare
        document.querySelectorAll('[data-ordina]').forEach(th => {
            th.addEventListener('click', () => {
                const ordina = document.getElementById('ordina');
                const direzione = document.getElementById('direzione');
                if (ordina.value === th.dataset.ordina) {
                    direzione.value = direzione.value === 'asc' ? 'desc' : 'asc';
                } else {
                    ordina.value = th.dataset.ordina;
                    direzione.value = 'asc';
                }
                quandoCambia();
            });
        });
        document.getElementById('reset-filtri').addEventListener('click', () => {
            for (const id of this.campi) document.getElementById(id).value = '';
            document.getElementById('ordina').value = 'id';
            document.getElementById('direzione').value = 'asc';
            document.querySelector('#chips-disponibilita .chip').click();
        });
    },

    impostaCategoria(categoria, quandoCambia) {
        document.getElementById('categoria').value = categoria;
        document.querySelector('.filtri-avanzati').open = true;
        quandoCambia();
    },
};
