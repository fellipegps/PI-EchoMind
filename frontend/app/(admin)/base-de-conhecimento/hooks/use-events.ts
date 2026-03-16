import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import { eventsApi, EventResponse } from "@/lib/api";
import { EventFormState } from "../types";

export function useEvents() {
  const [events, setEvents] = useState<EventResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await eventsApi.list();
      setEvents(data);
    } catch (error: any) {
      toast.error(error?.message || "Erro ao carregar eventos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const saveEvent = async (form: EventFormState, editingId: string | null) => {
    if (!form.event_date) return;

    const isoDate = format(form.event_date, "yyyy-MM-dd") + "T00:00:00";

    try {
      if (editingId) {
        const updated = await eventsApi.update(editingId, {
          title: form.title,
          event_date: isoDate,
          event_type: form.event_type,
          description: form.description || null,
        });
        setEvents((prev) => prev.map((e) => (e.id === editingId ? updated : e)));
        toast.success("Evento atualizado!");
      } else {
        const created = await eventsApi.create({
          title: form.title,
          event_date: isoDate,
          event_type: form.event_type,
          description: form.description || null,
        });
        setEvents((prev) => [created, ...prev]);
        toast.success("Evento criado!");
      }
    } catch (error: any) {
      toast.error(error?.message || "Erro ao salvar evento.");
      throw error;
    }
  };

  const deleteEvent = async (id: string) => {
    try {
      await eventsApi.delete(id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      toast.success("Evento excluído!");
    } catch (error: any) {
      toast.error(error?.message || "Erro ao excluir evento.");
    }
  };

  return { events, loading, saveEvent, deleteEvent, refetch: fetchEvents };
}
