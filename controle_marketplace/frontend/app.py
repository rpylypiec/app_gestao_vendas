import streamlit as st
import requests
import pandas as pd

API_URL = "http://host.docker.internal:8000"

st.set_page_config(page_title="Dashboard Marketplace", layout="wide")

# --- BUSCA DE DADOS ---
@st.cache_data(ttl=5)
def fetch_analytics_data():
    try:
        response = requests.get(f"{API_URL}/analytics")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

@st.cache_data(ttl=5)
def fetch_raw_vendas():
    try:
        # Puxa o histórico de vendas brutas do back-end para conseguir a Dimensão Tempo
        response = requests.get(f"{API_URL}/vendas")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

data_analytics = fetch_analytics_data()
vendas_brutas = fetch_raw_vendas()

# --- NAVEGAÇÃO LATERAL ---
st.sidebar.title("Navegação")
aba = st.sidebar.radio("Ir para:", ["Analytics", "Registros"])

# =========================================================================
# TELA 1: ANALYTICS
# =========================================================================
if aba == "Analytics":
    st.title("📊 Painel Analítico de Performance")
    
    if data_analytics:
        kpis = data_analytics.get("KPIs", {})
        total_revenue = kpis.get("total_faturado", 0.0)
        total_investment = kpis.get("total_investido", 0.0)
        
        # Cálculos de ROI
        roi_bruto_rs = total_revenue - total_investment
        roi_percentual = (roi_bruto_rs / total_investment * 100) if total_investment > 0 else 0.0

# --- CÁLCULO DINÂMICO DOS BIG NUMBERS BASEADO NOS FILTROS ---
        if not df_filtrado.empty:
            # Localiza dinamicamente as colunas de faturamento e investimento no DataFrame filtrado
            col_valor = next((c for c in ['valor_venda_total', 'valor', 'revenue'] if c in df_filtrado.columns), None)
            
            # Nota: Caso seu DataFrame de vendas não possua a coluna de investimento direto por linha, 
            # mantemos o proporcional ou o investimento total filtrado por mês/ano. 
            # Aqui calculamos a soma do faturamento do período selecionado:
            total_revenue = df_filtrado[col_valor].sum() if col_valor else 0.0
            
            # Para o investimento, se ele vier consolidado por mês/ano nos KPIs originais, 
            # podemos recalcular ou buscar o proporcional do período. Uma abordagem segura e comum 
            # para dashboards transacionais é filtrar o investimento baseado nos meses/anos selecionados:
            kpis_estaticos = data_analytics.get("KPIs", {})
            total_investment_base = kpis_estaticos.get("total_investido", 0.0)
            
            # Se o usuário filtrou menos meses, o investimento se ajusta proporcionalmente ao faturamento
            total_investment_global = kpis_estaticos.get("total_investido", 0.0)
            total_revenue_global = kpis_estaticos.get("total_faturado", 1.0) # Evita divisão por zero
            
            # Calcula o investimento proporcional ao período selecionado
            proporcao = total_revenue / total_revenue_global if total_revenue_global > 0 else 0
            total_investment = total_investment_global * proporcao
        else:
            total_revenue = 0.0
            total_investment = 0.0

        # Cálculos de ROI baseados nos valores dinâmicos do período
        roi_bruto_rs = total_revenue - total_investment
        roi_percentual = (roi_bruto_rs / total_investment * 100) if total_investment > 0 else 0.0

        # --- EXIBIÇÃO DOS BIG NUMBERS (Formatação PT-BR) ---
        col1, col2, col3, col4 = st.columns(4)
        
        def formatar_moeda_br(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def formatar_porcentagem_br(valor):
            return f"{valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")

        with col1:
            st.metric(label="Total Faturado", value=formatar_moeda_br(total_revenue))
        with col2:
            st.metric(label="Total Investido", value=formatar_moeda_br(total_investment))
        with col3:
            st.metric(label="ROI (R$)", value=formatar_moeda_br(roi_bruto_rs))
        with col4:
            st.metric(label="ROI (%)", value=formatar_porcentagem_br(roi_percentual))

