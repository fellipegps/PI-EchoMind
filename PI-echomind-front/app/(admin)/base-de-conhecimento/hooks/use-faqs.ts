import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { faqApi, FaqDTO } from "@/lib/api";
import { Faq } from "../types";

function toFaq(dto: FaqDTO): Faq {
  return {
    id: dto.id,
    question: dto.question,
    answer: dto.answer,
    category: dto.category,
    show_on_totem: false, // campo local — ainda não existe no backend
    created_at: dto.created_at,
  };
}

export function useFaqs() {
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFaqs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await faqApi.list();
      // Preserva o estado local de show_on_totem ao recarregar
      setFaqs((prev) =>
        data.map((dto) => {
          const existing = prev.find((f) => f.id === dto.id);
          return { ...toFaq(dto), show_on_totem: existing?.show_on_totem ?? false };
        })
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      setError(msg);
      toast.error(`Erro ao carregar FAQs: ${msg}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFaqs();
  }, [fetchFaqs]);

  const saveFaq = async (
    faqForm: { question: string; answer: string },
    editingId: string | null
  ) => {
    try {
      if (editingId) {
        const updated = await faqApi.update(editingId, faqForm);
        setFaqs((prev) =>
          prev.map((f) =>
            f.id === editingId
              ? { ...toFaq(updated), show_on_totem: f.show_on_totem }
              : f
          )
        );
        toast.success("FAQ atualizada!");
      } else {
        const created = await faqApi.create({ ...faqForm, category: "Geral" });
        setFaqs((prev) => [toFaq(created), ...prev]);
        toast.success("FAQ criada!");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Erro ao salvar FAQ: ${msg}`);
      console.error(err);
      // Não atualiza o estado local — só o backend é fonte da verdade
    }
  };

  const deleteFaq = async (id: string) => {
    try {
      await faqApi.delete(id);
      setFaqs((prev) => prev.filter((f) => f.id !== id));
      toast.success("FAQ excluída!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Erro ao excluir FAQ: ${msg}`);
      console.error(err);
    }
  };

  const toggleTotemStatus = (id: string) => {
    setFaqs((prev) => {
      const faqToUpdate = prev.find((f) => f.id === id);
      const activeCount = prev.filter((f) => f.show_on_totem).length;

      if (faqToUpdate && !faqToUpdate.show_on_totem && activeCount >= 4) {
        toast.error("Limite máximo de 4 FAQs no totem atingido!");
        return prev;
      }

      return prev.map((f) =>
        f.id === id ? { ...f, show_on_totem: !f.show_on_totem } : f
      );
    });
  };

  return { faqs, loading, error, saveFaq, deleteFaq, toggleTotemStatus, refresh: fetchFaqs };
}
