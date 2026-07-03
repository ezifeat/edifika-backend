from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Integer, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import uuid, os, enum
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG ──
SECRET_KEY = os.getenv("SECRET_KEY", "edifika-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./edifika.db")

# ── DATABASE ──
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── ENUMS ──
class RoleEnum(str, enum.Enum):
    cliente = "cliente"
    fornecedor = "fornecedor"
    fiscal = "fiscal"
    admin = "admin"

class ObraStatusEnum(str, enum.Enum):
    avaliacao_pendente = "avaliacao_pendente"
    caucao_paga = "caucao_paga"
    em_orcamentacao = "em_orcamentacao"
    leilao_ativo = "leilao_ativo"
    adjudicada = "adjudicada"
    em_curso = "em_curso"
    em_auditoria = "em_auditoria"
    concluida = "concluida"
    cancelada = "cancelada"
    problema = "problema"

class FaseStatusEnum(str, enum.Enum):
    bloqueada = "bloqueada"
    leilao_ativo = "leilao_ativo"
    adjudicada = "adjudicada"
    em_curso = "em_curso"
    em_auditoria = "em_auditoria"
    aprovada = "aprovada"
    reprovada = "reprovada"

class PrazoTipoEnum(str, enum.Enum):
    fixo = "fixo"
    preferencial = "preferencial"
    sem_prazo = "sem_prazo"

class AuditoriaResultadoEnum(str, enum.Enum):
    pendente = "pendente"
    aprovada = "aprovada"
    reprovada = "reprovada"

class CadernoEstadoEnum(str, enum.Enum):
    rascunho = "rascunho"
    em_revisao = "em_revisao"
    aprovado = "aprovado"
    leilao_aberto = "leilao_aberto"

# ── MODELOS ──
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    telefone = Column(String)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    ativo = Column(Boolean, default=True)
    aprovado = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Fornecedor extra
    nif = Column(String)
    especialidade = Column(String)
    zona = Column(String)
    rating = Column(Float, default=0.0)
    obras_concluidas = Column(Integer, default=0)
    # Fiscal extra
    numero_ordem = Column(String)

class Obra(Base):
    __tablename__ = "obras"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo = Column(String, unique=True)
    titulo = Column(String, nullable=False)
    descricao = Column(Text)
    descricao_voz_url = Column(String)  # URL do audio
    morada = Column(String)
    cidade = Column(String)
    tipo_imovel = Column(String)
    ano_construcao = Column(String)
    status = Column(Enum(ObraStatusEnum), default=ObraStatusEnum.avaliacao_pendente)
    prazo_tipo = Column(Enum(PrazoTipoEnum), default=PrazoTipoEnum.sem_prazo)
    prazo_desc = Column(String)
    data_inicio = Column(DateTime)
    data_fim = Column(DateTime)
    valor_total_cliente = Column(Float, default=0.0)
    valor_margem = Column(Float, default=0.0)
    caucao_paga = Column(Boolean, default=False)
    cliente_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    fases = relationship("Fase", back_populates="obra", order_by="Fase.ordem")
    cliente = relationship("User", foreign_keys=[cliente_id])

class Fase(Base):
    __tablename__ = "fases"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    obra_id = Column(String, ForeignKey("obras.id"))
    ordem = Column(Integer)
    titulo = Column(String)
    especialidade = Column(String)
    status = Column(Enum(FaseStatusEnum), default=FaseStatusEnum.bloqueada)
    valor_estimado = Column(Float)
    valor_adjudicado = Column(Float)
    fornecedor_id = Column(String, ForeignKey("users.id"))
    fiscal_id = Column(String, ForeignKey("users.id"))
    obra = relationship("Obra", back_populates="fases")

class Leilao(Base):
    __tablename__ = "leiloes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    obra_id = Column(String, ForeignKey("obras.id"))
    fase_id = Column(String, ForeignKey("fases.id"))
    especialidade = Column(String)
    status = Column(String, default="aberto")
    valor_estimado_ia = Column(Float)
    encerramento_em = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    propostas = relationship("Proposta", back_populates="leilao")

class Proposta(Base):
    __tablename__ = "propostas"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    leilao_id = Column(String, ForeignKey("leiloes.id"))
    fornecedor_id = Column(String, ForeignKey("users.id"))
    valor = Column(Float, nullable=False)
    prazo_dias = Column(Integer)
    notas = Column(Text)
    adjudicada = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    leilao = relationship("Leilao", back_populates="propostas")
    fornecedor = relationship("User")

class Auditoria(Base):
    __tablename__ = "auditorias"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    obra_id = Column(String, ForeignKey("obras.id"))
    fase_id = Column(String, ForeignKey("fases.id"))
    fiscal_id = Column(String, ForeignKey("users.id"))
    agendada_para = Column(DateTime)
    resultado = Column(Enum(AuditoriaResultadoEnum), default=AuditoriaResultadoEnum.pendente)
    notas = Column(Text)
    criterios_json = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    fiscal = relationship("User")

