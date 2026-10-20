import { describe, expect, it } from "vitest";
import { validatePublicConfig } from "./public-config";

const valid = {
  NEXT_PUBLIC_API_URL: "https://api.example.test",
  NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_synthetic",
  ECHOMIND_REQUIRE_API_URL: "true",
};

describe("production public configuration", () => {
  it("accepts HTTPS origins and a publishable key", () => {
    expect(() => validatePublicConfig(valid)).not.toThrow();
  });
  it.each(["http://localhost:8000", "https://api.example.test/v1", "https://api.example.test/",
    "https://user:password@api.example.test", "https://api.example.test?key=private",
    "https://api.example.test#secret", "https://127.0.0.1", "https://*.example.test"])(
    "rejects invalid API origin %s", (url) => {
      expect(() => validatePublicConfig({ ...valid, NEXT_PUBLIC_API_URL: url }))
        .toThrow("NEXT_PUBLIC_API_URL");
    },
  );
  it("requires the API when publishing the complete application", () => {
    expect(() => validatePublicConfig({ ...valid, NEXT_PUBLIC_API_URL: "" }))
      .toThrow("NEXT_PUBLIC_API_URL");
  });
  it("preserves the existing frontend-only deployment option", () => {
    expect(() => validatePublicConfig({ ...valid, NEXT_PUBLIC_API_URL: "", ECHOMIND_REQUIRE_API_URL: "false" }))
      .not.toThrow();
  });
  it("does not reveal rejected credentials", () => {
    const secret = "sb_secret_never_print_this";
    expect(() => validatePublicConfig({ ...valid, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: secret }))
      .toThrow(/^Configuração pública inválida\. Revise: NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY\.$/);
  });
  it("rejects accidentally exposed backend variables", () => {
    expect(() => validatePublicConfig({ ...valid, NEXT_PUBLIC_DATABASE_URL: "private" }))
      .toThrow("NEXT_PUBLIC_DATABASE_URL");
  });
  it("rejects absent Supabase settings", () => {
    expect(() => validatePublicConfig({})).toThrow("NEXT_PUBLIC_SUPABASE_URL");
  });
});
