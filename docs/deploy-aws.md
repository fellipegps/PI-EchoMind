# Preparação do EchoMind para publicação na AWS

Branch de trabalho: `codex/deploy-config`. A preparação será feita em etapas;
cada etapa precisa de evidência de validação antes de ser marcada como concluída.
As etapas iniciais preparam o backend localmente. A publicação depende das
etapas de infraestrutura, segredos, HTTPS e validação dos serviços reais.

## Arquitetura definida

- Frontend Next.js na Vercel, usando a configuração já documentada no README.
- Backend FastAPI em um container Linux `amd64` em uma EC2 na região `us-east-1`.
- PostgreSQL, pgvector e autenticação continuam no Supabase.
- Geração das respostas continua na Groq; embeddings E5 rodam na CPU da EC2.
- Uma instância e um worker. O limitador em memória bloqueia configurações com
  mais workers ou réplicas; escalar exige primeiro um store compartilhado.
- `t3.small` com 2 GiB permanece como candidata para o MVP de baixo tráfego;
  o tamanho definitivo depende da medição no container com o modelo real e da
  margem para o sistema operacional e o proxy. A medição local anterior não
  equivale a um teste em Linux limitado a 2 GiB. Não é necessário usar GPU.
- A disponibilidade e a validade dos créditos da conta precisam ser verificadas
  antes de provisionar. Esta configuração não promete hospedagem gratuita permanente.

## Checklist de execução

- [x] **1. Análise e empacotamento do backend:** Dockerfile, contexto sem segredos,
  dependências fixadas para Python 3.12/Linux, usuário sem privilégios, um worker,
  teste de construção, inicialização, `/health` e encerramento controlado.
- [x] **2. Inicialização automática:** Compose para a EC2, reinício após falha/reboot,
  volume do cache de modelos, rotação de logs, limites de recursos e tempo de parada.
  O Docker precisa estar habilitado no boot. Um healthcheck isolado não reinicia
  automaticamente um processo travado.
- [x] **3. Persistência e segurança dos uploads durante atualizações:** definir e
  implementar a retenção dos originais, recuperação de processamento interrompido,
  drenagem antes de trocar versões e teste de recriação do container sem perda.
  Definir backup e recuperação; volume local não substitui backup.
- [x] **4. Configuração de produção e segredos:** exemplo sem valores reais,
  validação de variáveis obrigatórias, armazenamento fora do Git e da imagem,
  entrega ao processo em tempo de execução e permissões mínimas. Se houver uso do
  Secrets Manager pelo agente, usar `asm-exec` e referências dinâmicas.
- [ ] **5. HTTPS e acesso público:** definir domínio da API, proxy e certificados
  com renovação, portas públicas 80/443, API acessível somente pelo proxy, CORS exato,
  streaming e limite de upload. Configurar confiança no IP do proxy para preservar
  o IP do cliente no rate limiting sem aceitar cabeçalhos falsificados.
- [ ] **6. Infraestrutura AWS:** revisar créditos e custos, identidade dedicada,
  EC2 por infraestrutura como código, acesso administrativo via Systems Manager,
  EBS criptografado e persistente, regras de rede, backup e orçamento/alertas.
- [ ] **7. Banco e frontend:** conferir migrations com backup e acesso PostgreSQL,
  aplicar migrations como operação explícita, ajustar URL HTTPS da API na Vercel e
  URLs de autenticação no Supabase. Reindexação de embeddings continua manual.
- [ ] **8. Publicação por GitHub Actions:** testes antes de publicar, autenticação
  temporária OIDC, imagem identificada pelo commit, atualizações serializadas,
  drenagem de tarefas, verificação após deploy e recuperação da versão anterior.
  O fluxo atual em `.github/workflows/ci.yml` apenas testa e constrói o frontend.
- [ ] **9. Validação em produção:** login, recuperação de senha, chat, upload e
  consulta de documentos, memória/CPU/disco com embeddings reais, revisão de
  vulnerabilidades das dependências, logs e recuperação após reinício.

## Diagnóstico inicial, antes das etapas de preparação

