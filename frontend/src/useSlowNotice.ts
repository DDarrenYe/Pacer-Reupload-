import { useEffect, useState } from "react";

/** True once `active` has been true for `ms`: used to explain Render's cold starts. */
export function useSlowNotice(active: boolean, ms = 4000): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), ms);
    return () => clearTimeout(timer);
  }, [active, ms]);
  return slow;
}
