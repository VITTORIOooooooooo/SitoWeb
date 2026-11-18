/* =====================================================================
   azienda.js — navbar della pagina azienda
   - evidenzia la sezione che si sta leggendo ("scrollspy")
   - barra di avanzamento della lettura
   - pulsante "torna su"
   - animazioni all'ingresso delle sezioni e contatori dei numeri
   ===================================================================== */
const linkNav = [...document.querySelectorAll('#nav-sezioni a')];
const sezioni = linkNav.map(a => document.querySelector(a.getAttribute('href')));

/* Scrollspy: la sezione "attiva" è l'ultima il cui inizio ha superato la navbar */
function aggiornaNav() {
    const soglia = 140;
    let attiva = 0;
    sezioni.forEach((s, i) => { if (s.getBoundingClientRect().top <= soglia) attiva = i; });
    if (sezioni[0].getBoundingClientRect().top > soglia) attiva = -1;

    linkNav.forEach((a, i) => a.classList.toggle('attivo', i === attiva));
    if (attiva >= 0) {
        // fa scorrere orizzontalmente la navbar (su telefono) per mostrare il link attivo
        const link = linkNav[attiva], ul = link.closest('ul');
        const centro = link.offsetLeft - ul.clientWidth / 2 + link.clientWidth / 2;
        if (Math.abs(ul.scrollLeft - centro) > 40) ul.scrollTo({ left: centro, behavior: 'smooth' });
    }

    const totale = document.documentElement.scrollHeight - innerHeight;
    document.getElementById('progresso').style.width = (scrollY / totale * 100) + '%';
    document.getElementById('torna-su').classList.toggle('visibile', scrollY > 700);
}

let inAttesa = false;
addEventListener('scroll', () => {
    if (inAttesa) return;
    inAttesa = true;
    requestAnimationFrame(() => { aggiornaNav(); inAttesa = false; });
}, { passive: true });
aggiornaNav();

document.getElementById('torna-su').addEventListener('click', () => scrollTo({ top: 0 }));

/* Animazione all'ingresso e contatori */
function animaContatore(nodo) {
    const fine = Number(nodo.dataset.conta);
    const suffisso = nodo.dataset.suffisso || '';
    const durata = 1200, inizio = performance.now();
    function passo(ora) {
        const t = Math.min((ora - inizio) / durata, 1);
        const valore = Math.round(fine * (1 - Math.pow(1 - t, 3)));
        nodo.textContent = valore.toLocaleString('it-IT') + suffisso;
        if (t < 1) requestAnimationFrame(passo);
    }
    requestAnimationFrame(passo);
}

const osservatore = new IntersectionObserver(voci => {
    for (const voce of voci) {
        if (!voce.isIntersecting) continue;
        voce.target.classList.add('visibile');
        voce.target.querySelectorAll('[data-conta]').forEach(animaContatore);
        osservatore.unobserve(voce.target);
    }
}, { threshold: 0.15 });
document.querySelectorAll('.rivela').forEach(n => osservatore.observe(n));
