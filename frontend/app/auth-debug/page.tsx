"use client";

import { useAuth } from "@/components/auth/AuthProvider";

export default function AuthDebugPage() {
  const {
    user,
    accessToken,
  } = useAuth();

  return (
    <main
      style={{
        padding: 24,
        maxWidth: 720,
        margin: "0 auto",
      }}
    >
      <h1>Auth debug</h1>

      <p>
        User: {user?.email ?? "none"}
      </p>

      <p>
        Access token presente:{" "}
        {accessToken ? "sì" : "no"}
      </p>
    </main>
  );
}