| Área | Situação inicial | Consequência para o deploy |
| --- | --- | --- |
| Runtime | FastAPI/Uvicorn e Python 3.12; frontend Next.js com Node 22 | Empacotar apenas o backend para EC2; manter o frontend separado |
| Dependências | Há versões fixas e intervalos em `requirements.txt` | Usar um lock específico de produção para evitar resolução diferente a cada build |
| Inicialização | A API pede Alembic antes de iniciar e aquece o RAG com timeout | Não aplicar migrations nem reindexar automaticamente ao reiniciar |
| Verificação | `/health` retorna que a API está viva | Não comprova banco, login, LLM ou disponibilidade do modelo |
| Uploads | Os bytes originais são passados em memória para `BackgroundTasks` | Encerrar o processo pode interromper um upload já aceito; um volume sozinho não resolve |
| Documentos processados | Metadados, texto, chunks e vetores ficam no PostgreSQL/Supabase | Recriar a API preserva o conteúdo já persistido; é necessário planejar backup do banco |
| Arquivos originais | Não há gravação durável dos PDFs/TXTs/DOCXs recebidos | A retenção e a retomada precisam ser tratadas na etapa 3 |
| Modelos | O código aceita `HF_HOME` para o cache do FastEmbed | Montar um volume nesse caminho para evitar novo download a cada atualização |
| Rate limiting | O código exige uma instância e um worker e usa o IP da conexão | Manter um worker e configurar corretamente o proxy HTTPS |
| Segredos | O backend usa `DATABASE_URL`, `SUPABASE_SECRET_KEY` e `GROQ_API_KEY` | Injetar em runtime; nunca copiar `.env` para o build ou usar chaves privadas no frontend |

## Etapa 1: empacotamento

Arquivos:

- `echomind-backend/Dockerfile`: base oficial Python 3.12/Bookworm fixada por digest,
  dependências com hashes, execução com UID/GID 10001 e um worker Uvicorn.
- `echomind-backend/.dockerignore`: permite apenas os arquivos explicitamente
  necessários; exclui configuração local, credenciais, testes e caches.
- `echomind-backend/requirements-deploy.lock`: dependências diretas e transitivas
  resolvidas para Python 3.12 em Linux `amd64`. Não substitui o arquivo usado no
  desenvolvimento Windows/Python 3.13 ou superior.

A imagem não contém banco de dados, frontend, segredos ou modelos baixados.
O caminho do cache é `/var/cache/echomind/models`. O volume é configurado pelo
Compose da etapa 2. A etapa 1 não garante retenção dos arquivos originais ou recuperação de
uploads interrompidos.

### Construir a imagem

Na raiz do repositório, com Docker em modo de containers Linux:

```sh
docker build --platform linux/amd64 --tag echomind-backend:local ./echomind-backend
```

O build não precisa de credenciais AWS, Supabase ou Groq. Não use o `.env` como
argumento de build. A base fixada por digest e o lock precisam ser atualizados
deliberadamente para incorporar correções de dependências.

### Verificar inicialização sem acessar serviços reais

Este teste usa apenas valores fictícios e desativa o aquecimento do RAG. O banco
aponta para uma porta local indisponível dentro do container. Não valida chat,
autenticação, migrations, ingestão ou download do E5.

```sh
docker run --detach --name echomind-backend-smoke --publish 127.0.0.1:18000:8000 --cpus 2 --memory 2g --env DATABASE_URL=postgresql://smoke:smoke@127.0.0.1:1/smoke --env SUPABASE_URL=http://127.0.0.1:54321 --env SUPABASE_SECRET_KEY=smoke-placeholder --env GROQ_API_KEY=smoke-placeholder --env RAG_WARMUP_ENABLED=false echomind-backend:local
```

Após a inicialização, abra `http://127.0.0.1:18000/health`. A resposta esperada é
`{"status":"ok","service":"EchoMind API"}`. O container deve executar com o
usuário `10001:10001` e sem processos de desenvolvimento ou recarga automática.

```sh
docker inspect --format '{{.Config.User}}' echomind-backend-smoke
docker stop --timeout 310 echomind-backend-smoke
docker inspect --format '{{.State.ExitCode}}' echomind-backend-smoke
docker rm echomind-backend-smoke
```

O código de saída esperado é `0`. A API permite até 300 segundos para concluir
requisições no encerramento; o orquestrador deve esperar mais que isso. Esse
timeout não garante concluir uploads longos; a etapa 3 precisa impedir que uma
atualização mate processamento ainda em curso.

### Atualizar o lock

Com `uv` disponível, execute na raiz do repositório e depois repita o build e os
testes. Use um interpretador Python 3.12; no Windows ele está atualmente em
`echomind-backend/.venv/Scripts/python.exe`.

```sh
uv pip compile echomind-backend/requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-annotate --no-header --no-emit-index-url --output-file echomind-backend/requirements-deploy.lock
```

## Evidência de validação da etapa 1

Etapa 1 concluída em 2026-10-14, com Docker Desktop executando containers Linux.

