"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { toBlob } from "html-to-image";
import styles from "./RecipeShareButton.module.css";

interface RecipeShareButtonProps {
  name: string;
  imageUrl?: string | null;
  calories: number;
  protein?: number | null;
  servings?: number | null;
  preparation?: string | null;
}

export function RecipeShareButton({
  name,
  imageUrl,
  calories,
  protein,
  servings,
  preparation,
}: RecipeShareButtonProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);

  const portions = Math.max(
    1,
    Number(servings || 1),
  );

  const kcalPerPortion = Math.round(
    Number(calories || 0) / portions,
  );

  const proteinPerPortion =
    protein != null
      ? Math.round(Number(protein || 0) / portions)
      : null;

  useEffect(() => {
    setMounted(true);

    return () => {
      setMounted(false);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      setBlob(null);
      setBusy(false);
    }
  }, [open]);

  async function waitForImage() {
    const image = imageRef.current;

    if (!image || image.complete) {
      return;
    }

    await new Promise<void>((resolve) => {
      image.addEventListener(
        "load",
        () => resolve(),
        { once: true },
      );

      image.addEventListener(
        "error",
        () => resolve(),
        { once: true },
      );
    });
  }

  async function generate() {
    if (!cardRef.current || busy) {
      return;
    }

    setBusy(true);

    try {
      await waitForImage();

      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => resolve());
        });
      });

      const result = await toBlob(
        cardRef.current,
        {
          width: 1080,
          height: 1350,
          pixelRatio: 1,
          backgroundColor: "#ffffff",
          cacheBust: true,
          skipFonts: false,
          style: {
            animation: "none",
            transition: "none",
            transform: "none",
          },
        },
      );

      if (!result) {
        throw new Error(
          "Impossibile creare il frame.",
        );
      }

      setBlob(result);
    } catch (error) {
      console.error(
        "SanoSync share image error:",
        error,
      );
    } finally {
      setBusy(false);
    }
  }

  function download() {
    if (!blob) {
      return;
    }

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = "sanosync-ricetta.png";

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  async function share() {
    if (!blob) {
      return;
    }

    const file = new File(
      [blob],
      "sanosync-ricetta.png",
      {
        type: "image/png",
      },
    );

    if (
      typeof navigator !== "undefined" &&
      navigator.share &&
      navigator.canShare?.({
        files: [file],
      })
    ) {
      try {
        await navigator.share({
          title: name,
          text: `La mia ricetta SanoSync: ${name}`,
          files: [file],
        });

        return;
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return;
        }
      }
    }

    download();
  }

  const modal =
    open && mounted
      ? createPortal(
          <div
            className={styles.overlay}
            role="dialog"
            aria-modal="true"
            aria-label="Condividi ricetta"
          >
            <div className={styles.dialog}>
              <header
                className={styles.dialogHeader}
              >
                <div>
                  <strong>
                    Condividi ricetta
                  </strong>

                  <span>
                    Crea il tuo frame SanoSync
                  </span>
                </div>

                <button
                  type="button"
                  className={styles.closeButton}
                  onClick={() => setOpen(false)}
                  aria-label="Chiudi"
                >
                  ×
                </button>
              </header>

              <main
                className={styles.previewArea}
              >
                <div
                  ref={cardRef}
                  className={styles.shareCard}
                >
                  <div
                    className={styles.shareTop}
                  >
                    <div
                      className={styles.logo}
                    >
                      <img
                        src="/Logowhite.png"
                        alt="SanoSync"
                      />
                    </div>

                    <div
                      className={
                        styles.recipeLabel
                      }
                    >
                      RICETTA
                    </div>
                  </div>

                  <div
                    className={styles.imageFrame}
                  >
                    {imageUrl ? (
                      <img
                        ref={imageRef}
                        src={imageUrl}
                        alt=""
                      />
                    ) : (
                      <div
                        className={
                          styles.imagePlaceholder
                        }
                      >
                        S
                      </div>
                    )}
                  </div>

                  <div
                    className={styles.shareContent}
                  >
                    <div
                      className={styles.eyebrow}
                    >
                      PRONTA QUANDO TI SERVE
                    </div>

                    <h2>{name}</h2>

                    <div
                      className={styles.stats}
                    >
                      <div>
                        <strong>
                          {kcalPerPortion}
                        </strong>

                        <span>
                          kcal / porzione
                        </span>
                      </div>

                      {proteinPerPortion !=
                        null && (
                        <div>
                          <strong>
                            {proteinPerPortion} g
                          </strong>

                          <span>
                            proteine / porzione
                          </span>
                        </div>
                      )}
                    </div>

                    <div
                      className={
                        styles.servings
                      }
                    >
                      {portions}{" "}
                      {portions === 1
                        ? "porzione"
                        : "porzioni"}
                    </div>

                    {preparation?.trim() ? (
                      <div
                        className={
                          styles.preparation
                        }
                      >
                        <div
                          className={
                            styles.preparationLabel
                          }
                        >
                          PREPARAZIONE
                        </div>

                        <p>
                          {preparation.trim()}
                        </p>
                      </div>
                    ) : null}
                  </div>

                  <div
                    className={styles.shareFooter}
                  >
                    <span>SanoSync</span>

                    <span>
                      mangia bene. vivi meglio.
                    </span>
                  </div>
                </div>
              </main>

              <footer
                className={styles.dialogActions}
              >
                {!blob ? (
                  <button
                    type="button"
                    className={
                      styles.primaryButton
                    }
                    onClick={() =>
                      void generate()
                    }
                    disabled={busy}
                  >
                    {busy
                      ? "Creo il frame…"
                      : "Genera frame"}
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      className={
                        styles.primaryButton
                      }
                      onClick={() =>
                        void share()
                      }
                    >
                      Condividi
                    </button>

                    <button
                      type="button"
                      className={
                        styles.secondaryButton
                      }
                      onClick={download}
                    >
                      Scarica PNG
                    </button>
                  </>
                )}
              </footer>
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        type="button"
        className={styles.shareButton}
        onClick={() => setOpen(true)}
      >
        Condividi
      </button>

      {modal}
    </>
  );
}
