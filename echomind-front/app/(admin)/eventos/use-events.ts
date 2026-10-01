import { useEffect, useState } from "react";
import { format } from "date-fns";
import { toast } from "sonner";

import { eventApi, type CompanyEvent, type EventCourse, type EventInput } from "@/lib/api";
import type { EventFormState } from "./types";

function sortEvents(events: CompanyEvent[]) {
  return [...events].sort((a, b) =>
    a.event_date.localeCompare(b.event_date) || a.title.localeCompare(b.title, "pt-BR")
  );
}

export function useEvents() {
  const [events, setEvents] = useState<CompanyEvent[]>([]);
  const [courses, setCourses] = useState<EventCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([eventApi.list(), eventApi.listCourses()])
      .then(([items, courseItems]) => {
        if (!cancelled) {
          setEvents(sortEvents(items));
          setCourses(courseItems);
        }
      })
      .catch(() => {
        if (!cancelled) toast.error("Erro ao carregar eventos.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveEvent = async (form: EventFormState, editingId: string | null) => {
    const start = form.period?.from;
    if (!start) return false;
    const end = form.period?.to ?? start;
    const payload: EventInput = {
      title: form.title.trim(),
      event_date: format(start, "yyyy-MM-dd"),
      event_end_date: format(end, "yyyy-MM-dd"),
      event_type: form.event_type,
      course: form.course,
      description: form.description.trim() || null,
      location: form.location.trim(),
      image_url: form.image_url.trim() || null,
      link_url: form.link_url.trim() || null,
    };

    setSaving(true);
    try {
      if (editingId) {
        const updated = await eventApi.update(editingId, payload);
        setEvents((current) =>
          sortEvents(current.map((event) => (event.id === editingId ? updated : event)))
        );
        toast.success("Evento atualizado!");
      } else {
        const created = await eventApi.create(payload);
        setEvents((current) => sortEvents([...current, created]));
        toast.success("Evento criado!");
      }
      return true;
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Erro ao salvar evento.");
      return false;
    } finally {
      setSaving(false);
    }
  };

  const deleteEvent = async (id: string) => {
    try {
      await eventApi.delete(id);
      setEvents((current) => current.filter((event) => event.id !== id));
      toast.success("Evento excluído!");
      return true;
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Erro ao excluir evento.");
      return false;
    }
  };

  const createCourse = async (name: string) => {
    setSaving(true);
    try {
      const created = await eventApi.createCourse(name.trim());
      setCourses((current) => {
        if (current.some((course) => course.id === created.id)) return current;
        return [...current, created].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
      });
      toast.success("Curso criado!");
      return created;
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : "Erro ao criar curso.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  return { events, courses, loading, saving, saveEvent, deleteEvent, createCourse };
}
