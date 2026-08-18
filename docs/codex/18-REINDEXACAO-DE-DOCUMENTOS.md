# PR 18 — Reindexação de documentos prontos

## Objetivo

Estender o script de reindexação da PR 03 para incluir chunks de documentos `ready`, agora que schema e contrato vetorial são reais.

## Contexto

O script inicial deliberadamente só conhece FAQ/evento. Esta fase evita código antecipado e completa a operação depois do pipeline estabilizado.

## Pré-requisitos

- PRs 03, 12, 13 e 17 mergeadas.
- Reindexação e indexação documental idempotentes comprovadas.

## Dependências

Obrigatórias: PR 03, PR 12, PR 13 e PR 17.

Não depende de: frontend.

Paralelização: PR 19 pode ser feita em paralelo; ambas precedem o fechamento do MVP.

## Escopo desta PR

- Consultar documentos `ready` e chunks por tenant.
- Reindexar FAQ, evento e chunk documental na coleção daquele tenant.
- Excluir/reconstruir somente a coleção alvo, com confirmação/dry-run se o padrão operacional permitir.
- Ignorar `pending`, `processing` e `error`.
- Validar contagens e reportar falha por tenant sem mascarar parcial.
- Testar seleção, ordem, isolamento, idempotência e retomada segura.

## Arquivos provavelmente envolvidos

- `echomind-backend/scripts/reindex_all.py`
- repository/query documental
- testes do script
- `README.md`

## Implementação

Reutilizar `index_document_chunk`; não duplicar montagem de conteúdo/metadata. Processar tenant por tenant e liberar recursos entre tenants. Definir política clara ao falhar no meio.

## Regras técnicas

- Não tocar em `knowledge_documents`.
- Não apagar coleção de outro tenant.
- Não reprocessar arquivo nem recriar chunks; apenas reindexar chunks persistidos.
- Não executar automaticamente em deploy.

## Não implementar nesta PR

- endpoint de reindex;
- scheduler;
- retry distribuído;
- mudança de embedding/threshold;
- frontend;
- Hybrid Search.

## Testes obrigatórios

- Seleciona somente `ready`.
- Reutiliza IDs/metadata determinísticos.
- Tenant A não altera coleção B.
- Segunda execução produz o mesmo conjunto.
- Falha de um tenant é reportada de modo claro conforme política.
- FAQ/evento continuam incluídos.

## Critérios de aceite

- Operador consegue reconstruir coleções a partir do banco relacional atual.
- Conteúdo não pronto é ignorado.
- Script permanece consciente e não automático.

## Definition of Done

Script, testes e instruções operacionais verdes, sem endpoint ou feature futura.

## Riscos e cuidados

Limpar antes de confirmar que a fonte relacional está íntegra pode causar indisponibilidade. Documentar uso e evitar paralelismo destrutivo entre execuções.

## Resultado esperado

Troca de embedding/recuperação de desastre pode reconstruir todos os tipos atuais com isolamento.

## Instrução final ao Codex

Estenda somente o script para documentos `ready`, teste e pare.