| Verificação | Resultado |
| --- | --- |
| Build `linux/amd64` | Sucesso; imagem local `echomind-backend:deploy-step1` |
| Instalação com hashes e somente wheels | Sucesso para as 105 dependências fixadas |
| `pip check` no build | Nenhuma dependência incompatível |
| Inicialização com dois CPUs e limite de 2 GiB | Sucesso com aquecimento do RAG desativado e configurações fictícias |
| GET `/health` pela porta publicada em localhost | HTTP 200 e resposta esperada |
| Healthcheck do Docker | `healthy` |
| Usuário do processo | UID/GID `10001:10001` |
| Configuração local na imagem | Nenhum `.env`, diretório `.aws`, virtualenv ou cache Python encontrado em `/app` |
| Cache de modelos | Caminho configurado gravável pelo usuário sem privilégios |
| Migrations disponíveis na imagem | `alembic heads` retorna `0023 (head)` sem conectar ao banco |
| Testes rápidos com as dependências da imagem | 514 passaram; 8 avisos de transação SQLAlchemy nas fixtures SQLite |
| Encerramento via SIGTERM | Código de saída 0; sem encerramento por falta de memória |
| Limpeza | Containers descartáveis removidos; imagem local preservada |

Os testes foram montados somente para leitura em um container descartável,
com datasets sintéticos e fixtures SQLite/mocks. Pytest e seus auxiliares foram
instalados apenas em `/tmp` desse container, preservando a imagem de produção;
`packaging` permaneceu na versão 24.2 do lock. O `.env.example` público foi
montado apenas para os testes de consistência da documentação. Nenhum `.env`
real foi lido ou enviado ao Docker.

Esses resultados não validam consumo de memória com E5 carregado, banco remoto,
autenticação real, Groq, HTTPS ou persistência após interrupção. Nenhum recurso
AWS foi criado ou alterado.

## Etapa 2: inicialização automática e cache persistente

O arquivo `deploy/compose.yaml` define a execução de uma única API na EC2:

| Configuração | Comportamento |
| --- | --- |
| `restart: unless-stopped` | Reinicia o container após falha ou reinício do Docker; respeita uma parada intencional |
| `init: true` | Usa um processo init para encaminhar sinais e recolher processos filhos |
| `stop_grace_period: 310s` | Dá ao Uvicorn tempo para usar seus 300 segundos de encerramento |
| Volume `model_cache` | Preserva o cache em `/var/cache/echomind/models` ao recriar o container |
| `logging.driver: local` | Rotação em arquivos de 10 MB, com até três arquivos e compressão |
| `read_only`, `cap_drop`, `security_opt` | Sistema de arquivos da imagem somente para leitura, sem capabilities extras ou elevação de privilégios |
| `/tmp` em tmpfs de 64 MiB | Área temporária gravável; o cache durável usa o volume separado |
| Dois CPUs e 1536 MiB de RAM | Limites iniciais ajustáveis por configuração; deixam margem em um host candidato de 2 GiB |
| Memória + swap limitadas ao mesmo valor | Impede que o container use swap adicional |
| Limite de 256 processos/threads | Restringe criação excessiva de processos |
| Porta em `127.0.0.1` | A API permanece acessível apenas no próprio host até configurar o proxy HTTPS |
| `env_file` no formato `raw` | Recebe configuração em runtime e preserva `$` e outros caracteres literais |

A API continua com uma instância e um worker, mesmo que o arquivo de runtime
tenha valores diferentes para os três controles de concorrência. Essa proteção
não impede alguém de iniciar outra cópia manualmente ou usar `--scale`; mantenha
uma única réplica até substituir o rate limiter por armazenamento compartilhado.

O volume inicial recebe as permissões UID/GID 10001 da imagem. Use um volume
Docker nomeado, como definido no Compose; substituir por um diretório do host
exige preparar suas permissões. O volume reside no armazenamento do Docker:
a configuração de EBS e a retenção após término/substituição da EC2 serão
definidas na etapa 6. O cache pode ser baixado novamente e não é backup de
documentos, banco ou arquivos originais.

### Preparar a execução na EC2

Requisitos: Linux com Docker Engine instalado e Compose **2.30.0 ou superior**.
O Compose 2.30 introduziu `env_file.format: raw`. Instalação do host e habilitação
no boot serão incluídas na infraestrutura da etapa 6; não foram aplicadas a uma
máquina AWS nesta etapa.

Na EC2 com systemd, habilite o Docker e o containerd no boot:

```sh
sudo systemctl enable --now docker.service containerd.service
systemctl is-enabled docker.service containerd.service
```

A política de reinício é gerenciada pelo próprio Docker. Não é necessário um
segundo serviço systemd para reiniciar o processo da API. Após a primeira criação
do container, o Docker o recupera no boot, desde que o container e seu armazenamento
continuem existindo e ele não tenha sido parado intencionalmente. O teste de reboot
da EC2 faz parte da validação em produção.

A configuração exige duas referências sem valores secretos:

```sh
export BACKEND_IMAGE=echomind-backend:local
export BACKEND_ENV_FILE=/etc/echomind/backend.env
```

`BACKEND_ENV_FILE` deve ser um caminho absoluto para um arquivo legível pelo
operador autorizado, fora do repositório. Ele é obrigatório. A etapa 4 vai definir
o provisionamento e a validação dos valores reais. Use linhas `CHAVE=valor` sem
aspas envolvendo o valor ou comentários no fim da linha: no formato `raw`, aspas
e comentários inline são preservados literalmente. `*.env` também está ignorado
no Git como proteção adicional contra inclusão acidental.

