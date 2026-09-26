"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";
import { LoginCard } from "./LoginCard";
import { useI18n } from "@/components/i18n/I18nProvider";
import styles from "./AuthGate.module.css";

export function AuthGate({
  children,
}: {
  children: ReactNode;
}) {
  const { loading, user } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();

  if (pathname === "/privacy" || pathname === "/terms") {
    return children;
  }

  if (loading) {
    return (
      <main className={styles.centered}>
        <p className={styles.brand}>
          SANOSYNC
        </p>
        <p className={styles.muted}>
          {t("loadingSession")}
        </p>
      </main>
    );
  }

  if (!user) {
    return <LoginCard />;
  }

  return children;
}
