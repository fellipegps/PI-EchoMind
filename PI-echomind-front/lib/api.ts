/**
 * lib/api.ts
 * Camada de serviço centralizada – toda comunicação com o backend FastAPI passa por aqui.
 * Troque BASE_URL via variável de ambiente NEXT_PUBLIC_API_URL no .env.local
 */

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
  daily_interactions: { date: string; count: number }[];
  top_faqs: { question: string; count: number }[];
}

// ─── Helper interno ───────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `Erro ${res.status}`);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

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
      onError(new Error("A IA não retornou resposta. Verifique os logs: docker compose logs api --tail=50"));
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

  convert: (id: string, answer: string) =>
    request<Faq>(`/unanswered/${id}/convert`, {
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