Na raiz do projeto, para construir localmente e iniciar após configurar o runtime:

```sh
docker compose --file deploy/compose.yaml build backend
docker compose --file deploy/compose.yaml up --detach --no-build --pull never --wait --wait-timeout 120
docker compose --file deploy/compose.yaml ps
docker compose --file deploy/compose.yaml logs --tail 100 backend
```

O nome de projeto padrão é `echomind`; mantenha esse nome ao atualizar para
reutilizar o volume `echomind_model_cache`. A tag local serve para preparação;
imagens publicadas receberão identificação pelo commit na etapa 8. A política de
reinício não aplica migrations ou reindexações. Atualizações e paradas durante
ingestões usam a drenagem e recuperação descritas na etapa 3.

As opções `BACKEND_CPUS`, `BACKEND_MEMORY_LIMIT` e `BACKEND_PORT` ajustam CPU,
memória e porta local. O valor de memória é um limite, não uma medição de consumo:
o teste desta etapa não carrega E5 e não confirma que 1536 MiB sejam suficientes
para chat e ingestão reais.

### Validação reproduzível sem segredos

Com a imagem construída, execute na raiz:

```sh
python deploy/validate_runtime.py --image echomind-backend:local
```

O script usa um projeto de teste com nome aleatório, configurações fictícias e
porta aleatória em localhost. Ele verifica a configuração aplicada pelo Docker,
inicialização saudável, escrita do cache, preservação ao recriar o container,
reinício após matar o processo Uvicorn e respeito a uma parada intencional. Ao
final remove somente os recursos desse projeto descartável, incluindo seu volume
de teste. O arquivo de ambiente fictício é criado na pasta temporária do sistema.

O teste não reinicia o Docker Desktop nem o computador, para preservar os demais
containers locais. Ele verifica a política configurada e a recuperação de falha
do processo; reboot do host será testado na EC2. A rotação de logs é conferida pela
configuração efetivamente aplicada, sem produzir arquivos de log artificiais de
dezenas de MB. O marcador de cache usado no teste é sintético, não um modelo real.

`/health` indica que a API está viva. Uma transição para `unhealthy` não provoca
reinício automático; recuperação de travamentos exige uma estratégia adicional
de monitoramento. A política desta etapa atua quando o processo encerra.

Com `init: true`, uma parada limpa pode retornar `143` (SIGTERM), pois o Uvicorn
0.29 reemite o sinal após concluir o shutdown. O verificador aceita `0` ou `143`
e exige também `Application shutdown complete.` nos logs; um código `137` na
parada controlada continua sendo falha.

## Evidência de validação da etapa 2

Etapa 2 concluída em 2026-10-14 com Docker Compose 5.1.4 e a imagem validada na
etapa 1 (`echomind-backend:deploy-step1`). O verificador terminou com código 0.

| Verificação | Resultado |
| --- | --- |
| Validação do Compose | Configuração aceita pelo Compose, usando arquivo fictício fora do repositório |
| Inicialização e HTTP | Container saudável e `/health` com a resposta esperada pela porta local |
| Limites aplicados | Dois CPUs, 1536 MiB de RAM, sem swap adicional, 256 processos/threads e parada de 310 segundos |
| Isolamento aplicado | Imagem somente para leitura, init ativo, capabilities removidas e elevação de privilégios bloqueada |
| Logs | Driver `local`, limite de 10 MB por arquivo e três arquivos configurados no Docker |
| Runtime | Caracteres `$` preservados e os três controles de concorrência fixados em 1 |
| Permissões | Usuário 10001 grava no volume do cache e na área temporária |
| Recriação do container | ID do container mudou e o marcador do cache permaneceu disponível |
| Falha do Uvicorn | Docker reiniciou automaticamente o container, que voltou a ficar saudável com o cache preservado |
| Parada intencional | Shutdown da aplicação concluído; saída 143 esperada com init; container permaneceu parado |
| Limpeza | Containers, rede e volume do projeto de teste removidos; imagem preservada |

Não houve leitura de segredos reais, acesso ao banco/Groq ou operação de
infraestrutura AWS. O reboot da EC2, o modelo E5 real e o comportamento de
uploads interrompidos permanecem para as etapas correspondentes. A próxima
etapa seguinte àquela validação é a **3: persistência dos arquivos e recuperação de uploads**.

## Etapa 3: originais duráveis, recuperação e manutenção

O volume `echomind_documents` é montado em `/var/lib/echomind/documents`, separado
do cache de modelos. `DOCUMENT_STORAGE_DIR` aponta para ele; o Compose fixa esse
caminho. Em desenvolvimento, o exemplo usa `.document-data`, ignorado pelo Git.
Os arquivos são privados, gravados com permissões restritas e organizados por
chaves derivadas da instituição e do documento, sem usar o nome fornecido no upload
como caminho. O volume não é publicado como conteúdo estático.

