"use client";

import { useMemo, useRef, useState } from "react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarIcon, CalendarDays, Loader2, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import type { CompanyEvent } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { EVENT_TYPES } from "./constants";
import type { EventFormState } from "./types";
import { useEvents } from "./use-events";

const EMPTY_FORM: EventFormState = {
  title: "",
  period: undefined,
  event_type: "outro",
  course: "Geral",
  description: "",
  location: "",
  image_url: "",
  link_url: "",
};

function parseEventDate(value: string) {
  return new Date(`${value}T12:00:00`);
}

function formatPeriod(start: string, end: string) {
  const first = format(parseEventDate(start), "dd/MM/yyyy", { locale: ptBR });
  if (start === end) return first;
  return `${first} – ${format(parseEventDate(end), "dd/MM/yyyy", { locale: ptBR })}`;
}

function isValidExternalUrl(value: string, protocols: string[]) {
  if (!value) return true;
  if (/\s|[\u0000-\u001f\u007f]/.test(value)) return false;
  try {
    const url = new URL(value);
    return protocols.includes(url.protocol) && Boolean(url.hostname) && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function EventsManager() {
  const { events, courses, loading, saving, saveEvent, deleteEvent, createCourse } = useEvents();
  const searchInput = useRef<HTMLInputElement | null>(null);
  const formTrigger = useRef<HTMLElement | null>(null);
  const deleteTrigger = useRef<HTMLButtonElement | null>(null);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CompanyEvent | null>(null);
  const [deleting, setDeleting] = useState<CompanyEvent | null>(null);
  const [form, setForm] = useState<EventFormState>(EMPTY_FORM);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [creatingCourse, setCreatingCourse] = useState(false);
  const [newCourseName, setNewCourseName] = useState("");

  const filteredEvents = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("pt-BR");
    if (!term) return events;
    return events.filter((event) =>
      [event.title, event.event_type, event.course, event.location]
        .join(" ")
        .toLocaleLowerCase("pt-BR")
        .includes(term)
    );
  }, [events, search]);

  const openForm = (event?: CompanyEvent) => {
    formTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setEditing(event ?? null);
    setPreviewFailed(false);
    setCreatingCourse(false);
    setNewCourseName("");
    setForm(
      event
        ? {
            title: event.title,
            period: {
              from: parseEventDate(event.event_date),
              to: parseEventDate(event.event_end_date),
            },
            event_type: event.event_type,
            course: event.course,
            description: event.description ?? "",
            location: event.location,
            image_url: event.image_url ?? "",
            link_url: event.link_url ?? "",
          }
        : EMPTY_FORM
    );
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.period?.from || !form.location.trim() || !form.course.trim()) {
      toast.error("Preencha título, período, curso e local.");
      return;
    }
    if (!isValidExternalUrl(form.image_url.trim(), ["https:"])) {
      toast.error("A URL da imagem deve ser um endereço https válido.");
      return;
    }
    if (!isValidExternalUrl(form.link_url.trim(), ["http:", "https:"])) {
      toast.error("O link relacionado deve ser um endereço http ou https válido.");
      return;
    }
    if (await saveEvent(form, editing?.id ?? null)) setDialogOpen(false);
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    if (await deleteEvent(deleting.id)) setDeleting(null);
  };

  const handleCreateCourse = async () => {
    const name = newCourseName.trim();
    if (name.length < 2) {
      toast.error("Informe um nome de curso com pelo menos 2 caracteres.");
      return;
    }
    const course = await createCourse(name);
    if (!course) return;
    setForm((current) => ({ ...current, course: course.name }));
    setNewCourseName("");
    setCreatingCourse(false);
  };

  const selectedPeriod = form.period?.from
    ? form.period.to
      ? `${format(form.period.from, "dd/MM/yyyy")} – ${format(form.period.to, "dd/MM/yyyy")}`
      : format(form.period.from, "dd/MM/yyyy")
    : "Selecione o período";

  return (
    <section aria-label="Gestão de eventos" className="min-w-0 space-y-6">
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1 space-y-2 sm:max-w-xl">
          <Label htmlFor="events-search">Pesquisar eventos</Label>
          <div className="relative">
            <Search aria-hidden="true" className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input ref={searchInput} id="events-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Pesquisar por título, curso, tipo ou local..." className="pl-9" />
          </div>
        </div>
        <Button onClick={() => openForm()}><Plus aria-hidden="true" /> Novo evento</Button>
      </div>

      {loading ? (
        <Card><CardContent role="status" aria-label="Carregando eventos" className="flex items-center justify-center gap-3 px-4 py-12 text-muted-foreground"><Loader2 aria-hidden="true" className="size-5 animate-spin motion-reduce:animate-none" />Carregando eventos...</CardContent></Card>
      ) : filteredEvents.length === 0 ? (
        <Card className="border-dashed"><CardContent role="status" className="flex flex-col items-center gap-3 px-4 py-12 text-center text-muted-foreground"><CalendarDays aria-hidden="true" className="size-10" /><p>Nenhum evento encontrado.</p></CardContent></Card>
      ) : (
        <ul aria-label="Eventos cadastrados" className="space-y-4">
          {filteredEvents.map((event) => (
            <li key={event.id} className="min-w-0">
              <article aria-labelledby={`event-heading-${event.id}`}>
                <Card className="min-w-0">
                  <CardContent className="flex min-w-0 flex-col gap-6 px-4 py-4 md:px-6 md:py-6 xl:flex-row xl:items-start">
                    <div className="min-w-0 flex-1 space-y-4">
                      <div className="flex min-w-0 items-start gap-3">
                        {event.image_url && (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={event.image_url} alt="" className="h-14 w-20 shrink-0 rounded-sm border object-cover" />
                        )}
                        <div className="min-w-0 space-y-2">
                          <Badge variant="secondary" className="max-w-full whitespace-normal [overflow-wrap:anywhere]">{EVENT_TYPES.find((type) => type.value === event.event_type)?.label ?? event.event_type}</Badge>
                          <h2 id={`event-heading-${event.id}`} className="text-lg font-semibold leading-7 [overflow-wrap:anywhere]">{event.title}</h2>
                        </div>
                      </div>
                      <dl className="grid min-w-0 gap-4 text-sm sm:grid-cols-2 xl:grid-cols-3">
                        <div className="min-w-0 space-y-1"><dt className="text-muted-foreground">Período</dt><dd className="[overflow-wrap:anywhere]">{formatPeriod(event.event_date, event.event_end_date)}</dd></div>
                        <div className="min-w-0 space-y-1"><dt className="text-muted-foreground">Curso</dt><dd className="[overflow-wrap:anywhere]">{event.course}</dd></div>
                        <div className="min-w-0 space-y-1"><dt className="text-muted-foreground">Local</dt><dd className="[overflow-wrap:anywhere]">{event.location}</dd></div>
                      </dl>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button variant="outline" size="icon" onClick={() => openForm(event)} aria-label={`Editar ${event.title}`}><Pencil aria-hidden="true" /></Button>
                      <Button variant="outline" size="icon" className="text-destructive" onClick={(click) => { deleteTrigger.current = click.currentTarget; setDeleting(event); }} aria-label={`Excluir ${event.title}`}><Trash2 aria-hidden="true" /></Button>
                    </div>
                  </CardContent>
                </Card>
              </article>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl" onCloseAutoFocus={(event) => { event.preventDefault(); formTrigger.current?.focus(); }}>
          <DialogHeader className="pr-8 text-left">
            <DialogTitle>{editing ? "Editar evento" : "Novo evento"}</DialogTitle>
            <DialogDescription>Informe o período e os dados exibidos no portal público.</DialogDescription>
          </DialogHeader>
          <div className="grid min-h-0 min-w-0 gap-5 overflow-y-auto px-1 py-1 sm:grid-cols-2 [&>div]:min-w-0" onFocusCapture={(event) => { if (event.target instanceof HTMLElement && event.currentTarget.contains(event.target)) event.target.scrollIntoView?.({ block: "nearest", inline: "nearest" }); }}>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-title">Título</Label>
              <Input id="event-title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ex: Workshop de Design" />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-period">Período</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button id="event-period" aria-label={`Período: ${selectedPeriod}`} aria-describedby="event-period-hint" variant="outline" className={cn("h-auto min-h-11 w-full justify-start whitespace-normal text-left font-normal", !form.period?.from && "text-muted-foreground")}>
                    <CalendarIcon aria-hidden="true" className="shrink-0" /> {selectedPeriod}
                  </Button>
                </PopoverTrigger>
                <PopoverContent aria-label="Selecionar período" className="max-h-[var(--radix-popover-content-available-height)] w-auto max-w-[calc(100vw-2rem)] overflow-auto p-0" align="start" collisionPadding={16}>
                  <Calendar className="[--cell-size:2.75rem]" labels={{ labelNext: () => "Próximo mês", labelPrevious: () => "Mês anterior" }} defaultMonth={form.period?.from} mode="range" locale={ptBR} selected={form.period} onSelect={(period) => setForm({ ...form, period })} numberOfMonths={1} />
                </PopoverContent>
              </Popover>
              <p id="event-period-hint" className="text-xs text-muted-foreground">Para um evento de um dia, selecione apenas uma data.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-type">Tipo</Label>
              <Select value={form.event_type} onValueChange={(event_type) => setForm({ ...form, event_type })}>
                <SelectTrigger id="event-type" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent position="popper" className="max-w-[calc(100vw-2rem)]">
                  {EVENT_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-course">Curso relacionado</Label>
              <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
                <Select value={form.course} onValueChange={(course) => setForm({ ...form, course })}>
                  <SelectTrigger id="event-course" className="w-full min-w-0 flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent position="popper" className="max-w-[calc(100vw-2rem)]">
                    {courses.map((course) => <SelectItem key={course.id} value={course.name} className="whitespace-normal [overflow-wrap:anywhere]">{course.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button type="button" variant="outline" onClick={() => setCreatingCourse((current) => !current)} aria-expanded={creatingCourse} aria-controls="new-course-panel">
                  <Plus aria-hidden="true" /> Criar curso
                </Button>
              </div>
              {creatingCourse && (
                <div id="new-course-panel" className="space-y-2 rounded-sm border bg-muted p-4">
                  <Label htmlFor="new-event-course">Nome do novo curso</Label>
                  <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
                    <Input
                      id="new-event-course"
                      value={newCourseName}
                      onChange={(event) => setNewCourseName(event.target.value)}
                      placeholder="Ex: Engenharia Civil"
                      maxLength={200}
                    />
                    <Button type="button" onClick={() => void handleCreateCourse()} disabled={saving}>Adicionar</Button>
                  </div>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-location">Local</Label>
              <Input id="event-location" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Ex: Auditório do Bloco F" maxLength={300} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-description">Descrição</Label>
              <Textarea id="event-description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Detalhes do evento..." rows={3} className="max-h-48 min-h-24 resize-none overflow-y-auto [field-sizing:fixed]" />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-image-url">URL da imagem de capa</Label>
              <Input id="event-image-url" type="url" value={form.image_url} onChange={(event) => { setForm({ ...form, image_url: event.target.value }); setPreviewFailed(false); }} placeholder="https://exemplo.com/capa.webp" aria-describedby="event-image-hint" />
              <p id="event-image-hint" className="text-xs text-muted-foreground [overflow-wrap:anywhere]">Use o endereço direto de uma imagem (https), por exemplo terminando em .jpg, .png ou .webp. Links de Google Drive e Instagram costumam não funcionar.</p>
              {form.image_url.trim() && isValidExternalUrl(form.image_url.trim(), ["https:"]) && !previewFailed && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={form.image_url.trim()} alt="Prévia da capa do evento" className="max-h-44 w-full rounded-md border object-cover" onError={() => setPreviewFailed(true)} />
              )}
              {previewFailed && <p className="rounded-sm border border-warning bg-card p-3 text-sm text-foreground" role="alert">Não foi possível carregar esta imagem</p>}
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-link-url">Link relacionado</Label>
              <Input id="event-link-url" type="url" value={form.link_url} onChange={(event) => setForm({ ...form, link_url: event.target.value })} placeholder="https://exemplo.com/inscricoes" />
            </div>
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={() => void handleSave()} disabled={saving} aria-busy={saving}>{saving && <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" />}{saving ? "Salvando..." : "Salvar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(null); }}>
        <AlertDialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto" onCloseAutoFocus={(event) => { event.preventDefault(); if (deleteTrigger.current?.isConnected) deleteTrigger.current.focus(); else searchInput.current?.focus(); }}>
          <AlertDialogHeader className="text-left">
            <AlertDialogTitle>Excluir evento?</AlertDialogTitle>
            <AlertDialogDescription tabIndex={0} aria-label="Efeito da exclusão" className="max-h-[40dvh] overflow-y-auto rounded-sm [overflow-wrap:anywhere] focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">O evento “{deleting?.title}” será removido permanentemente.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col gap-2 sm:flex-row sm:space-x-0">
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive" onClick={() => void confirmDelete()}>Excluir</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
