import Link from "next/link";
import styles from "../legal.module.css";

const sections = [
  ["1. Titolare e contatti", <>SanoSync è gestito da Fabio Zanda. Per richieste sulla privacy, accesso ai dati o cancellazione dell’account scrivi a <a href="mailto:info@sanosync.app">info@sanosync.app</a>.</>],
  ["2. Dati trattati", <>Trattiamo dati identificativi e di accesso, informazioni del profilo, età, genere scelto per il calcolo, altezza, peso, obiettivi, pasti, attività, preferenze e contenuti inviati alle funzioni AI. Se colleghi Oura, riceviamo soltanto i dati compresi nelle autorizzazioni che concedi.</>],
  ["3. Finalità e basi giuridiche", <>Usiamo i dati per autenticarti, calcolare il piano, registrare le attività, personalizzare l’esperienza, proteggere il servizio e rispondere alle richieste. Il trattamento è necessario per erogare il servizio; per integrazioni facoltative e dati potenzialmente relativi alla salute ci basiamo sul tuo consenso, revocabile in ogni momento.</>],
  ["4. Servizi e destinatari", <>SanoSync utilizza fornitori di autenticazione e database (Supabase), hosting (Vercel e Render), elaborazione AI (Groq e, dove abilitato, OpenAI) e integrazioni scelte dall’utente, come Oura. Condividiamo solo quanto necessario e non vendiamo dati personali.</>],
  ["5. Conservazione e sicurezza", <>Conserviamo i dati finché l’account è attivo o per il tempo necessario a erogare il servizio e adempiere obblighi di legge. Applichiamo misure tecniche e organizzative ragionevoli, ma nessun sistema connesso a Internet può garantire sicurezza assoluta.</>],
  ["6. Trasferimenti internazionali", <>Alcuni fornitori possono trattare dati fuori dallo Spazio Economico Europeo. In tali casi usiamo strumenti riconosciuti dalla normativa applicabile, come decisioni di adeguatezza o clausole contrattuali standard.</>],
  ["7. I tuoi diritti", <>Puoi chiedere accesso, rettifica, cancellazione, limitazione, portabilità o opposizione e revocare il consenso. Puoi inoltre presentare reclamo all’autorità di controllo competente. Per iniziare una richiesta usa il contatto indicato sopra.</>],
  ["8. Minori", <>SanoSync non è destinato a minori di 18 anni e non raccoglie consapevolmente dati di minori.</>],
  ["9. Aggiornamenti", <>Potremo aggiornare questa informativa per riflettere modifiche al servizio o alla normativa. La versione pubblicata indica sempre la data dell’ultimo aggiornamento.</>],
];

export default function PrivacyPage() {
  return <main className={styles.page}>
    <header className={styles.header}>
      <Link href="/" className={styles.brand}>SanoSync</Link>
      <p className={styles.kicker}>Documenti legali</p><h1>Privacy Policy</h1>
      <p className={styles.lead}>Come raccogliamo, utilizziamo e proteggiamo i dati personali necessari a offrirti SanoSync.</p>
      <p className={styles.updated}>Ultimo aggiornamento: 2 settembre 2026</p>
    </header>
    <article className={styles.content}>{sections.map(([title, body]) => <section key={String(title)}><h2>{title}</h2><p>{body}</p></section>)}</article>
    <footer className={styles.footer}><Link href="/terms">Termini e condizioni</Link><Link href="/">Torna a SanoSync</Link></footer>
  </main>;
}
