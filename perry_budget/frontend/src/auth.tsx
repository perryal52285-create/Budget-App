import { createContext, useContext, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "./api";

export type User = {
  id: number;
  username: string;
  display_name: string;
  earner_id: number | null;
  theme: string;
  must_change_password: boolean;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => void;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<{ user: User | null }>("/me"),
    staleTime: 60_000,
  });

  const login = async (username: string, password: string) => {
    await apiPost("/login", { username, password });
    await qc.invalidateQueries({ queryKey: ["me"] });
  };

  const logout = async () => {
    await apiPost("/logout");
    qc.setQueryData(["me"], { user: null });
    qc.clear();
  };

  const refresh = () => qc.invalidateQueries({ queryKey: ["me"] });

  return (
    <Ctx.Provider value={{ user: data?.user ?? null, loading: isLoading, login, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
