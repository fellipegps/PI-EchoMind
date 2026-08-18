# PR 07 — Validação de upload, sanitização e SHA-256

## Objetivo

Criar primitivas puras para validar arquivo documental, limitar tamanho, sanitizar nome e calcular SHA-256 determinístico antes de parsing/indexação.

## Contexto

Upload futuro precisa rejeitar cedo extensão/MIME/tamanho inválidos e detectar duplicidade por tenant. O contrato deve ser testável sem FastAPI ou banco externo.

## Pré-requisitos

- PR 06 mergeada.
- Confirmar como configurações de ambiente são declaradas no backend.

## Dependências

Obrigatórias: PR 06.

Não depende de: extractors, PGVector, endpoints ou frontend.

Paralelização: PRs 08 e 09 podem começar separadamente depois desta fase.

## Escopo desta PR

- Introduzir módulo de ingestão/validação sem stubs de extractors futuros.
- Permitir `.pdf`, `.txt`, `.docx` com extensão e MIME coerentes.
- Configurar `MAX_DOCUMENT_SIZE_MB`, default 10, em config e `.env.example`.
- Ler bytes de forma limitada, rejeitando excesso sem consumo inseguro de memória quando a API futura integrar.
- Sanitizar filename por basename e normalização segura.
- Calcular SHA-256 dos bytes originais.
- Integrar a consulta de duplicidade do repository em um serviço de validação sem criar documento.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/document_ingestion.py` (novo)
- módulo de config existente
- `echomind-backend/.env.example`
- `echomind-backend/tests/test_document_ingestion.py`

## Implementação

Separar validações puras (bytes/nome/MIME/config) da consulta de duplicidade. Definir exceções de domínio claras que a PR 15 mapeará para HTTP. Não confiar apenas no `Content-Type` enviado pelo cliente.

## Regras técnicas

- Hash é do arquivo original, antes de normalização.
- Mesmo hash em tenants diferentes continua válido.
- Filename retornado não pode conter caminho, NUL ou segmentos relativos.
- A validação do cliente futuro nunca substitui esta validação do servidor.

## Não implementar nesta PR

- extração PDF/TXT/DOCX;
- chunking;
- criação de registro `documents`;
- endpoint multipart;
- background processing;
- indexação;
- frontend.

## Testes obrigatórios

- Formatos/extensões/MIMEs válidos e combinações inválidas.
- Arquivo vazio e acima/abaixo do limite.
- Limite configurável.
- SHA-256 determinístico e sensível aos bytes.
- Sanitização de caminhos Unix/Windows e nomes maliciosos.
- Duplicado no mesmo tenant/estado é rejeitado; outro tenant é permitido.

## Critérios de aceite

- Entradas inválidas falham antes do parser.
- Exceções são estáveis para mapeamento HTTP futuro.
- Nenhum endpoint ou parser foi criado.

## Definition of Done

Validação e hashing cobertos sem rede, com suíte rápida verde e configuração documentada.

## Riscos e cuidados

MIME é um sinal, não prova absoluta; manter allowlist dupla. Evitar ler arquivo ilimitado. Não transformar mensagens internas em stack traces para usuário.

## Resultado esperado

Existe uma fronteira segura e determinística para os extractors e a API.

## Instrução final ao Codex

Implemente exclusivamente validação/hash/config e seus testes. Não faça parsing nem rotas. Pare.
