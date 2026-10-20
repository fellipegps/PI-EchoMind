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
- `t3.small` com 2 GiB é a configuração inicial do MVP de baixo tráfego,
  mantida após os ensaios controlados na EC2 descritos abaixo. Os ensaios
  cobriram documentos sintéticos de até 256 KiB e rajadas curtas de quatro
  consultas; carga sustentada e uploads máximos ainda precisam de validação.
  Não é necessário usar GPU.
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
- [x] **5. HTTPS e acesso público:** definir domínio da API, proxy e certificados
  com renovação, portas públicas 80/443, API acessível somente pelo proxy, CORS exato,
  streaming e limite de upload. Configurar confiança no IP do proxy para preservar
  o IP do cliente no rate limiting sem aceitar cabeçalhos falsificados.
- [x] **6. Preparação da infraestrutura AWS:** revisar créditos e custos, definir identidade dedicada,
  EC2 por infraestrutura como código, acesso administrativo via Systems Manager,
  EBS criptografado e persistente, regras de rede, backup e orçamento/alertas.
  Template validado; identidade dedicada e infraestrutura base criadas e conferidas.
- [x] **7. Banco e frontend:** conferir migrations com backup e acesso PostgreSQL,
  aplicar migrations como operação explícita, ajustar URL HTTPS da API na Vercel e
  URLs de autenticação no Supabase. Reindexação de embeddings continua manual.
  Banco real atualizado, serviços configurados e frontend publicado. Login,
  chat, documentos, cadastro e recuperação por e-mail aprovados. A correção da
  orientação de cadastro aguarda publicação, conforme o registro de autenticação.
- [x] **8. Preparação da publicação por GitHub Actions:** testes antes de publicar, autenticação
  temporária OIDC, imagem identificada pelo commit, atualizações serializadas,
  drenagem de tarefas, verificação após deploy e recuperação da versão anterior.
  Workflow, infraestrutura complementar e recuperação validados localmente.
  A ativação na AWS/GitHub e a primeira execução real permanecem pendentes;
  `AWS_DEPLOY_ENABLED` fica ausente/desativado até concluir os pré-requisitos.
- [ ] **9. Validação em produção:** login, recuperação de senha, chat, upload e
  consulta de documentos, memória/CPU/disco com embeddings reais, revisão de
  vulnerabilidades das dependências, logs e recuperação após reinício.
  Fluxos funcionais e carga controlada medidos; busca durante ingestão corrigida
  e publicada. Faltam carga sustentada/documentos máximos e restauração do EBS.

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

## Etapa 5: HTTPS e acesso público

A publicação usa o Compose base junto de `deploy/compose.https.yaml`. O overlay
adiciona Caddy, remove a publicação da porta 8000 do backend e permite entrada
pública apenas pelo proxy. O Compose base sozinho continua disponível para
diagnóstico privado; ele não representa a configuração final de publicação.

| Conexão | Configuração |
| --- | --- |
| Internet → EC2 | TCP 80 para redirecionamento/desafio ACME e TCP 443 para HTTPS |
| Host → Caddy | 80 → 8080 e 443 → 8443; processo com UID/GID 10001, sem capabilities |
| Caddy → API | HTTP na bridge local Docker; backend em 8000 sem publicação no host |
| Identidade do proxy | IP fixo `172.30.80.2`; Uvicorn aceita headers encaminhados somente desse IP |
| Backend | IP fixo `172.30.80.3`, mesma rede; acesso de saída para Supabase/Groq/modelos |
| Certificados | Emissão e renovação automáticas pelo Caddy; volume `proxy_data` em `/data` |
| Estado do proxy | Volume `proxy_config` em `/config`; nenhum segredo do backend é entregue ao proxy |
| Recursos do proxy | Limite de 128 MiB de RAM, sem swap extra, 0,5 CPU e logs locais rotacionados |

A imagem oficial Caddy 2.11.7 está fixada por digest no Dockerfile do proxy.
O build remove a capability de portas baixas do executável, pois o processo
usa portas internas altas. Isso permite `cap_drop: ALL`, raiz somente para
leitura e `no-new-privileges`. O backend mantém um worker e os limites anteriores.
A máquina de 2 GiB continua candidata, dependendo da medição com E5 real e do
consumo total do host, API e proxy na etapa 9.

### Domínio, DNS e portas antes de publicar

O domínio real ainda precisa ser escolhido. Use um subdomínio sob seu controle,
por exemplo `api.seudominio.com`. Não use IP, URL com `https://`, porta, caminho
ou curinga no campo `API_DOMAIN`. Não é necessário hospedar o DNS no Route 53.
Se ainda não houver domínio, resolva essa escolha antes do primeiro início
público; não foi comprado ou registrado nenhum domínio nesta etapa.

Na etapa 6, defina um IP público estável e confira custos de infraestrutura,
IPv4 e domínio. Crie um registro DNS `A` do subdomínio apontando para esse IP.
Só publique `AAAA` se IPv6 estiver configurado e testado de ponta a ponta.
Um registro IPv6 incorreto pode impedir a emissão do certificado.

O Security Group e o firewall do host devem permitir TCP 80/443 de clientes
IPv4 (`0.0.0.0/0`); regras IPv6 só serão necessárias se IPv6 for adotado.
Não abra 8000, 8080, 8443, 8090 ou 2019 na EC2. O acesso administrativo seguirá
Systems Manager na etapa 6. O proxy precisa alcançar os serviços de certificado
por HTTPS e resolver DNS. Essas regras ainda não foram criadas na AWS.

O modelo atual recebe o cliente diretamente no Caddy. Não coloque CDN ou outro
proxy na frente sem revisar a confiança nos cabeçalhos e repetir os testes de
IP e rate limiting. Escolha uma subnet Docker livre antes de publicar: se a
rede padrão conflitar com VPC, VPN ou outra bridge, altere `PROXY_SUBNET`,
`PROXY_IP` e `BACKEND_PRIVATE_IP` em conjunto. Use dois IPs diferentes e válidos
nessa subnet; a rede configurada também impede usar `*` como IP confiável.

### Configuração do servidor

`deploy/proxy/.env.example` contém apenas parâmetros de publicação, caminhos e
marcadores públicos. A configuração privada do backend continua no arquivo
da etapa 4. No futuro host Linux, prepare o arquivo de publicação:

```sh
sudo install -m 600 deploy/proxy/.env.example /etc/echomind/deploy.env
sudoedit /etc/echomind/deploy.env
```

Preencha `API_DOMAIN`, `ACME_EMAIL`, nomes das imagens já disponíveis no host e
o caminho absoluto `BACKEND_ENV_FILE`. Use um endereço de email que você
acompanhe para avisos da autoridade certificadora. A entrega das imagens por
CI/CD será tratada na etapa 8. Os arquivos `.env` preenchidos ficam fora do Git.

Depois de ativar HTTPS, **todos os comandos que recriam a stack** precisam usar
os dois arquivos Compose e o arquivo de publicação. Usar apenas o arquivo base
reintroduz a porta de diagnóstico e remove a configuração de confiança no proxy.
Na raiz do checkout, uma função de conveniência para a sessão administrativa:

```sh
dc() {
  sudo docker compose --env-file /etc/echomind/deploy.env \
    -f deploy/compose.yaml -f deploy/compose.https.yaml "$@"
}
dc config --quiet
# Só após DNS, portas, imagens e configuração privada estarem prontos:
dc up --detach --no-build --wait
curl --fail https://api.seudominio.com/health
```

Use o mesmo prefixo `dc` para os comandos privados de drenagem/retomada da
etapa 3 e para recriação durante rotação da etapa 4. `/health` verifica a API;
o healthcheck local do Caddy verifica apenas que o proxy responde e não
comprova emissão de certificado, autenticação, banco ou IA. Confirme HTTPS
externamente usando validação normal do certificado, sem `curl -k`.

No frontend, defina `NEXT_PUBLIC_API_URL=https://api.seudominio.com`, sem barra
final. No backend, `ALLOWED_ORIGINS` deve conter as origens HTTPS exatas do
frontend, incluindo a produção na Vercel ou seu domínio próprio. Não libere
`*.vercel.app`; previews necessários recebem entradas explícitas. CORS continua
sob responsabilidade da API; erros produzidos pelo proxy antes de chegar à API
podem não incluir os cabeçalhos CORS. URLs de autenticação e a validação dos
serviços reais serão conferidas na etapa 7.

### Streaming, uploads e IP do cliente

O proxy mantém as respostas do chat em fluxo, sem compressão adicionada pelo
proxy e sem buffer de resposta completo. A configuração usa flush positivo
de 100 ms, preservando o cancelamento da requisição upstream quando o cliente
desconecta; respostas sem tamanho conhecido são enviadas progressivamente.
Não há timeout total de escrita que corte uma resposta longa do chat.
A conexão com o backend tem timeout de 5 s e seus cabeçalhos devem chegar em
até 60 s. Cabeçalhos de entrada têm limite de 16 KiB e timeout de 10 s;
um corpo de entrada deve terminar em até 120 s.

O limite do arquivo continua em **10 MiB** na API, com 64 KiB adicionais para
multipart. O proxy admite até 11 MiB no corpo de `/documents/upload` e até
1 MiB nos demais caminhos. Ao alterar `MAX_DOCUMENT_SIZE_MB`, revise também
esse teto do proxy. Autenticação, tipos de arquivo e regras documentais
continuam sendo aplicados pela API.

O Caddy descarta os valores `X-Forwarded-*` recebidos de clientes e define os
seus próprios; também remove `Forwarded` e `X-Real-IP`. O Uvicorn confia apenas
no IP fixo do Caddy. Outros peers da bridge não conseguem escolher o IP usado
pelo rate limiter, mesmo enviando esses cabeçalhos. O teste com dois clientes
de IPs distintos confirmou limites independentes. A preservação do IP na rede
real da EC2 ainda deve ser conferida após o provisionamento.

### Renovação, atualização e persistência

Com um domínio público válido e portas/DNS corretos, Caddy gerencia a emissão
e a renovação sem cron adicional. O volume `/data` contém também chaves privadas
de certificados e dados da conta ACME: mantenha-o privado, persistente e fora
do Git. Nunca use `down --volumes` em produção. EBS criptografado, backup e
recuperação desses volumes serão preparados na etapa 6. Sem o volume, Caddy
precisa emitir novamente e pode encontrar limites da autoridade certificadora.

A API administrativa do Caddy fica desativada. Uma alteração do Caddyfile
exige nova imagem e recriação do proxy; use a janela de manutenção e drenagem
da etapa 3. Atualizações apenas do backend podem usar `dc up --detach --no-deps
--force-recreate backend`, preservando o proxy e os certificados, após a
drenagem. Há uma janela de indisponibilidade ao trocar o único backend;
publicação sem interrupção exigiria outra arquitetura e um limiter compartilhado.

### Validação local reproduzível

```sh
docker build --platform linux/amd64 -t echomind-backend:local ./echomind-backend
docker build --platform linux/amd64 -t echomind-proxy:local ./deploy/proxy
python deploy/validate_https.py \
  --backend-image echomind-backend:local --proxy-image echomind-proxy:local
```

O teste monta `deploy/fixtures/https_app.py` apenas no projeto descartável.
Ele usa a API e seus middlewares reais, substituindo conteúdo de chat,
persistência/autenticação de upload e dependências externas por dados sintéticos.
O adaptador não entra em nenhuma imagem de produção. A CA é local ao volume de
teste; o cliente valida o certificado com seu certificado público, sem instalar
confiança no computador. Nenhum certificado público é solicitado.

| Verificação | Resultado |
| --- | --- |
| Build e início do Caddy | Aprovados sem root, capabilities ou escrita na raiz |
| TLS, host e HTTP | Certificado local validado, Host incompatível rejeitado e redirecionamento 308 aprovado |
| Exposição | Backend sem porta no host; proxy recebe somente configuração própria |
| CORS | Origem permitida aceita e origem não autorizada rejeitada pelo HTTPS |
| Chat | Primeiro trecho chega antes da conclusão; desconexão cancela o gerador upstream |
| Upload | Arquivo de 10 MiB aceito; 10 MiB + 1 byte rejeitado com 413 e CORS preservado |
| Corpo no proxy | Corpo maior que 1 MiB em rota comum rejeitado com 413 |
| IP e rate limiting | Dois clientes independentes; cabeçalhos forjados não contornam o limite |
| Acesso direto interno | Uvicorn ignora cabeçalhos encaminhados de outro peer da bridge |
| Certificados persistentes | Mesmo certificado após recriar o proxy; arquivos de chave com modo 600 |
| Limpeza | Containers, redes e volumes do projeto de teste removidos |

A configuração de renovação automática foi preparada; emissão e renovação por
uma CA pública dependem do domínio, DNS e EC2 reais e ainda não foram testadas.
Não houve leitura de segredos reais, mudança de DNS, criação de recursos AWS ou
publicação do projeto.

## Etapa 6: infraestrutura AWS

**Preparação concluída e validada.** Os arquivos estão em `deploy/aws`; ainda não foram
criados recursos. O template só prepara o host e seus controles. Não instala
segredos, publica containers, aplica migrations ou altera DNS automaticamente.

### Conta, créditos e estimativa

Consulta somente de leitura em **14/10/2026** pelo AWS MCP:

- Plano `FREE`, estado `ACTIVE`, saldo informado de **US$ 100**.
- Data de expiração informada: **13/04/2027**. O plano termina antes se os
  créditos acabarem; não foi alterado para Paid.
- `t3.small` aparece como elegível na API EC2, com 2 vCPU e 2 GiB, arquitetura
  x86_64. Elegibilidade não significa uma máquina gratuita permanente.
- Quota regional de vCPU Standard: 5; nenhuma EC2 encontrada em `us-east-1`.
- Nenhuma stack ativa ou trilha CloudTrail encontrada na consulta regional.
- Perfil atual identificado como root. O preflight o registra como impedimento
  para executar a criação da infraestrutura.

Os preços unitários foram consultados na Price List API para `us-east-1` e nas
páginas oficiais de KMS/CloudWatch. Cálculo reproduzível:

```sh
python deploy/aws/estimate_cost.py
```

| Item | Hipótese | Estimativa mensal bruta em USD |
| --- | --- | --- |
| EC2 `t3.small` Linux | 730 horas, US$ 0,0208/h | 15,18 |
| EBS gp3 | 16 GiB de sistema + 20 GiB de dados, US$ 0,08/GiB-mês | 2,88 |
| Um IPv4 público | 730 horas, US$ 0,005/h | 3,65 |
| KMS para notificações | Uma chave própria | 1,00 |
| Alarmes | Quatro alarmes, antes de franquias gratuitas | 0,40 |
| Snapshots | Hipótese de 20 GiB-mês armazenados, US$ 0,05/GiB-mês | 1,00 |
| **Total ilustrativo** | Calculado sem arredondar cada parcela antes da soma | **24,11** |

