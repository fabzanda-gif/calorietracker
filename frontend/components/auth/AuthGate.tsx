"use client";

import type { ReactNode } from "react";

import { useAuth } from "./AuthProvider";
import { LoginCard } from "./LoginCard";
import styles from "./AuthGate.module.css";

export function AuthGate({
  children,
}: {
  children: ReactNode;
}) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <main className={styles.centered}>
        <p className={styles.brand}>
          SANOSYNC
        </p>
        <p className={styles.muted}>
          Caricamento sessione…
        </p>
      </main>
    );
  }

  if (!user) {
    return <LoginCard />;
  }

  return children;
}