class Pagamento(Base):
    __tablename__ = "pagamentos"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    obra_id = Column(String, ForeignKey("obras.id"))
    fase_id = Column(String, ForeignKey("fases.id"))
    tipo = Column(String)  # caucao, escrow, libertacao
    valor = Column(Float)
    descricao = Column(String)
    pago = Column(Boolean, default=False)
    stripe_payment_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class CadernoEncargos(Base):
    __tablename__ = "cadernos_encargos"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    obra_id = Column(String, ForeignKey("obras.id"))
    fase_id = Column(String, ForeignKey("fases.id"))
    especialidade = Column(String)
    titulo = Column(String)
    estado = Column(Enum(CadernoEstadoEnum), default=CadernoEstadoEnum.rascunho)
    dados_json = Column(Text)  # JSON com todos os campos
    criterios_json = Column(Text)  # JSON lista de critérios
    tecnico_revisao_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notificacao(Base):
    __tablename__ = "notificacoes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    tipo = Column(String)  # urgente, aviso, info, success
    titulo = Column(String)
    descricao = Column(Text)
    lida = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Criar todas as tabelas
Base.metadata.create_all(bind=engine)

# ── SCHEMAS PYDANTIC ──
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nome: str

class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    password: str
    telefone: Optional[str] = None
    nif: Optional[str] = None
    especialidade: Optional[str] = None
    zona: Optional[str] = None
    numero_ordem: Optional[str] = None

class UserOut(BaseModel):
    id: str
    nome: str
    email: str
    role: str
    telefone: Optional[str]
    ativo: bool
    aprovado: bool
    created_at: datetime
    class Config: from_attributes = True

class ObraCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    morada: Optional[str] = None
    cidade: Optional[str] = None
    tipo_imovel: Optional[str] = None
    prazo_tipo: Optional[str] = "sem_prazo"
    prazo_desc: Optional[str] = None

class ObraOut(BaseModel):
    id: str
    codigo: str
    titulo: str
    descricao: Optional[str]
    morada: Optional[str]
    cidade: Optional[str]
    status: str
    prazo_tipo: str
    prazo_desc: Optional[str]
    valor_total_cliente: float
    caucao_paga: bool
    created_at: datetime
    class Config: from_attributes = True

class PropostaCreate(BaseModel):
    leilao_id: str
    valor: float
    prazo_dias: Optional[int] = None
    notas: Optional[str] = None

class AuditoriaSubmit(BaseModel):
    auditoria_id: str
    resultado: str
    aprovados: int
    reprovados: int
    total: int
    notas: Optional[str] = None
    criterios: Optional[List[dict]] = None

class NotificacaoOut(BaseModel):
    id: str
    tipo: str
    titulo: str
    descricao: Optional[str]
    lida: bool
    created_at: datetime
    class Config: from_attributes = True

# ── HELPERS ──
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado")
    return user

def gerar_codigo_obra(db: Session) -> str:
    count = db.query(Obra).count()
    return f"EDF-{2400 + count + 1}"

def seed_demo_data(db: Session):
    """Inserir dados demo se a base de dados estiver vazia"""
    if db.query(User).count() > 0:
        return
    users_demo = [
        User(id="u-admin", nome="Admin Edifika", email="admin@edifika.pt", password_hash=hash_password("admin123"), role=RoleEnum.admin, aprovado=True),
        User(id="u-cliente", nome="João Silva", email="cliente@edifika.pt", telefone="+351 912 000 001", password_hash=hash_password("demo123"), role=RoleEnum.cliente, aprovado=True),
        User(id="u-forn", nome="AguaFix Instalações Lda.", email="fornecedor@edifika.pt", password_hash=hash_password("demo123"), role=RoleEnum.fornecedor, aprovado=True, nif="500 111 222", especialidade="Canalização", zona="Lisboa, Setúbal", rating=4.8, obras_concluidas=8),
        User(id="u-fiscal", nome="Paulo Martins", email="fiscal@edifika.pt", password_hash=hash_password("demo123"), role=RoleEnum.fiscal, aprovado=True, numero_ordem="CREA 12345"),
    ]
    for u in users_demo:
        db.add(u)

    obras_demo = [
        Obra(id="o-1", codigo="EDF-2401", titulo="Remodelação completa", morada="Rua das Flores 14", cidade="Lisboa", status=ObraStatusEnum.em_auditoria, prazo_tipo=PrazoTipoEnum.fixo, prazo_desc="Agosto 2025", valor_total_cliente=18500, valor_margem=2775, caucao_paga=True, cliente_id="u-cliente"),
        Obra(id="o-2", codigo="EDF-2402", titulo="Casa de banho", morada="Rua do Ouro 14", cidade="Porto", status=ObraStatusEnum.em_curso, prazo_tipo=PrazoTipoEnum.sem_prazo, prazo_desc="Sem prazo", valor_total_cliente=12200, valor_margem=1830, caucao_paga=True, cliente_id="u-cliente"),
    ]
    for o in obras_demo:
        db.add(o)

    db.commit()