Nesse cenário, US$ 100 equivalem a aproximadamente **4,15 meses**, antes de
variações de uso. O cálculo não inclui armazenamento/requisições de auditoria
S3, entregas SNS, chamadas KMS, tráfego excedente, domínio/DNS, impostos/câmbio
ou serviços externos Supabase/Groq/Vercel. Franquias podem reduzir parcelas,
mas não foram descontadas sem confirmação do uso aplicável. Snapshots são
incrementais: sete pontos de recuperação não equivalem a sete discos completos.
Revise saldo e preços imediatamente antes de criar recursos. No Free Plan,
esgotar créditos pode encerrar o acesso à conta e aos dados; não conte apenas
com a data de abril para manter o projeto disponível.

### Recursos preparados

| Área | Configuração |
| --- | --- |
| Rede | VPC própria IPv4, uma subnet pública em uma AZ, Internet Gateway e um Elastic IP; sem NAT Gateway ou balanceador |
| Entradas | Apenas TCP 80/443; sem chave SSH, porta 22 ou porta do backend |
| Saídas | TCP 80 para pacotes assinados do Ubuntu, 443 para serviços HTTPS e 5432 para Supabase com SSL |
| Sistema | Ubuntu 24.04 amd64 obtido do parâmetro público da Canonical; revisar AMI resolvida antes de executar |
| Compute | Uma `t3.small`, um worker; créditos de CPU em `standard`, com alerta de saldo baixo |
| Metadados | IMDSv2 obrigatório, hop limit 1 intencional: o host usa IAM, os containers não precisam de credenciais AWS |
| Armazenamento | Sistema gp3 criptografado de 16 GiB; EBS gp3 criptografado de dados de 20 GiB, chave gerenciada `aws/ebs`, retido em exclusão/substituição |
| Inicialização | Docker e containerd habilitados no boot e impedidos de iniciar sem as montagens persistentes |
| Backup | DLM diário às 03:00 UTC, retenção de sete snapshots do volume de dados |
| Operação | Role SSM dedicada para o host; política separada de sessões para o operador IAM |
| Alertas | Falha EC2, CPU alta, créditos de CPU baixos e falha de snapshot; tópico SNS criptografado |
| Orçamento | Conta inteira, US$ 30/mês brutos antes dos créditos, alertas reais em 50/80/100% e previsão em 100% |
| Auditoria | Trilha multirregional de eventos de gerenciamento em S3 privado/criptografado, validação dos logs e retenção de 90 dias |

O orçamento é um **alerta, não um limite de gastos**. Não há desligamento
automático que possa interromper uploads. Em modo CPU `standard`, falta de
créditos reduz o desempenho em vez de gerar cobrança de CPU excedente; isso
precisa ser observado no teste do E5. RAM e disco não têm alarmes neste template;
acompanhe-os durante a validação e escolha a monitoração definitiva na etapa 9.

A rede proposta é IPv4. Para o Supabase, use uma conexão compatível com IPv4,
como o **session pooler na porta 5432**; o endpoint direto IPv6 de um projeto
não funcionará nessa rede sem ajustes. Não compre um adicional IPv4 sem antes
verificar essa alternativa. O teste de banco real fica na etapa 7.

### Identidade e proteção de alterações

O host recebe apenas `AmazonSSMManagedInstanceCore`, sem chaves de acesso
estáticas e sem acesso aos segredos do Supabase/Groq. A role de snapshots tem
permissões para o disco selecionado, snapshots e regras de agendamento DLM;
exclusão fica limitada a snapshots com a tag de backup desta stack. Não há
permissão para Fast Snapshot Restore, cópias entre regiões ou compartilhamento
de snapshots. As regras públicas 80/443 são uma escolha deliberada para a API
pública com Caddy, conforme a etapa 5; os demais acessos continuam fechados.

O plano `deploy/aws/provisioning.yaml` concentra as permissões do projeto no
usuário dedicado com MFA. O mesmo login poderá revisar/aplicar mudanças na
stack `echomind-prod`, acessar a EC2 por SSM e iniciar, parar ou reiniciar
instâncias com a tag do projeto. CloudFormation usa automaticamente uma role
de serviço fixa: o proprietário não precisa alternar identidades nessas tarefas.
As políticas foram aplicadas e conferidas conforme o registro abaixo.

`SignInLocalDevelopmentAccess` permite o fluxo `aws login` com credenciais
temporárias. Não gere ou cole access keys no chat.
Não habilite Organizations, Control Tower ou uma configuração de SSO que crie
Organizations para resolver esse login: isso pode converter o Free Plan para
Paid automaticamente.

#### Preparação do primeiro operador

`deploy/aws/access.yaml` separa a identidade humana da infraestrutura da aplicação.
O plano usa a stack `echomind-access`, na região `us-east-1`, para criar somente
`echomind-access-operator`. A única política inicial é a política gerenciada AWS
`SignInLocalDevelopmentAccess`: permite autorização e renovação de tokens de
ferramentas, sem conceder acesso aos serviços da aplicação ou ao provisionamento.
O template não cria senha, access key, dispositivo MFA ou privilégios de administrador.

O proprietário configura a senha e o MFA diretamente no console privado após
a criação. Os valores não passam pela conversa, pelo template ou pelo Git.
O usuário tem retenção em exclusão/substituição da stack; isso não substitui a
revogação explícita de credenciais e permissões no desligamento do operador.
As permissões de operação e provisionamento estão no plano complementar abaixo.
Criar o usuário inicial não libera o provisionamento do stack principal.

Em 2026-10-19, o console da conta existente e a conexão AWS Core foram
autenticados novamente. A consulta confirmou plano FREE/ACTIVE com US$100 em
créditos, nenhum usuário IAM e nenhuma stack ativa em `us-east-1`. Não havia
trilha CloudTrail configurada; o histórico de eventos padrão de 90 dias não
substitui retenção durável. A trilha prevista no template principal continua pendente.

O novo template passou no cfn-lint e nas regras cfn-guard locais. A tentativa
inicial de registrar seu change set foi bloqueada pela revisão automática antes
da execução. Após autorização explícita do proprietário, em 2026-10-19, o change
set `approved-human-operator-20261019` foi criado, revisado e executado. A revisão
mostrou somente a inclusão do recurso `Operator`; `DescribeEvents` não retornou
erros de validação. A stack `echomind-access` chegou a `CREATE_COMPLETE`.

A conferência real confirmou `echomind-access-operator` com somente
`SignInLocalDevelopmentAccess`, sem políticas inline, grupos, access keys,
dispositivos MFA ou perfil de login do console. A criação não incluiu EC2 ou
outros recursos da aplicação. O formulário de senha personalizada foi aberto
para o proprietário preencher e enviar diretamente no console; o agente não
gerou nem preencheu senha ou semente MFA.

Na aba **Credenciais de segurança**, o proprietário deve definir a própria senha
em **Habilitar acesso ao console**, mantendo desmarcada a opção de exigir nova
senha no próximo login. Essa opção acrescentaria automaticamente a política
`IAMUserChangePassword`, que não faz parte do plano inicial aprovado. Depois,
usar **Atribuir dispositivo com MFA** nessa mesma aba para cadastrar seu
autenticador ou chave de segurança. Não compartilhar senha, QR code, semente ou
códigos MFA na conversa.

Ainda em 2026-10-19, após o proprietário concluir a configuração, as APIs IAM
confirmaram perfil de login ativo, `PasswordResetRequired=false`, um dispositivo
MFA cadastrado e nenhuma access key. A única política anexada continuou sendo
`SignInLocalDevelopmentAccess`, sem políticas inline ou grupos adicionais.
O login temporário do perfil local `default` foi concluído e a identidade STS
confirmada como esse usuário IAM. Os eventos de autenticação confirmaram MFA.
A integração AWS Core mantém sessão própria de administrador: ela não comprova
a identidade usada pelo CLI. `preflight_local.py --profile default` reutiliza
as verificações somente de leitura com o perfil que fará a implantação; não
exporta credenciais. As permissões de provisionamento foram aplicadas após a
autorização explícita do proprietário, conforme o registro abaixo.

#### Project permission bootstrap, service role separation and activation review

O arquivo `deploy/aws/provisioning.yaml`, preparado em 19/10/2026, cria a stack
`echomind-provisioning` com **sete recursos IAM**: três roles, um instance profile
e três políticas gerenciadas. Uma política é anexada ao operador existente;
duas à role de execução do CloudFormation. Não cria outro usuário, credenciais,
EC2 ou armazenamento. O proprietário autorizou explicitamente sua aplicação.

A role de execução pode criar/configurar rede, EC2 `t3.small`, disco, auditoria,
alertas e orçamento da aplicação na região configurada. Recursos novos usam
tags ou nomes do projeto; alterações usam tags/ARNs correspondentes. Essa role
não pode escrever em IAM, executar outras stacks ou expandir suas permissões.
Só pode passar as roles fixas do host e dos snapshots aos serviços previstos.
O operador não pode atualizar as stacks de acesso, criar usuários nem passar
uma role arbitrária. O uso de SSM e alterações da aplicação exigem MFA.
Consultas de metadados que exigem `Resource: '*'` podem mostrar outros recursos
regionais da conta; o escopo de leitura não é exclusivamente a tag do projeto.

A stack principal não contém mais recursos IAM. Ela recebe
`NodeInstanceProfileName` e `SnapshotExecutionRoleArn` dos outputs do bootstrap.
Toda criação/update/change set deve informar o output `ExecutionRoleArn` no
argumento **RoleARN** do CloudFormation, além de manter o nome `echomind-prod`.
Esses valores são identificadores públicos, não segredos. Preencher os parâmetros
privados locais preservando o e-mail de alertas; não versionar esse arquivo.
A interface de rede agora é explícita e marcada com `Project`, e as tags da EC2
são propagadas ao disco raiz, permitindo conferir dependências nas políticas.

Validação: cfn-lint dos quatro templates sem erros/avisos; cfn-guard aprovado;
13 testes de infraestrutura e 20 de publicação aprovados; limites de tamanho
IAM conferidos. A referência pública de autorização confirmou as 214 ações de
17 serviços. `ValidatePolicy` do IAM Access Analyzer retornou zero apontamentos
nas quatro políticas; `SimulateCustomPolicy` aprovou 25 cenários, incluindo
negação de MFA ausente, IAM, outra role, VPC/ENI/disco de outro projeto e máquina
maior. Evidências resumidas em `docs/provisioning-access-review.json`.
ARNs físicos sintéticos foram usados nas simulações. Esses checks não comprovam
que os provedores do CloudFormation executarão todas as operações reais;
eventuais permissões adicionais exigem revisão, nunca concessão automática de
administrador. `ValidateTemplate` aprovou os dois arquivos atuais: a aplicação
sem capabilities IAM, o bootstrap com `CAPABILITY_IAM`.

Após a autorização, o change set `approved-project-access-20261019` foi criado
e conferido: exatamente sete inclusões IAM, com o template original idêntico
ao arquivo revisado. `DescribeEvents` não retornou `VALIDATION_ERROR`. A execução
foi concluída e `echomind-provisioning` chegou a `CREATE_COMPLETE`, com os sete
recursos no mesmo estado. Os documentos das quatro políticas aplicadas foram
comparados com o plano aprovado e coincidiram, usando os ARNs físicos reais.
As relações de confiança, instance profile e anexos de políticas também foram
conferidos. O operador possui somente a política inicial de login e a política
do projeto, sem grupos, políticas inline ou access keys; mantém MFA ativo.

`SimulatePrincipalPolicy`, agora usando o usuário e a role existentes na conta,
aprovou os mesmos 25 cenários sem contexto ausente. O preflight local executado
com `default` confirmou a identidade IAM, nove consultas somente de leitura
sem erros e nenhum bloqueio nesses checks. O plano FREE permanece ACTIVE, com
US$100 de créditos, vencimento em 13/04/2027 e quota regional de cinco vCPUs
Standard; nenhuma EC2 está provisionada na região. Não há ainda trilha durável
CloudTrail, somente histórico padrão e auditoria da integração.

O usuário IAM conseguiu ler os outputs do bootstrap e validar `stack.yaml`.
`NodeInstanceProfileName` e `SnapshotExecutionRoleArn` foram atualizados em
`parameters.local.json`, preservando o e-mail e os demais parâmetros privados.
Esse arquivo permanece ignorado pelo Git. Não foram criados recursos da
aplicação, nem iniciada a etapa final. A criação real da EC2 ainda exige revisão
atual de custos, parâmetros e change set da aplicação.

O pipeline continua desativado. `pipeline.yaml` ainda prevê anexar permissões de
artefatos à role do host (`NodeReleasePolicy`); antes de ativá-lo, essa concessão
deve ser movida para o bootstrap/revisão de acesso. Não acrescentar escrita IAM
à role de execução da aplicação para contornar esse limite. O plano atual não
autoriza criar o provedor OIDC nem os recursos do pipeline.

`stack-policy.json` bloqueia substituição/exclusão por updates de Node, disco,
Elastic IP, chave KMS e bucket de auditoria. No fluxo por change set, aplicar
essa política imediatamente após `CREATE_COMPLETE`, antes de qualquer update:
a AWS rejeita `SetStackPolicy` enquanto a stack está `REVIEW_IN_PROGRESS` e o
change set não recebe esse documento. Ela protege updates, não o rollback da
criação inicial. Não existe Export/ImportValue entre stacks. Uma mudança
de AMI pode exigir substituir a EC2; um disco de uma AZ não se move para outra
AZ por simples edição. Planeje drenagem, backup e recuperação antes de liberar
uma mudança protegida. A proteção de término também exige operação explícita
para encerrar a EC2.

### Persistência e bootstrap

O volume de dados é identificado pelo **ID EBS/NVMe**, não por uma ordem fixa
de discos. Só um volume novo criado pela stack, sem filesystem ou assinatura,
pode ser formatado. Um volume de recuperação vazio, particionado ou com tipo
inesperado é rejeitado. Um ext4 existente é preservado.

O disco monta em `/srv/echomind`; Docker usa `docker/` e containerd usa
`containerd/` nesse disco. Configurar apenas `data-root` do Docker não basta
para o image store das instalações novas do Docker 29. A configuração privada
fica em `/srv/echomind/private`, com bind mount em `/etc/echomind`, mantendo
compatibilidade com o instalador da etapa 4 que rejeita links simbólicos.
As montagens entram no fstab por UUID e o serviço verifica ambas antes de subir.
Uma falha de bootstrap bloqueia o Docker até reparo; não usa o disco do sistema
como substituto silencioso para os dados.

O bootstrap instala Docker a partir do repositório oficial assinado e exige
Compose >= 2.30. A versão de pacotes do host acompanha o repositório no primeiro
boot; registre as versões efetivamente instaladas e teste upgrades, enquanto
as imagens da aplicação continuam fixadas por digest/commit. O script não
deve ser executado manualmente em um host existente sem reconciliação.