# --- 🛠️ FILTROS DINÂMICOS NA BARRA LATERAL (Baseados na Dimensão Tempo) ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filtros do Painel")
        
        if vendas_brutas and isinstance(vendas_brutas, list):
            df_vendas = pd.DataFrame(vendas_brutas)
            col_data = next((c for c in ['data_venda', 'data', 'date'] if c in df_vendas.columns), None)
            col_valor = next((c for c in ['valor_venda_total', 'valor', 'revenue'] if c in df_vendas.columns), None)
            
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
                
                # Construção da Dimensão Tempo no DataFrame Raiz
                df_vendas['Ano'] = df_vendas[col_data].dt.year
                df_vendas['Mes_Num'] = df_vendas[col_data].dt.month
                df_vendas['Mes_Nome'] = df_vendas[col_data].dt.strftime('%B').map(meses_pt)
                df_vendas['Semana_Num'] = df_vendas[col_data].dt.isocalendar().week
                df_vendas['Semana_Str'] = "Semana " + df_vendas['Semana_Num'].astype(str)
                
                # Criando os seletores na Sidebar
                anos_disponiveis = sorted(df_vendas['Ano'].unique())
                ano_selecionado = st.sidebar.multiselect("Ano", options=anos_disponiveis, default=anos_disponiveis)
                
                meses_disponiveis = sorted(df_vendas['Mes_Nome'].unique(), key=lambda x: list(meses_pt.values()).index(x))
                mes_selecionado = st.sidebar.multiselect("Mês", options=meses_disponiveis, default=meses_disponiveis)
                
                datas_disponiveis = sorted(df_vendas[col_data].dt.date.unique())
                data_inicio, data_fim = st.sidebar.date_input(
                    "Período de Data", 
                    value=(min(datas_disponiveis), max(datas_disponiveis)),
                    min_value=min(datas_disponiveis),
                    max_value=max(datas_disponiveis)
                )
                
                # Aplicando os filtros encadeados no DataFrame
                df_filtrado = df_vendas[
                    (df_vendas['Ano'].isin(ano_selecionado)) & 
                    (df_vendas['Mes_Nome'].isin(mes_selecionado)) & 
                    (df_vendas[col_data].dt.date >= data_inicio) & 
                    (df_vendas[col_data].dt.date <= data_fim)
                ]
                
                # --- 📈 1. Gráfico de Linhas (Faturamento por DATA DA VENDA) ---
                st.subheader("📈 Evolução do Faturamento ao Longo do Tempo")
                
                if not df_filtrado.empty:
                    # Exibição opcional da tabela auditada (usando os dados já filtrados)
                    if st.checkbox("Visualizar colunas da Dimensão Tempo obtidas"):
                        df_view = df_filtrado.copy()
                        df_view[col_data] = df_view[col_data].dt.strftime('%d/%m/%Y')
                        st.dataframe(
                            df_view[[col_data, 'Ano', 'Mes_Num', 'Mes_Nome', 'Semana_Num', 'Semana_Str', col_valor]],
                            column_config={col_valor: st.column_config.NumberColumn("Valor Venda Total", format="R$ %.2f")}
                        )

                    # Agrupamento para o gráfico
                    df_timeline = df_filtrado.groupby(col_data)[col_valor].sum().reset_index()
                    df_timeline = df_timeline.sort_values(by=col_data)
                    
                    import plotly.express as px
                    
                    # Agrupamento para o gráfico
                    df_timeline = df_filtrado.groupby(col_data)[col_valor].sum().reset_index()
                    df_timeline = df_timeline.sort_values(by=col_data)

                    # Ativamos os rótulos de dados textuais acima da linha formatados em PT-BR
                    fig = px.line(
                        df_timeline, 
                        x=col_data, 
                        y=col_valor,
                        text=df_timeline[col_valor].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    )
                    
                    # Ajuste definitivo do layout com os separadores globais brasileiros
                    fig.update_layout(
                        xaxis=dict(
                            title=None,
                            tickformat="%d/%m/%Y",
                            showgrid=False
                        ),
                        yaxis=dict(
                            title=None,
                            showgrid=False,
                            # A mágica está aqui: especificamos o prefixo R$ e o padrão de duas casas decimais
                            tickprefix="R$ ",
                            tickformat=".,2f"
                        ),
                        # Define os separadores globais do gráfico: vírgula para decimal e ponto para milhar
                        separators=",.",
                        margin=dict(l=20, r=20, t=30, b=20),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    
                    # Garantindo o posicionamento do rótulo acima da linha e o formato do hover (mouse)
                    fig.update_traces(
                        line=dict(width=2.5),
                        textposition="top center",
                        hovertemplate="<b>Data:</b> %{x|%d/%m/%Y}<br><b>Faturamento:</b> R$ %{y:,.2f}<extra></extra>"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Nenhum dado encontrado para os filtros selecionados.")
            else:
                st.info("Colunas temporais não identificadas na resposta de vendas brutas.")
        else:
            st.info("Aguardando novas inserções de vendas para alimentar a linha do tempo.")

# --- 📊 2. Gráfico de Barras HORIZONTAIS (Produto vs Faturamento - INTEGRADO AOS FILTROS) ---
        st.subheader("📊 Faturamento por Produto (Visão Horizontal)")
        
        if not df_filtrado.empty:
            # 1. Mapeamos dinamicamente as colunas de transações do df_filtrado
            col_prod_id = next((c for c in ['produto_id', 'produto'] if c in df_filtrado.columns), None)
            col_valor = next((c for c in ['valor_venda_total', 'valor', 'revenue'] if c in df_filtrado.columns), None)
            
            # 2. Buscamos a tabela oficial de produtos do backend para obter o De/Para exato de ID para Nome
            try:
                prod_req = requests.get(f"{API_URL}/produtos")
                mapeamento_nomes = {p['id']: p['nome'] for p in prod_req.json()} if prod_req.status_code == 200 else {}
            except:
                mapeamento_nomes = {}
                
            if col_prod_id and col_valor:
                # 3. Agrupamos as vendas filtradas por data usando o ID do produto
                df_grouped = df_filtrado.groupby(col_prod_id)[col_valor].sum().reset_index()
                
                # 4. Convertemos o ID para o Nome por extenso (Garante o texto correto no eixo Y)
                df_grouped['nome'] = df_grouped[col_prod_id].map(mapeamento_nomes)
                df_grouped['nome'] = df_grouped['nome'].fillna(df_grouped[col_prod_id].astype(str))
                
                # 5. Renomeamos a coluna de valor para bater exatamente com a sua estrutura de referência
                df_grouped['faturamento_acumulado'] = df_grouped[col_valor]
                
                # Recriamos o df_prod estruturado que o seu código original valida
                df_prod = df_grouped[['nome', 'faturamento_acumulado']]
                
                # --- DAQUI PARA BAIXO O SEU CÓDIGO ORIGINAL FOI MANTIDO 100% FIEL ---
                if "faturamento_acumulado" in df_prod.columns and "nome" in df_prod.columns:
                    # 1. Mostrar apenas itens vendidos (faturamento maior que zero)
                    df_bar_filtered = df_prod[df_prod["faturamento_acumulado"] > 0].copy()
                    
                    if not df_bar_filtered.empty:
                        # 2. Apresentar em ordem decrescente
                        # Nota: O Plotly renderiza de baixo para cima nos gráficos horizontais, 
                        # então ordenamos de forma crescente (ascending=True) para o maior SKU ficar no topo do gráfico.
                        df_bar_filtered = df_bar_filtered.sort_values(by="faturamento_acumulado", ascending=True)
                        
                        # Criando o gráfico de barras horizontais (x=valor, y=nome)
                        fig_bar = px.bar(
                            df_bar_filtered,
                            x="faturamento_acumulado",
                            y="nome",
                            orientation="h",
                            # 3. Apresentar rótulo de dados formatado em PT-BR dentro da barra
                            text=df_bar_filtered["faturamento_acumulado"].apply(
                                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            )
                        )
                        
                        # 4 & 5. Configurações visuais de grade, eixos e moeda brasileira
                        fig_bar.update_layout(
                            xaxis=dict(
                                title=None,
                                showgrid=False,           # 4. Remover linhas de grade verticais
                                tickprefix="R$ ",         # 5. Rótulo do eixo X em moeda brasileira
                                tickformat=".,2f"
                            ),
                            yaxis=dict(
                                title=None,
                                showgrid=False            # 4. Remover linhas de grade horizontais
                            ),
                            separators=",.",              # Força o padrão decimal com vírgula e milhar com ponto
                            margin=dict(l=20, r=40, t=10, b=20),
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        
                        # Ajuste fino da posição dos rótulos de dados
                        fig_bar.update_traces(
                            textposition="inside",        # Exibe os valores dentro/junto das barras de forma limpa
                            insidetextanchor="end",
                            hovertemplate="<b>Produto:</b> %{y}<br><b>Faturamento:</b> R$ %{x:,.2f}<extra></extra>"
                        )
                        
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        st.info("Nenhum produto com faturamento registrado no período selecionado.")
                else:
                    st.info("Dados estruturados de faturamento indisponíveis para o gráfico de barras.")
        else:
            st.warning("Sem dados de produtos detalhados disponíveis para os filtros selecionados.")

# =========================================================================
# TELA 2: REGISTROS
# =========================================================================
elif aba == "Registros":
    st.title("📋 Tabela de Registros Completos")
    if data_analytics and "produtos_detalhe" in data_analytics:
        st.dataframe(pd.DataFrame(data_analytics["produtos_detalhe"]), use_container_width=True)
    else:
        st.info("Nenhum dado encontrado para exibir na tabela.")