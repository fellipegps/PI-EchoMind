import { useState, useEffect } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import { eventApi } from "@/lib/api";
import type { CompanyEvent } from "@/lib/api";

export interface EventFormState {
  title: string;
  event_date: Date | undefined;
  event_type: string;
  description: string;
  location: string;
  published: boolean;
}

export function useEvents() {
  const [events, setEvents] = useState<CompanyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // ─── Carrega Eventos do backend ──────────────────────────────────────────
  useEffect(() => {
    eventApi
      .list()
      .then(setEvents)
      .catch(() => toast.error("Erro ao carregar eventos."))
      .finally(() => setLoading(false));
  }, []);

  // ─── Criar / Editar ──────────────────────────────────────────────────────
  const saveEvent = async (form: EventFormState, editingId: string | null) => {
    if (!form.event_date) return false;

    const formattedDate = format(form.event_date, "yyyy-MM-dd");
    const payload = {
      title: form.title,
      event_date: formattedDate,
      event_type: form.event_type,
      description: form.description || undefined,
      location: form.location,
      published: form.published,
    };

    setSaving(true);
    try {
      if (editingId) {
        const updated = await eventApi.update(editingId, payload);
        setEvents((prev) => prev.map((e) => (e.id === editingId ? updated : e)));
        toast.success("Evento atualizado!");
      } else {
        const created = await eventApi.create(payload);
        setEvents((prev) => [created, ...prev]);
        toast.success("Evento criado!");
      }
      return true;
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao salvar evento.");
      return false;
    } finally {
      setSaving(false);
    }
  };

  // ─── Deletar ─────────────────────────────────────────────────────────────
  const deleteEvent = async (id: string) => {
    try {
      await eventApi.delete(id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      toast.success("Evento excluído!");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erro ao excluir evento.");
    }
  };

  return { events, loading, saving, saveEvent, deleteEvent };
}
