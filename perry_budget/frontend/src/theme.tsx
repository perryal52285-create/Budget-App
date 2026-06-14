import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "terminal" | "bubbly";

type ThemeCtx = { theme: Theme; setTheme: (t: Theme) => void; toggle: () => void };

const Ctx = createContext<ThemeCtx | null>(null);

function read(): Theme {
  const t = document.documentElement.getAttribute("data-theme");
  return t === "bubbly" ? "bubbly" : "terminal";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(read);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("pb-theme", theme);
    } catch {
      /* ignore */
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "bubbly" ? "#fff6fb" : "#0a0e0b");
  }, [theme]);

  const setTheme = (t: Theme) => setThemeState(t);
  const toggle = () => setThemeState((t) => (t === "terminal" ? "bubbly" : "terminal"));

  return <Ctx.Provider value={{ theme, setTheme, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme must be used within ThemeProvider");
  return c;
}
