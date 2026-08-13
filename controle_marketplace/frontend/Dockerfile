FROM python:3.10-slim

WORKDIR /app

# 🔥 Adicionado plotly e pandas (usado no app.py para montar os DataFrames)
RUN pip install --no-cache-dir streamlit requests plotly pandas

# Copia o código do front-end para o container
COPY app.py .

# Expõe a porta padrão do Streamlit
EXPOSE 8501

# Comando para rodar o Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]