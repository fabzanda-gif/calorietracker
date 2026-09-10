"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type AppLocale = "it" | "en" | "nl";

const STORAGE_KEY = "sanosync-language";

const messages = {
  it: {
    today: "Oggi",
    activities: "Attività",
    progress: "Progressi",
    recipes: "Ricette",
    profile: "Profilo",
    signOut: "Esci",
    openProfile: "Apri il profilo",
    manageProfile: "Gestisci il profilo",
    primaryNavigation: "Navigazione principale",
    demoMode: "Modalità demo · dati reali in sola lettura",
    language: "Lingua dell’app",
    languageHelp:
      "La prima volta scegliamo in base alla lingua del dispositivo. Puoi cambiarla quando vuoi.",
    welcomeBack: "Bentornato.",
    startHere: "Inizia da qui.",
    loginIntro: "Accedi con lo stesso account che usi su SanoSync.",
    signupIntro: "Crea il tuo account e configura il tuo primo piano.",
    continueGoogle: "Continua con Google",
    signupGoogle: "Registrati con Google",
    or: "oppure",
    email: "Email",
    password: "Password",
    passwordPlaceholder: "La tua password",
    newPasswordPlaceholder: "Almeno 8 caratteri",
    login: "Accedi",
    createAccount: "Crea account",
    signingIn: "Accesso…",
    creatingAccount: "Creazione account…",
    noAccount: "Non hai ancora un account?",
    haveAccount: "Hai già un account?",
    register: "Registrati",
    privacyNote: "I tuoi dati restano privati e sotto il tuo controllo.",
    terms: "Termini e condizioni",
    consentPrefix: "Accetto i",
    consentMiddle: "e dichiaro di aver letto la",
    confirmationEmail:
      "Controlla la tua email e conferma l’account per iniziare.",
    signupFailed: "Registrazione non riuscita",
    loginFailed: "Accesso non riuscito",
    googleFailed: "Accesso con Google non riuscito",
  },
  en: {
    today: "Today",
    activities: "Activities",
    progress: "Progress",
    recipes: "Recipes",
    profile: "Profile",
    signOut: "Sign out",
    openProfile: "Open profile",
    manageProfile: "Manage profile",
    primaryNavigation: "Primary navigation",
    demoMode: "Demo mode · real data, read only",
    language: "App language",
    languageHelp:
      "We use your device language the first time. You can change it whenever you want.",
    welcomeBack: "Welcome back.",
    startHere: "Start here.",
    loginIntro: "Sign in with the same account you use on SanoSync.",
    signupIntro: "Create your account and set up your first plan.",
    continueGoogle: "Continue with Google",
    signupGoogle: "Sign up with Google",
    or: "or",
    email: "Email",
    password: "Password",
    passwordPlaceholder: "Your password",
    newPasswordPlaceholder: "At least 8 characters",
    login: "Sign in",
    createAccount: "Create account",
    signingIn: "Signing in…",
    creatingAccount: "Creating account…",
    noAccount: "Don’t have an account yet?",
    haveAccount: "Already have an account?",
    register: "Sign up",
    privacyNote: "Your data stays private and under your control.",
    terms: "Terms and conditions",
    consentPrefix: "I accept the",
    consentMiddle: "and confirm that I have read the",
    confirmationEmail:
      "Check your email and confirm your account to get started.",
    signupFailed: "Sign-up failed",
    loginFailed: "Sign-in failed",
    googleFailed: "Google sign-in failed",
  },
  nl: {
    today: "Vandaag",
    activities: "Activiteiten",
    progress: "Voortgang",
    recipes: "Recepten",
    profile: "Profiel",
    signOut: "Uitloggen",
    openProfile: "Profiel openen",
    manageProfile: "Profiel beheren",
    primaryNavigation: "Hoofdnavigatie",
    demoMode: "Demomodus · echte gegevens, alleen-lezen",
    language: "Taal van de app",
    languageHelp:
      "De eerste keer gebruiken we de taal van je apparaat. Je kunt deze altijd wijzigen.",
    welcomeBack: "Welkom terug.",
    startHere: "Begin hier.",
    loginIntro: "Log in met hetzelfde account dat je voor SanoSync gebruikt.",
    signupIntro: "Maak je account aan en stel je eerste plan in.",
    continueGoogle: "Doorgaan met Google",
    signupGoogle: "Registreren met Google",
    or: "of",
    email: "E-mail",
    password: "Wachtwoord",
    passwordPlaceholder: "Je wachtwoord",
    newPasswordPlaceholder: "Minimaal 8 tekens",
    login: "Inloggen",
    createAccount: "Account aanmaken",
    signingIn: "Inloggen…",
    creatingAccount: "Account aanmaken…",
    noAccount: "Heb je nog geen account?",
    haveAccount: "Heb je al een account?",
    register: "Registreren",
    privacyNote: "Je gegevens blijven privé en onder jouw controle.",
    terms: "Algemene voorwaarden",
    consentPrefix: "Ik accepteer de",
    consentMiddle: "en bevestig dat ik het volgende heb gelezen:",
    confirmationEmail:
      "Controleer je e-mail en bevestig je account om te beginnen.",
    signupFailed: "Registreren mislukt",
    loginFailed: "Inloggen mislukt",
    googleFailed: "Inloggen met Google mislukt",
  },
} as const;

type MessageKey = keyof typeof messages.it;

interface I18nContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
  t: (key: MessageKey) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AppLocale>("it");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const initial: AppLocale =
      stored === "it" || stored === "en" || stored === "nl"
        ? stored
        : navigator.language.toLowerCase().startsWith("it")
          ? "it"
          : navigator.language.toLowerCase().startsWith("nl")
            ? "nl"
            : "en";
    setLocaleState(initial);
    document.documentElement.lang = initial;
  }, []);

  function setLocale(next: AppLocale) {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next;
  }

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key) => messages[locale][key],
    }),
    [locale],
  );

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return value;
}
