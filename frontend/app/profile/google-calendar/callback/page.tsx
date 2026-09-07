"use client";

import {
  Suspense,
  useEffect,
  useState,
} from "react";
import {
  useRouter,
  useSearchParams,
} from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  exchangeGoogleCalendarCode,
} from "@/lib/api/google-calendar";


function GoogleCalendarCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const {
    accessToken,
  } = useAuth();

  const [message, setMessage] =
    useState(
      "Collegamento con Google Calendar…",
    );

  const [failed, setFailed] =
    useState(false);

  useEffect(() => {
    if (!accessToken) {
      return;
    }

    const token = accessToken;

    const error =
      searchParams.get("error");

    const code =
      searchParams.get("code");

    const state =
      searchParams.get("state");

    if (error) {
      setFailed(true);
      setMessage(
        "Autorizzazione Google Calendar annullata o rifiutata.",
      );
      return;
    }

    if (!code || !state) {
      setFailed(true);
      setMessage(
        "Risposta Google Calendar incompleta. Riprova dal profilo.",
      );
      return;
    }

    const authorizationCode = code;
    const oauthState = state;

    let active = true;

    async function completeConnection() {
      try {
        await exchangeGoogleCalendarCode(
          token,
          authorizationCode,
          oauthState,
        );

        if (!active) {
          return;
        }

        setMessage(
          "Google Calendar collegato correttamente.",
        );

        window.setTimeout(() => {
          router.replace(
            "/profile?googleCalendar=connected",
          );
        }, 700);
      } catch {
        if (!active) {
          return;
        }

        setFailed(true);

        setMessage(
          "Non è stato possibile completare "
          + "il collegamento con Google Calendar.",
        );
      }
    }

    void completeConnection();

    return () => {
      active = false;
    };
  }, [
    accessToken,
    router,
    searchParams,
  ]);

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: "24px",
        background: "#faf9f6",
      }}
    >
      <section
        style={{
          width: "min(480px, 100%)",
          padding: "32px",
          border:
            "1px solid rgba(0,0,0,0.1)",
          borderRadius: "18px",
          background: "white",
          textAlign: "center",
        }}
      >
        <h1
          style={{
            margin: "0 0 12px",
            color: "#102a49",
          }}
        >
          SanoSync + Google Calendar
        </h1>

        <p
          role={
            failed ? "alert" : "status"
          }
          style={{
            margin: 0,
            color: failed
              ? "#b42318"
              : "#556273",
          }}
        >
          {message}
        </p>

        {failed ? (
          <button
            type="button"
            onClick={() =>
              router.replace("/profile")
            }
            style={{
              marginTop: "22px",
              minHeight: "42px",
              padding: "0 18px",
              border: 0,
              borderRadius: "10px",
              background: "#ff6864",
              color: "white",
              fontWeight: 700,
              cursor: "pointer",
            }}
          >
            Torna al profilo
          </button>
        ) : null}
      </section>
    </main>
  );
}


export default function GoogleCalendarCallbackPage() {
  return (
    <Suspense
      fallback={
        <main
          style={{
            padding: "32px",
          }}
        >
          Collegamento con Google Calendar…
        </main>
      }
    >
      <GoogleCalendarCallbackContent />
    </Suspense>
  );
}
