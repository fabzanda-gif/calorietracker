import type { Metadata, Viewport } from "next";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { AuthGate } from "@/components/auth/AuthGate";
import { RegisterServiceWorker } from "@/components/pwa/RegisterServiceWorker";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SanoSync",
    template: "%s · SanoSync",
  },
  description:
    "SanoSync, il tuo compagno quotidiano per nutrizione, attività e progressi.",
  applicationName: "SanoSync",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      {
        url: "/icons/sanosync-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        url: "/icons/sanosync-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
    apple: [
      {
        url: "/icons/sanosync-180.png",
        sizes: "180x180",
        type: "image/png",
      },
    ],
  },
  appleWebApp: {
    capable: true,
    title: "SanoSync",
    statusBarStyle: "default",
  },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  themeColor: "#ff6865",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <body>
        <RegisterServiceWorker />
        <AuthProvider>
          <AuthGate>
            {children}
          </AuthGate>
        </AuthProvider>
      </body>
    </html>
  );
}
