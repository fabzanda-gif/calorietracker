"use client";

import {
  FormEvent,
  useState,
} from "react";

import { useAuth } from "./AuthProvider";
import styles from "./LoginCard.module.css";

export function LoginCard() {
  const {
    signInWithPassword,
    signInWithGoogle,
  } = useAuth();

  const [email, setEmail] =
    useState("");
  const [password, setPassword] =
    useState("");
  const [submitting, setSubmitting] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await signInWithPassword(
        email.trim(),
        password,
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Accesso non riuscito",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <p className={styles.brand}>
          SANOSYNC
        </p>

        <div className={styles.heading}>
          <h1>Bentornato.</h1>
          <p>
            Accedi con lo stesso account
            che usi su SanoSync.
          </p>
        </div>

        <button
          className={styles.googleButton}
          type="button"
          disabled={submitting}
          onClick={async () => {
            setSubmitting(true);
            setError(null);

            try {
              await signInWithGoogle();
            } catch (err) {
              setError(
                err instanceof Error
                  ? err.message
                  : "Accesso con Google non riuscito",
              );
              setSubmitting(false);
            }
          }}
        >
          Continua con Google
        </button>

        <div className={styles.divider}>
          <span>oppure</span>
        </div>

        <form
          className={styles.form}
          onSubmit={handleSubmit}
        >
          <label className={styles.field}>
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) =>
                setEmail(
                  event.target.value,
                )
              }
            />
          </label>

          <label className={styles.field}>
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value,
                )
              }
            />
          </label>

          {error ? (
            <p className={styles.error}>
              {error}
            </p>
          ) : null}

          <button
            className={styles.button}
            type="submit"
            disabled={submitting}
          >
            {submitting
              ? "Accesso…"
              : "Accedi"}
          </button>
        </form>
      </section>
    </main>
  );
}
