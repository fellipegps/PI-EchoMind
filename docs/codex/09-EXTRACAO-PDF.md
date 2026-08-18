# PR 09 — Extração PDF page-aware

## Objetivo

Implementar extração de PDF textual página por página, preservando número de página e distinguindo arquivo inválido, criptografado e sem camada textual.

## Contexto

PDFs institucionais precisam de referência de página. OCR está explicitamente fora do MVP; PDFs escaneados devem falhar de forma compreensível.

## Pré-requisitos

- PR 07 mergeada.
- Usar o mesmo contrato interno de extração acordado para a PR 08, sem depender da implementação dela.

## Dependências

Obrigatórias: PR 07.

Não depende de: PR 08 ou PRs 10–35.

Paralelização: pode ocorrer em paralelo com PR 08.

## Escopo desta PR

- Adicionar `pypdf` compatível com o projeto.
- Implementar `extract_pdf(...)` com `PdfReader` e saída por página.
- Preservar páginas vazias como lacunas de metadata sem gerar chunks vazios.
- Tratar PDF textual, corrompido, criptografado não abrível e documento sem texto suficiente.
- Emitir erro claro de “OCR não suportado no MVP” quando aplicável.
- Criar fixtures sintéticas pequenas e testes.

## Arquivos provavelmente envolvidos

- `echomind-backend/requirements.txt`
- `echomind-backend/app/document_ingestion.py`
- `echomind-backend/tests/test_document_ingestion.py`
- `echomind-backend/tests/fixtures/documents/`

## Implementação

Extrair e normalizar texto por página sem concatenar cedo. Definir um critério pequeno e testável para “texto insuficiente”, evitando classificar como OCR um PDF textual curto legítimo. A mensagem persistível deve ser curta.

## Regras técnicas

- Página é 1-based no contrato externo, salvo convenção existente expressa.
- Não executar ferramentas de sistema ou OCR.
- Não carregar arquivo acima do limite; a PR 07 permanece a barreira anterior.
- Saída não conhece banco, PGVector ou FastAPI.

## Não implementar nesta PR

- OCR/Tesseract/serviço externo;
- TXT/DOCX;
- chunking;
- persistência/indexação;
- API/background/frontend.

## Testes obrigatórios

- PDF textual de uma e várias páginas.
- Preservação da numeração e ordem.
- Página sem texto entre páginas válidas.
- PDF corrompido e criptografado.
- PDF sem camada textual gera erro específico de OCR não suportado.
- Suíte rápida completa.

## Critérios de aceite

- Conteúdo e página chegam no contrato de extração.
- Casos inválidos têm erro controlado e seguro.
- Nenhum OCR ou chunking foi antecipado.

## Definition of Done

Extractor, dependência, fixtures e testes PDF estão verdes.

## Riscos e cuidados

`extract_text()` pode retornar `None` e layouts complexos podem alterar espaços. Testar comportamento sem prometer fidelidade visual. Não incluir documentos reais nas fixtures.

## Resultado esperado

PDF textual fica pronto para chunking page-aware e citação posterior.

## Instrução final ao Codex

Implemente exclusivamente extração PDF textual e pare após os testes.
