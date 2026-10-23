"use client";

import { useEffect } from "react";

export function RegisterServiceWorker() {
  useEffect(() => {
    if (
      process.env.NODE_ENV !== "production" ||
      !("serviceWorker" in navigator)
    ) {
      return;
    }

    const register = async () => {
      try {
        await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
        });
      } catch (error) {
        console.error(
          "SanoSync service worker registration failed:",
          error,
        );
      }
    };

    if (document.readyState === "complete") {
      void register();
      return;
    }

    window.addEventListener(
      "load",
      () => void register(),
      { once: true },
    );
  }, []);

  return null;
}