O bootstrap também instala o AWS CLI **2.38.0 amd64**, com versão fixa. O ZIP e
a assinatura são baixados exclusivamente de `awscli.amazonaws.com`. A chave
pública do guia oficial está no template; o fingerprint
`FB5DB77FD5C118B80511ADA8A6310ACC4672475C` é conferido antes da importação e o
status `VALIDSIG` é obrigatório antes de extrair ou executar o instalador.
A chave publicada expira em **2027-07-01**: uma atualização exige conferir a
documentação oficial e repetir a validação, sem ignorar assinatura ou validade.

O SSM Agent precisa ser **3.3.2746.0 ou superior** para a interpolação `ENV_VAR`
usada pelo pipeline. O bootstrap confere o agente Snap já fornecido pela AMI e,
se necessário, solicita atualização pelo canal `stable`. Se a versão continuar
insuficiente ou o serviço não iniciar, a preparação falha e bloqueia o Docker;
o script não instala um segundo agente nem troca automaticamente para `candidate`.

Em 2026-10-19, a assinatura do instalador oficial fixado foi validada localmente
com a chave incorporada e uma cópia com um byte alterado foi rejeitada. Nenhum
instalador foi executado nessa verificação. Para repetir com GnuPG já instalado:

```sh
python deploy/aws/verify_cli_download.py
```

O verificador baixa somente arquivos públicos em diretório temporário isolado.
No Windows com o GnuPG do Git, informe `--gpg` com o caminho do executável e
`--msys-paths`. Os testes offline também exercitam assinatura inválida, assinante
incorreto e atualização insuficiente do SSM. Isso não substitui conferir a
instalação e a conectividade na EC2 real.

CloudFormation `CREATE_COMPLETE` não confirma o fim desse processo: a anexação
EBS ocorre após a criação da EC2, e o bootstrap aguarda o disco e o Elastic IP.
Antes de configurar a aplicação, confirme por SSM:

```sh
sudo test -f /srv/echomind/bootstrap-ready
sudo mountpoint -q /srv/echomind
sudo mountpoint -q /etc/echomind
sudo systemctl is-active docker containerd
sudo docker info --format '{{.DockerRootDir}}'
sudo docker compose version
```

O diretório de dados contém os volumes de originais, cache e certificados, o
estado Docker e os arquivos privados. Não publique seu conteúdo em logs. A
trilha CloudTrail registra chamadas administrativas, incluindo APIs SSM, mas
este template não habilita gravação do conteúdo interativo das sessões, evitando
registrar segredos exibidos em editores. Auditoria detalhada da sessão exige
um fluxo de configuração de segredos que não os mostre no terminal.

### Backup, restauração e encerramento

Os snapshots DLM são **crash-consistent** e podem perder alterações desde o
último snapshot; não prometem backup coordenado com o PostgreSQL externo.
Para uma cópia consistente da aplicação, use a drenagem e o arquivo de backup
da etapa 3. Prepare o backup do Supabase antes de migrations na etapa 7. O
alarme DLM detecta falhas reportadas; confirme também os snapshots concluídos,
pois ausência de execução de uma política desativada não equivale a erro emitido.

Para recuperar, escolha um snapshot, crie um EBS criptografado **na AZ de
destino**, aplique as tags `Project`/`EchoMindBackup` da nova stack e use seu ID
em `ExistingDataVolumeId`. Ele precisa estar desanexado e conter ext4. O volume
antigo não é sobrescrito. Só execute esse processo após revisar qual é a cópia
correta, o estado do banco e a interrupção da instância anterior. A restauração
com uma EC2 real ainda não foi executada; será um teste obrigatório antes de
considerar a publicação concluída.

Encerrar/parar a EC2 não elimina despesas de EBS, snapshots, Elastic IP, S3 ou
KMS. O template retém disco de dados, endereço público, chave KMS e bucket de
auditoria. Esses recursos precisam de inventário e remoção explícita quando
não forem mais necessários. Excluir uma stack não é um comando de limpeza
completa de custos nem substitui backup.

### Validação e execução futura

- `preflight.mcp.py`: script somente de leitura para `run_script` do AWS MCP;
  revisa plano, identidade, quota, AMI, zonas e recursos na região de destino.
- `parameters.example.json`: exemplo sem credenciais. A cópia privada
  `parameters.local.json`, ignorada pelo Git, contém o email informado para os
  alertas. Confira AZ e demais parâmetros antes de preparar um change set;
  não coloque senhas ou chaves nesse arquivo.
- `check_infra.py`: testes de invariantes, sintaxe Bash e recusa de formatação
  de discos recuperados, com comandos de disco simulados.
- `security.guard` e `check_guard.py`: controles de segurança do projeto e
  regressões negativas para SSH, portas amplas, IMDSv1, CPU ilimitada e exposição
  de dados. Não equivalem a uma certificação de conformidade.
- `validation.Dockerfile`: ambiente isolado com cfn-lint 1.57.2 e
  cfn-guard 3.2.1; o binário Guard tem SHA-256 fixado.
- `validate.ps1`: executa os validadores e testes em containers sem rede, com
  filesystem somente de leitura e apenas os arquivos públicos necessários
  montados. Não instala ferramentas, monta parâmetros privados ou chama AWS.

Para reproduzir a validação no PowerShell, na raiz do repositório, com Docker
Desktop em modo Linux:

```powershell
# O build baixa apenas os validadores e suas dependências no container.
docker build --platform linux/amd64 -f deploy/aws/validation.Dockerfile -t echomind-infra-validation:local deploy/aws
if ($LASTEXITCODE -ne 0) { throw 'Falha na construção dos validadores' }
& ./deploy/aws/validate.ps1
```

Validação executada em 14/10/2026. O build do Guard usa a tag oficial `3.2.1`
e confere o checksum publicado. O script exige a imagem local já construída;
não baixa uma imagem substituta. Nenhuma dependência foi instalada no Python
do projeto.

| Camada | Resultado atual |
| --- | --- |
| Conta/preços/quota/AMI | Preflight local IAM aprovado em 19/10; acesso de provisionamento aplicado e conferido. Rever preços antes de criar a aplicação |
| Invariantes e Bash | 13 testes passaram no container de validação, sem executar o bootstrap ou acessar discos reais |
| API `ValidateTemplate` | Templates atuais aprovados em 19/10: principal sem capability IAM; bootstrap com `CAPABILITY_IAM`. Não comprova execução ou toda a semântica |
| cfn-lint 1.57.2 | Aprovado para `us-east-1`, sem erros ou avisos |
| cfn-guard 3.2.1 | Template aprovado; seis regressões rejeitadas: SSH, faixa ampla de portas, disco sem criptografia, CPU ilimitada, IMDSv1 e bucket público |
| Change set/validação da conta | Após correção IAM e limpeza autorizadas, plano v2 criou os 26 recursos com `CREATE_COMPLETE`; stack policy aplicada e conferida |
| EC2/SSM/backup/alertas reais | Host e reinício verificados por SSM; inscrição SNS confirmada e DLM habilitado. Snapshot/restauração reais ainda pendentes |

A etapa 6 conclui a preparação e a validação local da infraestrutura. Não
confirma o funcionamento de serviços ainda não criados. Antes da criação real:
rever crédito/custos, medir o E5 no limite candidato, conferir os parâmetros
privados, usar identidade não root, revisar o change
set; aplicar `stack-policy.json` após a criação, antes de updates. A confirmação SNS só é enviada ao criar o
tópico. A preparação local original não enviou alertas nem alterou a conta;
o registro do plano real está descrito abaixo.

### Revisão real da criação da EC2 - 19/10/2026

O usuário IAM `echomind-access-operator`, pelo perfil `default`, registrou o
change set **`predeploy-application-20261019-v1`** da stack `echomind-prod`.
Na revisão inicial, o plano estava `CREATE_COMPLETE`/`AVAILABLE`, com exatamente **26 inclusões**:
uma EC2, rede dedicada, interface, Elastic IP, disco de dados e associação,
política DLM, quatro alarmes, SNS/KMS, orçamento e auditoria S3/CloudTrail.
O disco raiz de 16 GiB está dentro da definição da EC2; o disco de dados tem
20 GiB. Não havia novos recursos IAM no plano. Naquele momento a stack estava
`REVIEW_IN_PROGRESS`, sem recursos provisionados. A tentativa de execução e
o estado atual estão registrados na seção de recuperação abaixo.

O template registrado coincide com o arquivo revisado e a stack usa a role de
execução fixa do bootstrap. A AMI resolvida é `ami-02a9cdd4e98bc3c78`, Ubuntu
24.04 amd64, disponível no catálogo; `t3.small` é oferecida em `us-east-1a`.
Isso não reserva capacidade física. A consulta real confirmou quota de cinco
vCPUs Standard, plano FREE/ACTIVE e US$100 em créditos, válidos até 13/04/2027
ou seu esgotamento. O preflight local passou em todas as nove consultas.

A execução inicial do preflight encontrou limite de requisições de renovação
OAuth: vários processos CLI tentavam renovar a mesma sessão simultaneamente.
O adaptador agora consulta a identidade primeiro, deixa essa renovação terminar
e reutiliza o resultado STS nas verificações paralelas. A repetição real passou
sem erros, sem pedir outro login ou exportar credenciais.

Os seis preços foram reconferidos no AWS Price List: EC2 US$0,0208/h, gp3
US$0,08/GiB-mês, IPv4 US$0,005/h, snapshots US$0,05/GiB-mês, chave KMS US$1/mês
e alarmes padrão US$0,10 por métrica/mês. O cálculo continua **US$24,11/mês**
para 730 horas e 20 GiB-mês ilustrativos de snapshots, antes dos créditos e
franquias. Tráfego, armazenamento/requisições de auditoria e pipeline, entregas
SNS, chamadas KMS e provedores externos continuam variáveis/excluídos. Não é
hospedagem gratuita permanente; o orçamento de US$30 envia alertas e não
interrompe os recursos.

`DescribeEvents` foi negado ao perfil IAM com os seletores de change set e de
stack. A integração AWS Core leu os eventos somente para conferência: operação
concluída sem `VALIDATION_ERROR`. Nenhuma permissão foi ampliada para contornar
a negação; o acesso do CLI a essa API nova ainda precisa de revisão específica.
O template passou novamente no cfn-lint, nas regras Guard, nas seis regressões
de segurança e nos 13 testes de infraestrutura. Evidências públicas em
`docs/ec2-predeployment-review.json`, sem e-mail ou identificadores da conta.

Antes de executar: obter aprovação explícita para este change set e seu custo.
Após `CREATE_COMPLETE`, aplicar a stack policy antes de qualquer update,
conferir bootstrap/mounts/Docker/CLI/SSM, inscrição SNS e auditoria. Sucesso do
CloudFormation não comprova que o bootstrap terminou nem que a API funciona.
Não foi iniciada a etapa final nem habilitado o pipeline.

### Primeira tentativa e plano de recuperação - 19/10/2026

Esta seção preserva o diagnóstico e o plano inicialmente preparado após a falha.
A autorização posterior e a recuperação concluída estão registradas na próxima seção.

Após autorização explícita, o operador IAM executou o plano revisado. A chamada
foi aceita, mas a criação de `Node` falhou: a role do CloudFormation não autorizou
`ec2:RunInstances` sobre o volume raiz. A reversão automática terminou em
**`ROLLBACK_COMPLETE`**, sem uma EC2 criada. O filtro `FailedEvents=true` mostrou
essa única falha acionável; o cancelamento de `AlertTopic` foi consequência da
reversão, sem provar que sua criação teria terminado normalmente.

O erro estava na política que preparamos: a mesma condição `ec2:InstanceType`
era exigida em ARNs de instância e volume. A referência de autorização da AWS
não oferece essa chave no contexto de volume. CloudTrail confirmou que o
pedido real continha corretamente `Project=echomind-prod` no disco, portanto
não se tratava de uma tag ausente. As simulações anteriores forneciam contexto
de instância também para o volume e não reproduziam essa diferença real.

A correção local em `provisioning.yaml` separa as duas avaliações: instância
continua limitada a `t3.small` e à tag do projeto; volume exige a mesma tag,
criptografia, gp3 e exatamente 16 GiB, sem a chave de contexto da instância.
Não acrescenta ações de API nem permissões de administrador. Access Analyzer
retornou zero apontamentos; oito simulações específicas tiveram a decisão
esperada, incluindo o caso positivo sem contexto de instância. O relatório
preserva os diagnósticos de contexto ausente dos casos negativos. Os 13 testes
de infraestrutura e 20 de publicação, cfn-lint, cfn-guard e limites IAM passaram.

A tentativa de registrar o change set dessa correção foi **bloqueada pela
revisão automática**: a autorização existente cobre a infraestrutura da
aplicação, mas não aprova explicitamente a alteração de permissões IAM.
Nenhuma atualização da política foi registrada ou aplicada e não houve tentativa
de contornar o bloqueio. O arquivo local corrigido ainda difere da política ativa.

A reversão respeitou `Retain` e preservou quatro recursos desta tentativa:

| Recurso | Estado após a primeira reversão | Recuperação inicialmente proposta |
| --- | --- | --- |
| Disco de dados gp3 20 GiB | Criptografado, criado nesta tentativa sem snapshot, disponível e sem anexos; o nó nunca foi criado | Excluir esse disco vazio antes de recriar |
| Elastic IP | Reservado e sem associação | Liberar esse endereço antes de reservar o novo |
| Chave KMS de notificações | Habilitada; distinta da chave AWS EBS que cifra o disco | Agendar exclusão com espera de sete dias |
| Bucket de auditoria | Preservado com seus objetos | Manter bucket e conteúdo para auditoria |

Enquanto aguardam limpeza, disco/IP/chave têm custo base ilustrativo de
**US$6,25/mês**, antes dos créditos e do S3 variável; não há cobrança de CPU
de uma máquina nesta tentativa. Não foram removidos recursos retidos.

Para recuperar, aprovar primeiro a correção IAM e a limpeza delimitada acima.
Revisar/aplicar somente `NetworkPolicy` na stack de acesso, conferir novamente
`ROLLBACK_COMPLETE`, remover apenas a stack malsucedida `echomind-prod` e seus
recursos sem uso listados, mantendo ambas as stacks de acesso e a auditoria.
Então registrar/revisar um novo plano da aplicação com a mesma configuração,
executá-lo e conferir a inicialização. Mudanças adicionais fora desse escopo
exigem nova análise. Até a autorização dessa recuperação, a criação continuou pendente.

`deploy/aws/verify_host.sh` foi preparado para verificações somente de leitura
por SSM após a criação: cloud-init, marcador, mounts, diretórios privados,
Docker/containerd em disco durável, versões CLI/Compose/SSM e serviços ativos.
Não imprime arquivos de ambiente nem segredos. Sua sintaxe foi validada, mas
naquele momento ele ainda não havia sido executado em um host. Evidências e plano em
`docs/ec2-provisioning-recovery.json`.

### Infraestrutura criada e verificada - 19/10/2026

