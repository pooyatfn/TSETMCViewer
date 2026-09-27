import { useCallback, useEffect, useRef, useState } from "react";

/** Server-Sent Events from /api/v1/stream: a counter that bumps on every committed tick. */
export function useLiveTicks(): { tick: number; lastTick: string | null; connected: boolean } {
  const [state, setState] = useState({ tick: 0, lastTick: null as string | null, connected: false });
  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const es = new EventSource("/api/v1/stream");
    es.addEventListener("hello", () => setState((s) => ({ ...s, connected: true })));
    es.addEventListener("tick", (e) => {
      let lastTick: string | null = null;
      try {
        lastTick = (JSON.parse((e as MessageEvent<string>).data) as { tick?: string }).tick ?? null;
      } catch {
        /* keep null */
      }
      setState((s) => ({ tick: s.tick + 1, lastTick, connected: true }));
    });
    es.onerror = () => setState((s) => ({ ...s, connected: false })); // browser retries itself
    return () => es.close();
  }, []);
  return state;
}

export interface Query<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean; // true only before the first result
  refreshing: boolean; // true while re-fetching with previous data on screen
}

/**
 * Fetch on mount and whenever `deps` change (including the live tick).
 * The previous result stays on screen while refetching (no skeleton flash).
 */
export function useQuery<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]): Query<T> {
  const [state, setState] = useState<Query<T>>({
    data: undefined,
    error: undefined,
    loading: true,
    refreshing: false,
  });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => ({ ...s, refreshing: s.data !== undefined }));
    fnRef
      .current(ctrl.signal)
      .then((data) => setState({ data, error: undefined, loading: false, refreshing: false }))
      .catch((error: unknown) => {
        if (ctrl.signal.aborted) return;
        setState((s) => ({ ...s, error: error as Error, loading: false, refreshing: false }));
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

type Theme = "light" | "dark";

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem("theme");
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

/** Light/dark: follows the OS until the viewer picks one; the choice is remembered per browser. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => storedTheme() ?? systemTheme());
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onChange = () => storedTheme() ?? setTheme(systemTheme());
    mq?.addEventListener("change", onChange);
    return () => mq?.removeEventListener("change", onChange);
  }, []);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("theme", next);
      } catch {
        /* private mode: keep in memory only */
      }
      return next;
    });
  }, []);
  return [theme, toggle];
}

/** "#/fund/123" style routing: the panel has two views, a router library is not needed. */
export function useHashRoute(): [string, (to: string) => void] {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || "/");
  useEffect(() => {
    const onHash = () => {
      setRoute(window.location.hash.slice(1) || "/");
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = useCallback((to: string) => {
    window.location.hash = to;
  }, []);
  return [route, go];
}

/**
 * A counter that bumps every `ms`. Used only for collector health: a stopped
 * collector sends no ticks, so "nothing new arrived" can only be noticed by time.
 */
export function useHeartbeat(ms = 60_000): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setN((x) => x + 1), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return n;
}
