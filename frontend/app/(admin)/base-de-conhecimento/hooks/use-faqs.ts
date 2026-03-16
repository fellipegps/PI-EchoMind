import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { faqApi, FaqResponse } from "@/lib/api";

export function useFaqs() {
  const [faqs, setFaqs] = useState<FaqResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchFaqs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await faqApi.list();
      setFaqs(data);
    } catch (error: any) {
      toast.error(error?.message || "Erro ao carregar FAQs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFaqs();
  }, [fetchFaqs]);

  const saveFaq = async (
    faqForm: { question: string; answer: string; category?: string },
    editingId: string | null
  ) => {
    try {
      if (editingId) {
        const updated = await faqApi.update(editingId, faqForm);
        setFaqs((prev) => prev.map((f) => (f.id === editingId ? updated : f)));
        toast.success("FAQ atualizada!");
      } else {
        const created = await faqApi.create(faqForm);
        setFaqs((prev) => [created, ...prev]);
        toast.success("FAQ criada!");
      }
    } catch (error: any) {
      toast.error(error?.message || "Erro ao salvar FAQ.");
      throw error;
    }
  };

  const deleteFaq = async (id: string) => {
    try {
      await faqApi.delete(id);
      setFaqs((prev) => prev.filter((f) => f.id !== id));
      toast.success("FAQ excluída!");
    } catch (error: any) {
      toast.error(error?.message || "Erro ao excluir FAQ.");
    }
  };

  return { faqs, loading, saveFaq, deleteFaq, refetch: fetchFaqs };
}
