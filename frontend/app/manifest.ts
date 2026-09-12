import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "SanoSync",
    short_name: "SanoSync",
    description:
      "Nutrizione, attività e progressi quotidiani in un unico posto.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fff8f6",
    theme_color: "#f2f1ee",
    lang: "it",
    categories: [
      "health",
      "fitness",
      "lifestyle",
    ],
    icons: [
      {
        src: "/icons/sanosync-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/sanosync-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/sanosync-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      {
        name: "Oggi",
        short_name: "Oggi",
        description: "Apri la giornata di oggi",
        url: "/",
        icons: [
          {
            src: "/icons/sanosync-192.png",
            sizes: "192x192",
          },
        ],
      },
      {
        name: "Attività",
        short_name: "Attività",
        url: "/activities",
        icons: [
          {
            src: "/icons/sanosync-192.png",
            sizes: "192x192",
          },
        ],
      },
      {
        name: "Progressi",
        short_name: "Progressi",
        url: "/progress",
        icons: [
          {
            src: "/icons/sanosync-192.png",
            sizes: "192x192",
          },
        ],
      },
      {
        name: "Ricette",
        short_name: "Ricette",
        url: "/recipes",
        icons: [
          {
            src: "/icons/sanosync-192.png",
            sizes: "192x192",
          },
        ],
      },
    ],
  };
}
