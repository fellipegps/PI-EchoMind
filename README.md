# EchoMind

O EchoMind é uma aplicação web de atendimento institucional com IA. Cada instituição gerencia sua própria base de conhecimento e publica um portal para estudantes e visitantes.

- **Portal público** — chat com respostas em tempo real, agenda de eventos e guia de locais do campus com fichas, fotos e QR Codes. O campus de Anápolis da UniEVANGÉLICA inclui uma maquete 3D e uma vista de satélite.
- **Painel administrativo** — cadastro de FAQs, documentos, eventos e pontos de referência nos campi, com métricas de atendimento e triagem das perguntas encaminhadas pelos visitantes.
- **Respostas com base institucional** — a API recupera FAQs e trechos de documentos da instituição para gerar respostas com a Groq. Os eventos são consultados na agenda do portal.

## Como rodar localmente

Inicie a API primeiro. Em outro terminal, inicie o frontend usando o mesmo projeto Supabase.

| Componente | Tecnologias | Guia |
| --- | --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS, Leaflet e Three.js | [Configurar e rodar o frontend](echomind-front/README.md) |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, FastEmbed e Groq | [Configurar e rodar o backend](echomind-backend/README.md) |
| Dados e autenticação | Supabase Auth e PostgreSQL com pgvector | [Configurar o banco e aplicar as migrações](echomind-backend/README.md#2-configurar-o-ambiente) |

## Documentação técnica

- [RAG, avaliação e reindexação](echomind-backend/RAG.md)
- [Deploy e operação na AWS e na Vercel](deploy/README.md)
- [Configuração de campi e maquetes pela equipe EchoMind](deploy/operations/campus-maps.md)
