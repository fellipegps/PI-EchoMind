"use client";

import { useEffect, useState } from "react";
import { configApi, faqApi } from "@/lib/api";
import type { Faq } from "@/lib/api";

export function useTotemData() {
  const [totemFaqs, setTotemFaqs] = useState<Faq[]>(() => {
    if (typeof window === "undefined") return [];

    const cachedFaqs = localStorage.getItem("echomind_offline_faqs");
    if (!cachedFaqs) return [];

    try {
      return JSON.parse(cachedFaqs);
    } catch {
      return [];
    }
  });
  const [voiceGender, setVoiceGender] = useState<"feminina" | "masculina">("feminina");

  useEffect(() => {
    faqApi.listTotem()
      .then((faqs) => {
        setTotemFaqs(faqs);
        localStorage.setItem("echomind_offline_faqs", JSON.stringify(faqs.slice(0, 20)));
      })
      .catch(() => {});

    configApi.get()
      .then(cfg => {
        if (cfg.totem_voice_gender === "masculina" || cfg.totem_voice_gender === "feminina") {
          setVoiceGender(cfg.totem_voice_gender);
        }
      })
      .catch(() => {});
  }, []);

  return { totemFaqs, voiceGender };
}
