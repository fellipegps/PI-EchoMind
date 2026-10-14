/** Build-time checks. Diagnostics contain variable names only. */
function httpsOrigin(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.pathname === "/" &&
      !url.username && !url.password && !url.search && !url.hash &&
      !/[\s*\\]/.test(value) && !value.endsWith("/") &&
      /^[a-z0-9.-]+$/i.test(url.hostname) && !/CHANGE_ME/i.test(value) &&
      url.hostname.includes(".") && !url.hostname.endsWith(".localhost") &&
      !/^(localhost|127\.|\[::1\])/.test(url.hostname);
  } catch {
    return false;
  }
}

export function validatePublicConfig(environment: Record<string, string | undefined>): void {
  const invalid = new Set<string>();
  const api = environment.NEXT_PUBLIC_API_URL?.trim();
  if ((api && !httpsOrigin(api)) || (!api && environment.ECHOMIND_REQUIRE_API_URL === "true")) {
    invalid.add("NEXT_PUBLIC_API_URL");
  }
  if (!httpsOrigin(environment.NEXT_PUBLIC_SUPABASE_URL ?? "")) {
    invalid.add("NEXT_PUBLIC_SUPABASE_URL");
  }
  const key = environment.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";
  if (!/^sb_publishable_[A-Za-z0-9_-]+$/.test(key) || /CHANGE_ME|\.\.\./i.test(key)) {
    invalid.add("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY");
  }
  for (const [name, value] of Object.entries(environment)) {
    if (name.startsWith("NEXT_PUBLIC_") && (
      /DATABASE_URL|SUPABASE_SECRET|SERVICE_ROLE|GROQ_API_KEY/.test(name) ||
      /^(sb_secret_|gsk_)/.test(value ?? "")
    )) invalid.add(name);
  }
  if (invalid.size) {
    throw new Error(`Configuração pública inválida. Revise: ${[...invalid].sort().join(", ")}.`);
  }
}
