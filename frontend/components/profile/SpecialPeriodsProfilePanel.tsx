"use client";

import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { SpecialPeriodsCard } from "./SpecialPeriodsCard";

import styles from "./SpecialPeriodsProfilePanel.module.css";

export function SpecialPeriodsProfilePanel() {
  const pathname = usePathname();
  const { accessToken } = useAuth();

  if (pathname !== "/profile" || !accessToken) {
    return null;
  }

  return (
    <div className={styles.panel}>
      <SpecialPeriodsCard accessToken={accessToken} />
    </div>
  );
}
