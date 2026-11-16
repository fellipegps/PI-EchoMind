import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;

export const supabase = createClient(supabaseUrl, supabasePublishableKey);

if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem("echomind_token");
  } catch {
    // O navegador pode bloquear o acesso ao armazenamento.
  }
}
