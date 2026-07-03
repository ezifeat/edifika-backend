# Edifika — Backend API

## Instalação local (desenvolvimento)

```bash
cd ~/Desktop/edifika/backend

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com os teus valores

# Arrancar o servidor (SQLite para desenvolvimento)
uvicorn main:app --reload --port 8000
```

O servidor fica disponível em:
- API: http://localhost:8000
- Documentação interativa: http://localhost:8000/docs
- Documentação alternativa: http://localhost:8000/redoc

## Credenciais demo (criadas automaticamente)

| Role        | Email                    | Password  |
|-------------|--------------------------|-----------|
| Admin       | admin@edifika.pt         | admin123  |
| Cliente     | cliente@edifika.pt       | demo123   |
| Fornecedor  | fornecedor@edifika.pt    | demo123   |
| Fiscal      | fiscal@edifika.pt        | demo123   |

## Deploy em produção (Railway)

1. Criar conta em https://railway.app
2. Criar novo projecto → Deploy from GitHub
3. Adicionar PostgreSQL como serviço
4. Configurar variáveis de ambiente no Railway:
   - DATABASE_URL (gerada automaticamente pelo PostgreSQL do Railway)
   - SECRET_KEY
   - OPENAI_API_KEY
   - STRIPE_SECRET_KEY
   - SENDGRID_API_KEY

## Endpoints principais

### Auth
- POST /api/auth/login — login (devolve JWT)
- POST /api/auth/registo/cliente — registar cliente
- POST /api/auth/registo/fornecedor — registar fornecedor
- GET  /api/auth/me — dados do utilizador actual

### Obras
- GET  /api/obras — listar obras do utilizador
- POST /api/obras — criar nova obra
- GET  /api/obras/{id} — detalhe da obra
- PATCH /api/obras/{id}/status — alterar estado (admin)

### Leilões
- GET  /api/leiloes — listar leilões disponíveis
- POST /api/leiloes/proposta — submeter proposta (fornecedor)
- POST /api/leiloes/{id}/adjudicar/{proposta_id} — adjudicar (admin)

### Auditorias
- GET  /api/auditorias — listar auditorias (fiscal/admin)
- POST /api/auditorias/submeter — submeter resultado (fiscal)

### Cadernos
- GET  /api/cadernos — listar cadernos (admin)
- PATCH /api/cadernos/{id}/estado — aprovar/reprovar (admin)

### IA
- POST /api/ia/transcrever — transcrição de voz (Whisper)
- POST /api/ia/gerar-caderno — gerar caderno (GPT-4)
