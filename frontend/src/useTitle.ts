import { useEffect } from "react";

/** Sets the browser tab title, e.g. "Trends · Pacer". */
export function useTitle(title: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · Pacer` : "Pacer";
  }, [title]);
}
