import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# Carrega as variáveis contidas no arquivo .env
load_dotenv()

# Recupera os segredos do ambiente de forma segura
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
EXCEL_PATH = "Acompanhamento de Vendas Loja.xlsx"

def criar_database():
    print("Connecting to PostgreSQL to check database...")
    # Conecta ao banco padrão 'postgres' apenas para criar o nosso banco
    conn = psycopg2.connect(
        dbname="postgres", user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Verifica se o banco já existe
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'controle_marketplace';")
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute("CREATE DATABASE controle_marketplace;")
        print("🎉 Database 'controle_marketplace' criado com sucesso!")
    else:
        print("Database já existia.")
        
    cursor.close()
    conn.close()

def injetar_dados():
    # Agora conecta no nosso banco recém-criado
    URL_MKT = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/controle_marketplace"
    conn = psycopg2.connect(URL_MKT)
    cursor = conn.cursor()
    
    print("🏗️ Criando tabelas se não existirem...")
    # Criação das Tabelas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(255) UNIQUE NOT NULL,
            categoria VARCHAR(100)
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id SERIAL PRIMARY KEY,
            produto_id INTEGER REFERENCES produtos(id) ON DELETE CASCADE,
            quantidade INTEGER NOT NULL,
            custo_total NUMERIC(10,2) NOT NULL,
            data_compra DATE NOT NULL
        );
    ''')
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

    print("📖 Lendo dados do Excel...")
    df_excel_compras = pd.read_excel(EXCEL_PATH, sheet_name="Compras")
    df_excel_vendas = pd.read_excel(EXCEL_PATH, sheet_name="Vendas")
    
    # 🔥 DATA CLEANING: Remove linhas completamente vazias ou que tenham o Produto/Quantidade nulos
    df_excel_compras = df_excel_compras.dropna(subset=['Produto', 'Quantidade', 'Custo Total'])
    df_excel_vendas = df_excel_vendas.dropna(subset=['Produto', 'Quantidade', 'Receita Total'])
    
    # 1. Carga da Dimensão Produtos (Evitando duplicatas)
    print("🚀 Injetando Produtos...")
    produtos_unicos = df_excel_compras[['Produto', 'Categoria']].drop_duplicates(subset=['Produto'])
    
    mapa_produtos = {} # Para relacionar Nome -> ID do Postgres
    for _, row in produtos_unicos.iterrows():
        try:
            cursor.execute(
                "INSERT INTO produtos (nome, categoria) VALUES (%s, %s) ON CONFLICT (nome) DO UPDATE SET categoria = EXCLUDED.categoria RETURNING id;",
                (row['Produto'], row['Categoria'])
            )
            prod_id = cursor.fetchone()[0]
            mapa_produtos[row['Produto']] = prod_id
        except Exception as e:
            conn.rollback()
            print(f"Erro ao inserir produto {row['Produto']}: {e}")
    conn.commit()

    # 2. Carga da Fato Compras
    print("📥 Injetando Histórico de Compras...")
    for _, row in df_excel_compras.iterrows():
        prod_id = mapa_produtos.get(row['Produto'])
        if prod_id:
            data_c = row['Data Compra']
            if isinstance(data_c, str):
                data_c = datetime.strptime(data_c, "%Y-%m-%d").date()
            elif isinstance(data_c, pd.Timestamp):
                data_c = data_c.date()
                
            cursor.execute(
                "INSERT INTO compras (produto_id, quantidade, custo_total, data_compra) VALUES (%s, %s, %s, %s);",
                (prod_id, int(row['Quantidade']), float(row['Custo Total']), data_c)
            )
    conn.commit()

    # 3. Carga da Fato Vendas
    print("💰 Injetando Histórico de Vendas...")
    for _, row in df_excel_vendas.iterrows():
        prod_nome = row['Produto']
        if prod_nome not in mapa_produtos:
            cursor.execute("INSERT INTO produtos (nome, categoria) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING RETURNING id;", (prod_nome, "Outros"))
            res = cursor.fetchone()
            prod_id = res[0] if res else None
        else:
            prod_id = mapa_produtos[prod_nome]
            
        if prod_id:
            data_v = row['Data Venda']
            if isinstance(data_v, str):
                data_v = datetime.strptime(data_v, "%Y-%m-%d").date()
            elif isinstance(data_v, pd.Timestamp):
                data_v = data_v.date()
                
            cursor.execute(
                "INSERT INTO vendas (produto_id, quantidade, valor_venda_total, canal_venda, cliente, data_venda) VALUES (%s, %s, %s, %s, %s, %s);",
                (prod_id, int(row['Quantidade']), float(row['Receita Total']), row['Canal Venda'], row['Cliente'], data_v)
            )
    conn.commit()
    
    cursor.close()
    conn.close()
    print("✨ Carga de dados concluída com sucesso no PostgreSQL de forma segura!")

if __name__ == "__main__":
    criar_database()
    injetar_dados()