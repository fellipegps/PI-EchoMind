"use client";

import { useState } from "react";
import { useEvents } from "../hooks/use-events";
import type { EventFormState } from "../hooks/use-events";
import type { CompanyEvent } from "@/lib/api";
import { EVENT_TYPES } from "../constants";
import { Search, Plus, Pencil, Trash2, CalendarIcon } from "lucide-react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";

export function EventTab() {
  const { events, saveEvent, deleteEvent } = useEvents();
  
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CompanyEvent | null>(null);
  
  const [form, setForm] = useState<EventFormState>({ 
    title: "", 
    event_date: undefined, 
    event_type: "outro", 
    description: "" 
  });

  const filteredEvents = events.filter((e) => 
    e.title.toLowerCase().includes(search.toLowerCase())
  );

  const getEventTypeLabel = (value: string) => 
    EVENT_TYPES.find((t) => t.value === value)?.label ?? value;

  const openDialog = (event?: CompanyEvent) => {
    setEditingEvent(event || null);
    if (event) {
      setForm({
        title: event.title,
        event_date: new Date(event.event_date + "T12:00:00"),
        event_type: event.event_type,
        description: event.description || "",
      });
    } else {
      setForm({ title: "", event_date: undefined, event_type: "outro", description: "" });
    }
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (!form.title.trim() || !form.event_date) {
      toast.error("Preencha título e data");
      return;
    }
    
    saveEvent(form, editingEvent?.id || null);
    setDialogOpen(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Buscar eventos..." 
            value={search} 
            onChange={(e) => setSearch(e.target.value)} 
            className="pl-10" 
          />
        </div>
        <Button onClick={() => openDialog()}>
          <Plus className="h-4 w-4 mr-2" />Novo Evento
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Título</TableHead>
                <TableHead>Data</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="hidden md:table-cell">Descrição</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEvents.map((event) => (
                <TableRow key={event.id}>
                  <TableCell className="font-medium">{event.title}</TableCell>
                  <TableCell>
                    {format(new Date(event.event_date + "T12:00:00"), "dd/MM/yyyy", { locale: ptBR })}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{getEventTypeLabel(event.event_type)}</Badge>
                  </TableCell>
                  <TableCell className="hidden md:table-cell max-w-50 truncate text-muted-foreground">
                    {event.description || "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openDialog(event)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteEvent(event.id)} className="text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingEvent ? "Editar Evento" : "Novo Evento"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Título</Label>
              <Input 
                value={form.title} 
                onChange={(e) => setForm({ ...form, title: e.target.value })} 
                placeholder="Ex: Workshop de Design" 
              />
            </div>
            
            <div className="space-y-2 flex flex-col">
              <Label>Data</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button 
                    variant="outline" 
                    className={cn("justify-start text-left font-normal", !form.event_date && "text-muted-foreground")}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {form.event_date ? format(form.event_date, "PPP", { locale: ptBR }) : "Selecione uma data"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar 
                    mode="single" 
                    locale={ptBR} 
                    selected={form.event_date} 
                    onSelect={(d) => setForm({ ...form, event_date: d })} 
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label>Tipo</Label>
              <Select 
                value={form.event_type} 
                onValueChange={(v) => setForm({ ...form, event_type: v })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EVENT_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Descrição (opcional)</Label>
              <Textarea 
                value={form.description} 
                onChange={(e) => setForm({ ...form, description: e.target.value })} 
                placeholder="Detalhes do evento..." 
                rows={3} 
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button onClick={handleSave}>Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}