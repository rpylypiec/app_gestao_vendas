from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = FastAPI(title="Marketplace Data API - PostgreSQL")

# Construção dinâmica e segura da URL de conexão com o Postgres
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = "controle_marketplace"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Erro crítico ao conectar ao PostgreSQL: {e}")
        raise e

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Dimensão Produtos (Cadastro Único de SKU)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100)
        );
    ''')
    
    # Fato Compras (Entradas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY,
            produto_id INTEGER REFERENCES produtos(id) ON DELETE CASCADE,
            quantidade INTEGER NOT NULL,
            custo_total NUMERIC(10,2) NOT NULL,
            data_compra DATE NOT NULL
        );
    ''')
    
    # Fato Vendas (Saídas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id SERIAL PRIMARY KEY,
            produto_id INTEGER REFERENCES produtos(id) ON DELETE CASCADE,
            quantidade INTEGER NOT NULL,
            valor_venda_total NUMERIC(10,2) NOT NULL,
            canal_venda VARCHAR(100),
            cliente VARCHAR(255),
            data_venda DATE NOT NULL
        );
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

# Executa a criação das tabelas ao iniciar a API caso não existam
init_db()

# Schemas de validação de payload (Pydantic)
class Produto(BaseModel):
    nome: str
    categoria: str = None

class Compra(BaseModel):
    produto_id: int
    quantidade: int
    custo_total: float

class Venda(BaseModel):
    produto_id: int
    quantidade: int
    valor_venda_total: float
    canal_venda: str = "Facebook Marketplace"
    cliente: str = None

# ---- ROTAS OPERACIONAIS DE CADASTRO ----

@app.post("/produtos")
def cadastrar_produto(prod: Produto):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO produtos (nome, categoria) VALUES (%s, %s);",
            (prod.nome, prod.categoria)
        )
        conn.commit()
        return {"status": "Produto cadastrado com sucesso"}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Este SKU/Produto já está cadastrado.")
    finally:
        cursor.close()
        conn.close()

@app.post("/compras")
def registrar_compra(compra: Compra):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO compras (produto_id, quantidade, custo_total, data_compra) VALUES (%s, %s, %s, %s);",
        (compra.produto_id, compra.quantidade, compra.custo_total, datetime.now().date())
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "Entrada de estoque registrada"}

@app.post("/vendas")
def registrar_venda(venda: Venda):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Trava atômica de validação de estoque
    cursor.execute('''
        SELECT 
            COALESCE((SELECT SUM(quantidade) FROM compras WHERE produto_id = %s), 0) - 
            COALESCE((SELECT SUM(quantidade) FROM vendas WHERE produto_id = %s), 0) as estoque;
    ''', (venda.produto_id, venda.produto_id))
    
    estoque_atual = cursor.fetchone()[0]
    if estoque_atual < venda.quantidade:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Estoque insuficiente. Disponível localmente: {estoque_atual} un")

    cursor.execute(
        "INSERT INTO vendas (produto_id, quantidade, valor_venda_total, canal_venda, cliente, data_venda) VALUES (%s, %s, %s, %s, %s, %s);",
        (venda.produto_id, venda.quantidade, venda.valor_venda_total, venda.canal_venda, venda.cliente, datetime.now().date())
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "Venda registrada com sucesso"}

@app.get("/produtos")
def listar_produtos():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, nome FROM produtos ORDER BY nome ASC;")
    produtos = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(produtos)

# ---- PIPELINE ANALÍTICO (DATA ENGINE ROOM) ----

@app.get("/analytics")
def get_analytics():
    conn = get_db_connection()
    df_prod = pd.read_sql_query("SELECT * FROM produtos;", conn)
    df_comp = pd.read_sql_query("SELECT * FROM compras;", conn)
    df_vend = pd.read_sql_query("SELECT * FROM vendas;", conn)
    conn.close()
    
    if df_prod.empty:
        return {"mensagem": "Sem dados suficientes", "produtos_detalhe": [], "KPIs": {}, "canais_venda": {}}

    # Cast manual para float (evita incompatibilidade do tipo Decimal do Postgres no JSON do FastAPI)
    for df in [df_comp, df_vend]:
        if not df.empty:
            for col in ['custo_total', 'valor_venda_total']:
                if col in df.columns:
                    df[col] = df[col].astype(float)

    # 1. Agrupamento de Entradas (Custo Médio Ponderado)
    if not df_comp.empty:
        comp_agrup = df_comp.groupby('produto_id').agg(
            qtd_comprada=('quantidade', 'sum'),
            custo_total_acumulado=('custo_total', 'sum')
        ).reset_index()
        comp_agrup['custo_medio_unitario'] = comp_agrup['custo_total_acumulado'] / comp_agrup['qtd_comprada']
    else:
        comp_agrup = pd.DataFrame(columns=['produto_id', 'qtd_comprada', 'custo_total_acumulado', 'custo_medio_unitario'])

    # 2. Agrupamento de Saídas (Vendas)
    if not df_vend.empty:
        vend_agrup = df_vend.groupby('produto_id').agg(
            qtd_vendida=('quantidade', 'sum'),
            faturamento_acumulado=('valor_venda_total', 'sum')
        ).reset_index()
    else:
        vend_agrup = pd.DataFrame(columns=['produto_id', 'qtd_vendida', 'faturamento_acumulado'])

    # 3. Consolidação e Construção da View de Negócio
    resumo = df_prod.merge(comp_agrup, left_on='id', right_on='produto_id', how='left')
    resumo = resumo.merge(vend_agrup, left_on='id', right_on='produto_id', how='left')
    resumo.fillna(0, inplace=True)
    
    resumo['estoque_atual'] = resumo['qtd_comprada'] - resumo['qtd_vendida']
    resumo['cmv'] = resumo['qtd_vendida'] * resumo['custo_medio_unitario']
    resumo['lucro_real'] = resumo['faturamento_acumulado'] - resumo['cmv']
    resumo['margem_percentual'] = (resumo['lucro_real'] / resumo['faturamento_acumulado'].replace(0, 1)) * 100

    # 4. Métricas Globais (Dashboard)
    total_investido = float(df_comp['custo_total'].sum()) if not df_comp.empty else 0.0
    total_faturado = float(df_vend['valor_venda_total'].sum()) if not df_vend.empty else 0.0
    total_qtd_vendida = int(df_vend['quantidade'].sum()) if not df_vend.empty else 0
    total_cmv = float(resumo['cmv'].sum())
    
    lucro_total = total_faturado - total_cmv
    roi_percentual = (lucro_total / total_cmv * 100) if total_cmv > 0 else 0.0

    canais = {}
    if not df_vend.empty:
        canais = df_vend.groupby('canal_venda')['valor_venda_total'].sum().to_dict()

    return {
        "produtos_detalhe": resumo[['nome', 'categoria', 'estoque_atual', 'qtd_vendida', 'faturamento_acumulado', 'lucro_real', 'margem_percentual']].to_dict(orient="records"),
        "KPIs": {
            "total_investido": total_investido,
            "total_faturado": total_faturado,
            "quantidade_vendas": total_qtd_vendida,
            "ticket_medio": float(total_faturado / total_qtd_vendida) if total_qtd_vendida > 0 else 0.0,
            "lucro_total": lucro_total,
            "roi_percentual": roi_percentual
        },
        "canais_venda": canais
    }