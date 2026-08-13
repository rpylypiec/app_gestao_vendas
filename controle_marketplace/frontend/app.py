import streamlit as st
import requests
import pandas as pd
import plotly.express as px

API_URL = "http://host.docker.internal:8000"

st.set_page_config(page_title="Dashboard Marketplace", layout="wide")


# --- BUSCA DE DADOS ---
@st.cache_data(ttl=5)
def fetch_analytics_data():
    try:
        response = requests.get(f"{API_URL}/analytics", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=5)
def fetch_raw_vendas():
    try:
        # Puxa o histórico de vendas brutas do back-end para conseguir a Dimensão Tempo
        response = requests.get(f"{API_URL}/vendas", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []


data_analytics = fetch_analytics_data()
vendas_brutas = fetch_raw_vendas()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("Navegação")
aba = st.sidebar.radio(
    "Ir para:",
    ["Analytics", "Registros", "Cadastrar Compra", "Cadastrar Venda"]
)

# =========================================================================
# TELA 1: ANALYTICS
# =========================================================================
if aba == "Analytics":
    st.title("📊 Painel Analítico de Performance")

    def formatar_moeda_br(valor):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def formatar_porcentagem_br(valor):
        return f"{valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")

    # --- 1) PREPARA A DIMENSÃO TEMPO E OS FILTROS (sempre antes dos KPIs/gráficos) ---
    df_filtrado = pd.DataFrame()
    col_data = None
    col_valor = None
    col_prod_id = None

    if vendas_brutas and isinstance(vendas_brutas, list):
        df_vendas = pd.DataFrame(vendas_brutas)
        col_data = next((c for c in ['data_venda', 'data', 'date'] if c in df_vendas.columns), None)
        col_valor = next((c for c in ['valor_venda_total', 'valor', 'revenue'] if c in df_vendas.columns), None)
        col_prod_id = next((c for c in ['produto_id', 'produto'] if c in df_vendas.columns), None)

        if col_data and col_valor:
            df_vendas[col_data] = pd.to_datetime(df_vendas[col_data])
            df_vendas[col_valor] = df_vendas[col_valor].astype(float)

            # Tradutor manual de meses para garantir PT-BR
            meses_pt = {
                'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março',
                'April': 'Abril', 'May': 'Maio', 'June': 'Junho',
                'July': 'Julho', 'August': 'Agosto', 'September': 'Setembro',
                'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
            }

            # Construção da Dimensão Tempo
            df_vendas['Ano'] = df_vendas[col_data].dt.year
            df_vendas['Mes_Num'] = df_vendas[col_data].dt.month
            df_vendas['Mes_Nome'] = df_vendas[col_data].dt.strftime('%B').map(meses_pt)
            df_vendas['Semana_Num'] = df_vendas[col_data].dt.isocalendar().week
            df_vendas['Semana_Str'] = "Semana " + df_vendas['Semana_Num'].astype(str)

            # --- Filtros na sidebar ---
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filtros do Painel")

            anos_disponiveis = sorted(df_vendas['Ano'].unique())
            ano_selecionado = st.sidebar.multiselect("Ano", options=anos_disponiveis, default=anos_disponiveis)

            meses_disponiveis = sorted(
                df_vendas['Mes_Nome'].unique(), key=lambda x: list(meses_pt.values()).index(x)
            )
            mes_selecionado = st.sidebar.multiselect("Mês", options=meses_disponiveis, default=meses_disponiveis)

            datas_disponiveis = sorted(df_vendas[col_data].dt.date.unique())
            periodo_selecionado = st.sidebar.date_input(
                "Período de Data",
                value=(min(datas_disponiveis), max(datas_disponiveis)),
                min_value=min(datas_disponiveis),
                max_value=max(datas_disponiveis)
            )
            # Enquanto o usuário está selecionando o intervalo, o widget pode
            # retornar temporariamente apenas 1 data em vez de uma tupla (data_inicio, data_fim)
            if len(periodo_selecionado) == 2:
                data_inicio, data_fim = periodo_selecionado
            else:
                data_inicio = data_fim = periodo_selecionado[0]

            # Aplicando os filtros encadeados
            df_filtrado = df_vendas[
                (df_vendas['Ano'].isin(ano_selecionado)) &
                (df_vendas['Mes_Nome'].isin(mes_selecionado)) &
                (df_vendas[col_data].dt.date >= data_inicio) &
                (df_vendas[col_data].dt.date <= data_fim)
            ]
        else:
            st.sidebar.info("Colunas temporais não identificadas na resposta de vendas brutas.")
    else:
        st.sidebar.info("Aguardando novas inserções de vendas para alimentar os filtros.")

    if data_analytics:
        # --- 2) BIG NUMBERS BASEADOS NO PERÍODO FILTRADO ---
        if not df_filtrado.empty and col_valor:
            total_revenue = df_filtrado[col_valor].sum()

            kpis_estaticos = data_analytics.get("KPIs", {})
            total_investment_global = kpis_estaticos.get("total_investido", 0.0)
            total_revenue_global = kpis_estaticos.get("total_faturado", 1.0)  # evita divisão por zero

            # Investimento proporcional ao faturamento do período selecionado
            proporcao = total_revenue / total_revenue_global if total_revenue_global > 0 else 0
            total_investment = total_investment_global * proporcao
        else:
            total_revenue = 0.0
            total_investment = 0.0

        roi_bruto_rs = total_revenue - total_investment
        roi_percentual = (roi_bruto_rs / total_investment * 100) if total_investment > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Total Faturado", value=formatar_moeda_br(total_revenue))
        with col2:
            st.metric(label="Total Investido", value=formatar_moeda_br(total_investment))
        with col3:
            st.metric(label="ROI (R$)", value=formatar_moeda_br(roi_bruto_rs))
        with col4:
            st.metric(label="ROI (%)", value=formatar_porcentagem_br(roi_percentual))

        # --- 3) GRÁFICO DE LINHAS: Faturamento ao longo do tempo ---
        st.subheader("📈 Evolução do Faturamento ao Longo do Tempo")

        if not df_filtrado.empty and col_data and col_valor:
            if st.checkbox("Visualizar colunas da Dimensão Tempo obtidas"):
                df_view = df_filtrado.copy()
                df_view[col_data] = df_view[col_data].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    df_view[[col_data, 'Ano', 'Mes_Num', 'Mes_Nome', 'Semana_Num', 'Semana_Str', col_valor]],
                    column_config={col_valor: st.column_config.NumberColumn("Valor Venda Total", format="R$ %.2f")}
                )

            df_timeline = df_filtrado.groupby(col_data)[col_valor].sum().reset_index()
            df_timeline = df_timeline.sort_values(by=col_data)

            fig = px.line(
                df_timeline,
                x=col_data,
                y=col_valor,
                text=df_timeline[col_valor].apply(
                    lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
            )

            fig.update_layout(
                xaxis=dict(title=None, tickformat="%d/%m/%Y", showgrid=False),
                yaxis=dict(title=None, showgrid=False, tickprefix="R$ ", tickformat=",.2f"),
                separators=",.",
                margin=dict(l=20, r=20, t=30, b=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            fig.update_traces(
                line=dict(width=2.5),
                textposition="top center",
                hovertemplate="<b>Data:</b> %{x|%d/%m/%Y}<br><b>Faturamento:</b> R$ %{y:,.2f}<extra></extra>"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Nenhum dado encontrado para os filtros selecionados.")

        # --- 4) GRÁFICO DE BARRAS HORIZONTAIS: Faturamento por Produto ---
        st.subheader("📊 Faturamento por Produto (Visão Horizontal)")

        if not df_filtrado.empty and col_prod_id and col_valor:
            try:
                prod_req = requests.get(f"{API_URL}/produtos", timeout=10)
                mapeamento_nomes = {p['id']: p['nome'] for p in prod_req.json()} if prod_req.status_code == 200 else {}
            except Exception:
                mapeamento_nomes = {}

            df_grouped = df_filtrado.groupby(col_prod_id)[col_valor].sum().reset_index()
            df_grouped['nome'] = df_grouped[col_prod_id].map(mapeamento_nomes)
            df_grouped['nome'] = df_grouped['nome'].fillna(df_grouped[col_prod_id].astype(str))
            df_grouped['faturamento_acumulado'] = df_grouped[col_valor]

            df_prod = df_grouped[['nome', 'faturamento_acumulado']]
            df_bar_filtered = df_prod[df_prod["faturamento_acumulado"] > 0].copy()

            if not df_bar_filtered.empty:
                # Ordem crescente pois o Plotly desenha barras horizontais de baixo para cima
                df_bar_filtered = df_bar_filtered.sort_values(by="faturamento_acumulado", ascending=True)

                fig_bar = px.bar(
                    df_bar_filtered,
                    x="faturamento_acumulado",
                    y="nome",
                    orientation="h",
                    text=df_bar_filtered["faturamento_acumulado"].apply(
                        lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    )
                )

                fig_bar.update_layout(
                    xaxis=dict(title=None, showgrid=False, tickprefix="R$ ", tickformat=",.2f"),
                    yaxis=dict(title=None, showgrid=False),
                    separators=",.",
                    margin=dict(l=20, r=40, t=10, b=20),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )

                fig_bar.update_traces(
                    textposition="inside",
                    insidetextanchor="end",
                    hovertemplate="<b>Produto:</b> %{y}<br><b>Faturamento:</b> R$ %{x:,.2f}<extra></extra>"
                )

                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Nenhum produto com faturamento registrado no período selecionado.")
        else:
            st.warning("Sem dados de produtos detalhados disponíveis para os filtros selecionados.")
    else:
        st.info("Nenhum dado analítico disponível no momento.")

# =========================================================================
# TELA 2: REGISTROS
# =========================================================================
elif aba == "Registros":
    st.title("📋 Tabela de Registros Completos")
    if data_analytics and "produtos_detalhe" in data_analytics:
        df_registros = pd.DataFrame(data_analytics["produtos_detalhe"])
        
        if not df_registros.empty:
            # 1. Ignorar valores NaN preenchendo ou removendo para não quebrar a formatação
            df_registros = df_registros.dropna(subset=["faturamento_acumulado"]).copy()
            df_registros = df_registros.fillna(0)
            
            # 2. Ordenar do maior para o menor faturamento
            df_registros = df_registros.sort_values(by="faturamento_acumulado", ascending=False)
            
            # 3. Remover explicitamente colunas de ID para limpar a visualização
            colunas_para_remover = [c for c in df_registros.columns if "id" in c.lower() or c.lower() == "id"]
            if colunas_para_remover:
                df_registros = df_registros.drop(columns=colunas_para_remover)
            
            # Definir a ordem exata das colunas solicitadas
            colunas_desejadas = [
                "nome", "valor_custo", "faturamento_acumulado", 
                "lucro_real", "margem_percentual", "qtd_vendida", "estoque_atual"
            ]
            # Garante que apenas as colunas existentes e desejadas sejam exibidas na ordem
            colunas_finais = [c for c in colunas_desejadas if c in df_registros.columns]
            df_registros = df_registros[colunas_finais]
            
            # Renomear coluna 'nome' visualmente para 'Nome do produto' conforme solicitado
            if "nome" in df_registros.columns:
                df_registros = df_registros.rename(columns={"nome": "Nome do produto"})
            
            # 4. Formatação monetária (R$ . ,) e percentual ( , %) padrão brasileiro
            df_exibicao = df_registros.copy()
            
            formatar_moeda = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            formatar_porcentagem = lambda x: f"{x:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
            
            if "valor_custo" in df_exibicao.columns:
                df_exibicao["valor_custo"] = df_exibicao["valor_custo"].apply(formatar_moeda)
            if "faturamento_acumulado" in df_exibicao.columns:
                df_exibicao["faturamento_acumulado"] = df_exibicao["faturamento_acumulado"].apply(formatar_moeda)
            if "lucro_real" in df_exibicao.columns:
                df_exibicao["lucro_real"] = df_exibicao["lucro_real"].apply(formatar_moeda)
            if "margem_percentual" in df_exibicao.columns:
                df_exibicao["margem_percentual"] = df_exibicao["margem_percentual"].apply(formatar_porcentagem)
                
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum dado encontrado para exibir na tabela.")
    else:
        st.info("Nenhum dado encontrado para exibir na tabela.")

# =========================================================================
# TELA 3: CADASTRAR COMPRA
# =========================================================================
elif aba == "Cadastrar Compra":
    st.title("📦 Cadastrar Nova Compra (Estoque)")
    st.write("Utilize o formulário abaixo para registrar a aquisição de novos lotes de produtos.")

    with st.form("form_cadastro_compra", clear_on_submit=True):
        nome_produto = st.text_input("Nome do Produto *")
        valor_custo = st.number_input("Valor de Custo Unitário (R$) *", min_value=0.0, step=0.01, format="%.2f")
        quantidade = st.number_input("Quantidade Adquirida *", min_value=1, step=1)
        
        botao_submeter = st.form_submit_button("Registrar Entrada no Estoque")

        if botao_submeter:
            if not nome_produto.strip():
                st.error("O campo 'Nome do Produto' é obrigatório.")
            elif valor_custo <= 0:
                st.error("O 'Valor de Custo' deve ser maior que zero.")
            else:
                payload = {
                    "nome": nome_produto.strip(),
                    "valor_custo": valor_custo,
                    "quantidade": quantidade
                }
                try:
                    # Tenta ler a variável global API_URL configurada no seu app, se não existir usa o fallback padrão do Docker
                    url_compra = f"{API_URL}/compras" if 'API_URL' in locals() else "http://host.docker.internal:8000/compras"
                    response = requests.post(url_compra, json=payload)
                    
                    if response.status_code in [200, 201]:
                        st.success(f"Sucesso! Produto '{nome_produto}' registrado com {quantidade} unidades.")
                        st.rerun() # Atualiza a tela para retroalimentar o analítico imediatamente
                    else:
                        st.error(f"Erro retornado pelo servidor: {response.text}")
                except Exception as e:
                    st.error(f"Erro de conexão: Certifique-se de que o Backend (Uvicorn) está rodando. Detalhe: {e}")

# =========================================================================
# TELA 4: CADASTRAR VENDA
# =========================================================================
elif aba == "Cadastrar Venda":
    st.title("💰 Registrar Nova Venda")
    st.write("Selecione o produto e preencha os dados da transação para salvar no banco de dados.")

    # 1. MAPEAMENTO: Criamos um dicionário vinculando o Nome exato da tabela 'produtos' ao seu ID
    mapeamento_produtos_id = {}
    if data_analytics and "produtos_detalhe" in data_analytics:
        for p in data_analytics["produtos_detalhe"]:
            nome = p.get("nome") or p.get("Nome do produto")
            id_prod = p.get("id")
            
            if nome and id_prod is not None:
                mapeamento_produtos_id[str(nome).strip()] = id_prod

    lista_produtos = list(mapeamento_produtos_id.keys())

    with st.form("form_cadastro_venda", clear_on_submit=True):
        if lista_produtos:
            # Exibe a lista nominal vinda do banco, mas a seleção guardará o texto para buscarmos o ID
            produto_selecionado = st.selectbox("Selecione o Produto Vendido *", options=lista_produtos)
        else:
            st.error("Erro: Não há produtos carregados do banco de dados para realizar uma venda.")
            produto_selecionado = None
            
        # Novos campos solicitados para a tabela vendas
        cliente = st.text_input("Nome do Cliente *")
        canal_venda = st.selectbox("Canal de Venda *", options=["Mercado Livre", "Shopee", "Site Próprio", "Amazon", "Geral"])
        
        # Campos financeiros e quantitativos
        valor_venda_unitario = st.number_input("Preço de Venda Unitário (R$) *", min_value=0.0, step=0.01, format="%.2f")
        quantidade_vendida = st.number_input("Quantidade Vendida *", min_value=1, step=1)
        data_venda = st.date_input("Data da Venda *")

        botao_venda = st.form_submit_button("Registrar Venda no Banco")

        if botao_venda:
            if not produto_selecionado:
                st.error("Selecione um produto válido da lista.")
            elif not cliente.strip():
                st.error("O campo 'Cliente' é obrigatório.")
            elif valor_venda_unitario <= 0:
                st.error("O preço unitário deve ser maior que zero.")
            else:
                # 2. RESGATE POR DEBAIXO DOS PANOS: Localiza o ID correspondente ao Nome selecionado
                produto_id = mapeamento_produtos_id.get(str(produto_selecionado).strip())
                
                if produto_id is None:
                    st.error("Falha interna ao recuperar o ID numérico deste produto.")
                else:
                    # 3. CÁLCULO E MONTAGEM DO SCHEMA EXATO DO SERVIDOR
                    valor_venda_total = valor_venda_unitario * quantidade_vendida

                    payload_venda = {
                        "produto_id": int(produto_id),
                        "cliente": cliente.strip(),
                        "canal_venda": canal_venda,
                        "quantidade": int(quantidade_vendida),
                        "valor_venda_total": float(valor_venda_total),
                        "data": str(data_venda)
                    }
                    
                    try:
                        url_venda = f"{API_URL}/vendas" if 'API_URL' in locals() else "http://host.docker.internal:8000/vendas"
                        response = requests.post(url_venda, json=payload_venda)
                        
                        if response.status_code in [200, 201]:
                            st.success(f"Venda para '{cliente}' registrada com sucesso! Atualizando sistema...")
                            st.rerun()
                        else:
                            st.error(f"Erro de validação no Schema do Servidor: {response.text}")
                    except Exception as e:
                        st.error(f"Erro de conexão com o Backend: {e}")