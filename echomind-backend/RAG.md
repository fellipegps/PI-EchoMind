# Referência técnica do RAG

O [guia do backend](README.md) explica como configurar e executar a API. Rode os comandos desta referência a partir de `echomind-backend`, com o ambiente virtual ativo.

## Reindexação manual

O embedding padrao e `intfloat/multilingual-e5-small`, com exatamente 384
dimensoes. O adapter aplica `query: ` nas consultas e `passage: ` nas FAQs e
chunks **somente na entrada do encoder**; o texto persistido/apresentado, os
metadados e os IDs permanecem originais. Os chamadores entregam texto original,
sem acrescentar prefixos. Esse contrato segue o
[model card do E5](https://huggingface.co/intfloat/multilingual-e5-small#faq).

A inspecao do ambiente Python 3.12 (FastEmbed 0.6.1, LangChain Community 0.2.19
e Core 0.2.43) mostrou que o modelo customizado usa `CustomTextEmbedding`,
herdando `query_embed`/`passage_embed` sem prefixacao. O tokenizer recebia o
texto cru. O adapter E5 agora usa `TextEmbedding.embed` diretamente com o
prefixo correspondente, evitando combinar prefixos proprios com instrucoes
automaticas dos metodos especializados. Testes executam esse caminho real ate
um tokenizer/ONNX fake, sem baixar modelos. Outros modelos configurados mantem
o adapter anterior. Reavalie esse contrato ao atualizar FastEmbed/LangChain.

**Esta correcao exige reconstruir todos os vetores existentes, mesmo quando o
nome do modelo e a dimensao continuam iguais.** Nao existe troca atomica entre
colecoes nem uma barreira automatica por versao de embedding. Para atualizar:

1. Reserve janela de manutencao e registre a versao anterior. Tenha um backup
   consistente de fontes e vetores para eventual restauracao. Confirme o banco
   alvo e o inventario completo dos tenants/colecoes.
2. Bloqueie consultas ao chat/RAG e todas as escritas vetoriais (FAQs, upload,
   ingestao, exclusao, importacao). Drene requisicoes e processamento em curso;
   pare todas as instancias antigas antes de qualquer gravacao com o novo
   contrato. Somente pausar uploads nao impede consultas com contratos mistos.
3. Instale a versao corrigida em todos os executores, mantendo o atendimento
   bloqueado. Confirme as variaveis abaixo e a disponibilidade local do modelo
   no cache utilizado pelo operador/runtime. Nao use rollout gradual com
   instancias antigas e novas consultando a mesma colecao.
4. Execute a previa abaixo, revise todas as colecoes e resolva qualquer
   identificacao ambigua usando evidencia operacional. Execute a reconstrucao
   manual com as primitivas existentes, sem flags de Parent-Child.
5. Exija conclusao sem falhas e sem pendencias (saida `0`), confira todos os
   tenants, contagens de FAQs/chunks e amostras de fontes. Em caso de falha ou
   saida `2`, mantenha o RAG bloqueado, corrija a causa e gere outra previa antes
   de repetir. A repeticao reconstrói com os mesmos IDs, sem duplicar fontes.
6. Reinicie todas as instancias com a versao corrigida e so entao libere as
   consultas/escritas. Para reverter, mantenha a manutencao e restaure um backup
   compativel ou reconstrua integralmente os vetores com o adapter da versao
   anterior antes de reabrir o atendimento. Reverter somente o codigo misturaria
   novamente os contratos.

Os thresholds atuais permanecem inalterados; esta correcao nao os calibra. Nao
execute essa atualizacao automaticamente em ambientes reais. Os comandos a
seguir sao para o operador autorizado, durante a janela descrita acima:

```bash
# Confirme antes que o ambiente usa:
# EMBED_MODEL=intfloat/multilingual-e5-small
# EMBEDDING_DIM=384
python scripts/reindex_all.py --dry-run
# Revise a previa antes de autorizar as remocoes no mesmo banco:
python scripts/reindex_all.py --confirm
```

O script le a configuracao normal do backend, encontra tenants que possuem FAQs,
documentos `ready` ou uma colecao comprovadamente gerenciada pelo EchoMind e
processa um por vez. Isso inclui tenants sem fontes, que possuem apenas vetores
orfaos. A previa mostra tenant original, nome, UUID da colecao e quantidade de
vetores que sera removida, sem carregar o modelo ou escrever no banco. Para cada
tenant autorizado, somente a colecao correspondente e limpa e recriada; em
seguida, as FAQs e os `document_chunks` ja persistidos dos documentos
`ready` desse tenant sao indexados novamente com os IDs deterministicos atuais.
Documentos `pending`, `processing` e `error` sao ignorados. O arquivo original
nao e reprocessado e os chunks nao sao recriados.

Novas colecoes registram `managed_by=echomind`, `schema_version=1` e o
`tenant_id` original em seus metadados. Colecoes legadas sem esse marcador so
sao reconhecidas quando **todos** os vetores concordam sobre o tenant original,
o nome corresponde a sua sanitizacao e os tipos/IDs obedecem ao contrato
deterministico do EchoMind. Vetores legados de evento podem comprovar propriedade,
mas eventos nao sao reconstruidos. O nome sanitizado nunca e invertido para
adivinhar um tenant. Nomes duplicados, tenants que colidem na sanitizacao,
marcadores conflitantes e colecoes vazias sem identidade comprovada exigem
revisao operacional. Colecoes alheias, mesmo com prefixo `knowledge_`, permanecem
intactas. A identidade e revalidada antes de cada limpeza; uma troca do UUID
desde a previa interrompe a operacao.

Codigos de saida: `0` indica conclusao sem pendencias, `1` indica falha de
execucao e `2` indica casos preservados para revisao operacional. Na execucao
com `--confirm`, as acoes comprovadas podem concluir mesmo quando ha casos de
revisao; nenhuma colecao pendente e apagada. O relatorio mostra nome, UUID e
motivo. O operador deve consultar inventario/auditoria confiavel para comprovar
propriedade e tenant original antes de corrigir a identificacao. Nao associe
uma colecao a um tenant por semelhanca de nomes e nao a apague para contornar
o bloqueio.

A operacao para no primeiro tenant que falhar e informa os tenants ja concluidos.
A colecao que falhou pode estar vazia ou parcialmente reconstruida: nao ha
rollback vetorial distribuido. As fontes relacionais permanecem preservadas.
Corrija a causa, gere nova previa e repita o comando; os IDs deterministicos
permitem retomar sem duplicar vetores. Execute em janela de manutencao, com
upload, ingestao, exclusao e outras escritas vetoriais pausados. Nao execute duas
reindexacoes em paralelo. Confira o banco/ambiente alvo antes de cada comando;
testes e validacao usam somente PostgreSQL/pgvector local descartavel, nunca
staging ou producao.
Nenhuma reindexacao e iniciada automaticamente em startup, deploy, endpoint,
scheduler ou importacao.

As orientacoes de publicacao, verificacao de documentos e recuperacao estao no
[guia de deploy](../deploy/README.md). O limite de upload e definido por
`MAX_DOCUMENT_SIZE_MB`; PDFs digitalizados que dependem de OCR nao sao suportados.

## Avaliação offline

O dataset em `evals/rag_baseline_dataset.json` contém 20 casos
e um corpus inteiramente sintético, cobrindo datas, números, requisitos,
exceções, recusa, fontes e documentos vigentes/vencidos. Cada caso contém a
pergunta e a expectativa, enquanto as fontes guardam conteúdo e consultas de
recuperação sintéticos. O campo `human_review` permanece para revisão posterior;
a métrica automática não a substitui.

O runner executa recuperação, filtro de tenant/validade e geração extrativa com
adaptadores locais determinísticos. Ele não importa o runtime de produção nem
faz chamadas de rede, PGVector, embedding remoto ou LLM. As observações não são
lidas das expectativas: fontes, respostas e latências são produzidas durante a
execução. O relatório mede recall/precision de fontes, F1 lexical, correção por
regra, recusa, presença de citação e latência de cada etapa. Para regenerá-lo:

```bash
python scripts/eval_rag.py \
  --dataset evals/rag_baseline_dataset.json \
  --output evals/baseline_report.json
```

O JSON gerado lista saída, scores e falhas por caso, registra separadamente a
configuração de produção e o adaptador de avaliação e inclui hashes do dataset
e corpus. Ele é uma baseline executável de infraestrutura sintética, não mede a
qualidade do modelo real nem autoriza mudar threshold, embeddings ou estratégia.

### Calibração do threshold

O default de `SIMILARITY_THRESHOLD` permanece em `0.45`. A calibração executa
o modelo local `intfloat/multilingual-e5-small` sobre o corpus sintético e usa
14 casos para calibração e 6 como holdout. O sweep de `0.05` a `0.50`, em passos
de `0.01`, não encontrou um limiar que preserve simultaneamente recall mínimo e
recusa correta; portanto, a alteração anterior para `0.35` não foi confirmada.
O relatório completo está em
`evals/threshold_calibration_report.json`. O algoritmo, modelo,
top-K e filtro de validade permanecem fixos durante a comparação.

Para reproduzir a decisão:

```bash
python scripts/calibrate_similarity_threshold.py \
  --dataset evals/rag_baseline_dataset.json \
  --split evals/similarity_threshold_split.json \
  --output evals/threshold_calibration_report.json
```

Por padrão, o comando exige que o modelo já esteja no cache local e não acessa
a rede. Em uma preparação explícita do ambiente, use `--allow-model-download`
caso seja necessário baixar o modelo pela primeira vez. Nenhuma LLM é chamada.

### Busca híbrida PostgreSQL + PGVector

A recuperação agora preserva o PGVector e acrescenta candidatos lexicalmente
encontrados no PostgreSQL. As quatro consultas full-text usam `tenant_id`
explicitamente: FAQs, eventos, metadados de documentos e conteúdo dos chunks;
chunks também exigem documento `ready` e vigente. A migration `0010` adiciona
apenas índices GIN de expressão, sem tabela global ou cópia manual do corpus.

Os canais são fundidos com Reciprocal Rank Fusion (RRF): cada ocorrência soma
`1 / (60 + posição)`; fontes são deduplicadas por `(source_type, source_id)` e
empates usam posição vetorial, posição lexical, tipo e ID. O threshold de 0,45
continua valendo somente para o canal vetorial; a busca lexical permite que
códigos e siglas exatos sejam candidatos sem alterar embeddings, top-K ou a
estratégia semântica existente.

O custo adicional é de quatro consultas FTS curtas por pergunta, cobertas pelos
índices GIN. O rollback de aplicação é seguro porque a busca vetorial continua
autônoma; os índices da migration podem permanecer (ou ser removidos pelo
downgrade) sem apagar conteúdo nem vetores. Se o canal lexical falhar ou estiver
indisponível, a recuperação usa os candidatos vetoriais já obtidos; uma falha no
canal vetorial continua sendo erro porque ele permanece o componente central.

A comparação executável está em
`evals/hybrid_search_report.json`. Ela calcula embeddings com o
mesmo modelo FastEmbed do runtime, aplica tenant, validade, threshold, top-K e a
mesma implementação RRF da aplicação. O runner não aceita rankings preenchidos
no dataset e, por padrão, exige o modelo no cache local, sem rede ou LLM. A
consulta lexical offline usa um proxy determinístico por tokens; as consultas
PostgreSQL FTS reais, seus índices e filtros são exercitados pela suíte de
integração. Para reproduzir:

```bash
python scripts/eval_hybrid_search.py \
  --dataset evals/hybrid_search_eval.json \
  --baseline-pr22 evals/baseline_report.json \
  --output evals/hybrid_search_report.json
```

Nos seis casos dedicados, o canal vetorial obteve recall/MRR@3 de 0,500/0,500
e o híbrido 1,000/1,000, ganho de 0,500 nas duas métricas. Códigos, siglas e
nomes exatos melhoraram sem regressão nos três casos semânticos. A baseline da
PR 23 é o próprio canal vetorial executado com a configuração fixa anterior. A
baseline da PR 22 permanece registrada lado a lado em recall/precision de fontes
1,000/1,000; como os datasets são diferentes, esses números não são tratados
como um delta direto. O relatório registra hashes, versões e toda a configuração
fixa para permitir repetição da medição.

### Reranker de candidatos

O reranker é aplicado somente depois da recuperação e da fusão híbrida. Quando
ativado, reordena até 12 candidatos (configurável entre 10 e 15), limita cada
texto a 2.000 caracteres e entrega o `TOP_K_DOCS` existente. Conteúdo e metadata
dos objetos recuperados não são reconstruídos; tenant, fonte e validade já
filtrados permanecem inalterados.

A implementação usa o `TextCrossEncoder` do FastEmbed, já presente nas
dependências. O modelo operacional padrão é `BAAI/bge-reranker-base`, licença
MIT e tamanho aproximado de 1,04 GB. A sessão ONNX e os arquivos em `HF_HOME`
ficam em cache no processo. Como esse modelo não declara suporte amplo a PT-BR,
`RERANKER_ENABLED=false` é o default conservador; a ativação exige avaliação
controlada do corpus real. O modelo multilíngue listado pelo FastEmbed não foi
adotado porque sua licença é CC-BY-NC-4.0.

O runtime nunca baixa o modelo automaticamente. Quando o recurso é habilitado,
ele usa apenas os arquivos previamente preparados no cache; ausência ou falha
de carga aciona o fallback híbrido. O download consciente para avaliação pode
ser feito pelo runner com `--allow-model-download`.

Timeout, erro, modelo ausente ou reranker ocupado geram aviso com etapa,
quantidade de candidatos e latência, e retornam exatamente o ranking híbrido da
PR 24. As inferências usam um executor com capacidade um. Se uma chamada excede
o timeout, ela pode terminar na thread nativa, mas nenhuma outra inferência é
enfileirada enquanto essa chamada estiver ativa; isso limita o consumo e evita
acúmulo de trabalhos abandonados. Os testes usam fakes e não baixam modelo nem
fazem chamadas externas.

O benchmark versionado gera os candidatos com o embedding da PR 24, executa o
cross-encoder real sobre perguntas PT-BR e mede os tempos no host. Scores,
rankings e latências não ficam preenchidos no dataset. Para reproduzir sem rede,
o modelo deve estar no cache local:

```bash
python scripts/eval_reranker.py \
  --config evals/reranker_eval.json \
  --dataset evals/hybrid_search_eval.json \
  --baseline-pr22 evals/baseline_report.json \
  --baseline-pr24 evals/hybrid_search_report.json \
  --output evals/reranker_report.json
```

No benchmark local de seis casos, o ranking híbrido obteve Hit@3/MRR@3 de
1,000/1,000 e o reranker `BAAI/bge-reranker-base` obteve 1,000/0,889: Hit@3 foi
preservado, mas MRR@3 regrediu 0,111. O aquecimento medido foi de aproximadamente
3,17 s; a inferência teve média de 1,77 s e p95 de 2,13 s, acima do timeout
operacional de 1,5 s.
Esses resultados não justificam ativar o modelo: `RERANKER_ENABLED` permanece
`false`. O relatório registra ambiente e resultados por caso; tempos devem ser
reavaliados no hardware de destino antes de considerar outro modelo aprovado.

### Cache seguro de FAQs

O atalho de FAQ usa igualdade exata depois de normalizar Unicode, acentos,
caixa, pontuação e espaços. A confiança do cache é binária e exige `1.0`; não há
fuzzy matching nem reaproveitamento do threshold vetorial. Perguntas apenas
parecidas, extensões de uma FAQ ou coincidências por palavra são misses e seguem
uma única vez para o pipeline RAG existente. Se duas FAQs normalizarem para a
mesma pergunta, o resultado também é tratado como ambíguo e não usa o cache.

A consulta das dez FAQs candidatas continua sempre limitada pelo `tenant_id`.
Criação, atualização, exclusão, conversão de pergunta não respondida e incremento
de consulta invalidam as linhas em memória. O dataset sintético versionado no
teste `tests/quick/test_faq_cache_matching.py` contém seis hits e seis misses: o
matching antigo preservava 2/6 hits e produzia 5/6 falsos positivos conhecidos;
o matching seguro preserva 6/6 hits e produz 0/6 falsos positivos nesse conjunto.
O comparativo determinístico é reproduzido por:

```bash
python -m pytest tests/quick/test_faq_cache_matching.py
```

## Logs estruturados do RAG

Retrieval, geração do chat, ingestão e operações vetoriais emitem eventos JSON
locais pelo logger `echomind.observability`. O schema está na versão 1 e mantém
os campos `event`, `status`, `stage`, `correlation_id` e `tenant_ref`; eventos
aplicáveis também incluem `duration_ms`, contagens, tipos de fonte e um código
de erro técnico. A correlação é criada pelo servidor e isolada por operação.

O `tenant_ref` contém somente os primeiros 16 caracteres de um SHA-256 com
namespace próprio; o `tenant_id` original não é registrado. Perguntas,
respostas, texto ou bytes de documentos, nomes de arquivo, IDs de fonte,
mensagens de exceção, tokens, headers de autorização, senhas e secrets não fazem
parte do schema. Tipos de fonte desconhecidos são agrupados como `other`, e os
logs não devem ser usados diretamente como dimensões de métricas de alta
cardinalidade.

Nesta etapa, a saída usa apenas o logging padrão do processo e não envia dados a
APM, collector ou serviço externo. Retenção, acesso e descarte seguem a política
do ambiente que captura `stdout`/`stderr`; como o projeto ainda não definiu esse
destino, nenhuma retenção adicional é criada pela aplicação. Falhas do sink de
logging são isoladas e não mudam a resposta do chat nem o processamento.

## Métricas operacionais do RAG

O dashboard administrativo consulta agregados diários da tabela
`rag_metric_daily`. Cada linha representa somente um tenant e um dia, com
contagens fixas de chat, retrieval, ingestão, falhas, perguntas sem resposta e
tipos de fonte, além das somas necessárias para calcular médias de latência e
resultados recuperados. Perguntas, respostas, documentos, nomes, tokens,
mensagens de erro e IDs de fontes nunca são persistidos nessa tabela.

Os eventos sanitizados da seção anterior são a única origem dos agregados. A
retenção é de 90 dias corridos e o descarte de linhas vencidas ocorre durante a
gravação de novos eventos. O endpoint autenticado
`GET /dashboard/rag-metrics?days=30` aceita janelas de 1 a 90 dias e sempre usa
o tenant derivado da sessão administrativa; não recebe `tenant_id` do cliente.
A tabela possui chave por tenant/data, índice de retenção e RLS seguindo o
padrão atual do projeto. Falhas de persistência das métricas não alteram o
chat, o retrieval nem a ingestão principal.

A gravação não ocorre no caminho crítico da requisição: somente eventos
agregáveis entram em uma fila local limitada e um worker único os persiste em
lotes. Cada lote usa uma transação e executa a retenção uma vez por tenant. Se
o banco estiver indisponível ou a fila atingir o limite, a operação principal
continua normalmente; métricas operacionais podem ser descartadas até a
capacidade local se recuperar.