O proprietário autorizou a correção e a recuperação. O change set
`fix-root-volume-context-20261019` mostrou somente a alteração de `NetworkPolicy`,
sem substituições, e não teve erros de validação. Após executar, a stack de
acesso chegou a `UPDATE_COMPLETE`; a versão v2 da política aplicada coincide
integralmente com o arquivo revisado. A simulação da role real autorizou o disco
raiz com seu contexto próprio, sem `ec2:InstanceType` nem contexto ausente.

Foi removido somente o registro da stack malsucedida, após conferir
`ROLLBACK_COMPLETE` e seus recursos. O disco vazio de 20 GiB foi excluído e o
Elastic IP sem associação foi liberado; a ausência de ambos foi confirmada.
A chave de notificações dessa tentativa ficou `PendingDeletion`, com exclusão
agendada para **26/10/2026**, após sete dias. Ela não era a chave AWS que cifra
os discos. O bucket anterior e seus objetos foram preservados para auditoria;
as stacks de acesso permaneceram intactas.

O operador IAM registrou, revisou e executou
`predeploy-application-20261019-v2`, com as mesmas 26 inclusões autorizadas e
sem erros de validação. **`echomind-prod` está `CREATE_COMPLETE` e os 26 recursos
também estão completos.** `stack-policy.json` foi aplicada após a criação e seu
conteúdo foi conferido. A EC2 está protegida contra término, usa IMDSv2 com
hop limit 1 e créditos de CPU em modo `standard`. Os dois discos gp3 de 16 e
20 GiB estão criptografados, anexados e em uso; só 80/443 estão expostos.

`verify_host.sh` passou por SSM usando o usuário dedicado. Cloud-init terminou,
o marcador de bootstrap existe, `/srv/echomind` está em ext4 no disco de dados
e `/etc/echomind` está ligado ao diretório privado desse mesmo disco, root 700.
Docker e containerd guardam seus dados no volume durável. Versões observadas:
**Docker 29.9.1, Compose 5.6.0, AWS CLI 2.38.0 e SSM Agent 3.3.4793.0**.
Os três serviços estão ativos e habilitados para iniciar com o sistema.

Foi criado um arquivo temporário sem dados sensíveis no volume durável. Uma
reinicialização real, solicitada pelo operador IAM, preservou esse arquivo;
as verificações completas passaram novamente, com mounts e serviços ativos.
O arquivo de teste foi removido após a conferência. As verificações AWS de
instância, sistema e EBS estão `ok`. A checagem foi feita por estados, versões
e mounts, sem ler logs de bootstrap ou arquivos secretos. Ao enviar o script
por SSM, preservar `#!/bin/bash` na primeira linha e normalizar CRLF para LF.

O proprietário confirmou a inscrição de e-mail, e SNS confirmou o ARN da
assinatura, sem `PendingConfirmation`. Os quatro alarmes existem; o orçamento
mensal de US$30 está `HEALTHY` e observa custos antes dos créditos, sem funcionar
como limite de gasto. CloudTrail está gravando, com entrega observada no S3;
o bucket novo bloqueia acesso público, usa AES256 e versionamento. DLM está
`ENABLED`, agendado a cada 24 horas às 03:00 UTC, retendo sete snapshots do disco
de dados. O primeiro snapshot agendado e uma restauração real ainda precisam
ser conferidos; essa política não faz backup do banco externo Supabase.

Os identificadores físicos e o IP foram salvos em
`deploy/aws/outputs.local.json`, ignorado pelo Git junto dos parâmetros privados.
O último preflight informou plano FREE/ACTIVE, **US$120 em créditos** e vencimento
em 13/04/2027; não se inferiu o motivo da alteração do saldo. A estimativa base
continua US$24,11/mês antes de créditos e variáveis. A máquina foi deixada
**ligada**, com consumo dos recursos em andamento.

Esta etapa não instalou segredos de runtime, publicou a API, apontou DNS,
habilitou o pipeline nem iniciou a validação final da aplicação. Próximas
pendências: conexão de banco IPv4, variáveis privadas, domínio/HTTPS e ativação
revisada do pipeline. A consulta `DescribeEvents` do CLI continua pendente de
revisão; a integração AWS forneceu essa validação somente de leitura. O shell
interativo SSM não foi testado; Run Command foi testado pelo usuário dedicado.
Evidências públicas em `docs/ec2-infrastructure-verification.json`.

## Etapa 7: banco e frontend

**Preparação local validada; configuração real pendente.** O frontend de produção
informado é `https://echomind-front.vercel.app`. O domínio da API ainda não foi
escolhido. Ele será o endereço HTTPS do backend na EC2, separado do endereço do
frontend; precisa de DNS apontando para o Elastic IP e certificado do Caddy.
Não use localhost, IP HTTP ou um domínio fictício na configuração publicada.

### Diagnóstico dos serviços existentes

Consultas somente de leitura em 14/10/2026 identificaram o projeto Supabase
EchoMind ativo em `sa-east-1`, PostgreSQL 17.6 e pgvector 0.8.0. A AWS candidata
continua em `us-east-1`; essa distância afeta latência e deve ser medida antes
de uma mudança de região. O banco continua no Supabase.

- Revisão aplicada: **0022**. Head do repositório: **0023**.
- A `0023` remove `campus_locations`, tabela do mapa antigo. Havia **zero
  registros** na consulta. Isso precisa ser conferido novamente na manutenção;
  o downgrade recria a estrutura, sem recuperar registros removidos.
- As vinte tabelas públicas consultadas estavam com RLS ativo. A ausência de
  policies é intencional para tabelas acessadas pelo backend com filtros de
  tenant, sem leitura direta pelo navegador. Não criar policies amplas para
  eliminar os avisos informativos do advisor.
- A coluna vetorial do LangChain não fixa dimensão no tipo, mas os vetores
  armazenados consultados tinham **384 dimensões**. O preflight verifica os
  valores nesses casos; não exige reindexação só por o tipo ser `vector`.