### Como o upload passa a funcionar

1. Autenticar e validar o upload, seu limite, metadados e duplicidade por instituição.
2. Criar o registro dentro da transação do banco.
3. Gravar o original e um marcador de trabalho com escrita atômica, `fsync` do
   arquivo e, em Linux, dos diretórios envolvidos.
4. Confirmar a transação do banco e só então responder HTTP 202.
5. Carregar os bytes do disco ao processar o trabalho. Somente uma ingestão ocupa
   o slot de processamento, evitando carregar vários documentos/modelos em paralelo.
6. Remover o marcador ao concluir em `ready` ou `error`, mantendo o original até
   a exclusão explícita do documento.

O SHA-256 completo e o tamanho são conferidos antes do processamento. Falha na
gravação do original impede a confirmação do upload. Há uma reserva mínima de
64 MiB livres no volume para aceitar novos arquivos; capacidade e alertas de disco
serão definidos na infraestrutura. Backups também consomem espaço e precisam de
retenção limitada.

`app/document_runtime.py` verifica os marcadores na inicialização e a cada cinco
segundos, após concluir a rotina de aquecimento inicial dos modelos. Se essa rotina
ultrapassar o timeout de inicialização da API, o recuperador ainda aguarda sua
conclusão. Trabalhos `pending` são iniciados; trabalhos `processing` interrompidos
são retomados com os originais e remoção dos vetores parciais conhecidos antes da
substituição dos chunks. Uma trava de arquivo impede sobreposição entre o trabalho
imediato do upload e o recuperador. Falhas transitórias que impedem executar o
trabalho preservam seu marcador para nova tentativa. Falhas do parser/indexação
que já são tratadas pelo fluxo existente continuam retornando estado `error`;
não são repetidas indefinidamente.

Originais ausentes ou corrompidos deixam o documento em `error`, com orientação
para reenvio. O modo de recuperação pode ser desativado somente para testes com
`DOCUMENT_RECOVERY_ENABLED=false`; em produção, mantenha o valor padrão `true`.
A implementação usa os estados e tabelas já existentes, sem uma migration nova.

Se um commit do banco tiver resultado incerto, o original e o marcador são
preservados. Um trabalho sem registro correspondente não é removido
automaticamente: primeiro é preciso confirmar o estado do banco e comparar o
backup. Essa escolha pode deixar arquivos órfãos após falhas, mas evita descartar
um original cujo commit pode ter sido confirmado. Marcadores malformados exigem
triagem administrativa; os logs não incluem conteúdo dos documentos ou exceções
com caminhos privados.

### Exclusão e retenção

Os originais permanecem até o administrador excluir o documento. A exclusão é
serializada com a ingestão e pode pedir nova tentativa se outro documento estiver
ocupando o processamento. Um marcador de exclusão é persistido antes de remover
o registro. O original só é apagado depois da confirmação do banco. Se o processo
for interrompido nessa janela, o recuperador conclui a remoção ao constatar que o
registro foi excluído. Uma falha no banco preserva o original para repetir a operação.

Documentos enviados antes desta mudança não têm original recuperável a partir
dos chunks. Seu conteúdo já processado permanece no banco; reenvie os originais
que precisarem desta garantia. Pendências antigas sem marcador e sem original
precisam de triagem/reenvio. Um snapshot do volume também não substitui o backup
do PostgreSQL/Supabase, que contém metadados, chunks e vetores.

### Atualizar com drenagem

Os comandos administrativos são acessíveis via execução no container; não foi
criada uma rota pública para controle de manutenção. Com o Compose configurado,
use no shell Linux da EC2:

```sh
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime drain --timeout 300
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime status
```

`drain` persiste o modo de manutenção, bloqueia novos uploads e exclusões com HTTP
503 e aguarda o trabalho ativo. Pendências ainda não iniciadas ficam duráveis para
depois da atualização. Se o timeout vencer, o comando falha e a manutenção fica
ativada; aguarde e repita a drenagem, aumente o timeout ou cancele usando `resume`.
Não prossiga para trocar a versão depois de uma drenagem que falhou.

Após uma drenagem bem-sucedida, publique a imagem previamente construída:

```sh
docker compose --file deploy/compose.yaml up --detach --no-build --pull never --wait --wait-timeout 120
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime resume
```

Defina `BACKEND_IMAGE` com a nova versão antes de executar `up`. O modo de
manutenção sobrevive à recriação; `resume` libera os uploads e a retomada das
pendências depois das verificações da nova versão. Na etapa 8, esse procedimento
será integrado ao GitHub Actions. Um encerramento abrupto também mantém os
originais e marcadores, permitindo recuperação no mesmo volume, desde que o
armazenamento não tenha sido perdido.

