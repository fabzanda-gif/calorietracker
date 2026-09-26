"use client";

import { useEffect } from "react";

const EMPTY_DAY_MESSAGES = [
  "No activities logged on this day.",
  "Nessuna attività registrata in questo giorno.",
  "Geen activiteiten geregistreerd op deze dag.",
  "Aucune activité enregistrée ce jour-là.",
];

export default function ActivitiesUiGuard() {
  useEffect(() => {
    const syncUi = () => {
      const root = document.querySelector<HTMLElement>(
        'main[class*="ActivitiesPage_page"]',
      );

      if (!root) return;

      const detailCard = root.querySelector<HTMLElement>(
        '[class*="ActivitiesPage_detailCard"]',
      );

      const hasEmptySelectedDay = Array.from(
        root.querySelectorAll<HTMLElement>("p, div"),
      ).some((element) => {
        const text = element.textContent?.trim() ?? "";
        return EMPTY_DAY_MESSAGES.includes(text);
      });

      if (detailCard) {
        detailCard.dataset.staleHidden = hasEmptySelectedDay
          ? "true"
          : "false";
      }

      const calendar = root.querySelector<HTMLElement>(
        '[class*="ActivitiesPage_calendar"]',
      );
      const loading = root.querySelector<HTMLElement>(
        '[class*="ActivitiesPage_loading"]',
      );

      if (calendar && loading) {
        const hasCalendarDays = Boolean(
          calendar.querySelector(
            '[class*="ActivitiesPage_day"]',
          ),
        );

        loading.dataset.calendarReady = hasCalendarDays
          ? "true"
          : "false";
      }
    };

    syncUi();

    const observer = new MutationObserver(syncUi);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    window.addEventListener("resize", syncUi);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", syncUi);
    };
  }, []);

  return null;
}
