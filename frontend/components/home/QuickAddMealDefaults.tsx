"use client";

import { useEffect } from "react";

function setReactInputValue(input: HTMLInputElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  );

  descriptor?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

export function QuickAddMealDefaults() {
  useEffect(() => {
    const onInput = (event: Event) => {
      const target = event.target;

      if (!(target instanceof HTMLInputElement)) {
        return;
      }

      if (target.getAttribute("list") !== "home-quick-known-foods") {
        return;
      }

      if (!target.value.trim()) {
        return;
      }

      const dialog = target.closest<HTMLElement>(
        '[role="dialog"][aria-labelledby="quick-add-title"]',
      );

      if (!dialog) {
        return;
      }

      const nutritionInputs = Array.from(
        dialog.querySelectorAll<HTMLInputElement>(
          'input[type="number"]',
        ),
      );

      const caloriesInput = nutritionInputs[0];

      if (caloriesInput && !caloriesInput.value.trim()) {
        setReactInputValue(caloriesInput, "0");
      }
    };

    document.addEventListener("input", onInput);
    return () => document.removeEventListener("input", onInput);
  }, []);

  return null;
}
