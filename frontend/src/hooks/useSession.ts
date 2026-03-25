import { useEffect } from "react";
import { getSession } from "../lib/api";
import { useAppStore } from "../stores/appStore";

export function useSession() {
  const setAuth = useAppStore((s) => s.setAuth);
  const clearAuth = useAppStore((s) => s.clearAuth);
  const token = useAppStore((s) => s.token);

  useEffect(() => {
    const storedToken = localStorage.getItem("kg_token");
    if (!storedToken) return;

    let cancelled = false;

    async function validate() {
      try {
        const user = await getSession(storedToken!);
        if (!cancelled) {
          setAuth(storedToken!, user);
        }
      } catch {
        if (!cancelled) {
          clearAuth();
        }
      }
    }

    if (!token) {
      validate();
    }

    return () => {
      cancelled = true;
    };
  }, [token, setAuth, clearAuth]);
}
