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
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
  }
> = {
  pending: { label: "Pendente", variant: "warning" },
  processing: { label: "Processando", variant: "outline" },
  ready: { label: "Pronto", variant: "success" },
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
    <section className="min-w-0 space-y-6" aria-label="Gestão de documentos">
      <Card className="min-w-0">
        <CardHeader className="gap-2">
          <CardTitle><h2 className="text-lg font-semibold">Adicionar documento</h2></CardTitle>
          <p className="text-sm text-muted-foreground">Selecione um documento para alimentar a base de conhecimento do agente.</p>
        </CardHeader>
        <CardContent className="min-w-0 space-y-6">
          <div
            data-testid="document-dropzone"
            onDragOver={(event) => {
              event.preventDefault();
              if (canSelectFile) setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-56 min-w-0 flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors motion-reduce:transition-none md:px-6",
              isDragging ? "border-primary bg-accent" : "border-border bg-card",
              canSelectFile ? "cursor-pointer hover:border-primary focus-within:border-ring" : "cursor-not-allowed bg-muted"
            )}
            role="group"
            aria-label="Seleção de documento"
            aria-describedby="document-upload-help"
            aria-busy={isUploading || limitsLoading}
            onClick={(event) => {
              if (canSelectFile && event.target !== inputRef.current) inputRef.current?.click();
            }}
          >
            <input ref={inputRef} type="file" accept={ACCEPTED_FILES} className="hidden"
              aria-label="Selecionar documento" disabled={!canSelectFile} onChange={handleInputChange} />
            <div className="mb-4 rounded-full bg-accent p-3 text-primary">
              <UploadCloud aria-hidden="true" className="size-7" />
            </div>
            <h3 className="text-base font-semibold">Arraste um documento para esta área</h3>
            <p id="document-upload-help" className="mt-2 max-w-md text-sm leading-6 text-muted-foreground" aria-live="polite">
              Solte um arquivo PDF, TXT ou DOCX aqui ou clique para selecionar.{" "}
              {maxFileSizeBytes !== null ? `Limite de ${formatUploadLimit(maxFileSizeBytes)} MB.`
                : limitsLoading ? "Consultando limite de upload..." : "Envio indisponível até carregar o limite."}
            </p>
            <Button type="button" className="mt-4" disabled={!canSelectFile}
              aria-describedby="document-upload-help"
              onClick={(event) => {
                event.stopPropagation();
                if (canSelectFile) inputRef.current?.click();
              }}>
              {isUploading ? "Enviando..." : limitsLoading ? "Carregando limite..." : "Selecionar documento"}
            </Button>
          </div>

          {selectedFile && (
            <form aria-label="Metadados do documento" aria-busy={isUploading}
              className="min-w-0 space-y-6 rounded-xl border bg-card p-4 md:p-6" onSubmit={handleUpload}>
              <div className="flex min-w-0 gap-3">
                <FileText aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-medium">Arquivo selecionado</p>
                  <p className="text-sm text-muted-foreground [overflow-wrap:anywhere]">
                    {selectedFile.name} · {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
              <div className="space-y-4">
                <h3 className="text-sm font-semibold">Metadados opcionais</h3>
                <div className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div className="min-w-0 space-y-2">
                    <Label htmlFor="document-type">Tipo do documento</Label>
                    <Input id="document-type" value={metadata.document_type ?? ""}
                      onChange={(event) => updateMetadata("document_type", event.target.value)} disabled={isUploading} />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <Label htmlFor="document-number">Número do documento</Label>
                    <Input id="document-number" value={metadata.document_number ?? ""}
                      onChange={(event) => updateMetadata("document_number", event.target.value)} disabled={isUploading} />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <Label htmlFor="document-department">Departamento</Label>
                    <Input id="document-department" value={metadata.department ?? ""}
                      onChange={(event) => updateMetadata("department", event.target.value)} disabled={isUploading} />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <Label htmlFor="document-published-at">Data de publicação</Label>
                    <Input id="document-published-at" type="date" value={metadata.published_at ?? ""}
                      onChange={(event) => updateMetadata("published_at", event.target.value)} disabled={isUploading} />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <Label htmlFor="document-valid-until">Válido até</Label>
                    <Input id="document-valid-until" type="date" value={metadata.valid_until ?? ""}
                      onChange={(event) => updateMetadata("valid_until", event.target.value)} disabled={isUploading} />
                  </div>
                </div>
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={cancelSelection} disabled={isUploading}>Cancelar</Button>
                <Button type="submit" disabled={!canSelectFile}>
                  {isUploading && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" />}
                  {isUploading ? "Enviando..." : "Enviar documento"}
                </Button>
              </div>
              {isUploading && <p role="status" className="text-sm text-muted-foreground">Enviando documento. Aguarde a conclusão.</p>}
            </form>
          )}

          {limitsError && (
            <div className="space-y-3 rounded-lg border border-destructive bg-card p-4 text-sm text-destructive [overflow-wrap:anywhere]" role="alert">
              <p>Não foi possível carregar o limite de upload. Recarregue o limite para habilitar o envio.</p>
              <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={() => {
                setMaxFileSizeBytes(null);
                setLimitsLoading(true);
                setLimitsError(false);
                void loadUploadLimits();
              }}><RefreshCw aria-hidden="true" />Recarregar limite</Button>
            </div>
          )}
          {errorMessage && (
            <div className="flex min-w-0 flex-col gap-3 rounded-lg border border-destructive bg-card p-4 text-sm text-destructive sm:flex-row sm:items-center sm:justify-between" role="alert">
              <span className="min-w-0 [overflow-wrap:anywhere]">{errorMessage}</span>
              <Button type="button" variant="outline" onClick={() => { void loadDocuments(); }}>
                <RefreshCw aria-hidden="true" />Tentar novamente
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="min-w-0">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle><h2 className="text-lg font-semibold">Documentos enviados</h2></CardTitle>
          <Badge variant="secondary">{documents.length} arquivo(s)</Badge>
        </CardHeader>
        <CardContent className="min-w-0 p-0">
          <Table aria-label="Documentos enviados" className="block xl:table xl:table-fixed">
            <TableHeader className="hidden xl:table-header-group">
              <TableRow className="hover:bg-card">
                <TableHead className="w-[30%] px-6">Arquivo</TableHead>
                <TableHead className="w-[15%]">Status</TableHead>
                <TableHead className="w-[12%]">Tamanho</TableHead>
                <TableHead className="w-[10%]">Chunks</TableHead>
                <TableHead className="w-[21%]">Enviado em</TableHead>
                <TableHead className="w-[12%] px-6 text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="block xl:table-row-group">
              {isLoading ? (
                <TableRow className="block hover:bg-card xl:table-row">
                  <TableCell colSpan={6} className="block p-6 text-center whitespace-normal text-muted-foreground xl:table-cell">
                    <span className="inline-flex min-h-24 items-center gap-2" role="status">
                      <Loader2 className="size-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />Carregando documentos...
                    </span>
                  </TableCell>
                </TableRow>
              ) : documents.length === 0 ? (
                <TableRow className="block hover:bg-card xl:table-row">
                  <TableCell colSpan={6} className="block p-6 text-center whitespace-normal text-muted-foreground xl:table-cell">
                    <div className="flex min-h-24 flex-col items-center justify-center gap-3">
                      <FileText aria-hidden="true" className="size-6" />Nenhum documento enviado.
                    </div>
                  </TableCell>
                </TableRow>
              ) : documents.map((document) => {
                const status = STATUS_DETAILS[document.status];
                const isActive = ACTIVE_STATUSES.has(document.status);
                const isDeleting = deletingId === document.id;
                return (
                  <TableRow key={document.id} className="grid grid-cols-2 gap-4 p-4 hover:bg-card md:p-6 xl:table-row xl:p-0">
                    <TableCell className="col-span-2 block min-w-0 p-0 whitespace-normal font-medium xl:table-cell xl:px-6 xl:py-4">
                      <div className="flex min-w-0 items-start gap-3">
                        <FileText aria-hidden="true" className={cn("mt-0.5 size-5 shrink-0 text-primary", document.status === "error" && "text-destructive")} />
                        <div className="min-w-0 space-y-1">
                          <span className="block [overflow-wrap:anywhere]">{document.filename}</span>
                          {document.status === "error" && <span className="block text-xs font-normal text-destructive">Falha no processamento</span>}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="block min-w-0 p-0 whitespace-normal xl:table-cell xl:p-2">
                      <span className="mb-1 block text-xs text-muted-foreground xl:sr-only">Status</span>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className="block min-w-0 p-0 whitespace-normal text-muted-foreground xl:table-cell xl:p-2">
                      <span className="mb-1 block text-xs xl:sr-only">Tamanho</span>{formatFileSize(document.size_bytes)}
                    </TableCell>
                    <TableCell className="block min-w-0 p-0 whitespace-normal [overflow-wrap:anywhere] xl:table-cell xl:p-2">
                      <span className="mb-1 block text-xs text-muted-foreground xl:sr-only">Chunks</span><span>{document.chunk_count}</span>
                    </TableCell>
                    <TableCell className="block min-w-0 p-0 whitespace-normal text-muted-foreground xl:table-cell xl:p-2">
                      <span className="mb-1 block text-xs xl:sr-only">Enviado em</span>{formatDateTime(document.created_at)}
                    </TableCell>
                    <TableCell className="col-span-2 block min-w-0 p-0 whitespace-normal xl:table-cell xl:px-6 xl:py-4 xl:text-right">
                      {isActive && <p className="mb-2 text-xs text-muted-foreground xl:sr-only">Aguarde o processamento para excluir</p>}
                      <Button type="button" variant="outline" size="icon" className="text-destructive"
                        onClick={() => void deleteDocument(document)} disabled={isActive || deletingId !== null}
                        title={isActive ? "Aguarde o processamento para excluir" : undefined} aria-label={`Excluir ${document.filename}`}>
                        {isDeleting ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <X className="size-4" aria-hidden="true" />}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