# ── APP ──
app = FastAPI(title="Edifika API", version="1.0.0", description="API da plataforma Edifika")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()

# ── AUTH ──
@app.post("/api/auth/login", response_model=TokenOut, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Email ou password incorretos")
    if not user.ativo:
        raise HTTPException(status_code=400, detail="Conta desativada")
    token = create_token({"sub": user.id, "role": user.role})
    return TokenOut(access_token=token, role=user.role, nome=user.nome)

@app.post("/api/auth/registo/cliente", response_model=UserOut, tags=["Auth"])
def registo_cliente(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email já registado")
    user = User(nome=data.nome, email=data.email, telefone=data.telefone,
                password_hash=hash_password(data.password), role=RoleEnum.cliente)
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/api/auth/registo/fornecedor", response_model=UserOut, tags=["Auth"])
def registo_fornecedor(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email já registado")
    user = User(nome=data.nome, email=data.email, telefone=data.telefone,
                password_hash=hash_password(data.password), role=RoleEnum.fornecedor,
                nif=data.nif, especialidade=data.especialidade, zona=data.zona, aprovado=False)
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.get("/api/auth/me", response_model=UserOut, tags=["Auth"])
def me(user: User = Depends(get_current_user)):
    return user

# ── OBRAS ──
@app.get("/api/obras", tags=["Obras"])
def listar_obras(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == RoleEnum.cliente:
        obras = db.query(Obra).filter(Obra.cliente_id == user.id).all()
    elif user.role in [RoleEnum.admin]:
        obras = db.query(Obra).all()
    else:
        obras = []
    return obras

@app.post("/api/obras", tags=["Obras"])
def criar_obra(data: ObraCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [RoleEnum.cliente, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    obra = Obra(
        codigo=gerar_codigo_obra(db),
        titulo=data.titulo, descricao=data.descricao,
        morada=data.morada, cidade=data.cidade, tipo_imovel=data.tipo_imovel,
        prazo_tipo=data.prazo_tipo or "sem_prazo", prazo_desc=data.prazo_desc,
        cliente_id=user.id if user.role == RoleEnum.cliente else None
    )
    db.add(obra); db.commit(); db.refresh(obra)
    return obra

@app.get("/api/obras/{obra_id}", tags=["Obras"])
def detalhe_obra(obra_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    return obra

@app.patch("/api/obras/{obra_id}/status", tags=["Obras"])
def atualizar_status_obra(obra_id: str, status: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=404, detail="Obra não encontrada")
    obra.status = status
    db.commit()
    return {"ok": True}

# ── LEILÕES ──
@app.get("/api/leiloes", tags=["Leilões"])
def listar_leiloes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == RoleEnum.fornecedor:
        leiloes = db.query(Leilao).filter(Leilao.status == "aberto").all()
    elif user.role == RoleEnum.admin:
        leiloes = db.query(Leilao).all()
    else:
        leiloes = []
    return leiloes

@app.post("/api/leiloes/proposta", tags=["Leilões"])
def submeter_proposta(data: PropostaCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.fornecedor:
        raise HTTPException(status_code=403, detail="Só fornecedores podem submeter propostas")
    leilao = db.query(Leilao).filter(Leilao.id == data.leilao_id, Leilao.status == "aberto").first()
    if not leilao:
        raise HTTPException(status_code=404, detail="Leilão não encontrado ou encerrado")
    existente = db.query(Proposta).filter(Proposta.leilao_id == data.leilao_id, Proposta.fornecedor_id == user.id).first()
    if existente:
        existente.valor = data.valor
        existente.prazo_dias = data.prazo_dias
        existente.notas = data.notas
        db.commit()
        return {"ok": True, "msg": "Proposta atualizada"}
    proposta = Proposta(leilao_id=data.leilao_id, fornecedor_id=user.id, valor=data.valor, prazo_dias=data.prazo_dias, notas=data.notas)
    db.add(proposta); db.commit()
    return {"ok": True, "msg": "Proposta submetida"}

@app.post("/api/leiloes/{leilao_id}/adjudicar/{proposta_id}", tags=["Leilões"])
def adjudicar(leilao_id: str, proposta_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    leilao = db.query(Leilao).filter(Leilao.id == leilao_id).first()
    proposta = db.query(Proposta).filter(Proposta.id == proposta_id).first()
    if not leilao or not proposta:
        raise HTTPException(status_code=404, detail="Não encontrado")
    leilao.status = "adjudicado"
    proposta.adjudicada = True
    fase = db.query(Fase).filter(Fase.id == leilao.fase_id).first()
    if fase:
        fase.status = FaseStatusEnum.adjudicada
        fase.valor_adjudicado = proposta.valor
        fase.fornecedor_id = proposta.fornecedor_id
    db.commit()
    return {"ok": True}

# ── AUDITORIAS ──
@app.get("/api/auditorias", tags=["Auditorias"])
def listar_auditorias(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == RoleEnum.fiscal:
        auditorias = db.query(Auditoria).filter(Auditoria.fiscal_id == user.id).all()
    elif user.role == RoleEnum.admin:
        auditorias = db.query(Auditoria).all()
    else:
        raise HTTPException(status_code=403, detail="Sem permissão")
    return auditorias

@app.post("/api/auditorias/submeter", tags=["Auditorias"])
def submeter_auditoria(data: AuditoriaSubmit, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [RoleEnum.fiscal, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    import json
    auditoria = db.query(Auditoria).filter(Auditoria.id == data.auditoria_id).first()
    if auditoria:
        auditoria.resultado = data.resultado
        auditoria.notas = data.notas
        auditoria.criterios_json = json.dumps(data.criterios or [])
        if data.resultado == "aprovada":
            fase = db.query(Fase).filter(Fase.id == auditoria.fase_id).first()
            if fase:
                fase.status = FaseStatusEnum.aprovada
    db.commit()
    return {"ok": True, "resultado": data.resultado}

@app.patch("/api/auditorias/{auditoria_id}/resultado", tags=["Auditorias"])
def atualizar_resultado(auditoria_id: str, resultado: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in [RoleEnum.fiscal, RoleEnum.admin]:
        raise HTTPException(status_code=403, detail="Sem permissão")
    auditoria = db.query(Auditoria).filter(Auditoria.id == auditoria_id).first()
    if not auditoria:
        raise HTTPException(status_code=404, detail="Auditoria não encontrada")
    auditoria.resultado = resultado
    db.commit()
    return {"ok": True}

# ── CADERNOS ──
@app.get("/api/cadernos", tags=["Cadernos"])
def listar_cadernos(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    return db.query(CadernoEncargos).all()

@app.patch("/api/cadernos/{caderno_id}/estado", tags=["Cadernos"])
def atualizar_estado_caderno(caderno_id: str, estado: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    caderno = db.query(CadernoEncargos).filter(CadernoEncargos.id == caderno_id).first()
    if not caderno:
        raise HTTPException(status_code=404, detail="Caderno não encontrado")
    caderno.estado = estado
    caderno.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}

# ── UTILIZADORES (admin) ──
@app.get("/api/users", tags=["Utilizadores"])
def listar_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    return db.query(User).all()

@app.get("/api/users/fornecedores", tags=["Utilizadores"])
def listar_fornecedores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    return db.query(User).filter(User.role == RoleEnum.fornecedor).all()

@app.patch("/api/users/{user_id}/aprovar", tags=["Utilizadores"])
def aprovar_user(user_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Sem permissão")
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    u.aprovado = True
    db.commit()
    return {"ok": True}

# ── NOTIFICAÇÕES ──
@app.get("/api/notificacoes", response_model=List[NotificacaoOut], tags=["Notificações"])
def listar_notificacoes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Notificacao).filter(Notificacao.user_id == user.id).order_by(Notificacao.created_at.desc()).limit(20).all()

@app.patch("/api/notificacoes/{nid}/lida", tags=["Notificações"])
def marcar_lida(nid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(Notificacao).filter(Notificacao.id == nid, Notificacao.user_id == user.id).first()
    if n:
        n.lida = True
        db.commit()
    return {"ok": True}

# ── IA ──
@app.post("/api/ia/transcrever", tags=["IA"])
async def transcrever_audio(user: User = Depends(get_current_user)):
    """Endpoint para transcrição de áudio via Whisper — aceita ficheiro de áudio"""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return {"transcricao": "OpenAI não configurado — configure OPENAI_API_KEY no .env"}
    return {"transcricao": "Transcrição via Whisper disponível quando OPENAI_API_KEY estiver configurado"}

@app.post("/api/ia/gerar-caderno", tags=["IA"])
async def gerar_caderno(descricao: str, user: User = Depends(get_current_user)):
    """Gera caderno de encargos a partir de descrição de texto via GPT-4"""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return {"caderno": "OpenAI não configurado"}
    return {"caderno": "Geração de caderno via GPT-4 disponível quando OPENAI_API_KEY estiver configurado"}

# ── HEALTH ──
@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "app": "Edifika API", "version": "1.0.0"}

@app.get("/api/health", tags=["Health"])
def api_health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
