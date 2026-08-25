"use client";

import {
  ChangeEvent,
  DragEvent,
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { FileText, Loader2, RefreshCw, UploadCloud, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  documentApi,
  type DocumentStatus,
  type DocumentUploadMetadata,
  type KnowledgeDocument,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const POLLING_INTERVAL_MS = 2_000;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_FILES = ".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const ACTIVE_STATUSES = new Set<DocumentStatus>(["pending", "processing"]);
const METADATA_FIELDS = [
  "document_type",
  "document_number",
  "department",
  "published_at",
  "valid_until",
] as const satisfies readonly (keyof DocumentUploadMetadata)[];

const ALLOWED_FILE_TYPES: Record<string, string> = {
  ".pdf": "application/pdf",
  ".txt": "text/plain",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};

const STATUS_DETAILS: Record<
  DocumentStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline";
  }
> = {
  pending: { label: "Pendente", variant: "secondary" },
  processing: { label: "Processando", variant: "outline" },
  ready: { label: "Pronto", variant: "default" },
  error: { label: "Erro", variant: "destructive" },
};

const EMPTY_METADATA: DocumentUploadMetadata = {
  document_type: "",
  document_number: "",
  department: "",
  published_at: "",
  valid_until: "",
};

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function validateFile(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const expectedMimeType = ALLOWED_FILE_TYPES[extension];
  const normalizedMimeType = file.type.toLowerCase();

  if (!expectedMimeType || (normalizedMimeType && normalizedMimeType !== expectedMimeType)) {
    return "Selecione um arquivo PDF, TXT ou DOCX válido.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "O arquivo deve ter no máximo 10 MB.";
  }

  return null;
}

function compactMetadata(metadata: DocumentUploadMetadata): DocumentUploadMetadata {
  const compacted: DocumentUploadMetadata = {};

  for (const field of METADATA_FIELDS) {
    const value = metadata[field]?.trim();
    if (value) compacted[field] = value;
  }

  return compacted;
}

export function DocumentTab() {
  const inputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(false);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<DocumentUploadMetadata>(EMPTY_METADATA);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const response = await documentApi.list();
      if (mountedRef.current) {
        setDocuments(response.documents);
        setErrorMessage(null);
      }
    } catch {
      if (mountedRef.current) {
        setErrorMessage("Não foi possível carregar os documentos.");
      }
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    documentApi
      .list()
      .then((response) => {
        if (mountedRef.current) {
          setDocuments(response.documents);
          setErrorMessage(null);
        }
      })
      .catch(() => {
        if (mountedRef.current) {
          setErrorMessage("Não foi possível carregar os documentos.");
        }
      })
      .finally(() => {
        if (mountedRef.current) setIsLoading(false);
      });

    return () => {
      mountedRef.current = false;
    };
  }, []);

  const hasActiveDocuments = documents.some((document) =>
    ACTIVE_STATUSES.has(document.status)
  );

  useEffect(() => {
    if (!hasActiveDocuments) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedulePoll = () => {
      timer = setTimeout(async () => {
        try {
          const response = await documentApi.list();
          if (cancelled || !mountedRef.current) return;

          setDocuments(response.documents);
          setErrorMessage(null);
          if (response.documents.some((document) => ACTIVE_STATUSES.has(document.status))) {
            schedulePoll();
          }
        } catch {
          if (cancelled || !mountedRef.current) return;
          setErrorMessage("Não foi possível atualizar o processamento dos documentos.");
          schedulePoll();
        }
      }, POLLING_INTERVAL_MS);
    };

    schedulePoll();

    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [hasActiveDocuments]);

  const selectFile = (files: FileList | File[]) => {
    const selectedFiles = Array.from(files);
    setErrorMessage(null);

    if (selectedFiles.length !== 1) {
      setSelectedFile(null);
      setErrorMessage("Envie apenas um arquivo por vez.");
      return;
    }

    const file = selectedFiles[0];
    const validationError = validateFile(file);
    if (validationError) {
      setSelectedFile(null);
      setErrorMessage(validationError);
      return;
    }

    setSelectedFile(file);
    setMetadata(EMPTY_METADATA);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (!isUploading) selectFile(event.dataTransfer.files);
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) selectFile(event.target.files);
    event.target.value = "";
  };

  const cancelSelection = () => {
    setSelectedFile(null);
    setMetadata(EMPTY_METADATA);
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setErrorMessage(null);

    try {
      const uploaded = await documentApi.upload(selectedFile, compactMetadata(metadata));
      if (!mountedRef.current) return;

      setDocuments((current) => [
        uploaded,
        ...current.filter((document) => document.id !== uploaded.id),
      ]);
      cancelSelection();
    } catch {
      if (mountedRef.current) setErrorMessage("Não foi possível enviar o documento.");
    } finally {
      if (mountedRef.current) setIsUploading(false);
    }
  };

  const deleteDocument = async (document: KnowledgeDocument) => {
    if (ACTIVE_STATUSES.has(document.status) || deletingId !== null) return;

    setDeletingId(document.id);
    setErrorMessage(null);

    try {
      await documentApi.delete(document.id);
      if (mountedRef.current) {
        setDocuments((current) => current.filter((item) => item.id !== document.id));
      }
    } catch {
      if (mountedRef.current) setErrorMessage("Não foi possível excluir o documento.");
    } finally {
      if (mountedRef.current) setDeletingId(null);
    }
  };

  const updateMetadata = (field: keyof DocumentUploadMetadata, value: string) => {
    setMetadata((current) => ({ ...current, [field]: value }));
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4 p-6">
          <div
            data-testid="document-dropzone"
            onDragOver={(event) => {
              event.preventDefault();
              if (!isUploading) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed bg-muted/20 px-6 py-10 text-center transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30",
              isUploading && "cursor-not-allowed opacity-60"
            )}
            role="button"
            tabIndex={isUploading ? -1 : 0}
            aria-disabled={isUploading}
            aria-busy={isUploading}
            onClick={() => {
              if (!isUploading) inputRef.current?.click();
            }}
            onKeyDown={(event) => {
              if (!isUploading && (event.key === "Enter" || event.key === " ")) {
                event.preventDefault();
                inputRef.current?.click();
              }
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED_FILES}
              className="hidden"
              aria-label="Selecionar documento"
              onChange={handleInputChange}
            />
            <div className="mb-4 rounded-full bg-primary/10 p-4 text-primary">
              <UploadCloud className="h-8 w-8" />
            </div>
            <h2 className="text-lg font-semibold">Arraste documentos para alimentar o agente</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Solte um arquivo PDF, TXT ou DOCX aqui ou clique para selecionar. Limite de 10 MB.
            </p>
            <Button type="button" className="mt-5" disabled={isUploading}>
              {isUploading ? "Enviando..." : "Selecionar documento"}
            </Button>
          </div>

          {selectedFile && (
            <form
              aria-label="Metadados do documento"
              className="space-y-4 rounded-lg border bg-muted/10 p-4"
              onSubmit={handleUpload}
            >
              <div>
                <p className="text-sm font-medium">Arquivo selecionado</p>
                <p className="text-sm text-muted-foreground">
                  {selectedFile.name} · {formatFileSize(selectedFile.size)}
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="document-type">Tipo do documento</Label>
                  <Input
                    id="document-type"
                    value={metadata.document_type ?? ""}
                    onChange={(event) => updateMetadata("document_type", event.target.value)}
                    disabled={isUploading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="document-number">Número do documento</Label>
                  <Input
                    id="document-number"
                    value={metadata.document_number ?? ""}
                    onChange={(event) => updateMetadata("document_number", event.target.value)}
                    disabled={isUploading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="document-department">Departamento</Label>
                  <Input
                    id="document-department"
                    value={metadata.department ?? ""}
                    onChange={(event) => updateMetadata("department", event.target.value)}
                    disabled={isUploading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="document-published-at">Data de publicação</Label>
                  <Input
                    id="document-published-at"
                    type="date"
                    value={metadata.published_at ?? ""}
                    onChange={(event) => updateMetadata("published_at", event.target.value)}
                    disabled={isUploading}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="document-valid-until">Válido até</Label>
                  <Input
                    id="document-valid-until"
                    type="date"
                    value={metadata.valid_until ?? ""}
                    onChange={(event) => updateMetadata("valid_until", event.target.value)}
                    disabled={isUploading}
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={cancelSelection} disabled={isUploading}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={isUploading}>
                  {isUploading && <Loader2 className="animate-spin" aria-hidden="true" />}
                  {isUploading ? "Enviando..." : "Enviar documento"}
                </Button>
              </div>
            </form>
          )}

          {errorMessage && (
            <div
              className="flex flex-col gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive sm:flex-row sm:items-center sm:justify-between"
              role="alert"
            >
              <span>{errorMessage}</span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setIsLoading(true);
                  setErrorMessage(null);
                  void loadDocuments();
                }}
              >
                <RefreshCw aria-hidden="true" />
                Tentar novamente
              </Button>
            </div>
          )}
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
                <TableHead>Status</TableHead>
                <TableHead className="hidden sm:table-cell">Tamanho</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead className="hidden md:table-cell">Enviado em</TableHead>
                <TableHead className="text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    <span className="inline-flex items-center gap-2" role="status">
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      Carregando documentos...
                    </span>
                  </TableCell>
                </TableRow>
              ) : documents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                    Nenhum documento enviado.
                  </TableCell>
                </TableRow>
              ) : (
                documents.map((document) => {
                  const status = STATUS_DETAILS[document.status];
                  const isActive = ACTIVE_STATUSES.has(document.status);
                  const isDeleting = deletingId === document.id;

                  return (
                    <TableRow key={document.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <FileText
                            className={cn(
                              "h-4 w-4 shrink-0 text-primary",
                              document.status === "error" && "text-destructive"
                            )}
                            aria-hidden="true"
                          />
                          <div className="min-w-0">
                            <span className="block max-w-52 truncate">{document.filename}</span>
                            {document.status === "error" && (
                              <span className="block text-xs font-normal text-destructive">
                                Falha no processamento
                              </span>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={status.variant}>{status.label}</Badge>
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground sm:table-cell">
                        {formatFileSize(document.size_bytes)}
                      </TableCell>
                      <TableCell>{document.chunk_count}</TableCell>
                      <TableCell className="hidden text-muted-foreground md:table-cell">
                        {formatDateTime(document.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                          onClick={() => void deleteDocument(document)}
                          disabled={isActive || deletingId !== null}
                          title={isActive ? "Aguarde o processamento para excluir" : undefined}
                          aria-label={`Excluir ${document.filename}`}
                        >
                          {isDeleting ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                          ) : (
                            <X className="h-4 w-4" aria-hidden="true" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
