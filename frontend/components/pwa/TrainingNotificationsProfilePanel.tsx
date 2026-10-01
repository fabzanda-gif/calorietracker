"use client";

import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { TrainingNotificationsCard } from "@/components/pwa/TrainingNotificationsCard";

import styles from "./TrainingNotificationsProfilePanel.module.css";

export function TrainingNotificationsProfilePanel() {
  const pathname = usePathname();
  const { accessToken } = useAuth();

  if (pathname !== "/profile" || !accessToken) {
    return null;
  }

  return (
    <div className={styles.panel} aria-label="Notifiche allenamento">
      <TrainingNotificationsCard accessToken={accessToken} />
    </div>
  );
}
