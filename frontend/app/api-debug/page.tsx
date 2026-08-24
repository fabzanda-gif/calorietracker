"use client";

import {
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { getDay } from "@/lib/api/day";

export default function ApiDebugPage() {
  const { accessToken } =
    useAuth();

  const [result, setResult] =
    useState<string>(
      "Premi il pulsante per interrogare FastAPI.",
    );

  async function testApi() {
    if (!accessToken) {
      setResult(
        "Nessun access token disponibile.",
      );
      return;
    }

    try {
      const today =
        new Date()
          .toISOString()
          .slice(0, 10);

      const payload =
        await getDay(
          today,
          accessToken,
        );

      setResult(
        JSON.stringify(
          payload,
          null,
          2,
        ),
      );
    } catch (error) {
      setResult(
        error instanceof Error
          ? error.message
          : String(error),
      );
    }
  }

  return (
    <main
      style={{
        padding: 24,
        maxWidth: 720,
        margin: "0 auto",
      }}
    >
      <h1>FastAPI auth debug</h1>

      <button
        type="button"
        onClick={() => {
          void testApi();
        }}
      >
        Test FastAPI
      </button>

      <pre
        style={{
          whiteSpace: "pre-wrap",
          marginTop: 20,
        }}
      >
        {result}
      </pre>
    </main>
  );
}
