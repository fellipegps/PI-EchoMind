import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import { eventApi, EventDTO } from "@/lib/api";
import { CompanyEvent, EventFormState } from "../types";

function toCompanyEvent(dto: EventDTO): CompanyEvent {
  return {
    id: dto.id,
    title: dto.title,
    // O backend armazena datetime completo; pegamos só a data (yyyy-MM-dd)
    event_date: dto.event_date.substring(0, 10),
    event_type: dto.event_type,
    description: dto.description,
    created_at: dto.created_at,
  };
}

export function useEvents() {
  const [events, setEvents] = useState<CompanyEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await eventApi.list();
      setEvents(data.map(toCompanyEvent));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Erro ao carregar eventos: ${msg}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const saveEvent = async (form: EventFormState, editingId: string | null) => {
    if (!form.event_date) return;

    // Backend espera ISO datetime; enviamos noon UTC para evitar problemas de fuso
    const isoDate = `${format(form.event_date, "yyyy-MM-dd")}T12:00:00`;

    const payload = {
      title: form.title,
      description: form.description || undefined,
      event_date: isoDate,
      event_type: form.event_type,
    };

    try {
      if (editingId) {
        const updated = await eventApi.update(editingId, payload);
        setEvents((prev) =>
          prev.map((e) => (e.id === editingId ? toCompanyEvent(updated) : e))
        );
        toast.success("Evento atualizado!");
      } else {
        const created = await eventApi.create(payload);
        setEvents((prev) => [toCompanyEvent(created), ...prev]);
        toast.success("Evento criado!");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Erro ao salvar evento: ${msg}`);
      console.error(err);
      // Não atualiza o estado local — o backend é a fonte da verdade
    }
  };

  const deleteEvent = async (id: string) => {
    try {
      await eventApi.delete(id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      toast.success("Evento excluído!");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Erro ao excluir evento: ${msg}`);
      console.error(err);
    }
  };

  return { events, loading, saveEvent, deleteEvent, refresh: fetchEvents };
}
