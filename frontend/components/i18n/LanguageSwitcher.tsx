"use client";

import { useState } from "react";

import { useI18n, type AppLocale } from "./I18nProvider";
import styles from "./LanguageSwitcher.module.css";

const OPTIONS: Array<{
  locale: AppLocale;
  flag: string;
  label: string;
}> = [
  { locale: "it", flag: "🇮🇹", label: "Italiano" },
  { locale: "en", flag: "🇬🇧", label: "English" },
  { locale: "nl", flag: "🇳🇱", label: "Nederlands" },
];

export function LanguageSwitcher({
  variant = "compact",
  onChange,
}: {
  variant?: "compact" | "profile";
  onChange?: (locale: AppLocale) => void;
}) {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);

  function choose(next: AppLocale) {
    setLocale(next);
    onChange?.(next);
    setOpen(false);
  }

  if (variant === "profile") {
    return (
      <div className={styles.profileToggle} aria-label="Language">
        {OPTIONS.map((option) => (
          <button
            key={option.locale}
            type="button"
            className={
              locale === option.locale ? styles.profileActive : undefined
            }
            aria-pressed={locale === option.locale}
            onClick={() => choose(option.locale)}
          >
            {option.label}
          </button>
        ))}
      </div>
    );
  }

  const selected = OPTIONS.find((option) => option.locale === locale)!;

  return (
    <div className={styles.compact}>
      <button
        type="button"
        className={styles.compactButton}
        aria-label={
          locale === "it"
            ? "Cambia lingua"
            : locale === "nl"
              ? "Taal wijzigen"
              : "Change language"
        }
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden="true">{selected.flag}</span>
        <span className={styles.chevron} aria-hidden="true">⌄</span>
      </button>
      {open ? (
        <div className={styles.menu} role="menu">
          {OPTIONS.map((option) => (
            <button
              key={option.locale}
              type="button"
              role="menuitemradio"
              aria-checked={locale === option.locale}
              onClick={() => choose(option.locale)}
            >
              <span aria-hidden="true">{option.flag}</span>
              <span>{option.label}</span>
              <b aria-hidden="true">
                {locale === option.locale ? "✓" : ""}
              </b>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
