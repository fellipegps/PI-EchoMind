# PR 08 — Extração de TXT e DOCX

## Objetivo

Implementar extractors determinísticos de TXT e DOCX com um contrato comum, cobrindo encodings, parágrafos, tabelas e conteúdo vazio.

## Contexto

Validação de upload já existe na PR 07. Esta fase transforma apenas TXT/DOCX válidos em unidades de texto com metadados mínimos; PDF e chunking ficam separados.

## Pré-requisitos

- PR 07 mergeada.
- Definir estrutura interna mínima de saída sem acoplar a LangChain ou banco.

## Dependências

Obrigatórias: PR 07.

Não depende de: PR 09 ou PRs 10–35.

Paralelização: pode ocorrer em paralelo com PR 09; ambas devem mergear antes da PR 10.

## Escopo desta PR

- Adicionar `python-docx` em versão compatível.
- Implementar `extract_txt(...)`: UTF-8 primeiro, fallback controlado documentado e normalização de linhas que preserve parágrafos.
- Implementar `extract_docx(...)`: parágrafos e conteúdo de tabelas em ordem determinística.
- Retornar estrutura comum adequada a chunking posterior, com seção quando inferível sem heurística ampla.
- Rejeitar vazio/sem texto com erro de domínio controlado.
- Criar fixtures sintéticas mínimas e testes sem rede/banco.

## Arquivos provavelmente envolvidos

- `echomind-backend/requirements.txt`
- `echomind-backend/app/document_ingestion.py`
- `echomind-backend/tests/test_document_ingestion.py`
- `echomind-backend/tests/fixtures/documents/`

## Implementação

Preservar a ordem do documento. Tabelas DOCX devem incluir células relevantes sem duplicar texto já extraído. O fallback de encoding deve ser explícito e limitado, não uma detecção opaca que aceite lixo silenciosamente.

## Regras técnicas

- Saída não conhece ORM, PGVector, FastAPI ou splitter.
- Fixtures não contêm dados pessoais/reais.
- Erros públicos não expõem detalhes de biblioteca.
- Não perder quebras de parágrafo úteis a artigos/seções.

## Não implementar nesta PR

- PDF/OCR;
- chunking/overlap;
- SHA ou validação já cobertos na PR 07;
- persistência, indexação, API, background ou frontend.

## Testes obrigatórios

- TXT UTF-8, fallback permitido, quebra de linha e vazio.
- TXT com bytes inválidos fora do fallback.
- DOCX com parágrafos, tabela, ambos combinados e vazio.
- Ordem determinística e ausência de duplicação evidente.
- Suíte rápida completa.

## Critérios de aceite

- TXT/DOCX válidos retornam texto ordenado no contrato comum.
- Vazio/inválido produz erro controlado.
- Nenhum código PDF ou chunking foi introduzido.

## Definition of Done

Dependência, fixtures e testes estão verdes e documentam o comportamento dos dois formatos.

## Riscos e cuidados

DOCX pode intercalar tabelas e parágrafos; preservar a ordem real quando a biblioteca permitir. Não aceitar fallback de encoding que transforme arquivo binário em texto aparentemente válido.

## Resultado esperado

Dois formatos do MVP ficam extraíveis e prontos para o splitter futuro.

## Instrução final ao Codex

Implemente somente TXT/DOCX e seus testes. Não implemente PDF ou chunking. Pare.
