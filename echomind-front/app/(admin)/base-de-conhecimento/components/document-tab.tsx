"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

type UploadedDocument = {
  id: string;
  name: string;
  size: string;
  uploadedAt: string;
};

const formatFileSize = (bytes: number) => {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const isPdfFile = (file: File) =>
  file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

export function DocumentTab() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [documents, setDocuments] = useState<UploadedDocument[]>([
    {
      id: "mock-1",
      name: "manual-do-aluno.pdf",
      size: "1.8 MB",
      uploadedAt: "Hoje, 14:20",
    },
  ]);

  const addFiles = (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    const pdfFiles = files.filter(isPdfFile);

    if (!pdfFiles.length) {
      toast.error("Selecione apenas arquivos PDF");
      return;
    }

    if (pdfFiles.length !== files.length) {
      toast.warning("Arquivos que nao eram PDF foram ignorados");
    }

    const uploadedAt = new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date());

    const newDocuments = pdfFiles.map((file) => ({
      id: `${file.name}-${file.lastModified}-${crypto.randomUUID()}`,
      name: file.name,
      size: formatFileSize(file.size),
      uploadedAt: `Hoje, ${uploadedAt}`,
    }));

    setDocuments((current) => [...newDocuments, ...current]);
    toast.success("Documento adicionado para teste visual");
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    addFiles(event.dataTransfer.files);
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      addFiles(event.target.files);
      event.target.value = "";
    }
  };

  const removeDocument = (id: string) => {
    setDocuments((current) => current.filter((document) => document.id !== id));
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-6">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed bg-muted/20 px-6 py-10 text-center transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30"
            )}
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                inputRef.current?.click();
              }
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              multiple
              className="hidden"
              onChange={handleInputChange}
            />
            <div className="mb-4 rounded-full bg-primary/10 p-4 text-primary">
              <UploadCloud className="h-8 w-8" />
            </div>
            <h2 className="text-lg font-semibold">Arraste PDFs para alimentar o agente</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Solte documentos aqui ou clique para selecionar arquivos PDF. O envio e o processamento sao
              simulados apenas no frontend.
            </p>
            <Button type="button" className="mt-5">
              Selecionar PDFs
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Documentos enviados</CardTitle>
          <Badge variant="secondary">{documents.length} arquivo(s)</Badge>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Arquivo</TableHead>
                <TableHead className="hidden sm:table-cell">Tamanho</TableHead>
                <TableHead className="hidden md:table-cell">Enviado em</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((document) => (
                <TableRow key={document.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-destructive" />
                      <span className="max-w-52 truncate">{document.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-muted-foreground">
                    {document.size}
                  </TableCell>
                  <TableCell className="hidden md:table-cell text-muted-foreground">
                    {document.uploadedAt}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive"
                      onClick={() => removeDocument(document.id)}
                      aria-label={`Remover ${document.name}`}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
