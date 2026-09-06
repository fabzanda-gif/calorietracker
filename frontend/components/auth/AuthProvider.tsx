"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  Session,
  User,
} from "@supabase/supabase-js";

import { supabase } from "@/lib/supabase/client";

interface AuthContextValue {
  session: Session | null;
  user: User | null;
  accessToken: string | null;
  loading: boolean;
  signInWithPassword: (
    email: string,
    password: string,
  ) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signUpWithPassword: (
    email: string,
    password: string,
  ) => Promise<boolean>;
  signOut: () => Promise<void>;
}

const AuthContext =
  createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [session, setSession] =
    useState<Session | null>(null);
  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    let active = true;

    void supabase.auth
      .getSession()
      .then(({ data, error }) => {
        if (!active) {
          return;
        }

        if (error) {
          console.error(
            "Unable to restore Supabase session",
            error,
          );
        }

        setSession(data.session ?? null);
        setLoading(false);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        if (!active) {
          return;
        }

        setSession(nextSession);
        setLoading(false);
      },
    );

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      accessToken:
        session?.access_token ?? null,
      loading,

      async signInWithPassword(
        email: string,
        password: string,
      ) {
        const { error } =
          await supabase.auth.signInWithPassword({
            email,
            password,
          });

        if (error) {
          throw error;
        }
      },

      async signInWithGoogle() {
        const { error } =
          await supabase.auth.signInWithOAuth({
            provider: "google",
            options: {
              redirectTo: window.location.origin,
            },
          });

        if (error) {
          throw error;
        }
      },

      async signUpWithPassword(
        email: string,
        password: string,
      ) {
        const { data, error } =
          await supabase.auth.signUp({
            email,
            password,
            options: {
              emailRedirectTo: window.location.origin,
            },
          });

        if (error) {
          throw error;
        }

        return data.session == null;
      },

      async signOut() {
        const { error } =
          await supabase.auth.signOut();

        if (error) {
          throw error;
        }
      },
    }),
    [session, loading],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error(
      "useAuth must be used inside AuthProvider",
    );
  }

  return value;
}
