# Backend do EchoMind

API FastAPI para atendimento institucional, gestão de conteúdo e integração com Supabase e Groq. Use Python 3.12, um projeto Supabase de desenvolvimento e uma chave da Groq.

## 1. Preparar o ambiente Python

A partir da raiz do repositório:

```bash
cd echomind-backend
```

Escolha a opção do seu sistema e execute os comandos seguintes dentro de `echomind-backend`.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux e macOS com Python 3.12 instalado**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

**Arch Linux com uv**

```bash
sudo pacman -S uv
uv python install 3.12
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
```

Com o ambiente virtual ativo:

```bash
python --version
python -m pip install -r requirements.txt
```

A versão do interpretador deve ser `3.12.x`.

## 2. Configurar o ambiente

Se ainda não houver um `.env`, copie o [.env.example](.env.example).

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux e macOS
cp .env.example .env
```

| Variável | Valor para desenvolvimento |
| --- | --- |
| `DATABASE_URL` | URI PostgreSQL do projeto Supabase, com a senha do banco |
| `SUPABASE_URL` | URL desse mesmo projeto Supabase |
| `SUPABASE_SECRET_KEY` | Chave secreta `sb_secret_...` do Supabase |
| `GROQ_API_KEY` | Chave da API da Groq |
| `ALLOWED_ORIGINS` | Origens exatas do frontend. O exemplo já inclui `http://localhost:3000` e `http://127.0.0.1:3000` |

Use **Connect** no painel do Supabase para obter a URI do banco. Em uma rede somente IPv4, use a opção **Session pooler** quando a conexão direta estiver disponível apenas por IPv6. Consulte a [documentação de conexão do Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres) e a [documentação das chaves de API](https://supabase.com/docs/guides/getting-started/api-keys).

Mantenha as demais opções do exemplo no primeiro uso, incluindo `EMBEDDING_DIM=384`. O rate limiting usa memória do processo e exige uma instância e um worker. Para rodar em produção, siga o [guia de deploy](../deploy/README.md).

## 3. Aplicar as migrações e iniciar a API

Com o `.env` apontando para o banco de desenvolvimento:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

O Alembic gerencia o schema e as extensões necessárias. Aplique as migrações também quando atualizar para uma revisão com mudanças no banco.

- [Verificar se a API está respondendo](http://localhost:8000/health).
- [Abrir a documentação interativa da API](http://localhost:8000/docs). Para rotas administrativas, use **Authorize** com o token de acesso de uma sessão do Supabase.
- [Iniciar o frontend](../echomind-front/README.md) em outro terminal. Entre no painel, cadastre FAQs e teste o chat pelo link público da instituição.
- Nas próximas execuções, ative o ambiente virtual e rode novamente o comando do Uvicorn. Encerre com `Ctrl+C`.

## Importar uma base de conhecimento

O [template da UniEVANGÉLICA](templates/unievangelica.json) importa configuração e FAQs para uma conta existente. Use o **User UID** da conta em **Authentication → Users** no Supabase.

```bash
python scripts/import_knowledge.py --tenant-id UUID_DO_USUARIO --file templates/unievangelica.json
```

O comando atualiza FAQs da instituição e reindexa a base. Também é possível cadastrar conteúdo e enviar arquivos TXT, DOCX ou PDF com texto pelo painel.

## Testes

Instale as dependências de teste.

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

No terminal de testes, defina as variáveis conforme o shell.

```powershell
# Windows PowerShell
$env:PYTHON_DOTENV_DISABLED = '1'
$env:RAG_WARMUP_ENABLED = 'false'
$env:DOCUMENT_RECOVERY_ENABLED = 'false'
```

```bash
# Linux e macOS
export PYTHON_DOTENV_DISABLED=1 RAG_WARMUP_ENABLED=false DOCUMENT_RECOVERY_ENABLED=false
```

A suíte rápida usa SQLite e serviços simulados. Os comandos abaixo reproduzem os limites de cobertura global (72%) e dos módulos documentais (80% por módulo).

```bash
python -m pytest tests/quick -m "not integration and not e2e" --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=72
python scripts/check_document_coverage.py coverage.xml
```

Para testar as migrações e o pgvector, o [workflow da CI](../.github/workflows/ci.yml) mostra como preparar o banco descartável `echomind_integration` em PostgreSQL 17 e executar `python -m pytest -m integration`.

## Referência e operação

- [RAG, reindexação, avaliações offline, logs e métricas](RAG.md).
- [Deploy, backup e recuperação](../deploy/README.md).
- A privacidade da instituição fica em `/p/{slug}/privacidade`. O responsável e o contato são cadastrados no painel. O prazo de retenção do histórico é configurado no backend por `CHAT_HISTORY_RETENTION_DAYS`, com padrão de 30 dias.

[Voltar à visão geral do EchoMind](../README.md)
