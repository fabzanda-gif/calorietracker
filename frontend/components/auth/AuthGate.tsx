"use client";

import {
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";

import {
  getProfile,
  type ProfileResponse,
} from "@/lib/api/profile";
import {
  getOnboardingStatus,
  type OnboardingStatus,
} from "@/lib/api/onboarding";
import { WelcomeJourney } from "@/components/onboarding/WelcomeJourney";
import { useI18n } from "@/components/i18n/I18nProvider";

import { useAuth } from "./AuthProvider";
import { LoginCard } from "./LoginCard";
import styles from "./AuthGate.module.css";


export function AuthGate({
  children,
}: {
  children: ReactNode;
}) {
  const { loading, user, accessToken } = useAuth();
  const { t } = useI18n();
  const pathname = usePathname();

  const [
    onboardingCheckLoading,
    setOnboardingCheckLoading,
  ] = useState(false);
  const [
    needsOnboarding,
    setNeedsOnboarding,
  ] = useState(false);
  const [profile, setProfile] =
    useState<ProfileResponse | null>(null);
  const [
    onboardingStatus,
    setOnboardingStatus,
  ] = useState<OnboardingStatus | null>(null);

  const legalPage =
    pathname === "/privacy" || pathname === "/terms";

  useEffect(() => {
    if (
      loading ||
      !user ||
      !accessToken ||
      legalPage
    ) {
      setOnboardingCheckLoading(false);
      setNeedsOnboarding(false);
      setProfile(null);
      setOnboardingStatus(null);
      return;
    }

    let active = true;

    async function checkOnboarding() {
      setOnboardingCheckLoading(true);

      try {
        const [
          profileResponse,
          statusResponse,
        ] = await Promise.all([
          getProfile(accessToken),
          getOnboardingStatus(accessToken),
        ]);

        if (!active) {
          return;
        }

        setProfile(profileResponse);
        setOnboardingStatus(statusResponse);

        const isDemo =
          profileResponse.read_only === true ||
          profileResponse.demo_mode === true;

        setNeedsOnboarding(
          !isDemo && !statusResponse.completed,
        );
      } catch (error) {
        // Never lock an existing user out because the onboarding
        // eligibility check is temporarily unavailable.
        console.error(
          "Unable to check onboarding status",
          error,
        );

        if (active) {
          setNeedsOnboarding(false);
          setOnboardingStatus(null);
        }
      } finally {
        if (active) {
          setOnboardingCheckLoading(false);
        }
      }
    }

    void checkOnboarding();

    return () => {
      active = false;
    };
  }, [
    accessToken,
    legalPage,
    loading,
    user,
  ]);

  const initialName = useMemo(() => {
    const metadata =
      profile?.metadata ??
      user?.user_metadata ??
      {};

    const value =
      metadata.name ??
      metadata.first_name ??
      metadata.full_name;

    return typeof value === "string"
      ? value.trim().split(/\s+/)[0] ?? ""
      : "";
  }, [profile, user]);

  if (legalPage) {
    return children;
  }

  if (loading || onboardingCheckLoading) {
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

  if (!user || !accessToken) {
    return <LoginCard />;
  }

  if (needsOnboarding) {
    return (
      <WelcomeJourney
        accessToken={accessToken}
        initialName={initialName}
        initialStatus={onboardingStatus}
      />
    );
  }

  return children;
}
