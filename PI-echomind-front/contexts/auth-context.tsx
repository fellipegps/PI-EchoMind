"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { authApi, tokenStorage } from "@/lib/api";
import { toast } from "sonner";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [username, setUsername] = useState<string | null>(null);

  // Verifica se já existe token salvo ao montar
  useEffect(() => {
    const token = tokenStorage.get();
    if (token) {
      // Token presente — considera autenticado
      // (validação real viria de um endpoint /me)
      const savedUsername = localStorage.getItem("echomind_username");
      setIsAuthenticated(true);
      setUsername(savedUsername);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (usernameInput: string, password: string) => {
      const { access_token } = await authApi.login(usernameInput, password);
      tokenStorage.set(access_token);
      localStorage.setItem("echomind_username", usernameInput);
      setIsAuthenticated(true);
      setUsername(usernameInput);
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (usernameInput: string, password: string) => {
      await authApi.register(usernameInput, password);
      toast.success("Conta criada! Faça login para continuar.");
      router.push("/login");
    },
    [router]
  );

  const logout = useCallback(() => {
    tokenStorage.clear();
    localStorage.removeItem("echomind_username");
    setIsAuthenticated(false);
    setUsername(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, username, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  return ctx;
}
