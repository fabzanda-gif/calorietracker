"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { useExperienceMode } from "@/components/experience/ExperienceModeProvider";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { useI18n } from "@/components/i18n/I18nProvider";

import styles from "./AppNav.module.css";

const ITEMS = [
  { href: "/", label: "Home", icon: "⌂" },
  { href: "/plan", label: "Plan", icon: "▣" },
  { href: "/ai", label: "AI", icon: "✦" },
  { href: "/food", label: "Food", icon: "⌑" },
  {
    href: "/insights",
    label: "Insights",
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M4 18 9 13l3 3 7-8" />
        <path d="M14 8h5v5" />
      </svg>
    ),
  },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";

  if (
    href === "/plan" &&
    pathname.startsWith("/activities")
  ) {
    return true;
  }

  if (
    href === "/food" &&
    (
      pathname.startsWith("/recipes") ||
      pathname.startsWith("/inventory") ||
      pathname.startsWith("/ingredients")
    )
  ) {
    return true;
  }

  if (
    href === "/insights" &&
    pathname.startsWith("/progress")
  ) {
    return true;
  }

  if (href === "/activities" && pathname.startsWith("/training/")) {
    return true;
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const { t } = useI18n();
  const { experienceMode, setExperienceMode } = useExperienceMode();

  const metadataName =
    user?.user_metadata?.full_name ??
    user?.user_metadata?.name ??
    user?.user_metadata?.first_name;

  const displayName =
    typeof metadataName === "string" && metadataName.trim()
      ? metadataName.trim()
      : user?.email?.split("@")[0] ?? "Profilo";

  const initials =
    displayName
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "S";

  const metadataAvatar =
    user?.user_metadata?.avatar_url ?? user?.user_metadata?.picture;

  const avatarUrl =
    typeof metadataAvatar === "string" ? metadataAvatar : null;

  const readOnlyDemo = Boolean(
    user?.user_metadata?.demo_mode === true ||
    user?.user_metadata?.read_only === true ||
    user?.app_metadata?.demo_mode === true ||
    user?.app_metadata?.read_only === true,
  );

  return (
    <>
      {readOnlyDemo ? (
        <div className={styles.demoBanner} role="status">
          {t("demoMode")}
        </div>
      ) : null}

      <LanguageSwitcher />

      <div className={styles.globalExperienceSwitch} aria-label="Modalità SanoSync">
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
            alt={experienceMode === "zero" ? "SanoSync Zero Mode" : "SanoSync"}
            className={styles.brandLogo}
          />
        </div>

        <nav className={styles.desktopLinks}>
          {ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={active ? styles.desktopLinkActive : styles.desktopLink}
                aria-current={active ? "page" : undefined}
              >
                <span className={styles.desktopIcon} aria-hidden="true">
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </Link>
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
                <img src={avatarUrl} alt="" referrerPolicy="no-referrer" />
              ) : (
                initials
              )}
            </span>
            <span className={styles.profileDetails}>
              <strong>{displayName}</strong>
              <small>{user?.email ?? t("manageProfile")}</small>
            </span>
            <span className={styles.profileArrow} aria-hidden="true">›</span>
          </Link>

          <button
            type="button"
            className={styles.signOut}
            onClick={() => void signOut()}
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
        {ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? styles.mobileLinkActive : styles.mobileLink}
              aria-current={active ? "page" : undefined}
            >
              <span className={styles.mobileIcon} aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
