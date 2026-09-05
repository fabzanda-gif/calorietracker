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

export const EXPERIENCE_MODE_KEY =
  "sanosync-experience-mode";

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

export function ExperienceModeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [experienceMode, setMode] =
    useState<ExperienceMode>("standard");

  useEffect(() => {
    const stored =
      window.localStorage.getItem(
        EXPERIENCE_MODE_KEY,
      );

    setMode(
      stored === "zero"
        ? "zero"
        : "standard",
    );
  }, []);

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
      setMode(mode);
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
