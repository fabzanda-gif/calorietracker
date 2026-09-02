import Link from "next/link";
import styles from "../legal.module.css";

const sections = [
  ["1. Accettazione e requisiti", <>Creando un account o utilizzando SanoSync accetti questi Termini e la Privacy Policy. Devi avere almeno 18 anni, fornire informazioni accurate e mantenere sicure le credenziali.</>],
  ["2. Il servizio", <>SanoSync offre strumenti per registrare alimentazione, peso e attività, organizzare obiettivi e visualizzare stime personalizzate. Funzioni, disponibilità e integrazioni possono cambiare nel tempo.</>],
  ["3. Non è un servizio medico", <>Calorie, BMR, nutrienti, suggerimenti e contenuti generati sono stime informative e non costituiscono diagnosi, terapia o consiglio medico. Non usare SanoSync per emergenze o decisioni sanitarie. Consulta un professionista prima di cambiare dieta o attività, soprattutto in presenza di patologie, gravidanza o disturbi alimentari.</>],
  ["4. Responsabilità dell’utente", <>Sei responsabile dei dati inseriti, dell’uso delle stime e delle autorizzazioni concesse. È vietato usare il servizio illegalmente, tentare accessi non autorizzati o interferire con la sicurezza della piattaforma.</>],
  ["5. Intelligenza artificiale", <>Alcune funzioni interpretano testi o immagini tramite sistemi AI. I risultati possono essere incompleti o inesatti: controlla sempre ingredienti, quantità, allergeni e valori nutrizionali.</>],
  ["6. Servizi di terze parti", <>Collegamenti come Oura e i servizi di autenticazione o hosting restano soggetti ai termini dei rispettivi fornitori. SanoSync non controlla la loro disponibilità.</>],
  ["7. Disponibilità e responsabilità", <>Il servizio è fornito secondo disponibilità. Nei limiti consentiti dalla legge non garantiamo assenza di errori o continuità. Restano impregiudicati i diritti inderogabili riconosciuti al consumatore.</>],
  ["8. Sospensione e chiusura", <>Puoi smettere di usare il servizio e richiedere la cancellazione dell’account. Possiamo sospendere account utilizzati in violazione di questi Termini, con misure proporzionate.</>],
  ["9. Modifiche e contatti", <>Le modifiche sostanziali saranno pubblicate con una nuova data di aggiornamento. Per domande scrivi a <a href="mailto:fab.zanda@gmail.com">fab.zanda@gmail.com</a>.</>],
];

export default function TermsPage() {
  return <main className={styles.page}>
    <header className={styles.header}>
      <Link href="/" className={styles.brand}>SanoSync</Link>
      <p className={styles.kicker}>Documenti legali</p><h1>Termini e condizioni</h1>
      <p className={styles.lead}>Le regole essenziali per utilizzare SanoSync in modo consapevole.</p>
      <p className={styles.updated}>Ultimo aggiornamento: 2 settembre 2026</p>
    </header>
    <article className={styles.content}>{sections.map(([title, body], index) => <section className={index === 2 ? styles.notice : undefined} key={String(title)}><h2>{title}</h2><p>{body}</p></section>)}</article>
    <footer className={styles.footer}><Link href="/privacy">Privacy Policy</Link><Link href="/">Torna a SanoSync</Link></footer>
  </main>;
}
