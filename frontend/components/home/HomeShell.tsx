"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import styles from "./HomeShell.module.css";

export function HomeShell() {
  const {
    user,
    signOut,
  } = useAuth();

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.topline}>
          <p className={styles.eyebrow}>
            SanoSync
          </p>

          <button
            className={styles.signOut}
            type="button"
            onClick={() => {
              void signOut();
            }}
          >
            Esci
          </button>
        </div>

        <h1 className={styles.title}>
          La tua giornata, in un colpo
          d’occhio.
        </h1>

        <p className={styles.subtitle}>
          Sessione Supabase attiva.
        </p>
      </section>

      <section className={styles.card}>
        <span className={styles.cardLabel}>
          5D.2
        </span>

        <strong>
          Autenticazione collegata
        </strong>

        <p>
          {user?.email
            ? `Accesso come ${user.email}`
            : "Utente autenticato"}
        </p>

        <p>
          Prossimo step: collegare la
          Home ai dati reali della
          FastAPI usando il bearer token.
        </p>
      </section>
    </main>
  );
}
