"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";

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
  { href: "/inventory", label: "Dispensa", icon: "·", subLink: true },
  { href: "/ingredients", label: "Ingredienti", icon: "·", subLink: true },
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

type AppNavProps = {
  experienceMode?: "standard" | "zero";
};

export function AppNav({
  experienceMode = "standard",
}: AppNavProps) {
  const pathname = usePathname();
  const { user, signOut } = useAuth();

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

  return (
    <>
      <aside
        className={
          experienceMode === "zero"
            ? `${styles.desktopNav} ${styles.desktopNavZero}`
            : styles.desktopNav
        }
        aria-label="Navigazione principale"
      >
        <div className={styles.brandBlock}>
          <img
            src={
              experienceMode === "zero"
                ? "/assets/LogoZero.png"
                : "/assets/LogoCoral.png"
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
          {ITEMS.map((item, index) => {
            const active = isActive(pathname, item.href);
            const separatorBefore = index === 4;

            return (
              <div key={item.label}>
                {separatorBefore && (
                  <div
                    className={styles.separator}
                    aria-hidden="true"
                  />
                )}

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
                    <span>{item.label}</span>
                  </button>
                ) : (
                  <Link
                    href={item.href}
                    className={
                      "subLink" in item && item.subLink
                        ? active
                          ? styles.desktopSubLinkActive
                          : styles.desktopSubLink
                        : active
                        ? styles.desktopLinkActive
                        : styles.desktopLink
                    }
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
                    <span>{item.label}</span>
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
            aria-label="Apri il profilo"
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
                {user?.email ?? "Gestisci il profilo"}
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
            Esci
          </button>
        </div>
      </aside>

      <nav
        className={styles.mobileNav}
        aria-label="Navigazione principale"
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

              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
