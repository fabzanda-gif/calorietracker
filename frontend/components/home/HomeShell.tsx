import styles from "./HomeShell.module.css";

export function HomeShell() {
  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>SanoSync</p>
        <h1 className={styles.title}>La tua giornata, in un colpo d’occhio.</h1>
        <p className={styles.subtitle}>
          Il nuovo frontend è pronto per collegarsi alla FastAPI.
        </p>
      </section>

      <section className={styles.card}>
        <span className={styles.cardLabel}>5D.1</span>
        <strong>Frontend skeleton attivo</strong>
        <p>
          Prossimo step: autenticazione e Home mobile con dati reali.
        </p>
      </section>
    </main>
  );
}
