"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ExperienceMode =
  | "standard"
  | "zero";

type DayPeriod =
  | "day"
  | "evening";

const EVENING_START_HOUR = 18;

export const EXPERIENCE_MODE_KEY =
  "sanosync-experience-mode";

const EXPERIENCE_MODE_OVERRIDE_KEY =
  "sanosync-experience-mode-override";

type StoredOverride = {
  mode: ExperienceMode;
  period: DayPeriod;
};

type ExperienceModeContextValue = {
  experienceMode: ExperienceMode;
  setExperienceMode: (
    mode: ExperienceMode,
  ) => void;
};

const ExperienceModeContext =
  createContext<ExperienceModeContextValue | null>(
    null,
  );

function currentPeriod(
  date = new Date(),
): DayPeriod {
  return date.getHours() >=
    EVENING_START_HOUR
    ? "evening"
    : "day";
}

function automaticMode(
  period: DayPeriod,
): ExperienceMode {
  return period === "evening"
    ? "zero"
    : "standard";
}

function readOverride():
  StoredOverride | null {
  try {
    const raw =
      window.localStorage.getItem(
        EXPERIENCE_MODE_OVERRIDE_KEY,
      );

    if (!raw) {
      return null;
    }

    const value = JSON.parse(raw);

    if (
      (value?.mode === "standard" ||
        value?.mode === "zero") &&
      (value?.period === "day" ||
        value?.period === "evening")
    ) {
      return value as StoredOverride;
    }
  } catch {
    // Ignore invalid local state.
  }

  return null;
}

export function ExperienceModeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [experienceMode, setMode] =
    useState<ExperienceMode>("standard");

  const [period, setPeriod] =
    useState<DayPeriod>("day");

  useEffect(() => {
    const nextPeriod = currentPeriod();
    const override = readOverride();

    setPeriod(nextPeriod);

    setMode(
      override?.period === nextPeriod
        ? override.mode
        : automaticMode(nextPeriod),
    );
  }, []);

  useEffect(() => {
    const syncWithClock = () => {
      const nextPeriod = currentPeriod();

      if (nextPeriod === period) {
        return;
      }

      const override = readOverride();

      setPeriod(nextPeriod);

      setMode(
        override?.period === nextPeriod
          ? override.mode
          : automaticMode(nextPeriod),
      );
    };

    const timer = window.setInterval(
      syncWithClock,
      60_000,
    );

    return () => {
      window.clearInterval(timer);
    };
  }, [period]);

  useEffect(() => {
    document.documentElement.dataset.experienceMode =
      experienceMode;

    window.localStorage.setItem(
      EXPERIENCE_MODE_KEY,
      experienceMode,
    );
  }, [experienceMode]);

  const setExperienceMode = useCallback(
    (mode: ExperienceMode) => {
      const activePeriod = currentPeriod();

      setPeriod(activePeriod);
      setMode(mode);

      const override: StoredOverride = {
        mode,
        period: activePeriod,
      };

      window.localStorage.setItem(
        EXPERIENCE_MODE_OVERRIDE_KEY,
        JSON.stringify(override),
      );
    },
    [],
  );

  const value = useMemo(
    () => ({
      experienceMode,
      setExperienceMode,
    }),
    [
      experienceMode,
      setExperienceMode,
    ],
  );

  return (
    <ExperienceModeContext.Provider
      value={value}
    >
      {children}
    </ExperienceModeContext.Provider>
  );
}

export function useExperienceMode() {
  const context =
    useContext(ExperienceModeContext);

  if (!context) {
    throw new Error(
      "useExperienceMode must be used inside ExperienceModeProvider",
    );
  }

  return context;
}
