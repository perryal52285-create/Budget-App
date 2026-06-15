import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Theme = "terminal" | "bubbly";

// Concrete colors for charts. Recharts applies colors as SVG presentation
// attributes, where CSS custom properties don't resolve reliably across
// engines — so we hand charts real hex values keyed off the active theme.
export const THEME_COLORS: Record<Theme, {
  primary: string; danger: string; info: string; warn: string;
  textDim: string; border: string; surface: string;
}> = {
  terminal: {
    primary: "#46d970", danger: "#ff5b5b", info: "#5b9bff", warn: "#e3b341",
    textDim: "#6f9a82", border: "#1e2c24", surface: "#0e1411",
  },
  bubbly: {
    primary: "#ff79b0", danger: "#ff5b7a", info: "#6aa6ff", warn: "#f0a400",
    textDim: "#a8869a", border: "#ffd6ea", surface: "#ffffff",
  },
};

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

export function useChartColors() {
  return THEME_COLORS[useTheme().theme];
}
