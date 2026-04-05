"use client";

import { useState } from "react";
import { useFaqs } from "../hooks/use-faqs";
import { Faq } from "../types";
import { Search, Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function FaqTab() {
  const { faqs, saveFaq, deleteFaq, toggleTotemStatus } = useFaqs();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<Faq | null>(null);
  const [form, setForm] = useState({ question: "", answer: "" });

  const filteredFaqs = faqs.filter(f => 
    f.question.toLowerCase().includes(search.toLowerCase())
  );

  const openDialog = (faq?: Faq) => {
    setEditingFaq(faq || null);
    setForm(faq ? { question: faq.question, answer: faq.answer } : { question: "", answer: "" });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.question.trim() || !form.answer.trim()) {
      toast.error("Preencha todos os campos");
      return;
    }
    
    await saveFaq(form, editingFaq?.id || null);
    setDialogOpen(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Buscar FAQs..." 
            value={search} 
            onChange={(e) => setSearch(e.target.value)} 
            className="pl-10" 
          />
        </div>
        <Button onClick={() => openDialog()}>
          <Plus className="h-4 w-4 mr-2" />Nova FAQ
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pergunta</TableHead>
                <TableHead className="hidden md:table-cell">Resposta</TableHead>
                {/* Definimos uma largura fixa no Header também */}
                <TableHead className="w-35">Totem</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredFaqs.map((faq) => (
                <TableRow key={faq.id}>
                  <TableCell className="font-medium max-w-50 truncate">
                    {faq.question}
                  </TableCell>
                  <TableCell className="hidden md:table-cell max-w-75 truncate text-muted-foreground">
                    {faq.answer}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 w-30"> {/* Largura fixa aqui evita o balanço */}
                      <Switch 
                        checked={faq.show_on_totem} 
                        onCheckedChange={() => toggleTotemStatus(faq.id)} 
                      />
                      <Badge 
                        variant={faq.show_on_totem ? "default" : "secondary"}
                        className="w-20 justify-center" // Badge com largura fixa e texto centralizado
                      >
                        {faq.show_on_totem ? "No Totem" : "Oculta"}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => openDialog(faq)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        onClick={() => deleteFaq(faq.id)} 
                        className="text-destructive"
                      >
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
            <DialogTitle>{editingFaq ? "Editar FAQ" : "Nova FAQ"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Pergunta</Label>
              <Input 
                value={form.question} 
                onChange={(e) => setForm({ ...form, question: e.target.value })} 
              />
            </div>
            <div className="space-y-2">
              <Label>Resposta</Label>
              <Textarea 
                value={form.answer} 
                onChange={(e) => setForm({ ...form, answer: e.target.value })} 
                rows={4} 
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSave}>Salvar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}