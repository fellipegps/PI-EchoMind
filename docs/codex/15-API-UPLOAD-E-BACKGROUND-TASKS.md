# PR 15 — API de upload e BackgroundTasks

## Objetivo

Expor `POST /documents/upload` multipart, criar registro `pending`, agendar o processador in-process e retornar `202` com contrato testado.

## Contexto

Validação, repository, processamento e endpoints de leitura já foram isolados. Esta fase faz apenas a borda HTTP e o agendamento FastAPI do MVP.

## Pré-requisitos

- PRs 07, 13 e 14 mergeadas.
- Confirmar convenção real de autenticação e multipart no projeto.

## Dependências

Obrigatórias: PR 07, PR 13 e PR 14.

Não depende de: prompt/citação, validade ou frontend.

Paralelização: PRs 16–17 e 19 aguardam este contrato mergeado.

## Escopo desta PR

- Adicionar `POST /documents/upload` administrativo autenticado.
- Aceitar um PDF/TXT/DOCX e metadados opcionais por request.
- Obter tenant somente de `current_user.id`.
- Ler/copiar bytes necessários antes de fechar `UploadFile`.
- Validar tamanho, MIME/extensão/nome/hash e duplicidade.
- Criar documento `pending`, agendar `process_document` via `BackgroundTasks` e retornar `202` com `document.id`/response.
- Mapear tipo inválido, excesso e duplicidade a 4xx consistentes (`415`, `413`, `409` ou contrato validado).

## Arquivos provavelmente envolvidos

- `echomind-backend/app/main.py`/router
- schemas/config mínimos
- `echomind-backend/tests/test_documents.py`
- `echomind-backend/tests/conftest.py`

## Implementação

O teste HTTP deve substituir a execução da task por fake/controlador quando necessário, sem Groq/PGVector. A task recebe dados duráveis e abre sua própria sessão. Metadados opcionais vazios não bloqueiam upload.

## Regras técnicas

- Nunca confiar em `tenant_id` multipart.
- Não definir job ID separado: document ID é o acompanhamento.
- Resposta 202 deve ser rápida e não esperar embedding.
- Erro interno não vaza stack trace.
- Um arquivo por request.

## Não implementar nesta PR

- Celery/Redis/job table;
- múltiplos arquivos;
- OCR;
- frontend/polling;
- citação/validade;
- rate limiting (PR 28);
- Docker/deploy.

## Testes obrigatórios

- Autenticação obrigatória e tenant derivado do usuário.
- Upload válido retorna 202 e agenda exatamente uma task.
- PDF/TXT/DOCX aceitos.
- MIME/extensão inválidos, excesso e vazio.
- Hash duplicado mesmo tenant retorna 409; tenant distinto é permitido.
- Filename sanitizado.
- Metadados opcionais persistidos.
- `UploadFile` fechado não invalida os dados da task.
- Erro posterior do parser leva a `error` via serviço já testado.

## Critérios de aceite

- Upload cria acompanhamento persistente e agenda processamento sem bloquear.
- Regras HTTP e multi-tenant estão cobertas.
- APIs anteriores continuam verdes.

## Definition of Done

Contrato multipart/API testado, task in-process corretamente ligada e CI aplicável verde.

## Riscos e cuidados

Capturar `UploadFile` diretamente causa uso após fechamento. Leitura ilimitada esgota memória; reaproveitar barreira da PR 07. BackgroundTasks não é fila durável, decisão consciente do MVP.

## Resultado esperado

O pipeline documental pode ser iniciado por uma chamada autenticada e acompanhado pelos GETs existentes.

## Instrução final ao Codex

Implemente apenas POST multipart e ligação com BackgroundTasks. Teste, liste alterações e pare.
