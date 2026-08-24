import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SanoSync",
  description: "SanoSync mobile-first nutrition companion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>{children}</body>
    </html>
  );
}
