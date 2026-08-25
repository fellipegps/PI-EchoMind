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

export interface CurrentUser {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export type DocumentStatus = "pending" | "processing" | "ready" | "error";

export interface KnowledgeDocument {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  status: DocumentStatus;
  chunk_count: number;
  document_type: string | null;
  document_number: string | null;
  department: string | null;
  published_at: string | null;
  valid_until: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export interface DocumentListResponse {
  documents: KnowledgeDocument[];
  total: number;
}

export interface DocumentUploadMetadata {
  document_type?: string;
  document_number?: string;
  department?: string;
  published_at?: string;
  valid_until?: string;
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

const CLIENT_ERROR_MESSAGE = "Não foi possível concluir a solicitação.";
const SERVER_ERROR_MESSAGE = "O servidor não conseguiu concluir a solicitação.";
const CONNECTION_ERROR_MESSAGE = "Não foi possível conectar ao servidor.";

async function handleAuthenticatedResponse<T>(res: Response): Promise<T> {
  // Token expirado ou inválido — redireciona para login
  if (res.status === 401) {
    tokenStore.clear();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Sessão expirada. Faça login novamente.");
  }

  if (!res.ok) {
    throw new Error(res.status >= 500 ? SERVER_ERROR_MESSAGE : CLIENT_ERROR_MESSAGE);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  try {
    return (await res.json()) as T;
  } catch {
    throw new Error(SERVER_ERROR_MESSAGE);
  }
}

async function authenticatedFetch<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new Error(CONNECTION_ERROR_MESSAGE);
  }

  return handleAuthenticatedResponse<T>(res);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return authenticatedFetch<T>(path, {
    ...init,
    headers: {
      ...Object.fromEntries(headers.entries()),
    },
  });
}

async function multipartRequest<T>(path: string, formData: FormData): Promise<T> {
  const token = tokenStore.get();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return authenticatedFetch<T>(path, {
    method: "POST",
    headers: {
      ...Object.fromEntries(headers.entries()),
    },
    body: formData,
  });
}

async function publicRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");

  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...Object.fromEntries(headers.entries()),
    },
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `Erro ${res.status}`);
  }

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

  register: async (
    email: string,
    password: string,
    metadata?: { fullName?: string; companyName?: string }
  ) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: metadata?.fullName,
          company_name: metadata?.companyName,
        },
      },
    });
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

  me: () => request<CurrentUser>("/auth/me"),
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
  tenantId: string,
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
      body: JSON.stringify({ message, tenant_id: tenantId }),
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

  listTotem: (tenantId: string) =>
    publicRequest<Faq[]>(`/faqs/totem?tenant_id=${encodeURIComponent(tenantId)}`),

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
//  DOCUMENTOS
// ══════════════════════════════════════════════════════════════════════════════

const DOCUMENT_METADATA_FIELDS = [
  "document_type",
  "document_number",
  "department",
  "published_at",
  "valid_until",
] as const satisfies readonly (keyof DocumentUploadMetadata)[];

export const documentApi = {
  list: () =>
    request<DocumentListResponse>("/documents", { method: "GET" }),

  get: (id: string) =>
    request<KnowledgeDocument>(`/documents/${encodeURIComponent(id)}`, { method: "GET" }),

  upload: (file: File, metadata: DocumentUploadMetadata = {}) => {
    const formData = new FormData();
    formData.append("file", file);
    for (const field of DOCUMENT_METADATA_FIELDS) {
      const value = metadata[field];
      if (value !== undefined) {
        formData.append(field, value);
      }
    }

    return multipartRequest<KnowledgeDocument>("/documents/upload", formData);
  },

  delete: (id: string) =>
    request<void>(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

// ══════════════════════════════════════════════════════════════════════════════
//  CONFIGURAÇÃO
// ══════════════════════════════════════════════════════════════════════════════

export const configApi = {
  get: () => request<Config>("/config"),

  getPublic: (tenantId: string) =>
    publicRequest<Config>(`/config/public?tenant_id=${encodeURIComponent(tenantId)}`),

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
  save: (data: { question: string; answer: string; helpful: boolean; tenant_id: string }) =>
    publicRequest<{ saved: boolean; helpful: boolean }>("/feedback", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

