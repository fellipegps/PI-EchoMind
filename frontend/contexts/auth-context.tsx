"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { useRouter } from "next/navigation";
import { authApi, getToken, setToken, removeToken, AdminResponse } from "@/lib/api";

interface AuthContextValue {
  admin: AdminResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [admin, setAdmin] = useState<AdminResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check if there's already a token stored
  useEffect(() => {
    const token = getToken();
    if (token) {
      // Decode the JWT payload to get admin info (no validation – just reading)
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        // If token is expired, clean up
        if (payload.exp && payload.exp * 1000 < Date.now()) {
          removeToken();
        } else {
          setAdmin({ id: payload.sub, username: payload.username || "Admin" });
        }
      } catch {
        removeToken();
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await authApi.login(username, password);
      setToken(data.access_token);
      // Decode payload for basic info
      const payload = JSON.parse(atob(data.access_token.split(".")[1]));
      setAdmin({ id: payload.sub, username });
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (username: string, password: string) => {
      const data = await authApi.register(username, password);
      setAdmin(data);
      router.push("/login");
    },
    [router]
  );

  const logout = useCallback(() => {
    removeToken();
    setAdmin(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        admin,
        isAuthenticated: !!admin,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
