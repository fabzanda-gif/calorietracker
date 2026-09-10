"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useExperienceMode } from "@/components/experience/ExperienceModeProvider";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { useI18n } from "@/components/i18n/I18nProvider";
import { getProfile } from "@/lib/api/profile";

import styles from "./AppNav.module.css";

const ITEMS = [
  {
    href: "/",
    label: "Oggi",
    icon: "⌂",
  },
  {
    href: "/activities",
    label: "Attività",
    icon: "⌁",
  },
  {
    href: "/progress",
    label: "Progressi",
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M4 18 9 13l3 3 7-8" />
        <path d="M14 8h5v5" />
      </svg>
    ),
  },
  {
    href: "/recipes",
    label: "Ricette",
    icon: "⌑",
  },
];

const MOBILE_ITEMS = [
  ...ITEMS.slice(0, 4),
  {
    href: "/profile",
    label: "Profilo",
    icon: "●",
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  if (href === "#") {
    return false;
  }

  if (href === "/recipes" && (pathname.startsWith("/inventory") || pathname.startsWith("/ingredients"))) {
    return true;
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav() {
  const pathname = usePathname();
  const { user, accessToken, signOut } = useAuth();
  const { t } = useI18n();
  const [readOnlyDemo, setReadOnlyDemo] =
    useState(false);
  const {
    experienceMode,
    setExperienceMode,
  } = useExperienceMode();

  const metadataName =
    user?.user_metadata?.full_name ??
    user?.user_metadata?.name ??
    user?.user_metadata?.first_name;

  const displayName =
    typeof metadataName === "string" &&
    metadataName.trim()
      ? metadataName.trim()
      : user?.email?.split("@")[0] ?? "Profilo";

  const initials =
    displayName
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "S";

  const metadataAvatar =
    user?.user_metadata?.avatar_url ??
    user?.user_metadata?.picture;

  const avatarUrl =
    typeof metadataAvatar === "string"
      ? metadataAvatar
      : null;

  useEffect(() => {
    if (!accessToken) {
      setReadOnlyDemo(false);
      return;
    }

    let active = true;
    void getProfile(accessToken)
      .then((profile) => {
        if (active) {
          setReadOnlyDemo(
            profile.read_only === true,
          );
        }
      })
      .catch(() => {
        if (active) {
          setReadOnlyDemo(false);
        }
      });

    return () => {
      active = false;
    };
  }, [accessToken]);

  const navLabel = (href: string) => {
    if (href === "/") return t("today");
    if (href === "/activities") return t("activities");
    if (href === "/progress") return t("progress");
    if (href === "/recipes") return t("recipes");
    return t("profile");
  };

  return (
    <>
      {readOnlyDemo ? (
        <div
          className={styles.demoBanner}
          role="status"
        >
          {t("demoMode")}
        </div>
      ) : null}

      <LanguageSwitcher />

      <div
        className={styles.globalExperienceSwitch}
        aria-label="Modalità SanoSync"
      >
        <button
          type="button"
          className={
            experienceMode === "standard"
              ? styles.globalExperienceSwitchStandardActive
              : undefined
          }
          onClick={() => setExperienceMode("standard")}
        >
          Standard
        </button>

        <button
          type="button"
          className={
            experienceMode === "zero"
              ? styles.globalExperienceSwitchZeroActive
              : undefined
          }
          onClick={() => setExperienceMode("zero")}
        >
          Zero
        </button>
      </div>

      <aside
        className={
          experienceMode === "zero"
            ? `${styles.desktopNav} ${styles.desktopNavZero}`
            : styles.desktopNav
        }
        aria-label={t("primaryNavigation")}
      >
        <div className={styles.brandBlock}>
          <img
            src={
              experienceMode === "zero"
                ? "/assets/LogoZero.png"
                : "/assets/LogoStandardNavy.png"
            }
            alt={
              experienceMode === "zero"
                ? "SanoSync Zero Mode"
                : "SanoSync"
            }
            className={styles.brandLogo}
          />
        </div>

        <nav className={styles.desktopLinks}>
          {ITEMS.map((item) => {
            const active = isActive(pathname, item.href);

            return (
              <div key={item.href}>
                {item.href === "#" ? (
                  <button
                    type="button"
                    className={styles.desktopLink}
                    onClick={() => undefined}
                  >
                    <span
                      className={styles.desktopIcon}
                      aria-hidden="true"
                    >
                      {item.icon}
                    </span>
                    <span>{navLabel(item.href)}</span>
                  </button>
                ) : (
                  <Link
                    href={item.href}
                    className={active
                      ? styles.desktopLinkActive
                      : styles.desktopLink}
                    aria-current={
                      active ? "page" : undefined
                    }
                  >
                    <span
                      className={styles.desktopIcon}
                      aria-hidden="true"
                    >
                      {item.icon}
                    </span>
                    <span>{navLabel(item.href)}</span>
                  </Link>
                )}
              </div>
            );
          })}
        </nav>

        <div className={styles.profileArea}>
          <Link
            href="/profile"
            className={styles.profileCard}
            aria-label={t("openProfile")}
          >
            <span className={styles.profileAvatar}>
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  referrerPolicy="no-referrer"
                />
              ) : (
                initials
              )}
            </span>

            <span className={styles.profileDetails}>
              <strong>{displayName}</strong>
              <small>
                {user?.email ?? t("manageProfile")}
              </small>
            </span>

            <span
              className={styles.profileArrow}
              aria-hidden="true"
            >
              ›
            </span>
          </Link>

          <button
            type="button"
            className={styles.signOut}
            onClick={() => {
              void signOut();
            }}
          >
            {t("signOut")}
          </button>
        </div>
      </aside>

      <nav
        className={
          experienceMode === "zero"
            ? `${styles.mobileNav} ${styles.mobileNavZero}`
            : styles.mobileNav
        }
        aria-label={t("primaryNavigation")}
      >
        {MOBILE_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={
                active
                  ? styles.mobileLinkActive
                  : styles.mobileLink
              }
              aria-current={
                active ? "page" : undefined
              }
            >
              <span
                className={styles.mobileIcon}
                aria-hidden="true"
              >
                {item.icon}
              </span>

              <span>{navLabel(item.href)}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
