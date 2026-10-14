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
- [ ] **3. Persistência e segurança dos uploads durante atualizações:** definir e
  implementar a retenção dos originais, recuperação de processamento interrompido,
  drenagem antes de trocar versões e teste de recriação do container sem perda.
  Definir backup e recuperação; volume local não substitui backup.
- [ ] **4. Configuração de produção e segredos:** exemplo sem valores reais,
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

## O que a análise encontrou

| Área | Situação atual | Consequência para o deploy |
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
ingestões precisam da drenagem e recuperação a implementar na etapa 3.

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
etapa é a **3: persistência dos arquivos e recuperação de uploads**.

## Referências

- [FastAPI em containers](https://fastapi.tiangolo.com/deployment/docker/)
- [Boas práticas de build do Docker](https://docs.docker.com/build/building/best-practices/)
- [Contexto de build e `.dockerignore`](https://docs.docker.com/build/concepts/context/)
- [Configuração dos serviços Compose](https://docs.docker.com/reference/compose-file/services/)
- [Políticas de reinício do Docker](https://docs.docker.com/engine/containers/start-containers-automatically/)
- [Volumes Docker](https://docs.docker.com/engine/storage/volumes/)
- [Rotação de logs com o driver local](https://docs.docker.com/engine/logging/drivers/local/)
- [Tratamento de sinais no Uvicorn 0.29](https://github.com/encode/uvicorn/blob/0.29.0/uvicorn/server.py)
