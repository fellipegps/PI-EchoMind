# PR 10 — Chunking determinístico e page-aware

## Objetivo

Converter a saída dos extractors em chunks ordenados de base 800/100, preservando página, seção e determinismo.

## Contexto

TXT/DOCX e PDF agora produzem texto estruturado. O splitter deve permanecer independente de banco e PGVector para ser testado exaustivamente.

## Pré-requisitos

- PRs 08 e 09 mergeadas.
- Contrato comum de saída dos extractors estabilizado.

## Dependências

Obrigatórias: PR 08 e PR 09.

Não depende de: schema vetorial, API, background ou frontend.

Paralelização: PR 11 pode evoluir em paralelo; PR 12 aguarda ambas.

## Escopo desta PR

- Adicionar `langchain-text-splitters` compatível com LangChain 0.2.x.
- Implementar `chunk_document(...)` com `chunk_size=800`, `chunk_overlap=100` e separadores institucionais previstos.
- Manter chunks PDF page-aware e preencher `page_start/page_end` corretamente.
- Preservar `section_title` quando a extração fornecer, sem Parent-Child.
- Gerar `chunk_index` contíguo e determinístico.
- Testar limite, overlap, ordem, páginas, metadados, texto vazio e reexecução.

## Arquivos provavelmente envolvidos

- `echomind-backend/requirements.txt`
- `echomind-backend/app/document_ingestion.py`
- `echomind-backend/tests/test_document_ingestion.py`
- fixtures sintéticas existentes

## Implementação

Usar `RecursiveCharacterTextSplitter` com os separadores do plano original. Se um trecho atravessar páginas, metadata deve refletir o intervalo real; não inventar página. Normalizar apenas o necessário para estabilidade.

## Regras técnicas

- Mesma entrada/configuração produz mesmos chunks e índices.
- Conteúdo não vazio e ordem original são invariantes.
- Overlap não deve gerar chunks duplicados completos.
- Tamanho é medido conforme a implementação do splitter e documentado nos testes.

## Não implementar nesta PR

- Parent-Child Retrieval;
- embeddings/PGVector;
- persistência de chunks;
- API/background;
- tuning baseado em eval;
- frontend.

## Testes obrigatórios

- Texto menor/igual/maior que o tamanho.
- Overlap e separadores prioritários.
- Ordem e índices determinísticos em duas execuções.
- PDF de múltiplas páginas e chunk cruzando página.
- `page_start/page_end` e seção preservados.
- Vazio rejeitado sem chunk vazio.

## Critérios de aceite

- Chunks 800/100 são reprodutíveis e metadados continuam rastreáveis.
- Nenhum efeito em banco ou RAG.
- Suíte rápida verde.

## Definition of Done

Splitter e testes de limites/metadados estão verdes, sem técnicas avançadas de retrieval.

## Riscos e cuidados

Caracteres não equivalem a tokens; não misturar otimização de contexto nesta fase. Separadores jurídicos podem aparecer sem newline; documentar o comportamento real em testes.

## Resultado esperado

Qualquer extractor do MVP gera unidades persistíveis e indexáveis com ordem estável.

## Instrução final ao Codex

Implemente somente chunking e testes. Não persista nem indexe chunks. Pare.
