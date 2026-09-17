"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, clearToken, getToken } from "@/lib/api";
import type { CompanyMembership, MeResponse, User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  companies: CompanyMembership[];
  currentCompany: CompanyMembership | null;
  /** 当前企业是否为企业管理员（所有者或持有「管理员」角色） */
  isCompanyAdmin: boolean;
  loading: boolean;
  setCurrentCompanyId: (id: string) => void;
  refresh: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<CompanyMembership[]>([]);
  const [currentCompanyId, setCurrentCompanyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    try {
      const me = await api<MeResponse>("/auth/me");
      setUser(me.user);
      setCompanies(me.companies);
      setCurrentCompanyId((prev) =>
        prev && me.companies.some((c) => c.id === prev)
          ? prev
          : (me.companies[0]?.id ?? null)
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken();
        router.replace("/login");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const logout = useCallback(() => {
    clearToken();
    router.replace("/login");
  }, [router]);

  const currentCompany =
    companies.find((c) => c.id === currentCompanyId) ?? companies[0] ?? null;

  const isCompanyAdmin = currentCompany?.is_company_admin ?? false;

  return (
    <AuthContext.Provider
      value={{
        user,
        companies,
        currentCompany,
        isCompanyAdmin,
        loading,
        setCurrentCompanyId,
        refresh,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