### Backup e restauração

Política inicial para a publicação: backup diário e antes de cada atualização,
retenção de sete cópias diárias e da última cópia anterior ao deploy, guardadas
criptografadas fora da EC2. Testar a restauração regularmente. O agendamento,
destino AWS, criptografia e alertas serão configurados na etapa 6; não há backup
automático em nuvem ativado nesta etapa.

Para uma cópia consistente, drene primeiro e pause também ferramentas manuais de
reindexação. Exporte o PostgreSQL/Supabase na mesma janela de manutenção e produza
o arquivo dos originais e marcadores. A disponibilidade dos backups do próprio
Supabase depende do plano; confira isso antes da publicação.

No shell Linux, com diretório de backup privado fora do Git:

```sh
umask 077
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime backup > /CAMINHO_PRIVADO/echomind.documents.tar
```

O comando exige manutenção ativa e bloqueia alterações nos documentos durante
a cópia. O arquivo contém originais e identificadores de instituições, portanto
precisa das mesmas restrições de acesso dos dados de produção. Copie-o para o
destino criptografado fora da máquina e retome a aplicação com `resume`. A cópia
local sozinha não protege contra perda da EC2 ou do EBS.

Para recuperar: restaure o banco correspondente, prepare um volume de documentos
vazio e mantenha a API em manutenção. Então, no shell Linux:

```sh
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime drain --timeout 300
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime restore < /CAMINHO_PRIVADO/echomind.documents.tar
docker compose --file deploy/compose.yaml exec -T backend python -m app.document_runtime status
```

O restore exige volume vazio e rejeita links, caminhos arbitrários, membros
duplicados e arquivos maiores que 100 MiB. O limite padrão dos uploads permanece
10 MiB. Uma restauração interrompida pode deixar um volume parcialmente preenchido;
repita em outro volume vazio, preservando o backup original. Confira o banco e a
integridade dos documentos antes de liberar com `resume`.

