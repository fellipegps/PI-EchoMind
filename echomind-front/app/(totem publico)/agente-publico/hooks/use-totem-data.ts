"use client";

import { useEffect, useState } from "react";
import { configApi, faqApi } from "@/lib/api";
import type { Faq } from "@/lib/api";

function getTenantIdFromLocation() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("tenant") ?? "";
}

export function useTotemData() {
  const [tenantId] = useState(getTenantIdFromLocation);

  const [totemFaqs, setTotemFaqs] = useState<Faq[]>(() => {
    if (typeof window === "undefined") return [];

    const params = new URLSearchParams(window.location.search);
    const cacheTenantId = params.get("tenant") ?? "default";
    const cachedFaqs = localStorage.getItem(`echomind_offline_faqs:${cacheTenantId}`);
    if (!cachedFaqs) return [];

    try {
      return JSON.parse(cachedFaqs);
    } catch {
      return [];
    }
  });
  const [voiceGender, setVoiceGender] = useState<"feminina" | "masculina">("feminina");

  useEffect(() => {
    if (!tenantId) return;

    faqApi.listTotem(tenantId)
      .then((faqs) => {
        setTotemFaqs(faqs);
        localStorage.setItem(`echomind_offline_faqs:${tenantId}`, JSON.stringify(faqs.slice(0, 20)));
      })
      .catch(() => {});

    configApi.getPublic(tenantId)
      .then(cfg => {
        if (cfg.totem_voice_gender === "masculina" || cfg.totem_voice_gender === "feminina") {
          setVoiceGender(cfg.totem_voice_gender);
        }
      })
      .catch(() => {});
  }, [tenantId]);

  return { totemFaqs, voiceGender, tenantId };
}
