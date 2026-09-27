import { createContext, useContext } from "react";

import type { Tokens } from "./theme";

/** Resolved chart tokens for the active theme; re-read by App when the theme flips. */
export const TokensContext = createContext<Tokens | null>(null);

export function useTokens(): Tokens {
  const t = useContext(TokensContext);
  if (!t) throw new Error("useTokens outside <TokensContext.Provider>");
  return t;
}
