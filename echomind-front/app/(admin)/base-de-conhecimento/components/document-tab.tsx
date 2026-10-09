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
const BYTES_PER_MEGABYTE = 1024 * 1024;
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

function formatUploadLimit(bytes: number) {
  return new Intl.NumberFormat("pt-BR").format(bytes / BYTES_PER_MEGABYTE);
}

function validateFile(file: File, maxSizeBytes: number): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const expectedMimeType = ALLOWED_FILE_TYPES[extension];
  const normalizedMimeType = file.type.toLowerCase();

  if (!expectedMimeType || (normalizedMimeType && normalizedMimeType !== expectedMimeType)) {
    return "Selecione um arquivo PDF, TXT ou DOCX válido.";
  }

  if (file.size > maxSizeBytes) {
    return `O arquivo deve ter no máximo ${formatUploadLimit(maxSizeBytes)} MB.`;
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
  const listVersionRef = useRef(0);
  const listControllerRef = useRef<AbortController | null>(null);
  const mutationCountRef = useRef(0);
  const feedbackVersionRef = useRef(0);
  const limitsControllerRef = useRef<AbortController | null>(null);
  const [maxFileSizeBytes, setMaxFileSizeBytes] = useState<number | null>(null);
  const [limitsLoading, setLimitsLoading] = useState(true);
  const [limitsError, setLimitsError] = useState(false);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [listingState, setListingState] = useState({ pending: false, version: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<DocumentUploadMetadata>(EMPTY_METADATA);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadUploadLimits = useCallback(() => {
    limitsControllerRef.current?.abort();
    const controller = new AbortController();
    limitsControllerRef.current = controller;
    const isCurrent = () => mountedRef.current
      && limitsControllerRef.current === controller
      && !controller.signal.aborted;
    return documentApi.uploadLimits(controller.signal)
      .then((limits) => {
        if (!Number.isSafeInteger(limits.max_document_size_bytes) || limits.max_document_size_bytes <= 0) {
          throw new Error("Limite de upload inválido.");
        }
        if (isCurrent()) setMaxFileSizeBytes(limits.max_document_size_bytes);
      })
      .catch(() => {
        if (isCurrent()) setLimitsError(true);
      })
      .finally(() => {
        if (isCurrent()) {
          setLimitsLoading(false);
          limitsControllerRef.current = null;
        }
      });
  }, []);

  const invalidateListing = useCallback(() => {
    listVersionRef.current += 1;
    listControllerRef.current?.abort();
    listControllerRef.current = null;
  }, []);

  const loadDocuments = useCallback(async (source: "manual" | "poll" = "manual") => {
    if (!mountedRef.current || mutationCountRef.current > 0) return;

    invalidateListing();
    const version = listVersionRef.current;
    const feedbackVersion = ++feedbackVersionRef.current;
    const controller = new AbortController();
    listControllerRef.current = controller;
    setListingState({ pending: true, version });
    if (source === "manual") {
      setIsLoading(true);
      setErrorMessage(null);
    }
    const isCurrent = () => mountedRef.current
      && listVersionRef.current === version
      && !controller.signal.aborted;

    try {
      const response = await documentApi.list(controller.signal);
      if (isCurrent()) {
        setDocuments(response.documents);
        if (feedbackVersionRef.current === feedbackVersion) setErrorMessage(null);
      }
    } catch {
      if (isCurrent() && feedbackVersionRef.current === feedbackVersion) {
        setErrorMessage(source === "poll"
          ? "Não foi possível atualizar o processamento dos documentos."
          : "Não foi possível carregar os documentos.");
      }
    } finally {
      if (isCurrent()) {
        listControllerRef.current = null;
        setListingState({ pending: false, version });
        setIsLoading(false);
      }
    }
  }, [invalidateListing]);

  useEffect(() => {
    mountedRef.current = true;
    void loadDocuments();
    void loadUploadLimits();

    return () => {
      mountedRef.current = false;
      invalidateListing();
      limitsControllerRef.current?.abort();
      limitsControllerRef.current = null;
    };
  }, [invalidateListing, loadDocuments, loadUploadLimits]);

  const hasActiveDocuments = documents.some((document) =>
    ACTIVE_STATUSES.has(document.status)
  );

  useEffect(() => {
    if (!hasActiveDocuments || listingState.pending || isUploading || deletingId !== null) return;

    const timer = setTimeout(() => void loadDocuments("poll"), POLLING_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [hasActiveDocuments, listingState, isUploading, deletingId, loadDocuments]);

  const beginMutation = () => {
    mutationCountRef.current += 1;
    invalidateListing();
    setListingState({ pending: false, version: listVersionRef.current });
    setIsLoading(false);
    return ++feedbackVersionRef.current;
  };

  const finishMutation = () => {
    mutationCountRef.current -= 1;
    // Leituras anteriores a uma escrita nao podem publicar snapshots antigos,
    // mesmo quando o transporte/fake nao respeita o cancelamento.
    invalidateListing();
  };

  const selectFile = (files: FileList | File[]) => {
    if (maxFileSizeBytes === null) return;
    const selectedFiles = Array.from(files);
    feedbackVersionRef.current += 1;
    setErrorMessage(null);

    if (selectedFiles.length !== 1) {
      setSelectedFile(null);
      setErrorMessage("Envie apenas um arquivo por vez.");
      return;
    }

    const file = selectedFiles[0];
    const validationError = validateFile(file, maxFileSizeBytes);
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
    if (canSelectFile) selectFile(event.dataTransfer.files);
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
    if (!selectedFile || isUploading || maxFileSizeBytes === null) return;
    const validationError = validateFile(selectedFile, maxFileSizeBytes);
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }

    const feedbackVersion = beginMutation();
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
      if (mountedRef.current && feedbackVersionRef.current === feedbackVersion) {
        setErrorMessage("Não foi possível enviar o documento.");
      }
    } finally {
      finishMutation();
      if (mountedRef.current) setIsUploading(false);
    }
  };

  const deleteDocument = async (document: KnowledgeDocument) => {
    if (ACTIVE_STATUSES.has(document.status) || deletingId !== null) return;

    const feedbackVersion = beginMutation();
    setDeletingId(document.id);
    setErrorMessage(null);

    try {
      await documentApi.delete(document.id);
      if (mountedRef.current) {
        setDocuments((current) => current.filter((item) => item.id !== document.id));
      }
    } catch {
      if (mountedRef.current && feedbackVersionRef.current === feedbackVersion) {
        setErrorMessage("Não foi possível excluir o documento.");
      }
    } finally {
      finishMutation();
      if (mountedRef.current) setDeletingId(null);
    }
  };

  const updateMetadata = (field: keyof DocumentUploadMetadata, value: string) => {
    setMetadata((current) => ({ ...current, [field]: value }));
  };

  const canSelectFile = !isUploading && maxFileSizeBytes !== null;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4 p-6">
          <div
            data-testid="document-dropzone"
            onDragOver={(event) => {
              event.preventDefault();
              if (canSelectFile) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed bg-muted/20 px-6 py-10 text-center transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/30",
              !canSelectFile && "cursor-not-allowed opacity-60"
            )}
            role="button"
            tabIndex={canSelectFile ? 0 : -1}
            aria-disabled={!canSelectFile}
            aria-busy={isUploading || limitsLoading}
            onClick={() => {
              if (canSelectFile) inputRef.current?.click();
            }}
            onKeyDown={(event) => {
              if (canSelectFile && (event.key === "Enter" || event.key === " ")) {
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
              disabled={!canSelectFile}
              onChange={handleInputChange}
            />
            <div className="mb-4 rounded-full bg-primary/10 p-4 text-primary">
              <UploadCloud className="h-8 w-8" />
            </div>
            <h2 className="text-lg font-semibold">Arraste documentos para alimentar o agente</h2>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              Solte um arquivo PDF, TXT ou DOCX aqui ou clique para selecionar.{" "}
              {maxFileSizeBytes !== null
                ? `Limite de ${formatUploadLimit(maxFileSizeBytes)} MB.`
                : limitsLoading ? "Consultando limite de upload..." : "Envio indisponível até carregar o limite."}
            </p>
            <Button type="button" className="mt-5" disabled={!canSelectFile}>
              {isUploading ? "Enviando..." : limitsLoading ? "Carregando limite..." : "Selecionar documento"}
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
                <Button type="submit" disabled={!canSelectFile}>
                  {isUploading && <Loader2 className="animate-spin" aria-hidden="true" />}
                  {isUploading ? "Enviando..." : "Enviar documento"}
                </Button>
              </div>
            </form>
          )}

          {limitsError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
              <p>Não foi possível carregar o limite de upload. Recarregue o limite para habilitar o envio.</p>
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => {
                setMaxFileSizeBytes(null);
                setLimitsLoading(true);
                setLimitsError(false);
                void loadUploadLimits();
              }}>
                <RefreshCw aria-hidden="true" />
                Recarregar limite
              </Button>
            </div>
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
