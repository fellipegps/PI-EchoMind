/**
 * lib/api.ts
 * Camada de serviço centralizada – toda comunicação com o backend FastAPI passa por aqui.
 * Troque BASE_URL via variável de ambiente NEXT_PUBLIC_API_URL no .env.local
 */

import { supabase } from "./supabase";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Tipos espelhados dos schemas Pydantic ────────────────────────────────────

export interface Faq {
  id: string;
  question: string;
  answer: string;
  show_on_totem: boolean;
  created_at: string;
}

export interface CompanyEvent {
  id: string;
  title: string;
  event_date: string;
  event_type: string;
  description: string | null;
  created_at: string;
}

export interface Config {
  id: string;
  company_name: string;
  description: string | null;
  tone_of_voice: string;
  totem_voice_gender: string;
  website: string | null;
  phone: string | null;
  address: string | null;
  business_hours: string | null;
  updated_at: string | null;
}

export interface UnansweredQuestion {
  id: string;
  canonical_question: string;
  count: number;
  first_asked: string;
  last_asked: string;
  similar_questions: string[];
}

export interface DashboardData {
  total_questions: number;
  unanswered_questions: number;
  avg_response_time: string;
  satisfaction_rate: number;
  daily_interactions: { date: string; count: number }[];
  top_faqs: { question: string; count: number }[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  email: string;
}

export interface AdminUser {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

// ─── Gerenciamento do token JWT ───────────────────────────────────────────────

const TOKEN_KEY = "echomind_token";

export const tokenStore = {
  get: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null,
  set: (token: string) =>
    typeof window !== "undefined" && localStorage.setItem(TOKEN_KEY, token),
  clear: () =>
    typeof window !== "undefined" && localStorage.removeItem(TOKEN_KEY),
};

// ─── Helper interno ───────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...Object.fromEntries(headers.entries()),
    },
  });

  // Token expirado ou inválido — redireciona para login
  if (res.status === 401) {
    tokenStore.clear();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Sessão expirada. Faça login novamente.");
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `Erro ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ══════════════════════════════════════════════════════════════════════════════
//  AUTH
// ══════════════════════════════════════════════════════════════════════════════

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      throw new Error(error.message);
    }

    const accessToken = data.session?.access_token;
    if (!accessToken) {
      throw new Error("Sessão inválida. Tente novamente.");
    }

    tokenStore.set(accessToken);
    return {
      access_token: accessToken,
      token_type: "bearer",
      email: data.user?.email ?? email,
    };
  },

  register: async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      throw new Error(error.message);
    }

    return { email: data.user?.email };
  },

  resetPassword: async (email: string) => {
    const redirectTo =
      typeof window !== "undefined" ? `${window.location.origin}/redefinir-senha` : undefined;
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo });
    if (error) {
      throw new Error(error.message);
    }
  },

  logout: async () => {
    await supabase.auth.signOut();
    tokenStore.clear();
    if (typeof window !== "undefined") window.location.href = "/login";
  },

  isAuthenticated: () => !!tokenStore.get(),

  me: () => request<AdminUser>("/auth/me"),
};

// ══════════════════════════════════════════════════════════════════════════════
//  CHAT – streaming
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Envia uma mensagem e recebe tokens em streaming.
 * @param message  Texto do usuário
 * @param onToken  Callback chamado a cada token recebido
 * @param onDone   Callback chamado quando o stream termina
 */
export async function streamChat(
  message: string,
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
): Promise<void> {
  // 1. Tenta conectar ao backend
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch {
    onError(new Error("Não foi possível conectar ao servidor. Verifique se o backend está rodando."));
    return;
  }

  // 2. Erro HTTP antes do stream (503, 400, etc.)
  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try { const body = await res.json(); detail = body?.detail ?? detail; } catch {}
    onError(new Error(detail));
    return;
  }

  // 3. Lê o stream token a token
  try {
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let receivedAny = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const token = decoder.decode(value, { stream: true });
      if (token) {
        receivedAny = true;
        onToken(token);
      }
    }

    // Stream encerrou sem nenhum token = erro silencioso no backend
    // Neste caso chama onError para o frontend mostrar algo adequado
    if (!receivedAny) {
      onError(new Error("A IA não retornou resposta. Verifique se o backend está rodando em http://localhost:8000"));
      return;
    }

    onDone();
  } catch {
    onError(new Error("Conexão interrompida durante a resposta. Tente novamente."));
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  FAQs
// ══════════════════════════════════════════════════════════════════════════════

export const faqApi = {
  list: () => request<Faq[]>("/faqs"),

  listTotem: () => request<Faq[]>("/faqs/totem"),

  create: (data: { question: string; answer: string; show_on_totem?: boolean }) =>
    request<Faq>("/faqs", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: Partial<{ question: string; answer: string; show_on_totem: boolean }>) =>
    request<Faq>(`/faqs/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  toggleTotem: (id: string) =>
    request<Faq>(`/faqs/${id}/toggle-totem`, { method: "PATCH" }),

  delete: (id: string) =>
    request<void>(`/faqs/${id}`, { method: "DELETE" }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  EVENTS
// ══════════════════════════════════════════════════════════════════════════════

export const eventApi = {
  list: () => request<CompanyEvent[]>("/events"),

  create: (data: { title: string; event_date: string; event_type: string; description?: string }) =>
    request<CompanyEvent>("/events", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: Partial<{ title: string; event_date: string; event_type: string; description: string }>) =>
    request<CompanyEvent>(`/events/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  delete: (id: string) =>
    request<void>(`/events/${id}`, { method: "DELETE" }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  CONFIGURAÇÃO
// ══════════════════════════════════════════════════════════════════════════════

export const configApi = {
  get: () => request<Config>("/config"),

  save: (data: Partial<Config>) =>
    request<Config>("/config", { method: "PUT", body: JSON.stringify(data) }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  PERGUNTAS NÃO RESPONDIDAS
// ══════════════════════════════════════════════════════════════════════════════

export const unansweredApi = {
  list: () => request<UnansweredQuestion[]>("/unanswered"),

  convert: (id: string, answer: string, question?: string) =>
    request<Faq>(`/unanswered/${id}/convert`, {
      method: "POST",
      body: JSON.stringify({ answer, question }),
    }),

  /** Remove a pergunta da lista sem criar FAQ. */
  delete: (id: string) =>
    request<void>(`/unanswered/${id}`, { method: "DELETE" }),

  /**
   * Curadoria Human-in-the-loop:
   * gera embedding do par (pergunta + resposta manual) e salva no pgvector,
   * depois remove a pergunta dos pendentes. Não cria FAQ formal.
   */
  learn: (id: string, answer: string) =>
    request<void>(`/unanswered/${id}/learn`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

export const dashboardApi = {
  get: () => request<DashboardData>("/dashboard"),
};


// ══════════════════════════════════════════════════════════════════════════════
//  FEEDBACK DO TOTEM
// ══════════════════════════════════════════════════════════════════════════════

export const feedbackApi = {
  save: (data: { question: string; answer: string; helpful: boolean }) =>
    request<{ saved: boolean; helpful: boolean }>("/feedback", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  TTS — Text-to-Speech via Google TTS (backend)
// ══════════════════════════════════════════════════════════════════════════════

/** Busca o áudio MP3 do backend e retorna uma Blob URL pronta para Audio(). */
export async function fetchTTSAudio(
  texto: string,
  genero: "feminina" | "masculina" = "feminina"
): Promise<string> {
  const params = new URLSearchParams({ texto, genero });
  const res = await fetch(`${BASE_URL}/tts?${params.toString()}`);

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `Erro TTS ${res.status}`);
  }

  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
