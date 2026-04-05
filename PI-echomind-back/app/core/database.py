from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

# 1. Criação do engine assíncrono
# echo=True permite ver o SQL real no terminal (ótimo para o TCC)
# pool_pre_ping=True ajuda a manter a conexão viva com o Docker
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_pre_ping=True
)

# 2. Fábrica de sessões (Sessionmaker)
AsyncSessionLocal = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

# 3. Classe Base para os Modelos
class Base(DeclarativeBase):
    pass

# 4. Função de Inicialização do Banco (A "Mágica" do pgvector)
async def init_db():
    """
    Cria a extensão pgvector e gera as tabelas baseadas nos modelos 
    que o SQLAlchemy 'conhece' no momento da execução.
    """
    async with engine.begin() as conn:
        print("🛠️ Verificando extensão pgvector...")
        # Resolve o erro de tipo 'vector' não existir no Postgres
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        print("🛠️ Criando tabelas baseadas nos metadados do Base...")
        # Cria as tabelas (faq, events, etc.) apenas se elas não existirem
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Banco de Dados inicializado com sucesso!")

# 5. Dependency Injection para o FastAPI
async def get_db():
    """
    Gera uma sessão de banco de dados para cada requisição da API.
    Garante que a conexão seja fechada automaticamente após o uso.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()