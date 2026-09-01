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
    href: "/inventory",
    label: "Cosa mangio?",
    icon: "♨",
  },
  {
    href: "/recipes",
    label: "Ricette",
    icon: "♨",
  },
  {
    href: "/progress",
    label: "Progressi",
    icon: "⌁",
  },
  {
    href: "#",
    label: "Condivisioni",
    icon: "♧",
  },
  {
    href: "/profile",
    label: "Impostazioni",
    icon: "⚙",
  },
  {
    href: "#",
    label: "Aiuto",
    icon: "?",
  },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  if (href === "#") {
    return false;
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav() {
  const pathname = usePathname();
  const { signOut } = useAuth();

  return (
    <>
      <aside
        className={styles.desktopNav}
        aria-label="Navigazione principale"
      >
        <div className={styles.brandBlock}>
          <div className={styles.logoMark} aria-hidden="true">
            S
          </div>

          <div className={styles.brandName}>SanoSync</div>
        </div>

        <nav className={styles.desktopLinks}>
          {ITEMS.map((item, index) => {
            const active = isActive(pathname, item.href);
            const separatorBefore = index === 5;

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
                      active
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

        <button
          type="button"
          className={styles.signOut}
          onClick={() => {
            void signOut();
          }}
        >
          Esci
        </button>
      </aside>

      <nav
        className={styles.mobileNav}
        aria-label="Navigazione principale"
      >
        {ITEMS.slice(0, 4).map((item) => {
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
