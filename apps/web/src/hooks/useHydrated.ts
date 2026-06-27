import { useSyncExternalStore } from "react";

// SSR-safe hydration guard. Server snapshot = false (matches SSR markup), client
// snapshot = true; React swaps after hydration. Avoids setState-in-effect.
const emptySubscribe = () => () => {};

export function useHydrated() {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
}