Preserve os volumes ao atualizar. `docker compose down --volumes` apaga também
os originais; essa opção fica restrita aos projetos descartáveis de teste.
O volume de produção deve usar EBS criptografado e política explícita de retenção
na etapa 6. [Snapshots EBS](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)
e a capacidade provisionada têm custos próprios, sujeitos aos créditos e
[preços vigentes](https://aws.amazon.com/ebs/pricing/).

## Evidência de validação da etapa 3

Etapa 3 concluída em 2026-10-14 usando a imagem Linux
`echomind-backend:deploy-step3`, Python 3.12.15 e Docker Compose 5.1.4.

| Verificação | Resultado |
| --- | --- |
| Suíte rápida na imagem de produção | 538 testes passaram; dez avisos das transações SQLite usadas nas fixtures |
| Cobertura global | 90,28%, acima do gate de 72% |
| Gates documentais | Ingestão 92,53%; processamento 92,06%; repositório 97,35%; upload 100% |
| Original antes de confirmar o upload | Testado; falha de armazenamento retorna 503 sem agendar processamento |
| Falha de commit do banco | Original e marcador preservados para reconciliação |
| Retomada | Estados `pending` e `processing` concluem em `ready`, sem reindexação duplicada após conclusão |
| Vetores parciais | Remoção dos IDs conhecidos validada antes da substituição dos chunks |
| Integridade e isolamento | SHA-256/tamanho, escopo da instituição e caminhos derivados validados |
| Exclusão | Original removido após confirmação; falhas preservam os bytes e permitem nova tentativa |
| Backup e restore | Original e trabalho pendente restaurados; links/caminhos inválidos e sobrescrita rejeitados |
| Inicialização | Recuperação aguarda o aquecimento; encerramento durante aquecimento impede iniciar um recuperador tardio |
| Compose real | Recriação preservou original/cache e permitiu concluir um documento sintético interrompido |
| Falha do processo | Reinício automático saudável com original preservado |
| Manutenção | Comandos privados de drenagem/status/retomada e encerramento controlado validados |
| Limpeza | Containers, redes e volumes dos projetos descartáveis removidos; imagem local preservada |

Os testes usam SQLite e indexadores sintéticos; o teste Compose mantém o banco
fictício no volume descartável somente para simular recuperação. Em produção,
o banco continua no Supabase. Não houve leitura de segredos reais, alteração no
banco remoto ou criação de recursos AWS. E5 real, backup externo automatizado,
criptografia/retenção do EBS e recuperação de uma EC2 perdida continuam nas
etapas de infraestrutura e validação em produção.

## Etapa 4: configuração de produção e segredos

O exemplo público está em `deploy/.env.example`. Ele contém apenas nomes,
valores operacionais e marcadores `CHANGE_ME`; não contém credenciais reais.
O arquivo preenchido fica fora do checkout e é entregue ao container por
`BACKEND_ENV_FILE`. A imagem continua sem `.env` e sem credenciais AWS.

| Variável | Destino | Tratamento |
| --- | --- | --- |
| `DATABASE_URL` | Backend e migrações | Segredo; URI PostgreSQL com senha codificada e `sslmode=require`, `verify-ca` ou `verify-full` |
| `SUPABASE_SECRET_KEY` | Backend | Segredo; chave atual `sb_secret_…`, nunca chave publishable |
| `GROQ_API_KEY` | Backend | Segredo; chave `gsk_…` |
| `SUPABASE_URL`, `ALLOWED_ORIGINS` | Backend | Endereço HTTPS do projeto e origens exatas do frontend, sem caminho/barra final |
| `NEXT_PUBLIC_API_URL` | Frontend/Vercel | URL pública HTTPS da API, definida na etapa 5 |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Frontend/Vercel | Dados públicos; publishable `sb_publishable_…` depende das políticas de acesso do Supabase |

As três variáveis secretas nunca recebem o prefixo `NEXT_PUBLIC_`, nem entram
em build args, Dockerfile, commits, logs ou respostas da API. Uma URL PostgreSQL
contém a senha e deve receber o mesmo cuidado de uma chave privada. A imagem e
o frontend são construídos sem essas três credenciais. O processo da API recebe
os valores somente quando o container é criado.

### Preparar e conferir no host Linux

Os comandos abaixo são instruções para o futuro servidor; não foram executados
em uma EC2 nesta etapa. Use uma sessão administrativa privada. Não cole os
valores em mensagens, comandos do histórico ou parâmetros de linha de comando.

```sh
sudo install -d -m 700 /etc/echomind
sudo install -m 600 deploy/.env.example /etc/echomind/backend.env
sudoedit /etc/echomind/backend.env
sudo python3 deploy/configure_runtime.py --file /etc/echomind/backend.env
```

Preencha os cinco campos essenciais: banco, URL do Supabase, chave secreta do
Supabase, chave da Groq e origens do frontend. Obtenha a URI do banco no painel
do Supabase usando um método de conexão compatível com a rede da EC2; confira
acesso IPv4/IPv6 antes de publicar. Codifique caracteres especiais da senha na
URI, por exemplo `@` como `%40`. Não altere o valor da chave da API com escaping.

O formato é `NAME=value`, sem aspas e sem comentário no fim da linha. O Compose
usa `format: raw` para preservar `$`, `#` e outros caracteres literalmente.
Comentários ocupam uma linha própria. O exemplo deve continuar com valores
fictícios no Git; arquivos `.env` preenchidos já são ignorados como proteção
adicional, mas devem ficar fora do checkout.

Para instalar a partir de outro arquivo privado já preenchido:

```sh
sudo python3 deploy/configure_runtime.py \
  --file /caminho/privado/backend.env \
  --output /etc/echomind/backend.env
```

A ferramenta valida antes de gravar, recusa arquivos no checkout, links
simbólicos, variáveis não previstas e arquivos legíveis por outros usuários.
No Linux exige propriedade do usuário executor, arquivo `600` e diretório de
destino `700`; instala de forma atômica. Para trocar um arquivo existente,
adicione `--replace`. Uma configuração inválida preserva o arquivo anterior.
No Windows permite validar o conteúdo, mas não instala nem promete validar
ACLs do Linux. Ela nunca busca segredos na AWS e nunca imprime os valores.

O Docker lê o arquivo no host; a API com UID 10001 não precisa acessá-lo
diretamente. Apenas o administrador que opera o Docker precisa dessa permissão.
Acesso ao daemon Docker permite inspecionar variáveis do container; limite esse
acesso a administradores. Evite compartilhar `docker inspect`, saídas de
`docker compose config` e dumps do ambiente. Para conferir só a sintaxe do
Compose, use `docker compose ... config --quiet`.

### Validação ao iniciar

O Compose força `ECHOMIND_ENV=production`. Antes de criar a conexão SQLAlchemy
ou o cliente Supabase, a API valida variáveis essenciais, marcadores não
substituídos, referências dinâmicas ainda não resolvidas, PostgreSQL com SSL,
URLs/origens HTTPS sem curingas, tipos de chave, limites numéricos, dimensão
384 e um único worker/instância. Os erros informam apenas os nomes a revisar.
Em produção não há leitura automática de `.env`; desenvolvimento mantém o
comportamento anterior. As migrações preservam senhas codificadas com `%`,
escapando a interpolação do ConfigParser antes de entregar a URI ao Alembic.

Isso valida a estrutura, sem autenticar credenciais ou conectar aos serviços.
Não substitui os testes reais da etapa 7/9. `DOCUMENT_RECOVERY_ENABLED` e
`RAG_WARMUP_ENABLED` ficam ligados no exemplo; podem ser desligados em testes
controlados ou manutenção. O teste Compose usa serviços fictícios e desliga
ambos para não chamar Supabase/Groq nem baixar o modelo. Apenas os subprocessos
de recuperação sintética usam `ECHOMIND_ENV=testing` e SQLite.

### Secrets Manager e rotação

O arquivo restrito de runtime é a opção preparada nesta etapa. Ainda não foram
criados Secrets Manager, políticas IAM ou credenciais de produção. Se Secrets
Manager for adotado, a identidade, permissões e custos serão definidos na etapa
6. Para o agente, valores devem chegar por referências dinâmicas resolvidas
por `asm-exec`, nunca por consultas que imprimam o segredo. Exemplo para uma
sessão privada com o wrapper e a autenticação já configurados:

```sh
export DATABASE_URL='{{resolve:secretsmanager:echomind/production:SecretString:DATABASE_URL}}'
export SUPABASE_SECRET_KEY='{{resolve:secretsmanager:echomind/production:SecretString:SUPABASE_SECRET_KEY}}'
export GROQ_API_KEY='{{resolve:secretsmanager:echomind/production:SecretString:GROQ_API_KEY}}'
# Configure SUPABASE_URL e ALLOWED_ORIGINS com os endereços públicos reais.
asm-exec -- python3 deploy/configure_runtime.py \
  --from-environment --output /etc/echomind/backend.env
```

O wrapper deve executar como o proprietário autorizado do diretório privado.
O instalador só lê as variáveis previstas no exemplo e rejeita referências
ainda não resolvidas. Não use `sudo` dentro do wrapper sem configurar a
preservação segura do ambiente, pois os valores podem ser descartados. Limite
uma futura identidade de resolução ao segredo necessário e, se houver chave
KMS própria, à decriptação correspondente; a API atual não precisa de acesso
à AWS para atender Supabase/Groq.

Para rotacionar: gere a nova credencial no provedor, prepare/valide o novo
arquivo privado, drene os uploads pelo procedimento da etapa 3, instale o
arquivo com `--replace` e recrie o container com `up --force-recreate`.
Um `restart` simples não recarrega `env_file`. Confira saúde e serviços reais,
retome a admissão de uploads e só então revogue a credencial antiga.
O fluxo automático com verificação e recuperação fica para a etapa 8.

### Validação da etapa 4

| Verificação | Resultado |
| --- | --- |
| Build Linux `amd64` | Imagem local `echomind-backend:deploy-step4` construída |
| Suíte rápida na imagem | 585 testes passaram; dez avisos conhecidos das fixtures SQLite |
| Cobertura | Global 90,45%; módulo de configuração 100%; gates documentais aprovados |
| Segredos fictícios | Valores com `$`, `#` e senhas com `%40`, `%2F`, `%25` preservados |
| Falha de configuração | API rejeita configuração inválida antes da conexão; diagnóstico sem valores |
| Instalação Linux | Arquivo `600` e diretório `700`; links, acesso de outros usuários e sobrescrita implícita rejeitados |
| Rotação | Configuração inválida preserva o arquivo anterior; troca válida testada |
| Compose real | Saúde, isolamento, limites, cache/originais, recuperação, reinício, drenagem/retomada e parada aprovados |
| Limpeza | Containers, redes e volumes dos testes descartáveis removidos |

Todos os valores de teste foram fictícios. Nenhum `.env` real foi lido, nenhum
serviço remoto foi autenticado e nenhum recurso AWS foi criado.
Credenciais reais e as URLs definitivas serão preenchidas privadamente no
servidor quando as etapas de infraestrutura e HTTPS estiverem prontas.

A próxima etapa é a **5: HTTPS e acesso público**.

## Referências

- [FastAPI em containers](https://fastapi.tiangolo.com/deployment/docker/)
- [Boas práticas de build do Docker](https://docs.docker.com/build/building/best-practices/)
- [Contexto de build e `.dockerignore`](https://docs.docker.com/build/concepts/context/)
- [Configuração dos serviços Compose](https://docs.docker.com/reference/compose-file/services/)
- [Políticas de reinício do Docker](https://docs.docker.com/engine/containers/start-containers-automatically/)
- [Volumes Docker](https://docs.docker.com/engine/storage/volumes/)
- [Rotação de logs com o driver local](https://docs.docker.com/engine/logging/drivers/local/)
- [Tratamento de sinais no Uvicorn 0.29](https://github.com/encode/uvicorn/blob/0.29.0/uvicorn/server.py)
- [Sintaxe e formato raw de env_file no Compose](https://docs.docker.com/reference/compose-file/services/#env_file)
- [Chaves públicas e secretas do Supabase](https://supabase.com/docs/guides/getting-started/api-keys)
- [Conexões PostgreSQL do Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Interpolação do ConfigParser](https://docs.python.org/3.12/library/configparser.html#interpolation-of-values)
