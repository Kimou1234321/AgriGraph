import { useSyncExternalStore } from "react";

/** Subscribes to `document.documentElement` classList for Tailwind `dark` mode. */
function subscribeDarkMode(onStoreChange) {
  const el = document.documentElement;
  const observer = new MutationObserver(onStoreChange);
  observer.observe(el, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

function getDarkModeSnapshot() {
  return document.documentElement.classList.contains("dark");
}

function getServerSnapshot() {
  return false;
}

/** Returns true when `class="dark"` is on the document root. */
export function useIsDark() {
  return useSyncExternalStore(subscribeDarkMode, getDarkModeSnapshot, getServerSnapshot);
}
