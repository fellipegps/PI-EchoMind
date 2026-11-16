import { isAuthSessionMissingError, type AuthError, type Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export class SessionExpiredError extends Error {
  constructor() {
    super("Sessão expirada. Faça login novamente.");
  }
}

const SESSION_CHECK_ERROR = "Não foi possível validar sua sessão no painel. Tente novamente.";

type SessionResult = { data: { session: Session | null }; error: AuthError | null };

function requireSession({ data: { session }, error }: SessionResult): Session {
  if (isAuthSessionMissingError(error) || (!session && !error)) {
    throw new SessionExpiredError();
  }
  if (error || !session) throw new Error(SESSION_CHECK_ERROR);
  return session;
}

let pendingRefresh: { token: string; session: Promise<Session> } | undefined;

function sessionAfterUnauthorized(rejectedSession: Session): Promise<Session> {
  const rejectedToken = rejectedSession.access_token;
  if (pendingRefresh?.token === rejectedToken) return pendingRefresh.session;

  const session = (async () => {
    const current = requireSession(await supabase.auth.getSession());
    if (current.user.id !== rejectedSession.user.id) throw new Error(SESSION_CHECK_ERROR);
    if (current.access_token !== rejectedToken) return current;

    const renewed = requireSession(await supabase.auth.refreshSession());
    if (renewed.user.id !== rejectedSession.user.id) throw new Error(SESSION_CHECK_ERROR);
    return renewed;
  })().finally(() => {
    if (pendingRefresh?.session === session) pendingRefresh = undefined;
  });

  pendingRefresh = { token: rejectedToken, session };
  return session;
}

export async function fetchFromApi(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    throw new Error("Não foi possível conectar ao servidor.");
  }
}

export async function fetchWithSession(url: string, init: RequestInit): Promise<Response> {
  const session = requireSession(await supabase.auth.getSession());
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  const response = await fetchFromApi(url, { ...init, headers });
  if (response.status !== 401) return response;

  // A API valida a credencial antes de executar a operação protegida.
  const renewed = await sessionAfterUnauthorized(session);
  const retryHeaders = new Headers(headers);
  retryHeaders.set("Authorization", `Bearer ${renewed.access_token}`);
  const retried = await fetchFromApi(url, { ...init, headers: retryHeaders });
  if (retried.status === 401) throw new Error(SESSION_CHECK_ERROR);
  return retried;
}
