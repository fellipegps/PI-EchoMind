/**
 * Cliente HTTP centralizado para a API EchoMind.
 * Lê a URL base de NEXT_PUBLIC_API_URL (default: http://localhost:8000).
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Token helpers ─────────────────────────────────────────────────────────────

const TOKEN_KEY = "echomind_token";

export const tokenStorage = {
  get: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
  },
  set: (token: string) => {
    if (typeof window === "undefined") return;
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(TOKEN_KEY);
  },
};

// ─── HTTP client ───────────────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = tokenStorage.get();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(
      `Não foi possível conectar ao servidor (${BASE_URL}). Verifique se o backend está rodando.`
    );
  }

  if (!res.ok) {
    let detail = `Erro ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = await res.text().catch(() => detail);
    }
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ─── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export const authApi = {
  /**
   * O backend usa OAuth2PasswordRequestForm (form-data, não JSON).
   */
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const body = new URLSearchParams({ username, password });

    let res: Response;
    try {
      res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });
    } catch {
      throw new Error(
        `Não foi possível conectar ao servidor (${BASE_URL}). Verifique se o backend está rodando.`
      );
    }

    if (!res.ok) {
      let detail = `Erro ${res.status}`;
      try {
        const b = await res.json();
        detail = b?.detail ?? JSON.stringify(b);
      } catch {
        /* noop */
      }
      throw new Error(detail);
    }

    return res.json();
  },

  register: (username: string, password: string) =>
    request<{ id: string; username: string }>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
};

// ─── FAQ ──────────────────────────────────────────────────────────────────────

export interface FaqDTO {
  id: string;
  question: string;
  answer: string;
  category: string;
  created_at: string;
}

export interface FaqCreatePayload {
  question: string;
  answer: string;
  category?: string;
}

export interface FaqUpdatePayload {
  question?: string;
  answer?: string;
  category?: string;
}

export const faqApi = {
  list: () => request<FaqDTO[]>("/api/v1/faqs/"),
  create: (payload: FaqCreatePayload) =>
    request<FaqDTO>("/api/v1/faqs/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: FaqUpdatePayload) =>
    request<FaqDTO>(`/api/v1/faqs/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    request<void>(`/api/v1/faqs/${id}`, { method: "DELETE" }),
};

// ─── Events ───────────────────────────────────────────────────────────────────

export interface EventDTO {
  id: string;
  title: string;
  description: string | null;
  event_date: string;
  event_type: string;
  created_at: string;
}

export interface EventCreatePayload {
  title: string;
  description?: string;
  event_date: string;
  event_type: string;
}

export interface EventUpdatePayload {
  title?: string;
  description?: string;
  event_date?: string;
  event_type?: string;
}

export const eventApi = {
  list: () => request<EventDTO[]>("/api/v1/events/"),
  create: (payload: EventCreatePayload) =>
    request<EventDTO>("/api/v1/events/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: EventUpdatePayload) =>
    request<EventDTO>(`/api/v1/events/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  delete: (id: string) =>
    request<void>(`/api/v1/events/${id}`, { method: "DELETE" }),
};
