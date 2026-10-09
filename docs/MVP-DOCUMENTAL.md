# MVP documental — operação e aceite

Este guia descreve o fluxo documental entregue até a PR 21. Ele não inclui OCR,
busca híbrida, reranking, Parent-Child Retrieval, scheduler ou reindexação
automática.

## Setup e contrato de upload

Antes de iniciar a API, configure o backend, instale as dependências e aplique as
migrations conforme o `README.md`. As variáveis específicas do fluxo são:

```env
MAX_DOCUMENT_SIZE_MB=10
EMBED_MODEL=intfloat/multilingual-e5-small
EMBEDDING_DIM=384
SIMILARITY_THRESHOLD=0.45
TOP_K_DOCS=3
```

`MAX_DOCUMENT_SIZE_MB` deve ser um inteiro positivo e vale por arquivo; o padrão
é 10 MiB. O backend aceita exatamente um arquivo por upload e valida extensão e
MIME em conjunto:

| Formato | Extensão | MIME aceito |
| --- | --- | --- |
| Texto | `.txt` | `text/plain` |
| PDF textual | `.pdf` | `application/pdf` |
| Word | `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

O upload autenticado usa `multipart/form-data` em `POST /documents/upload`. Os
campos opcionais são `document_type`, `document_number`, `department`,
`published_at` e `valid_until`; datas usam `YYYY-MM-DD`. O cliente nunca envia
`tenant_id`: o tenant vem exclusivamente da sessão autenticada.

As demais operações autenticadas são `GET /documents`,
`GET /documents/{document_id}` e `DELETE /documents/{document_id}`.

A aba Documentos consulta `GET /documents/upload-limits`, autenticado e sem cache,
que retorna somente `{"max_document_size_bytes": 10485760}` no limite padrão.
O valor reutiliza a configuração efetiva do backend; não revela outros ajustes.
A UI compara o tamanho original do arquivo em bytes com esse valor, aceitando
igualdade. A unidade MB da configuração e da UI usa `1024 × 1024` bytes (MiB).
Se a consulta falhar ou retornar um limite inválido, o envio fica desabilitado
até uma nova consulta bem-sucedida pelo botão **Recarregar limite**; listagem,
polling e exclusão continuam independentes. Não há fallback fixo de 10 MB.
O servidor continua validando cada upload e retornando 413 para excesso.
Publique o endpoint no backend antes de atualizar o frontend; um backend antigo
sem esse contrato mantém o envio bloqueado na nova UI. Os contratos existentes
de listagem, consulta, upload e DELETE permanecem iguais.

## Estados e comportamento

| Estado | Significado | Ação esperada no painel |
| --- | --- | --- |
| `pending` | Registro criado e aguardando processamento | Consultar novamente em aproximadamente 2 s |
| `processing` | Extração, chunking ou indexação em andamento | Continuar a consulta periódica |
| `ready` | Chunks persistidos e vetores disponíveis | Mostrar `chunk_count` e encerrar polling |
| `error` | Processamento ou exclusão requer recuperação | Mostrar a mensagem e encerrar polling |

Documentos `pending` e `processing` não podem ser excluídos (HTTP 409). Antes de
remover vetores de um documento terminal, o DELETE confirma `error` com uma
mensagem de exclusão não concluída. Só depois remove vetores e registro
relacional, retornando 204. O painel remove o item apenas após esse sucesso.

Se a remoção vetorial ou relacional falhar, um documento antes `ready` tem seus
vetores reconstruídos pelos chunks preservados, com os mesmos IDs determinísticos,
e volta a `ready`. A API ainda informa a falha original: 503 para remoção vetorial
ou 500 para exclusão/commit relacional. Documentos que já estavam em `error` não
são reativados por essa compensação.

Se a compensação ou seu commit falhar, a API retorna 503 e o marcador `error`
continua confirmado, com documento, chunks e parents preservados. Vetores
residuais não entram no contexto do chat. Após resolver a indisponibilidade,
repita o DELETE: ele remove também os vetores parciais pelos mesmos IDs antes
de apagar os registros. Outra repetição após a conclusão retorna 404.

Não há transação distribuída nem recuperação automática em background. Uma
interrupção depois de confirmar o marcador também exige nova tentativa de DELETE.
A preparação e a compensação usam locks no documento do tenant; se outra
tentativa restaurar `ready` antes da remoção, a API retorna 409 sem tocar nos
vetores. Nenhuma migration é necessária para esse comportamento.

Um `document_chunk` com `valid_until` anterior à data civil atual é filtrado
depois da recuperação e não entra no contexto final. Sem `valid_until`, o chunk
permanece elegível. FAQs e eventos não passam por esse filtro. As fontes
documentais apresentam apenas os metadados realmente disponíveis; o conteúdo
recuperado é tratado como dado, nunca como instrução do sistema.

## Migration do zero até `head`

Use exclusivamente um banco vazio, local e descartável. Com
`DATABASE_URL` apontando para ele e a extensão `vector` habilitada:

```bash
cd echomind-backend
python -m alembic upgrade head
python -m alembic current
```

`alembic current` deve apontar para `0009_documents (head)`. O backend não cria
schema no startup. As migrations `0007` e `0008` removeram a estrutura legada
`knowledge_documents`; ela não deve ser recriada.

## Reindexação manual

Depois de confirmar `EMBED_MODEL=intfloat/multilingual-e5-small` e
`EMBEDDING_DIM=384`, execute conscientemente:

```bash
cd echomind-backend
python scripts/reindex_all.py --confirm
```

Use primeiro `python scripts/reindex_all.py --dry-run` e revise as remoções
previstas antes de executar com `--confirm`. O comando reindexa, tenant por
tenant, FAQs e chunks já persistidos de documentos `ready`, incluindo coleções
comprovadamente gerenciadas que só possuem vetores órfãos. Ele ignora documentos
`pending`, `processing` e `error`, não lê novamente
o arquivo original, não recria chunks e nunca roda em startup ou deploy. A
operação para no primeiro tenant com falha; corrija a causa e repita o comando.
Coleções ambíguas ou alheias são preservadas. A identidade vem de metadados
explícitos ou do contrato legado completo, nunca da inversão do nome sanitizado.
Saída `2` indica revisão operacional pendente; saída `1` indica falha de execução,
que pode deixar a coleção do tenant vazia ou parcial. Pause as escritas vetoriais,
corrija a causa e gere nova prévia antes de retomar. Não execute duas reindexações
em paralelo. Os critérios de identidade, limites e roteiro operacional estão na
seção de reindexação manual do `README.md`.

## Gates reproduzíveis

Backend rápido, determinístico e sem serviços externos:

```bash
cd echomind-backend
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not integration and not e2e" --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=72
```

Integração requer PostgreSQL 17 + pgvector descartável, banco local chamado
`echomind_integration`, embedding fake e nenhuma chamada a Groq ou Supabase. O
procedimento completo para subir e remover o container está no `README.md`; após
criar a extensão, rode:

```bash
python -m alembic upgrade head
python -m pytest -m integration
```

Frontend:

```bash
cd echomind-front
corepack pnpm install --frozen-lockfile
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test:run
corepack pnpm build
```

Os nomes estáveis dos checks são `Backend / unit-api`,
`Database / migration-integration` e `Frontend / quality-build`.

## Branch protection recomendada

Para `main`, recomenda-se exigir pull request, branch atualizada antes do merge,
ao menos uma aprovação e os três checks estáveis acima. Também se recomenda
bloquear force-push e exclusão da branch e invalidar aprovações quando novos
commits forem enviados. Esta é apenas a configuração recomendada: a PR 21 não
altera regras remotas do repositório.

## Roteiro manual local com arquivos sintéticos

1. Crie `aceite.txt` com duas frases institucionais fictícias.
2. Crie `aceite.docx` com um título e um parágrafo fictícios.
3. Exporte esse DOCX como `aceite.pdf`, mantendo uma camada de texto selecionável.
4. Entre com uma conta local de teste e envie cada arquivo pela aba Documentos,
   sem usar dados pessoais ou credenciais de produção.
5. Confirme `pending`/`processing` e depois `ready`, com `chunk_count` maior que
   zero; envie também um DOCX corrompido e confirme o estado `error`.
6. Faça uma pergunta que use o conteúdo sintético e confirme a fonte documental.
7. Exclua o documento `ready` e confirme que ele some da lista e deixa de ser
   recuperado.
8. Repita com outro tenant local e confirme que listagem, busca e exclusão não
   atravessam tenants.

O roteiro complementa, mas não substitui, os testes automatizados.

## OCR não suportado e troubleshooting

O MVP não executa OCR. Um PDF escaneado somente como imagem, sem camada textual,
termina em `error` com mensagem segura de falha de extração. Gere novamente o PDF
a partir do arquivo original com texto selecionável ou extraia o texto para TXT
ou DOCX antes do upload. Não envie repetidamente o mesmo arquivo esperando que o
backend reconheça imagens.

Se um documento ficar em `error`, verifique primeiro formato/MIME, integridade do
arquivo e existência de texto utilizável. Se a API não iniciar após uma mudança
de schema, confirme `alembic current`. Se documentos `ready` estiverem no banco,
mas não forem recuperados após uma troca autorizada de embedding, execute a
reindexação manual.

## Matriz de rastreabilidade resumida

| Requisito | Evidência automatizada principal |
| --- | --- |
| Upload → `ready` → retrieval com fonte → delete | `test_integrated_upload_retrieval_source_validity_tenant_and_delete_flow` |
| TXT, DOCX e PDF textual sintéticos | Casos parametrizados `txt`, `docx` e `pdf` do fluxo integrado |
| Erro real de parser sem chunks/vetores parciais | `test_integrated_parser_error_has_no_chunks_or_vectors` |
| Isolamento relacional e vetorial por tenant | Fluxo integrado e `test_real_pgvector_deletion_is_scoped_by_document_and_tenant` |
| Documento vencido fora do contexto | Fluxo integrado e `test_real_pgvector_retrieval_excludes_expired_chunks_and_keeps_tenant` |
| FAQ/evento preservados | `test_real_pgvector_keeps_faq_and_event_retrievable` e regressão rápida de contexto |
| Fonte parcial e prompt injection | `tests/quick/test_rag_context_sources.py` |
| Reindexação idempotente e isolada | Testes rápidos de reindexação e `test_manual_reindex_rebuilds_ready_sources_idempotently_per_tenant` |
| Cliente e aba Documentos | Testes Vitest de `document-api` e `document-tab` |
| Migration do zero | `tests/integration/test_migrations.py` e gate `Database / migration-integration` |
