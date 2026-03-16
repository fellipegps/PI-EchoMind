const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ─── Token helpers ────────────────────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("echomind_token");
}

export function setToken(token: string): void {
  localStorage.setItem("echomind_token", token);
}

export function removeToken(): void {
  localStorage.removeItem("echomind_token");
}

// ─── Core fetch ───────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {},
  authenticated = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (authenticated) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    removeToken();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Sessão expirada. Faça login novamente.");
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Erro ${res.status}: ${res.statusText}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AdminResponse {
  id: string;
  username: string;
}

export const authApi = {
  login: async (username: string, password: string): Promise<TokenResponse> => {
    const body = new URLSearchParams({ username, password });
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Usuário ou senha incorretos.");
    }
    return res.json();
  },

  register: async (username: string, password: string): Promise<AdminResponse> => {
    return request<AdminResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }, false);
  },
};

// ─── FAQs ─────────────────────────────────────────────────────────────────────

export interface FaqResponse {
  id: string;
  question: string;
  answer: string;
  category: string;
  created_at: string;
}

export interface FaqCreate {
  question: string;
  answer: string;
  category?: string;
}

export const faqApi = {
  list: (): Promise<FaqResponse[]> =>
    request<FaqResponse[]>("/faqs", {}, false),

  create: (data: FaqCreate): Promise<FaqResponse> =>
    request<FaqResponse>("/faqs", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<FaqCreate>): Promise<FaqResponse> =>
    request<FaqResponse>(`/faqs/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string): Promise<void> =>
    request<void>(`/faqs/${id}`, { method: "DELETE" }),

  ask: (question: string): Promise<{ answer: string; source_faq_id?: string }> =>
    request<{ answer: string; source_faq_id?: string }>("/faqs/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }, false),
};

// ─── Events ───────────────────────────────────────────────────────────────────

export interface EventResponse {
  id: string;
  title: string;
  description: string | null;
  event_date: string;
  event_type: string;
  created_at: string;
}

export interface EventCreate {
  title: string;
  description?: string | null;
  event_date: string;
  event_type?: string;
}

export const eventsApi = {
  list: (): Promise<EventResponse[]> =>
    request<EventResponse[]>("/events", {}, false),

  upcoming: (): Promise<EventResponse[]> =>
    request<EventResponse[]>("/events/upcoming", {}, false),

  create: (data: EventCreate): Promise<EventResponse> =>
    request<EventResponse>("/events", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<EventCreate>): Promise<EventResponse> =>
    request<EventResponse>(`/events/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  delete: (id: string): Promise<void> =>
    request<void>(`/events/${id}`, { method: "DELETE" }),
};

// ─── Metrics ──────────────────────────────────────────────────────────────────

export interface MetricsOverview {
  total_interactions: number;
  unanswered_count: number;
  total_faqs: number;
  total_events: number;
  daily_interactions: { date: string; count: number }[];
  top_faqs: { question: string; count: number }[];
}

export const metricsApi = {
  overview: (): Promise<MetricsOverview> =>
    request<MetricsOverview>("/metrics/overview"),
};

// ─── Unanswered ───────────────────────────────────────────────────────────────

export interface UnansweredResponse {
  id: string;
  question: string;
  created_at: string;
  resolved: boolean;
}

export const unansweredApi = {
  list: (): Promise<UnansweredResponse[]> =>
    request<UnansweredResponse[]>("/unanswered"),

  resolve: (id: string): Promise<{ status: string }> =>
    request<{ status: string }>(`/unanswered/${id}/resolve`, {
      method: "PATCH",
    }),
};
