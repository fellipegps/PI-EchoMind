"use client";

import { useMemo, useState } from "react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarIcon, Pencil, Plus, Search, Trash2 } from "lucide-react";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="relative flex-1">
          <span className="sr-only">Pesquisar eventos</span>
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Pesquisar por título, curso, tipo ou local..."
            className="pl-9"
          />
        </label>
        <Button onClick={() => openForm()}>
          <Plus className="h-4 w-4" /> Novo evento
        </Button>
      </div>

      <Card>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Título</TableHead>
                <TableHead>Período</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Curso</TableHead>
                <TableHead>Local</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEvents.map((event) => (
                <TableRow key={event.id}>
                  <TableCell>
                    <div className="flex min-w-48 items-center gap-3">
                      {event.image_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={event.image_url} alt="" className="h-10 w-14 rounded object-cover" />
                      )}
                      <span className="font-medium">{event.title}</span>
                    </div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {formatPeriod(event.event_date, event.event_end_date)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {EVENT_TYPES.find((type) => type.value === event.event_type)?.label ?? event.event_type}
                    </Badge>
                  </TableCell>
                  <TableCell>{event.course}</TableCell>
                  <TableCell>{event.location}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openForm(event)} aria-label={`Editar ${event.title}`}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="text-destructive" onClick={() => setDeleting(event)} aria-label={`Excluir ${event.title}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!loading && filteredEvents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                    Nenhum evento encontrado.
                  </TableCell>
                </TableRow>
              )}
              {loading && (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-muted-foreground" role="status">
                    Carregando eventos...
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Editar evento" : "Novo evento"}</DialogTitle>
            <DialogDescription>Informe o período e os dados exibidos no portal público.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-title">Título</Label>
              <Input id="event-title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Ex: Workshop de Design" />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Período</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className={cn("w-full justify-start text-left font-normal", !form.period?.from && "text-muted-foreground")}>
                    <CalendarIcon className="mr-2 h-4 w-4" /> {selectedPeriod}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar mode="range" locale={ptBR} selected={form.period} onSelect={(period) => setForm({ ...form, period })} numberOfMonths={1} />
                </PopoverContent>
              </Popover>
              <p className="text-xs text-muted-foreground">Para um evento de um dia, selecione apenas uma data.</p>
            </div>
            <div className="space-y-2">
              <Label>Tipo</Label>
              <Select value={form.event_type} onValueChange={(event_type) => setForm({ ...form, event_type })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EVENT_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-course">Curso relacionado</Label>
              <div className="flex gap-2">
                <Select value={form.course} onValueChange={(course) => setForm({ ...form, course })}>
                  <SelectTrigger id="event-course" className="min-w-0 flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {courses.map((course) => <SelectItem key={course.id} value={course.name}>{course.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button type="button" variant="outline" onClick={() => setCreatingCourse((current) => !current)}>
                  <Plus className="h-4 w-4" /> Criar curso
                </Button>
              </div>
              {creatingCourse && (
                <div className="space-y-2 rounded-md border p-3">
                  <Label htmlFor="new-event-course">Nome do novo curso</Label>
                  <div className="flex gap-2">
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
              <Textarea id="event-description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Detalhes do evento..." rows={3} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-image-url">URL da imagem de capa</Label>
              <Input id="event-image-url" type="url" value={form.image_url} onChange={(event) => { setForm({ ...form, image_url: event.target.value }); setPreviewFailed(false); }} placeholder="https://exemplo.com/capa.webp" />
              <p className="text-xs text-muted-foreground">Use o endereço direto de uma imagem (https), por exemplo terminando em .jpg, .png ou .webp. Links de Google Drive e Instagram costumam não funcionar.</p>
              {form.image_url.trim() && isValidExternalUrl(form.image_url.trim(), ["https:"]) && !previewFailed && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={form.image_url.trim()} alt="Prévia da capa do evento" className="max-h-44 w-full rounded-md border object-cover" onError={() => setPreviewFailed(true)} />
              )}
              {previewFailed && <p className="text-sm text-amber-700" role="alert">Não foi possível carregar esta imagem</p>}
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-link-url">Link relacionado</Label>
              <Input id="event-link-url" type="url" value={form.link_url} onChange={(event) => setForm({ ...form, link_url: event.target.value })} placeholder="https://exemplo.com/inscricoes" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={() => void handleSave()} disabled={saving}>{saving ? "Salvando..." : "Salvar"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir evento?</AlertDialogTitle>
            <AlertDialogDescription>O evento “{deleting?.title}” será removido permanentemente.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={() => void confirmDelete()}>Excluir</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