- O advisor também apontou a extensão vector em `public` e proteção contra
  senhas vazadas desativada. Não foram alteradas: mover a extensão exige revisar
  dependências; a configuração de Auth deve ser conferida no plano disponível.
  [Extensões no schema público](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public),
  [RLS sem policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
  e [proteção de senhas](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

O conector Vercel listou um projeto EchoMind, mas retornou **403 ao consultar
suas configurações**; a CLI não estava instalada. A referência local em
`.vercel/project.json` não confirma que o projeto corresponde ao domínio
informado. Antes de editar ou publicar, conferir no painel qual projeto possui
`echomind-front.vercel.app` e restabelecer o acesso da integração a esse projeto.
Não houve alteração de variáveis, domínio, Auth ou deploy remoto nesta etapa.

### Conexão e preflight do banco

A EC2 preparada usa IPv4. Obtenha **Session pooler, porta 5432** no botão
Connect do Supabase; o hostname real não deve ser montado por tentativa a
partir da região. Use o mesmo projeto do frontend e `sslmode=require` ou
validação de certificado mais forte. Não use transaction pooler na porta 6543
para esse fluxo. Conexão direta é adequada se o ambiente de manutenção tiver
acesso IPv6; o teste via conector não comprova a conectividade da EC2.
[Modos de conexão](https://supabase.com/docs/guides/database/connecting-to-postgres).

`scripts/check_database.py`, incluído na imagem de produção, recebe
`DATABASE_URL` somente pelo processo, sem carregar `.env`. A transação é de
leitura, com timeout; confere revisões, tabelas essenciais, RLS, pgvector e
dimensões. Não mostra DSN, valores de credenciais, textos ou embeddings.
Por padrão termina com erro se o banco não estiver pronto; `--inventory`
serve apenas para diagnóstico e pode informar `ready=false` sem falhar.
Esse diagnóstico não comprova autenticação, permissões de cada rota nem toda
a equivalência do schema; esses testes continuam necessários.

No host, depois de instalar os arquivos privados da etapa 4 e escolher a
imagem candidata, use o Compose da etapa 2:

```sh
docker compose --env-file /etc/echomind/deploy.env -f deploy/compose.yaml run --rm --no-deps backend python scripts/check_database.py --inventory
```

O comando não inicia Uvicorn, workers documentais ou downloads de modelos.
Não publique a saída de `docker compose config` com a configuração real.

### Backup antes de aplicar a migration

O Free Plan do Supabase exige preparar exportação própria; não foi presumido
backup diário recuperável da plataforma. O snapshot EBS da etapa 6 não contém
o PostgreSQL externo. [Backups Supabase](https://supabase.com/docs/guides/platform/backups).

O procedimento abaixo cria um **backup do schema public da aplicação**,
incluindo dados, revisão Alembic e RLS. Ele não é backup completo do Supabase:
não inclui Auth, configurações de provedores, roles/senhas ou objetos Storage.
Uma recuperação completa do projeto requer um plano separado para esses itens.

Prepare privadamente `/etc/echomind/pg_service.conf` a partir do exemplo em
`deploy/database`, com o endpoint correto. A senha fica somente em
`/etc/echomind/pgpass`, no formato libpq, com `:` e `\` escapados quando necessário.
Use diretório 700 e arquivos 600. Esses arquivos e os dumps ficam fora do Git;
não cole a senha no comando, no chat ou em logs. Use cliente PostgreSQL 17.

Exemplo no host Linux, em sessão administrativa, com a imagem cliente já
disponível localmente e diretório privado de backup preparado:

```sh
set -eu
release="$(date -u +%Y%m%dT%H%M%SZ)"
test ! -e "/srv/echomind/db-backups/$release.dump"
pg_client() {
  docker run --rm --pull never --user 0:0 \
    --mount type=bind,source=/etc/echomind/pg_service.conf,target=/private/pg_service.conf,readonly \
    --mount type=bind,source=/etc/echomind/pgpass,target=/private/pgpass,readonly \
    --mount type=bind,source=/srv/echomind/db-backups,target=/backup \
    -e PGSERVICE=echomind -e PGSERVICEFILE=/private/pg_service.conf \
    -e PGPASSFILE=/private/pgpass pgvector/pgvector:0.8.6-pg17 "$@"
}
pg_client pg_dump --schema=public --format=custom --no-owner --no-privileges --file="/backup/$release.dump"
chmod 600 "/srv/echomind/db-backups/$release.dump"
pg_client pg_restore --list "/backup/$release.dump" >/dev/null
sha256sum "/srv/echomind/db-backups/$release.dump"
```

Antes do dump final, drene uploads/processamento conforme a etapa 3 e interrompa
as demais escritas da aplicação durante a manutenção. Guarde uma cópia protegida
fora da EC2 e registre hash, horário, revisão e imagem candidata em local privado.
Um dump legível por `--list` não comprova que ele restaura.

Restaure **essa cópia real** primeiro em um PostgreSQL descartável e vazio,
com extensões vector/uuid-ossp já instaladas. Use `pg_restore --schema=public
--no-owner --no-privileges --exit-on-error --single-transaction` apontando
explicitamente para o banco de teste. O filtro de schema evita tentar recriar
o schema public já existente. Compare revisão, contagens e registros de aceite;
revise permissões/owners removidos por esses flags antes de restaurar no serviço
gerenciado. Não use `--clean` no banco real como procedimento automático.

Somente após esse teste, revisão da migration e nova conferência da tabela
retirada, a aplicação será uma operação separada:

```sh
docker compose --env-file /etc/echomind/deploy.env -f deploy/compose.yaml run --rm --no-deps backend python -m alembic upgrade 0023
docker compose --env-file /etc/echomind/deploy.env -f deploy/compose.yaml run --rm --no-deps backend python scripts/check_database.py
```

O destino `0023` é explícito para não incluir futuras migrations sem revisão.
Se falhar, mantenha a aplicação em manutenção; não execute downgrade para tentar
recuperar registros. O teste sintético desta etapa não substitui a restauração
do dump real. Nenhuma migration ou exportação de dados reais foi executada.

### Vercel, CORS e Supabase Auth

No projeto que possui o domínio informado, conferir Root Directory
`echomind-front`, preset Next.js, Node 22 e pnpm 10.30.0. O lockfile permanece
versionado. O exemplo em `deploy/frontend/.env.example` contém somente campos
públicos e a opção de validação do build.

| Local | Configuração de produção |
| --- | --- |
| Vercel `NEXT_PUBLIC_API_URL` | Origem HTTPS da API, a definir, sem caminho ou barra final |
| Vercel `NEXT_PUBLIC_SUPABASE_URL` | URL do mesmo projeto Supabase usado pelo backend |
| Vercel `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Chave publishable desse projeto, nunca secret/service_role |
| Vercel `ECHOMIND_REQUIRE_API_URL` | `true` para publicar o projeto completo com a API |
| Backend `ALLOWED_ORIGINS` | `https://echomind-front.vercel.app`, mais outras origens exatas se forem necessárias |
| Supabase Auth Site URL | `https://echomind-front.vercel.app` |
| Supabase Auth Redirect URLs | `https://echomind-front.vercel.app/redefinir-senha` |

O build agora rejeita origens HTTP/localhost, caminhos, credenciais na URL,
chaves incompatíveis e variáveis públicas de segredos do backend. A API ausente
continua permitida para o frontend isolado já existente; a opção
`ECHOMIND_REQUIRE_API_URL=true` exige seu endereço na publicação completa.
Essa validação confere formato, sem autenticar chaves ou testar serviços reais.

As variáveis `NEXT_PUBLIC_*` entram no bundle durante o build: mudar seu valor
na Vercel exige novo deployment. Produção e Preview precisam de configurações
próprias; prefira um Supabase de teste para previews, sem liberar origens ou
redirects genéricos em produção. Não colocar DATABASE_URL, GROQ_API_KEY ou
SUPABASE_SECRET_KEY na Vercel deste frontend.
[Variáveis Vercel](https://vercel.com/docs/environment-variables) e
[variáveis Next.js](https://nextjs.org/docs/app/guides/environment-variables).

Preserve URLs locais ainda usadas no desenvolvimento. O reset de senha já usa
`window.location.origin/redefinir-senha`; confirme que o template de email
respeita esse destino e teste com uma conta de aceite. Site URL também afeta
confirmação de cadastro. O envio de emails de teste e a alteração desses valores
não foram realizados. [Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).

### Evidência e pendências

O ensaio local `deploy/validate_database_release.py` cria e remove somente um
container PostgreSQL descartável em loopback. Usa credenciais sintéticas,
não carrega `.env`, não baixa imagem e mantém o dump dentro do container.
Na raiz do projeto, com Docker e as dependências Python já disponíveis:

```powershell
& ./echomind-backend/.venv/Scripts/python.exe ./deploy/validate_database_release.py
```

Ele validou `0022 -> 0023`, detectou a pendência pelo preflight e restaurou
a revisão anterior, um registro removido e RLS em outro banco vazio. Também
verificou dimensão de vetores em coluna sem dimensão fixa. A imagem usa
PostgreSQL 17.11/pgvector 0.8.6; isso não equivale a testar o dump real do
Supabase 17.6/pgvector 0.8.0.

Resultados finais desta etapa:

| Verificação | Resultado |
| --- | --- |
| Integração PostgreSQL/pgvector | 87 testes aprovados em banco local descartável |
| Frontend: configuração, API e páginas de autenticação | 44 testes aprovados, incluindo 14 casos da nova validação pública |
| Frontend: lint, tipos e build de produção | Aprovados com configuração pública sintética HTTPS |
| Imagem backend Linux amd64 | Construída; preflight final informou `ready=true` no banco local migrado |
| Backup/restauração | Ensaio sintético aprovado; backup do Supabase real permanece pendente |

O aviso de descontinuação futura da integração LangChain PGVector permanece;
a atualização de dependências deve ter validação própria e não foi incluída
nesta etapa. A CI executará novamente seus gates após o envio dos commits.

Os testes HTTP de deduplicação passaram a compartilhar um único ciclo de vida
da aplicação e a usar armazenamento temporário. A corrida entre transações
continua testada em sessões PostgreSQL independentes; não se força uma barreira
dentro do lock de admissão. O teste de compensação concorrente isola a camada
transacional, pois o endpoint serializa as operações no filesystem. As proteções
da aplicação não foram desabilitadas para publicar.

- [x] Diagnóstico de revisão, RLS e vetores do Supabase, somente de leitura.
- [x] Preflight incluído e executado na imagem Linux de produção.
- [x] Ensaio sintético de backup, migration e restauração.
- [x] Validação das variáveis públicas e build de produção do frontend.
- [x] Escolher domínio da API: `echomind-api.duckdns.org`, informado como reservado pelo responsável.
- [x] Apontar o DNS para o Elastic IP e validar HTTPS/health na EC2 real.
- [x] Criar backup real consistente do schema público e testar a restauração em banco local separado.
- [x] Aplicar `0023` e conferir o banco real depois da manutenção.
- [x] Conferir conexão privada IPv4/session pooler a partir da EC2.
- [x] Conferir projeto e deployment Vercel via integração reconectada, usando o ID e o contexto padrão.
- [x] Configurar valores reais de Vercel/CORS/Auth para produção, preservando retornos locais explícitos.
- [x] Refazer o build de produção da Vercel e testar login, chat e documentos.
- [x] Testar cadastro real e o ciclo de recuperação de senha por e-mail.

## Etapa 8: publicação por GitHub Actions

**Situação: preparação concluída e validada localmente. Automação ainda não
ativada e nenhum recurso AWS criado pela automação.** Em 2026-10-19, a primeira
instalação manual da API foi publicada na infraestrutura da etapa 6, com banco,
identidade dedicada, DNS e TLS verificados. O hostname é
`echomind-api.duckdns.org`; o domínio do frontend é `echomind-front.vercel.app`.
Essa instalação não ativa a publicação por commits. Consulte o registro de
primeira publicação abaixo e as pendências de CI/CD desta seção.

### Fluxo preparado

1. Um push/merge na `main` executa o CI existente: backend, banco e frontend.
   O CI agora também valida os templates, as regras de segurança, os workflows
   e os cenários de falha/recuperação do deploy. Constrói a imagem com o lock
   de produção e ensaia inicialização, reinício, persistência e rollback com
   serviços fictícios, antes de conceder credenciais ao workflow de publicação.
2. `deploy-aws.yml` recebe o resultado do CI e só continua para um **push da
   main deste repositório com CI bem-sucedido**, quando `AWS_DEPLOY_ENABLED=true`.
   PRs, forks e execução manual do CI não publicam. A branch de preparação não
   publica ao receber commits.
3. O workflow confere se o commit testado ainda é o mais recente da `main`, faz
   checkout desse SHA e assume um papel temporário por OIDC. Não se armazena
   access key AWS ou chave SSH no GitHub.
4. Constrói backend e Caddy Linux `amd64` no runner, publica no ECR com tags
   imutáveis de commit e entrega referências por **digest** no manifesto. Um
   reprocessamento reaproveita as imagens do mesmo SHA; nunca altera uma tag.
5. Empacota apenas dois arquivos Compose, `rollout.py` e um manifesto público.
   O bundle determinístico fica no S3 privado, com gravação condicional que
   impede sobrescrever o bundle de um commit. Arquivos `.env` não participam.
6. Um segundo papel, do ambiente `aws-production`, chama somente o documento SSM
   preparado e somente a EC2 indicada. Não pode usar `AWS-RunShellScript`,
   alterar IAM, provisionar instâncias ou consultar documentos de backup.
7. O host confere checksum, tipo/tamanho/nomes dos arquivos do bundle, mounts
   persistentes, arquivos privados e espaço livre (mínimo 4 GiB). Baixa as imagens
   antes da manutenção, valida Compose e executa o preflight de banco da versão
   candidata. **Migration pendente bloqueia a publicação; não se executa Alembic
   nem reindexação automaticamente.**
8. Drena uploads/exclusões usando um utilitário isolado da aplicação, sem rede
   ou segredos. Gera backup dos originais/marcadores e o envia ao S3 criptografado.
   Se a drenagem ou o backup falharem, a versão anterior permanece e é retomada.
9. Troca os containers, verifica saúde Compose, revisão/schema/RLS/vetores no
   banco e `/health` pelo domínio com certificado TLS confiável. Só então libera
   documentos e grava a versão corrente de forma atômica no disco persistente.
10. Se a troca ou verificação falhar, drena com o utilitário da versão anterior,
    recria essa versão, confere sua saúde e retoma os documentos. Se a própria
    recuperação falhar, mantém o marcador de operação pendente para intervenção.

O GitHub serializa publicações sem cancelar a execução em andamento. Locks no
host também bloqueiam atualizações concorrentes por SSM ou pelo operador. O
GitHub pode substituir uma execução em espera por uma mais recente; não há
garantia de publicar todos os commits intermediários. O SHA é conferido outra
vez antes de enviar o comando, inclusive depois de uma espera por aprovação.

O serviço tem uma única EC2 e um worker: a troca pode causar indisponibilidade
temporária e os documentos ficam em manutenção. Este fluxo não oferece deploy
sem interrupção. A verificação automática de saúde não valida uma conversa Groq,
login ou embeddings E5 reais; esses ensaios permanecem na etapa 9.

### Arquivos e fronteiras de acesso

| Arquivo | Responsabilidade |
| --- | --- |
| `.github/workflows/deploy-aws.yml` | Encadear CI aprovado, publicação, OIDC e comando SSM |
| `deploy/aws/pipeline.yaml` | Dois repositórios ECR, bucket S3, OIDC, papéis restritos e documento SSM |
| `deploy/pipeline/package_release.py` | Empacotamento por allowlist, sem arquivos de configuração |
| `deploy/pipeline/publish_release.py` | Publicar/reaproveitar imagens e bundle imutáveis |
| `deploy/pipeline/ensure_main.py` | Recusar um CI aprovado que já ficou desatualizado |
| `deploy/pipeline/send_release.py` | Enviar comando e observar somente status, sem reproduzir logs privados |
| `deploy/pipeline/rollout.py` | Drenagem, backup, atualização, saúde e recuperação no host |
| `deploy/pipeline/validate.py` | Validações offline na imagem Docker de ferramentas |
| `deploy/pipeline/smoke_release.py` | Ensaio descartável com falha real de container e dados fictícios |

O papel `aws-build` publica somente nesses ECRs e em `releases/` do bucket. O
papel `aws-production` só envia o documento SSM à instância e consulta o resultado
do comando. A consulta `GetCommandInvocation` e a autenticação ECR exigem
`Resource: '*'`, conforme a referência de autorização AWS; as operações que
permitem restringir recursos usam os ARNs concretos do template.

O papel da EC2 ganha leitura das imagens e de `releases/`, além de escrita em
`backups/`. Ele não pode ler nem apagar backups. O aplicativo continua sem AWS
access keys; o limite de salto do IMDS permanece em um. A credencial temporária
de login ECR fica em diretório restrito temporário, removido após o comando.

Permissão para publicar o código implantado equivale a executar código como
root nesta EC2: proteja quem escreve no repositório e revisa workflows, scripts,
Compose e Dockerfiles. Papéis separados reduzem o alcance, mas não transformam
um release malicioso aprovado em código seguro.

### Pré-requisitos de ativação - ainda pendentes

- [x] Medir E5 real no Linux com limite de 1536 MiB, dois CPUs e sem swap; manter t3.small/2 GiB para MVP de baixo tráfego, com validação final em produção.
- [x] Preparar e validar o template do primeiro operador, sem credenciais embutidas ou privilégios administrativos.
- [x] Criar e conferir o usuário dedicado por CloudFormation, após aprovação explícita, com somente a política de autenticação temporária.
- [x] Proprietário configura senha e MFA; conferir pelas APIs que o perfil está ativo, possui MFA e não tem access keys ou políticas adicionais.
- [x] Autenticar o perfil local `default` como o novo usuário; confirmar identidade e MFA.
- [x] Preparar/revisar `provisioning.yaml` com permissões do projeto, roles fixas e 25 simulações de autorização.
- [x] Aprovar/aplicar `echomind-provisioning`; conferir políticas e relações de confiança, simular os 25 cenários com as identidades reais e executar o preflight com o perfil IAM local.
- [x] Rever créditos/preços/AMI/quota e executar o plano v2 com identidade IAM: 26 recursos criados, sem erros de validação.
- [x] Provisionar a infraestrutura da etapa 6 com identidade não-root, créditos/custos revisados e bootstrap pronto.
- [x] Aprovar/aplicar a correção IAM do volume raiz e limpar a tentativa revertida; preservar auditoria e repetir a criação conforme o plano de recuperação.
- [x] Aplicar `stack-policy.json` após `CREATE_COMPLETE`, antes de qualquer update; conferir o documento aplicado.
- [x] Verificar uma reinicialização real, retorno dos serviços, mounts e preservação de arquivo no disco de dados.
- [x] Proprietário confirma inscrição SNS; conferir assinatura, quatro alarmes, orçamento saudável e entrega CloudTrail.
- [ ] Conferir o primeiro snapshot DLM agendado e ensaiar a restauração real do disco.
- [ ] Revisar a autorização de leitura de `DescribeEvents` no perfil local; enquanto isso, usar AWS Core somente para consultar a validação.
- [x] Preparar a instalação automática do AWS CLI **2.38.0**, verificando a assinatura oficial antes da execução, e a checagem/atualização do SSM Agent.
- [x] Confirmar na EC2 real AWS CLI **2.38.0**, SSM Agent **3.3.4793.0**, serviços ativos e marcador de bootstrap.
- [x] Criar backup consistente do schema público real, restaurá-lo localmente e aplicar a revisão 0023; preflight real de schema/RLS/vetores aprovado via TLS.
- [x] Conferir a conexão PostgreSQL de produção pela EC2/IPv4.
- [x] Instalar `/etc/echomind/backend.env` e `/etc/echomind/deploy.env`, root `600`, diretórios/mounts privados.
- [x] Configurar `API_DOMAIN=echomind-api.duckdns.org` e e-mail ACME real no `deploy.env`; CORS exato no backend.
- [x] Apontar DuckDNS para o Elastic IP; conferir propagação, portas 80/443 e certificado público válido.
- [x] Publicar a primeira versão manual, conferir limites/volumes e preservar o certificado após recriação real do proxy.
- [ ] Incorporar a versão manual atual ao procedimento de rollback antes de ativar a primeira publicação automática. Não tratar o servidor como vazio.
- [x] Criar os ambientes GitHub `aws-build` e `aws-production`, ambos restritos exclusivamente à branch `main`, sem tags permitidas.
- [ ] Proteger a branch `main` e as alterações do pipeline.
- [ ] Verificar o `sub` OIDC real do repositório. Repositórios novos/opt-in podem incluir IDs imutáveis: informar o prefixo exato em `GitHubSubjectPrefix`, sem wildcard. Não imprimir o token.
- [ ] Inspecionar o provedor OIDC GitHub já existente na conta. Reutilizar seu ARN; criar um apenas se não existir.
- [ ] Separar a concessão `NodeReleasePolicy` do pipeline para o bootstrap de acesso, mantendo a execução da aplicação sem escrita IAM.
- [ ] Criar/revisar change set de `deploy/aws/pipeline.yaml`, sem executar até conferir identidade, custos e permissões.
- [ ] Configurar as variáveis públicas do repositório abaixo, usando outputs reais.
- [ ] Habilitar `AWS_DEPLOY_ENABLED=true` somente quando os pré-requisitos estiverem atendidos; acompanhar a primeira publicação.

O stack complementar recebe `InstanceId` do stack principal e `NodeRoleName`
da role real do instance profile da EC2. Não substitui a role nem o nó. As
trust policies exigem `aud=sts.amazonaws.com` e o `sub` exato de cada ambiente.
Como o subject de ambiente não traz a branch, a restrição dos ambientes à
`main` é obrigatória antes de conceder acesso. Revisores de produção são uma
opção adicional conforme os recursos disponíveis no plano GitHub.

| Variável GitHub do repositório | Origem |
| --- | --- |
| `AWS_DEPLOY_ENABLED` | Ausente/`false` durante preparação; `true` para ativar |
| `AWS_ACCOUNT_ID` | Conta AWS de destino |
| `AWS_BUILD_ROLE_ARN` | Output `BuildRoleArn` |
| `AWS_DEPLOY_ROLE_ARN` | Output `DeployRoleArn` |
| `AWS_BACKEND_REPOSITORY` | Output `BackendRepositoryUri` |
| `AWS_PROXY_REPOSITORY` | Output `ProxyRepositoryUri` |
| `AWS_RELEASE_BUCKET` | Output `ReleaseBucketName` |
| `AWS_DEPLOY_DOCUMENT` | Output `DeployDocumentName` |
| `AWS_INSTANCE_ID` | Output `InstanceId` do stack principal |

Essas variáveis identificam recursos; não contêm segredos da aplicação. As
credenciais Supabase/Groq/banco continuam exclusivamente no arquivo privado
do host. As tags `BACKEND_IMAGE`/`PROXY_IMAGE` do exemplo `deploy.env` são
substituídas pelo manifesto durante o pipeline. Valores com `CHANGE_ME` nos
outros campos impedem a execução. Mantenha os demais valores do exemplo,
incluindo as portas padrão e `BACKEND_ENV_FILE=/etc/echomind/backend.env`.

Em 2026-10-14, os dois ambientes AWS foram criados no GitHub e as regras
`main` foram conferidas pela interface (uma branch e zero tags permitidas).
Foi configurada a variável de repositório `AWS_DEPLOY_ENABLED=false`.
O ambiente `Production` já existente foi preservado; o workflow e a trust
policy usam o nome exclusivo `aws-production` para evitar compartilhar a
configuração usada pela integração anterior. As variáveis com outputs AWS
continuam pendentes da criação dos recursos.

O frontend continua com o fluxo Git da Vercel. Este pipeline publica o backend
e o proxy; não muda configurações Vercel/Auth. Configure a URL pública da API
na Vercel somente quando o endereço HTTPS responder, depois refaça o build.
Frontend e backend não são uma publicação atômica; mantenha compatibilidade
de API entre versões durante essa transição.

### Estado, backup, custos e recuperação

`/srv/echomind/current.json` registra a última versão saudável, seus digests,
diretório do release e configurações públicas. `previous.json` guarda a anterior.
`pending.json` registra uma troca em andamento. Esses arquivos não contêm
credenciais, ficam restritos no volume criptografado e nunca vão ao GitHub.

A primeira implantação precisa iniciar sem containers Compose `echomind`
externos a este fluxo; se já existirem, ele bloqueia para o operador registrar
ou migrar a instalação conscientemente. No primeiro deploy não há versão
anterior: uma falha para o candidato e conserva os volumes para diagnóstico.

O backup por deploy contém **originais e marcadores de documentos**, não banco,
credenciais, certificados ou cache de modelos. O backup do PostgreSQL é uma
operação separada da etapa 7. Snapshots diários do EBS continuam cobrindo o disco
durável da etapa 6. S3 expira os backups por deploy após sete dias, bundles após
90 dias e versões não correntes após sete dias. Essa janela finita exige um
plano separado caso seja necessário recuperar dados mais antigos.

Os ECRs retêm imagens com tag; apenas imagens sem tag expiram após sete dias.
Os releases locais também ficam preservados para rollback. **O armazenamento
cresce com novas versões:** revisar a limpeza de versões antigas, preservando
`current`, `previous`, qualquer operação pendente e as imagens por eles usadas.
O pipeline não executa prune, remove volumes ou apaga versões ativas. Espaço
insuficiente interrompe o deploy; backups locais grandes podem exigir mais que
os 4 GiB mínimos, e uma falha ao gerá-los também bloqueia a troca.

ECR, S3, requisições, transferências aplicáveis e minutos de Actions podem gerar
custo/consumir franquias. Não foram acrescentados CodePipeline, CodeBuild,
load balancer ou uma nova chave KMS mensal. A estimativa anterior de US$24,11
da etapa 6 **não inclui o armazenamento/uso incremental desta etapa**. Recalcular
com tamanho das imagens, documentos e frequência de deploy antes da ativação;
créditos não garantem gratuidade permanente. Bucket e ECR retidos continuam
cobrando armazenamento mesmo após excluir o stack.

Rollback restaura somente aplicação/proxy/Compose e suas configurações públicas.
Não desfaz migrations, rotaciona credenciais ou restaura documentos por cima de
dados novos. Um banco modificado de maneira incompatível impede recuperar a
versão anterior: revisar compatibilidade e realizar migrations explicitamente.

Após um reboot, timeout, cancelamento manual ou perda do runner, não suponha
que o comando remoto parou. O workflow observa até cerca de 52 minutos e o
documento limita execução a 50 minutos. Confira o comando no SSM e o estado
do host antes de repetir. `pending.json` bloqueia novas transações quando há
uma interrupção não reconciliada. Não remova esse arquivo para forçar um deploy.

O operador pode recuperar a versão anterior com `rollout.py --recover-previous`
por uma sessão SSM administrativa, usando código revisado e as variáveis públicas
`RELEASE_BUCKET`, `BACKEND_REPOSITORY` e `PROXY_REPOSITORY` dos outputs. O utilitário
adquire o lock, confere o manifesto salvo, drena, recria, verifica e retoma a
versão anterior antes de retirar o marcador. Se for a primeira implantação,
sem anterior, exige diagnóstico/parada manual do candidato; nunca inventa uma
versão de recuperação. Depois de um deploy saudável, um rollback deliberado
pode usar `--release` com o diretório preservado da versão desejada, sujeito ao
mesmo preflight e backup. Nenhum desses comandos faz downgrade do banco.

### Evidências locais da etapa 8

```sh
docker build --tag echomind-infra-validation:local --file deploy/aws/validation.Dockerfile deploy/aws
python deploy/pipeline/validate.py
python deploy/pipeline/smoke_release.py --image echomind-backend:deploy-step7
```

O contexto de build do validador exclui parâmetros privados. A execução offline
monta somente arquivos públicos, sem rede. Ferramentas: cfn-lint 1.57.2,
cfn-guard 3.2.1 e actionlint 1.7.12; binários baixados com SHA-256 fixado.

| Verificação | Resultado |
| --- | --- |
| actionlint nos dois workflows | Aprovado |
| cfn-lint nos dois templates, região us-east-1 | Zero erros/avisos |
| Guard para o bucket do pipeline | Aprovado |
| Testes de segurança/ordenação/falhas/recuperação | 20 testes aprovados |
| Ensaio Docker real com API sintética | Candidato falhou; anterior recriada e saudável; manutenção liberada |
| Originais e backup no ensaio | Conteúdo preservado e conferido após rollback |
| Validador da imagem de produção usado no CI | Inicialização, limites, reinício, cache, recuperação de documento e manutenção aprovados |
| Limpeza do ensaio | Apenas projeto descartável removido; volumes reais não utilizados |
| OIDC, ECR, S3 de releases e documento SSM do pipeline | Ainda não criados/ativados/executados; a infraestrutura base e o agente SSM da EC2 já foram verificados |
| HTTPS/banco real, chat, E5 e medição de recursos | HTTPS/banco, chat, E5 e documentos aprovados na EC2; capacidade sob carga ainda pendente |

## Medição prévia da capacidade - 2026-10-14

Executado `deploy/measure_resources.py` na imagem Linux de produção já construída
`echomind-backend:deploy-step7`, limitada a **1536 MiB**, **dois CPUs**, sem swap.
O teste usa o singleton e o adapter E5 do aplicativo, importação completa da API,
extração/divisão de um TXT de 10 MiB e sobreposição de 40 embeddings de chunks
com 20 embeddings de perguntas. A indexação atual envia um chunk por chamada.
Reranker permaneceu desligado. Não acessa banco, Groq ou autenticação reais.

| Ensaio | Pico RSS do processo | Pico cgroup, incluindo cache de arquivos | OOM |
| --- | --- | --- | --- |
| Modelo já no cache | 1004,21 MiB | 983,35 MiB | Nenhum |
| Primeiro download/carregamento | 1036,06 MiB | 1462,68 MiB | Nenhum |

RSS e cgroup usam critérios diferentes, inclusive compartilhamento/contabilização
do cache, por isso não devem ser somados nem tratados como números equivalentes.
Durante o ensaio frio, o processo terminou em aproximadamente 1008 MiB RSS;
parte importante do cgroup era cache do download. Uma tentativa preliminar de
carga atingiu o teto de 1536 MiB, com recuperação de páginas e sem OOM; o ensaio
completo acima foi repetido com cache novo e terminou sem eventos de limite.

**Decisão:** não usar uma máquina de 1 GiB. Manter `t3.small`/2 GiB e o limite
de 1536 MiB do backend como configuração inicial do MVP, um worker, uma ingestão
por vez e reranker desligado. Preservar memória para Caddy e sistema operacional.
Esses limites são tetos, não reservas; o consumo real e os créditos de CPU ainda
precisam ser acompanhados na EC2. Não é aprovação para tráfego arbitrário.

Relatórios públicos, sem documentos/credenciais reais: `docs/e5-memory-linux.json`
e `docs/e5-memory-linux-cold.json`. Modelo ONNX: 470268510 bytes, SHA-256
`ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665`.

Limitações: não foi uma conversa HTTP completa nem persistência PGVector real;
somente 40 dos 14625 chunks produzidos foram codificados. O teste não cobre PDFs
ou DOCXs extremos, muitas conversas concorrentes ou o desempenho da CPU T3 após
esgotar créditos. Os tempos no Docker local não são previsão de latência AWS.
O cache público de medição ficou em volume Docker próprio para repetições; o
cache usado no ensaio frio e os containers descartáveis foram removidos.

```sh
python deploy/measure_resources.py --output docs/e5-memory-linux.json
python deploy/measure_resources.py --cold --output docs/e5-memory-linux-cold.json
```

## Banco real preparado - 2026-10-14

Backup consistente do **schema público** criado com `pg_dump` PostgreSQL 17 e
snapshot exportado de uma transação somente de leitura. A conexão ao endpoint
direto manteve TLS de ponta a ponta por um relay TCP vinculado exclusivamente
ao loopback do Windows, para permitir ao cliente Docker alcançar o endereço IPv6.
Não foi aberta uma porta de banco na rede pública/local.

O dump foi restaurado em PostgreSQL/pgvector Docker descartável: contagens das
20 tabelas iguais às do snapshot, revisão `0022` preservada e RLS conferido.
O dump, manifesto com hash/contagens e logs privados ficam em `.database-backups/`,
ignorada pelo Git e com ACL Windows restrita ao proprietário. O banco de ensaio
e seu armazenamento temporário foram removidos.

Após o ensaio, a revisão `0023` foi aplicada ao Supabase real. O aplicador exige
backup intacto/restaurado com menos de duas horas, revisão esperada e tabela
legada vazia. A trava exclusiva, a nova conferência de ausência de registros e
a execução do Alembic compartilham a mesma transação; não há intervalo aberto
entre conferir e remover a tabela. `alembic/env.py` agora aceita uma conexão
fornecida pelo chamador, mantendo o fluxo CLI anterior.

Validação local adicional provocou rollback após executar a migration: a
revisão `0022` e o registro sentinela sintético reapareceram, comprovando que
o Alembic respeita a transação externa. No banco real, a tabela antiga estava
vazia sob a trava; após commit, o preflight informou **`ready=true`, revisão
`0023`, nenhuma migration pendente**, com schema, RLS e vetores compatíveis.

Ferramentas adicionadas: `deploy/backup_production_database.py` e
`deploy/apply_prepared_database.py`. Recebem credenciais apenas da configuração
local existente dentro do processo e não as imprimem. Nenhum dump ou dado real
foi incluído no commit. Este backup não cobre Auth, Storage, papéis ou configurações
do projeto Supabase, nem substitui uma cópia externa criptografada periódica.
A conexão session pooler IPv4 pela EC2 foi aprovada na primeira publicação de 2026-10-19.

## Primeira publicação da API - 2026-10-19

API publicada em **https://echomind-api.duckdns.org**, com health público
**https://echomind-api.duckdns.org/health**. O Supabase estava pausado e foi
retomado; confirmou `ACTIVE_HEALTHY`. O painel Connect forneceu o session pooler
real `aws-1-sa-east-1.pooler.supabase.com:5432`. A EC2 conectou por IPv4 e TLS 1.3;
o preflight da imagem informou revisão `0023`, nenhuma migration pendente,
schema/RLS/vetores compatíveis e `ready=true`. Nenhuma migration ou reindexação
foi executada nesta publicação.

A instalação usou o usuário IAM dedicado pelo AWS MCP oficial. Não houve
alteração IAM nem criação de recursos AWS adicionais. As imagens foram montadas
na EC2 a partir de 66 arquivos públicos allowlisted do commit
`ed86db754495d3b1c7b13b1b0ea40d9e7fec5060`, transferidos pelo SSM e conferidos por
SHA256. O pacote não contém `.env`, Git, backups ou documentos. A primeira
tentativa revelou CRLF no arquivo Shell e permissões restritivas nos arquivos
públicos copiados para a imagem. Corrigimos `.gitattributes`, conferimos LF e
normalizamos os arquivos públicos para `644`/diretórios `755`, sob a pasta da
release root `700`. Os próximos pacotes preservam essas permissões de leitura
para o UID 10001. Isso não altera o conteúdo do código implantado.

As credenciais locais existentes foram processadas em memória e criptografadas
para um certificado temporário RSA gerado na EC2. Apenas ciphertext passou nos
comandos SSM. O host conferiu o digest, decriptou em memória e instalou o runtime
validado de forma atômica. A chave privada temporária e o envelope foram
removidos; os arquivos de configuração persistentes permanecem root `600` em
`/etc/echomind`, no disco de dados criptografado. Nenhum valor secreto entrou
em exemplos, relatórios ou commits. Ferramentas e limitações desse primeiro
procedimento estão em `deploy/manual/README.md`.

Backend e Caddy estão saudáveis, com UID 10001, filesystem raiz somente leitura,
política `unless-stopped`, limites de 1536/128 MiB e volumes persistentes. A porta
8000 não é publicada no host. O aquecimento real de embeddings terminou sem
erro em aproximadamente 10,9 segundos. Uma amostra após iniciar mediu backend
944 MiB e proxy 56,36 MiB, sem OOM ou reinícios. É uma amostra de inicialização,
não um teste de capacidade, concorrência ou ingestão de documentos.

O DuckDNS confirmou o IP reservado da EC2 e o DNS público foi conferido.
Certificado Let's Encrypt válido, hostname/cadeia verificados sem desabilitar
TLS, expiração em 2027-01-17; renovação automática configurada pelo Caddy.
HTTP redireciona para HTTPS com `308`, health responde `200`, HSTS está ativo,
CORS permite a origem exata da Vercel e recusa uma origem externa. `/auth/me`
sem credenciais responde `403`, comportamento do HTTPBearer da versão FastAPI
fixada. A recriação real apenas do proxy preservou o número de série do
certificado e a API saudável; o backend permaneceu no mesmo container.

No Supabase, a Site URL agora é `https://echomind-front.vercel.app`. Retornos
autorizados: `/redefinir-senha` nessa origem e os endereços locais explícitos
`http://localhost:3000` e `http://localhost:3000/redefinir-senha`. Na Vercel,
**Production** recebeu `NEXT_PUBLIC_API_URL=https://echomind-api.duckdns.org`
e `ECHOMIND_REQUIRE_API_URL=true`. Essas variáveis só entram no frontend após
um novo build; **nenhum novo deployment do frontend foi executado nesta etapa**.

Relatório público: `docs/first-publication-verification.json`. O host guarda
`/srv/echomind/manual-current.json` com revisão e IDs reais das imagens, sem
credenciais. As configurações locais, envelopes e provas de tela ficam em
`.publication/`, ignorada pelo Git. A automação `AWS_DEPLOY_ENABLED` continua
desativada. O build Vercel e a validação funcional foram concluídos na seção
seguinte. O relatório acima preserva o estado histórico da primeira publicação.

## Publicação do frontend e validação funcional - 2026-10-19

O frontend está publicado em **https://echomind-front.vercel.app** e integrado à
API HTTPS da EC2. O domínio retornava `404 NOT_FOUND`; o projeto existente foi
configurado como Next.js, raiz `echomind-front`, Node 22, instalação com lock
congelado e build via pnpm. Os valores públicos aplicados estão registrados em
`deploy/frontend/vercel-project-settings.json`; esse arquivo documenta os
campos da configuração do projeto na Vercel, não é um `vercel.json` autoaplicado.
As proteções dos deployments de preview foram preservadas.

O deployment de produção `dpl_ARhU4VRHjc2cqNWMcW7pGGzgC59F` chegou a `READY`
e recebeu o domínio verificado. Foram enviados 141 arquivos versionados do
frontend no commit `7172218bca4957b1b8bc39b287837d93484dc690`, sem `.env`, Git,
dependências locais ou artefatos privados. Antes da publicação, typecheck e lint
passaram; a suíte do frontend aprovou **232 testes em 25 arquivos**. Não houve
push, merge ou ativação da automação AWS.

| Ensaio real | Resultado |
| --- | --- |
| Login feito pelo responsável | Painel autenticado carregou dados reais pela API e pelo Supabase |
| Portal público | Instituição e FAQs carregaram; chat respondeu à FAQ selecionada |
| Upload sintético `deploy-check.txt` | 214 bytes, status pronto e um chunk |
| Chat autenticado com documento | Respondeu o identificador sintético correto, citando o arquivo |
| Recriação autorizada do backend | Mesma imagem, drenagem, recriação e retomada; chat com documento aprovado novamente |
| Persistência após recriação | Dois originais presentes e íntegros antes da limpeza |
| Limpeza autorizada | Somente o documento sintético excluído; um documento real e seu original íntegro preservados |
| Estado final | Backend/proxy saudáveis, zero reinícios automáticos/OOM, fila vazia e uploads liberados |
| HTTPS público | Health 200, redirecionamento 308, TLS/cadeia/hostname válidos, HSTS e CORS exato aprovados |

O registro de um documento anterior já tinha 20 chunks no banco, mas seu original
não estava no volume da EC2. O responsável indicou o arquivo local; tamanho de
12.837 bytes e SHA-256 coincidiram com o registro existente. O original foi
transferido como CMS criptografado, validado e instalado atomicamente sem
sobrescrever arquivos, mudar o banco ou reindexar. Sobreviveu à recriação. A chave
temporária foi removida e nenhum conteúdo do documento entrou no Git ou nos
relatórios públicos. Esse reparo de um original não equivale a restaurar backup
completo do disco.

O utilitário `deploy/manual/restore_document_original.py` implementa essa operação
com ensaio por padrão e `--apply` explícito. `check_document_originals.py` confere
hashes e tamanhos dentro do backend e emite somente contagens;
`check_application_host.py` emite estado dos containers, memória cgroup e campos
operacionais permitidos, sem ambientes ou logs brutos. Consulte o README manual
antes de reutilizar essas ferramentas.

Após a recriação e a nova consulta, o backend registrou **1.003.491.328 bytes
atuais (957 MiB)** e **1.129.517.056 bytes de pico (1.077 MiB, cerca de 1,05 GiB)**,
sob limite de 1.536 MiB. O proxy atingiu pico de cerca de 20 MiB. Não houve eventos
OOM nem de alcance do limite. É um ensaio funcional pequeno; não determina a
capacidade para documentos de 10 MiB, concorrência ou créditos de CPU.

O navegador não registrou erros de console no intervalo observado. A leitura dos
logs de build pelo conector Vercel retornou `403`, portanto não foi possível
auditar esses logs; o estado `READY`, os testes locais e os fluxos reais foram
verificados separadamente. O AWS MCP apresentou erro interno na execução de API;
as verificações SSM desta etapa usaram o AWS CLI com o perfil dedicado existente,
conforme o fallback permitido em `AGENTS.md`.

Relatório sanitizado: `docs/frontend-publication-verification.json`. Capturas e
envelopes locais ficam em `.publication/`, ignorada pelo Git.

- [x] Publicar frontend e conferir integração de produção.
- [x] Testar login, FAQ pública, upload e resposta baseada no documento.
- [x] Recriar backend com autorização e comprovar persistência dos originais.
- [x] Remover somente o arquivo sintético e conferir integridade final.
- [x] Testar cadastro e recuperação por e-mail com participação do responsável.
- [x] Medir memória/CPU/disco na EC2 com ingestões de 64/256 KiB, lotes curtos
  de 1/2/4 consultas e métricas de créditos de CPU.
- [ ] Validar carga sustentada, ingestão completa de 10 MiB e créditos esgotados.
- [ ] Conferir primeiro snapshot agendado e ensaiar restauração do EBS.
- [ ] Concluir revisão de vulnerabilidades e observabilidade da etapa 9.
- [ ] Concluir permissões/OIDC, proteção da branch, adoção da release manual e
  ensaio real de deploy/rollback antes de habilitar `AWS_DEPLOY_ENABLED`.

## Cadastro e recuperação de senha em produção - 2026-10-19

O responsável criou uma conta própria de teste no formulário de produção,
definindo pessoalmente a senha. O retorno para o login foi observado e o banco
confirmou a existência da conta criada nesta data. Uma única solicitação de
recuperação foi enviada pelo formulário à caixa indicada pelo responsável.
O site exibiu sucesso; os logs agregados do Supabase mostraram um pedido
`/recover` aceito com `200`, um evento de e-mail de recuperação e nenhum erro
no intervalo examinado. O responsável confirmou recebimento do link, redefinição
e entrada com a nova senha. Senhas, links, sessões e endereços da conta de teste
não foram incluídos no Git ou neste relatório.

A Site URL e o retorno de recuperação correspondem à origem de produção já
documentada. Cadastro por e-mail está habilitado, confirmação inicial de e-mail
está desabilitada e SMTP próprio não está configurado. Nenhuma dessas opções
foi alterada nesta etapa. A marcação de e-mail confirmado no banco, nesse modo,
é automática e não comprova recebimento de confirmação de cadastro; o ensaio
de recebimento realizado foi o de recuperação. A documentação atual restringe
o SMTP padrão a testes com endereços autorizados e limita o volume; o sucesso
observado com esta caixa não comprova entrega geral para futuros usuários.
Antes de ampliar o uso público, preparar SMTP próprio e validar confirmação,
limites e entregabilidade. Não conceder acesso administrativo ao projeto apenas
para permitir que uma pessoa receba mensagens de autenticação.

Foi corrigida uma orientação incompatível com a configuração real: o cadastro
sempre pedia confirmação de e-mail, mesmo quando o Supabase já retornava uma
sessão e liberava o acesso. `authApi.register` agora informa se há confirmação
pendente com base na resposta do provedor; o formulário mostra a orientação
correspondente e mantém o destino de login. A correção não muda as regras de
confirmação, credenciais ou permissões do Supabase. Testes cobrem os dois modos
e erro do provedor: **236 testes em 26 arquivos**, typecheck e lint aprovados.

Código da correção: commit `df559e6663feae1b53ea7e110cd8b5d5e9ace11f`.
**Publicação dessa correção ainda pendente:** o conector Vercel retornou `403`
ao consultar o deployment existente sob o escopo da equipe correta. O CLI local
não está disponível. Não houve nova tentativa de deploy, mudança de escopo,
push ou merge. Os testes reais de cadastro/recuperação acima usam a versão já
publicada anteriormente; a nova orientação foi verificada localmente.

Relatório: `docs/auth-publication-verification.json`. A conta de teste permanece
existente, sem exclusão solicitada. O ensaio de capacidade está registrado na
seção seguinte; snapshot/restauração, observabilidade e ativação da automação
continuam pendentes. `AWS_DEPLOY_ENABLED` segue desativado.

- [x] Conferir configurações reais de cadastro e retorno de recuperação.
- [x] Cadastrar conta de teste com senha definida pelo responsável.
- [x] Solicitar recuperação uma vez e conferir resposta e eventos agregados.
- [x] Confirmar recebimento, redefinição e login com participação do responsável.
- [x] Corrigir orientação de cadastro e validar os dois modos localmente.
- [ ] Publicar a correção de orientação quando o acesso à Vercel estiver disponível.
- [ ] Configurar SMTP próprio e validar confirmação antes de ampliar o uso público.

## Medição controlada na EC2 - 2026-10-19

**Decisão de dimensionamento inicial:** manter `t3.small`, dois vCPUs e 2 GiB,
um worker e uma ingestão por vez. Backend com teto de 1.536 MiB/dois CPUs,
Caddy com 128 MiB/0,5 CPU, cache persistente do E5 e reranker desligado.
Uma instância de 1 GiB não oferece margem para esse backend mais o sistema
operacional e o proxy. Os resultados abaixo não estabelecem um limite geral de
usuários, requisições por segundo ou desempenho após esgotar créditos de CPU.

O AWS MCP oficial confirmou a instância em execução e modo de créditos de CPU
`standard`. A observação do host cobriu cerca de **11min32s**, com **336 amostras**
a cada dois segundos mais o tempo de coleta. O observador lê os cgroups dos
containers existentes e os contadores do host; não carrega outro modelo nem
outro backend na máquina. Não houve mudança de instância, IAM, limites, imagem
ou configuração de produção, nem criação de recursos AWS nesta etapa.

| Métrica observada | Resultado |
| --- | --- |
| Pico de memória do backend nas amostras do ensaio | 984,21 MiB |
| Pico histórico do cgroup, antes e depois | 1.077,19 MiB; não aumentou neste ensaio |
| Pico amostrado do Caddy | 34,55 MiB |
| Menor memória disponível no host | 405,91 MiB |
| Swap utilizado | Zero |
| CPU média do backend na janela inteira, incluindo intervalos ociosos | 5,04% dos dois vCPUs |
| Maior CPU ocupada do host em uma amostra curta | 62% |
| Espaço livre mínimo no disco raiz/dados | 11,45 / 16,05 GiB |
| OOM, eventos de teto de memória, reinícios ou amostras de containers não saudáveis | Zero |

O contador de pico do cgroup inclui toda a vida do container; não foi zerado.
Por isso o pico histórico de 1.077 MiB, anterior ao ensaio, não foi atribuído à
carga nova. A amostragem pode perder picos muito curtos; o contador histórico
permaneceu igual. RSS, memória disponível do host e memória cgroup têm critérios
diferentes e não devem ser somados como se fossem a mesma medida.

Dois TXT sintéticos foram enviados pela interface autenticada da conta de teste,
separada da instituição real. Todos os trechos foram indexados no Supabase real,
usando o E5 existente na EC2. Os arquivos não contêm dados pessoais ou reais.

| Arquivo | Tamanho | Trechos / vetores documentais | Aceite até estado pronto |
| --- | --- | --- | --- |
| `capacity-64k.txt` | 65.536 bytes | 104 / 104 | 92,600 s |
| `capacity-256k.txt` | 262.144 bytes | 335 / 335 | 281,578 s |

A segunda carga foi limitada a 256 KiB após medir a indexação sequencial do
primeiro arquivo. O ensaio não executou ingestão de 1 MiB ou 10 MiB em produção,
nem PDF/DOCX. O teste local anterior de 10 MiB apenas dividia o arquivo inteiro
e codificava 40 trechos; continua sem equivaler a indexar o upload máximo.
O processamento faz inserções de vetores trecho a trecho. CPU e memória com
folga, combinadas com esse caminho e o tempo total medido, apontam as operações
sequenciais de banco como prioridade de investigação/otimização; não foi feita
uma medição isolada para atribuir todo o tempo à rede entre regiões.

As consultas passaram pelo HTTPS público da conta sintética, com banco,
retrieval e Groq reais. Não houve cópia de sessões ou tokens do navegador.
Tempos incluem a conexão/TLS do cliente e os serviços externos.

| Lote | Contexto | Respostas corretas | Tempo médio / máximo |
| --- | --- | --- | --- |
| Uma consulta, pergunta de controle | Primeiro arquivo pronto | 1/1 | 4,724 / 4,724 s |
| Duas consultas, duas formulações | Segundo arquivo em processamento | 2/2 | 6,393 / 6,651 s |
| Quatro consultas, quatro formulações | Segundo arquivo em processamento | 2/4 | 9,408 / 9,656 s |
| Quatro consultas, mesma pergunta de controle | Segundo arquivo em processamento | 4/4 | 10,294 / 11,037 s |
| Mesmas quatro formulações do lote misto | Ambos os arquivos prontos | 4/4 | 11,034 / 11,828 s |

Todas as solicitações responderam HTTP `200`, inclusive as respostas sem a
informação pedida. O verificador exige também o identificador sintético correto;
HTTP 200 isoladamente não aprova o teste. Uma primeira resposta correta usou
hífen tipográfico, levando à correção do verificador e inclusão de regressão
para essa formatação. Foram enviados 17 pedidos no total, incluindo esse
diagnóstico e uma reprodução isolada da pergunta que falhou.
Os lotes são pequenos e não sustentados; não calcular P95/P99 nem extrapolar
capacidade contínua a partir deles. O lote de duas formulações não é uma
comparação estrita com o lote de pergunta única.

**Problema de retrieval encontrado:** uma das perguntas sem informação também
falhou com apenas uma solicitação durante a ingestão. Eventos operacionais
mostraram dez candidatos vetoriais e zero candidatos elegíveis/resultados.
Depois de concluir a ingestão, as mesmas quatro formulações passaram. O código
busca os primeiros candidatos vetoriais e valida o estado do documento depois;
os resultados são compatíveis com trechos ainda em processamento ocupando o
top-k e ocultando fontes prontas. Corrigir a elegibilidade antes do corte de
candidatos e adicionar regressão de documento pronto + documento em processamento
é prioridade antes de ampliar o uso público. Nenhuma correção da aplicação ou
troca de imagem foi feita nesta etapa de medição.

O CloudWatch forneceu amostras de cinco minutos entre 19:40 e 19:55 UTC,
consultadas às 20:00 UTC. CPU média máxima nesses intervalos: **11,80%**;
saldo mínimo/último de **83,47 / 88,17 créditos de CPU**, com zero saldo excedente
e zero créditos excedentes cobrados nas amostras disponíveis. Essas métricas
têm atraso e não são a mesma janela/granularidade dos contadores locais.
Não foi provocado esgotamento de créditos; desempenho em throttling continua
sem ensaio. Os valores são créditos de CPU, não o saldo financeiro da conta.

Após autorização específica, somente os dois arquivos sintéticos foram
excluídos: dois documentos, 439 trechos e 439 vetores, além dos originais.
A sessão do navegador terminou durante a coleta; a limpeza usou SSM com o
operador existente. Antes de remover, um ensaio confirmou nomes, tamanhos e
SHA-256, arquivos íntegros e runtime ocioso. A operação adquiriu as travas de
admissão/processamento e das linhas do banco, removeu vetores e documentos na
mesma transação e usou marcadores duráveis para concluir os originais.
Não foi carregada outra instância do modelo. O verificador final encontrou um
documento real, 20 trechos e seu original íntegro, nenhum arquivo sintético ou
vetor remanescente, fila vazia e uploads liberados. Interações/métricas sintéticas
continuam na conta de teste. API/proxy saudáveis; HTTPS/health/CORS aprovados.

Ferramentas: `deploy/manual/observe_capacity.py`, `deploy/measure_public_chat.py`
e `deploy/test_capacity_tools.py`. O leitor de eventos do host passou a exportar
somente contagens operacionais reconhecidas, incluindo os nomes reais de eventos
de ingestão/chat. Cinco testes dos medidores passaram, junto da verificação de
sintaxe. Relatório sanitizado: `docs/capacity-aws-production.json`; arquivos e
artefatos privados permanecem em `.publication/`, ignorada pelo Git.

- [x] Medir host/containers e conferir limites na EC2 existente.
- [x] Indexar integralmente os dois arquivos sintéticos e medir conclusão.
- [x] Testar consultas simultâneas e verificar conteúdo, além do HTTP.
- [x] Conferir créditos de CPU e saúde pública após os ensaios.
- [x] Limpar somente os arquivos autorizados e verificar o original real.
- [x] Corrigir e testar localmente retrieval enquanto outro documento está em processamento.
- [x] Publicar a correção de retrieval na AWS e repetir a verificação funcional em produção.
- [x] Otimizar e medir localmente gravação vetorial por lotes antes de uploads grandes.
- [ ] Publicar a indexação em lotes e medir a ingestão completa na EC2 existente.
- [ ] Validar carga sustentada, upload máximo completo, PDFs/DOCXs e créditos esgotados.
- [ ] Ensaiar snapshot/restauração e concluir os demais itens da etapa 9.

### Correção de elegibilidade antes do top-k - 19/10/2026

A regressão foi reproduzida em PostgreSQL 17/pgvector 0.8.6 descartável:
um documento pronto deixou de aparecer quando 50 vetores mais próximos pertenciam
a um documento indisponível. As três variações (`pending`, `processing` e `error`)
falharam no código anterior, mesmo com a busca lexical desativada para isolar
o caminho vetorial.

O adaptador `app/retrieval_store.py` mantém o armazenamento PGVector existente e
aplica a elegibilidade relacional na consulta SQL, antes da ordenação e do limite.
Um `EXISTS` confirma documento e trecho do mesmo tenant, estado `ready` e validade
vigente no calendário informado pelo RAG. Fontes parent também exigem o vínculo
com o filho correspondente. A consulta restringe coleção e tenant dos metadados;
eventos legados são excluídos antes do corte. FAQs continuam no mesmo fluxo.
A validação posterior permanece para rejeitar fontes removidas ou alteradas
enquanto a consulta estava em andamento.

O teste verifica também que os mesmos vetores passam a participar da busca ao
mudar o documento para `ready`, sem reindexação. Os embeddings são determinísticos
e locais, e o limiar do teste é ampliado para isolar a seleção de candidatos;
isso não representa nova medição de qualidade do E5/Groq ou de carga sustentada.
Os limites de candidatos, workers e memória da aplicação foram preservados.
Não há alteração de schema, migração ou reindexação dos documentos existentes.

A correção utiliza o binding e os modelos ORM da versão fixada
`langchain-community==0.2.19`; uma atualização dessa dependência deve repetir os
testes reais de integração do adaptador. A inclusão futura de índices vetoriais
aproximados exige validar novamente o efeito de filtros e a recuperação de
candidatos, incluindo a configuração de varredura iterativa do pgvector.

Esta etapa preparou e validou a correção localmente. A publicação posterior está
registrada abaixo; os resultados anteriores de capacidade continuam históricos.

Validação local: **582 testes rápidos aprovados** e **90 testes de integração
aprovados**, incluindo as três regressões novas. Três testes de permissões do
host Linux foram ignorados pela própria suíte no Windows. O gate global atingiu
**89,98% de cobertura**, acima dos 72% exigidos; os quatro módulos documentais
também passaram no gate individual de 80%. O PostgreSQL usado nos ensaios foi
local e descartável, com embeddings sintéticos, sem acesso ao banco de produção.
A imagem `echomind-backend:retrieval-fix-20261019` foi construída localmente com
as dependências travadas do deploy. O smoke Linux em containers descartáveis
passou em inicialização saudável, limites e isolamento, persistência do cache e
dos originais após recriação, recuperação de ingestão interrompida, reinício
automático após falha, pausa/retomada de escritas e encerramento limpo.
Os recursos descartáveis foram removidos ao final.

### Correção publicada na EC2 - 19/10/2026

A revisão `a76179b29568b2660fb72269442db3e9e651f4e5` está ativa no backend,
incluindo a correção da aplicação do commit `35cfb2c`. A publicação usou o usuário
IAM dedicado e SSM na EC2 existente. Foram transferidos 69 arquivos públicos
commitados, em pacote de 211487 bytes, conferido por SHA-256 antes da extração.
A imagem construída na própria EC2 é
`sha256:6bbb84b3c5423b891de1edd3eb3a6513add66fb3179027cdc5a9e7279be357c9`.
Somente `rag_engine.py` e o novo `retrieval_store.py` mudaram entre os arquivos
de aplicação anteriormente publicados e esta versão.

O atualizador `deploy/manual/update_release.py` reutiliza a transação já testada
do pipeline, preservando a publicação manual. Ele exige os mesmos arquivos
Compose/proxy, trava o deploy, confere o banco, pausa escritas documentais e
produz uma cópia privada dos documentos no EBS de dados criptografado antes da
troca. Somente o backend foi recriado; o mesmo container do proxy continuou em
execução, com seus certificados e volumes. O estado anterior, sua imagem e sua
pasta de código foram retidos para recuperação. A configuração pública de imagem
e o manifesto manual foram atualizados após o sucesso. O arquivo de segredos
existente foi entregue diretamente ao Docker, sem leitura de seus valores.
Não houve migrations, reindexação, alteração IAM, novos recursos AWS ou ativação
do CI/CD. Nenhum volume foi removido.

Cinco testes do atualizador passaram em Windows e Linux; os 20 testes compartilhados
de transação, recuperação e segurança passaram no Linux descartável. Uma tentativa
no Windows encontrou ausência de Bash funcional, resolvida pela execução Linux.
Não foi provocada uma falha deliberada na produção. Erros/timeout de deploy mantêm
estado pendente para reconciliação; a cópia local no EBS auxilia recuperação,
mas não substitui o ensaio de restauração e um backup externo.

| Verificação após a publicação | Resultado |
| --- | --- |
| Backend e proxy | Saudáveis, zero reinícios e zero OOM |
| Aquecimento do modelo existente em cache | Sucesso, cerca de 5,44 s |
| Consulta real pelo novo adaptador | Dez candidatos elegíveis; fonte pronta conhecida encontrada |
| Consulta de outro tenant na mesma coleção | Zero resultados |
| Segurança da consulta de verificação | Transação somente leitura, sem carregar outro modelo |
| Original persistente | Um documento pronto e um original válido; zero ausentes/inválidos |
| Fila e manutenção | Fila vazia, escritas liberadas, nenhum deploy pendente |
| HTTPS/health | HTTP 200, cadeia/hostname válidos, TLS 1.3, HSTS e redirecionamento 308 |
| CORS e autenticação | Origem Vercel aceita, origem não autorizada recusada, anônimo recebe 403 |
| Chat público da conta sintética | HTTP 200 e nome institucional esperado; aproximadamente 10,63 s incluindo leitura da ficha |

O chat público usa a ficha institucional da conta sintética, que ficou sem
documentos após a limpeza autorizada anterior. A busca do documento real foi
conferida separadamente por consulta somente leitura, reutilizando um vetor
persistido para testar o SQL exato do novo adaptador. O cenário com 50 vetores
indisponíveis foi validado no PostgreSQL local descartável; nenhum novo documento
foi carregado em produção nesta publicação. Essas verificações não representam
novo ensaio de ingestão concorrente nem capacidade sustentada.

Evidências sanitizadas: `docs/retrieval-release-verification.json`.
Na publicação acima, o próximo item funcional era otimizar a gravação por lotes.
A preparação local dessa otimização está registrada abaixo. Os ensaios de carga
sustentada e restauração continuam na checklist. A branch permanece
`codex/deploy-config`, sem push/merge nem ativação automática de deploy.

### Indexação documental em lotes - preparação local

`RAGEngine.reindex_document_chunks` passa a gravar até **32 vetores por transação**
do PGVector, em vez de uma gravação por trecho. Os embeddings continuam sendo
gerados **um trecho por chamada**, com o mesmo singleton E5, cabeçalho, prefixo
`passage:`, dimensão 384, metadados normalizados e UUIDs determinísticos.
Só o lote atual de vetores fica em memória. Não foi ampliado o lote de inferência
ONNX, o número de workers, a concorrência de ingestões ou o teto de memória.

A reindexação administrativa agrupa os trechos por documento e usa o mesmo
caminho em lotes. FAQs e indexação individual mantêm seu comportamento. A geração
com quantidade/dimensão incorreta falha antes da gravação do lote. Erros de
embedding ou banco são propagados ao processamento existente para compensação;
não é marcado `ready` após uma indexação parcial. A limpeza continua restrita aos
IDs do documento e à coleção do tenant, e os IDs necessários à recuperação ficam
persistidos antes de iniciar a indexação. A busca continua recusando documentos
`pending`, `processing` e `error`, inclusive quando já há um lote gravado.

Os testes reais de PostgreSQL conferem 65 vetores em três lotes, metadados,
conteúdo, embeddings, remoção de órfãos, idempotência e preservação de outro
tenant. Outros ensaios provocam falha no segundo lote antes e depois do commit,
além de interrupção abrupta após o primeiro lote confirmado; a compensação e a
retomada mantêm exatamente os IDs dos trechos atuais, sem duplicações ou órfãos.

O gate passou com **587 testes rápidos e 94 de integração**, cobertura global de
**90,03%** e os quatro módulos documentais acima dos 80% exigidos. Três testes de
permissão Linux foram ignorados no Windows. Os testes de métricas passaram a usar
a mesma data UTC da persistência, corrigindo uma falha de relógio na virada do dia,
sem alterar o comportamento de métricas da aplicação.

O medidor `scripts/benchmark_vector_batches.py` recusa bancos remotos e exige o
nome do banco descartável de integração. Ele compara o laço antigo de indexação
com o novo método, usando o mesmo documento sintético e encoder, alternando a
ordem entre repetições. Contabiliza SQL e commits e confere a quantidade gravada.
O cenário com atraso adiciona explicitamente uma espera por comando SQL; ele não
mede latência entre AWS e Supabase nem permite prever o tempo de upload real.

Para **335 vetores**, as inserções caíram de **335 para 11**, os commits de
**336 para 12** e os comandos SQL observados de **672 para 24**. No PostgreSQL
local com embeddings sintéticos, três repetições deram mediana de **1,8334 s para
0,2098 s (8,74 vezes)**. Com 25 ms adicionais simulados por comando SQL, as
medianas foram **20,6361 s e 0,8640 s (23,88 vezes)**. Esses valores isolam o
caminho de gravação; não representam aceleração equivalente do upload completo.

No Linux com **E5 real já em cache**, dois CPUs, limite de 1536 MiB e sem swap,
uma comparação completa de 335 embeddings/gravações por método levou **25,6226 s
no caminho antigo e 22,0773 s em lotes**, ganho de **1,16 vez** neste ambiente de
baixa latência. Os 335 vetores foram conferidos em ambos os caminhos. O pico
cgroup do ensaio conjunto foi **1375,22 MiB**, sem eventos de limite, OOM ou
encerramento anormal. Esse pico cobre os dois métodos e não identifica um pico
isolado por método. O benchmark importa o RAG, usa PostgreSQL local e texto
sintético; não é uma requisição HTTP ou upload com extração, nem medição da EC2.
A inferência continua ocupando parte importante do tempo, e a economia de viagens
ao banco não deve ser convertida em previsão de aceleração de ponta a ponta.

O modo offline da biblioteca não reconheceu automaticamente o cache na primeira
tentativa. O medidor passou a aceitar um caminho explícito do snapshot público,
somente no ensaio, preservando o adapter e a configuração de inferência da
aplicação. A execução final ocorreu em rede Docker interna, sem download, AWS,
Supabase ou Groq. Evidências sanitizadas: `docs/vector-batch-benchmark.json`.
O smoke da imagem Linux também aprovou inicialização, limites, persistência,
recuperação documental, reinício automático, manutenção e encerramento limpo.

Esta preparação ainda precisa de publicação e medição na EC2. Os originais,
vetores e configurações de produção não foram modificados nesta etapa.

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
- [Autenticação por senha e recuperação no Supabase](https://supabase.com/docs/guides/auth/passwords)
- [Envio de e-mails por SMTP próprio no Supabase](https://supabase.com/docs/guides/auth/auth-smtp)
- [Conexões PostgreSQL do Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Interpolação do ConfigParser](https://docs.python.org/3.12/library/configparser.html#interpolation-of-values)
- [HTTPS automático no Caddy](https://caddyserver.com/docs/automatic-https)
- [Reverse proxy, headers e streaming no Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Opções de portas e timeouts do Caddy](https://caddyserver.com/docs/caddyfile/options)
- [Limite de corpo no Caddy](https://caddyserver.com/docs/caddyfile/directives/request_body)
- [Remoção de valores no merge de Compose](https://docs.docker.com/reference/compose-file/merge/#reset-value)
- [Middleware de proxy do Uvicorn 0.29.0](https://github.com/encode/uvicorn/blob/0.29.0/uvicorn/middleware/proxy_headers.py)
- [Acesso HTTP/HTTPS a uma EC2](https://repost.aws/knowledge-center/connect-http-https-ec2)
- [Condições do Free Tier e duração do Free Plan](https://aws.amazon.com/free/terms/)
- [Planos Free/Paid e conversões automáticas](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
- [IAM para DLM](https://docs.aws.amazon.com/ebs/latest/userguide/service-role.html)
- [Métricas de snapshots DLM](https://docs.aws.amazon.com/ebs/latest/userguide/monitor-dlm-cw-metrics.html)
- [Permissões de sessões SSM](https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-restrict-access-examples.html)
- [Alarmes CloudWatch com SNS criptografado](https://repost.aws/knowledge-center/cloudwatch-configure-alarm-sns)
- [Preços KMS](https://aws.amazon.com/kms/pricing/)
- [Preços CloudWatch](https://aws.amazon.com/cloudwatch/pricing/)
- [Dados persistentes do Docker e containerd](https://docs.docker.com/engine/daemon/#daemon-data-directory)
- [OIDC GitHub Actions com AWS e subjects de ambiente](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [Parâmetros SSM por variável de ambiente](https://docs.aws.amazon.com/systems-manager/latest/userguide/documents-syntax-data-elements-parameters.html)
- [Versão mínima do SSM Agent para ENV_VAR](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-troubleshooting.html)
- [Impedir sobrescrita com escritas condicionais no S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html)
- [Instalação e verificação de assinatura AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Preços ECR](https://aws.amazon.com/ecr/pricing/)
- [Preços S3](https://aws.amazon.com/s3/pricing/)
- [Alembic usando uma conexão/transação do chamador](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [Docker Engine no Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
