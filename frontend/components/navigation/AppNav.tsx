"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";

import styles from "./AppNav.module.css";


const ITEMS = [
  {
    href: "/",
    label: "Oggi",
    icon: "○",
  },
  {
    href: "/progress",
    label: "Progressi",
    icon: "↗",
  },
  {
    href: "/recipes",
    label: "Ricette",
    icon: "◇",
  },
];


function isActive(
  pathname: string,
  href: string,
): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return (
    pathname === href ||
    pathname.startsWith(`${href}/`)
  );
}


export function AppNav() {
  const pathname = usePathname();
  const { signOut } = useAuth();

  return (
    <>
      <nav
        className={styles.desktopNav}
        aria-label="Navigazione principale"
      >
        <Link
          href="/"
          className={styles.brand}
        >
          SANOSYNC
        </Link>

        <div className={styles.desktopLinks}>
          {ITEMS.map((item) => {
            const active = isActive(
              pathname,
              item.href,
            );

            return (
              <Link
                key={item.href}
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
                {item.label}
              </Link>
            );
          })}
        </div>

        <button
          type="button"
          className={styles.signOut}
          onClick={() => {
            void signOut();
          }}
        >
          Esci
        </button>
      </nav>

      <nav
        className={styles.mobileNav}
        aria-label="Navigazione principale"
      >
        {ITEMS.map((item) => {
          const active = isActive(
            pathname,
            item.href,
          );

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
