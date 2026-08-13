import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = "controle_marketplace"

print("--- Testando conexão com o PostgreSQL ---")
print(f"HOST: {DB_HOST}")
print(f"PORT: {DB_PORT}")
print(f"USER: {DB_USER}")
print(f"DB:   {DB_NAME}")
print("-" * 40)

try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        connect_timeout=5,
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    versao = cursor.fetchone()[0]
    print(f"✅ Conexão bem-sucedida!\n{versao}")

    cursor.execute("SELECT COUNT(*) FROM produtos;")
    print(f"📦 Produtos cadastrados: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM vendas;")
    print(f"💰 Vendas cadastradas: {cursor.fetchone()[0]}")

    cursor.close()
    conn.close()

except psycopg2.OperationalError as e:
    print(f"❌ Não foi possível conectar ao banco.\nErro: {e}")
except Exception as e:
    print(f"❌ Erro inesperado: {type(e).__name__}: {e}")