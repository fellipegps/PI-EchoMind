import { useState, useEffect } from "react";
import { toast } from "sonner";
import { faqApi } from "@/lib/api";
import type { Faq } from "@/lib/api";

export function useFaqs() {
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [loading, setLoading] = useState(true);

  // ─── Carrega FAQs do backend ─────────────────────────────────────────────
  useEffect(() => {
    faqApi
      .list()
      .then(setFaqs)
      .catch(() => toast.error("Erro ao carregar FAQs."))
      .finally(() => setLoading(false));
  }, []);

  // ─── Criar / Editar ──────────────────────────────────────────────────────
  const saveFaq = async (
    form: { question: string; answer: string },
    editingId: string | null
  ) => {
    try {
      if (editingId) {
        const updated = await faqApi.update(editingId, form);
        setFaqs((prev) => prev.map((f) => (f.id === editingId ? updated : f)));
        toast.success("FAQ atualizada!");
      } else {
        const created = await faqApi.create({ ...form, show_on_totem: false });
        setFaqs((prev) => [created, ...prev]);
        toast.success("FAQ criada!");
      }
    } catch (err: any) {
      toast.error(err.message ?? "Erro ao salvar FAQ.");
      throw err; // re-lança para o componente manter o dialog aberto
    }
  };

  // ─── Deletar ─────────────────────────────────────────────────────────────
  const deleteFaq = async (id: string) => {
    try {
      await faqApi.delete(id);
      setFaqs((prev) => prev.filter((f) => f.id !== id));
      toast.success("FAQ excluída!");
    } catch (err: any) {
      toast.error(err.message ?? "Erro ao excluir FAQ.");
    }
  };

  // ─── Toggle Totem ─────────────────────────────────────────────────────────
  const toggleTotemStatus = async (id: string) => {
    try {
      const updated = await faqApi.toggleTotem(id);
      setFaqs((prev) => prev.map((f) => (f.id === id ? updated : f)));
    } catch (err: any) {
      // Backend retorna 409 quando limite de 4 FAQs no totem é atingido
      toast.error(err.message ?? "Erro ao alterar status do totem.");
    }
  };

  return { faqs, loading, saveFaq, deleteFaq, toggleTotemStatus };
}