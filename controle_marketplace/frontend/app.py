import streamlit as st
import requests
import pandas as pd

API_URL = "http://host.docker.internal:8000"

st.set_page_config(page_title="Marketplace Data Analytics", layout="wide", initial_sidebar_state="expanded")
st.title("📈 Sistema Integrado de Gestão - Marketplace")

# Sidebar de controle
aba = st.sidebar.radio("Módulos", ["📊 Dashboard & Analytics", "📥 Painel Operacional (Lançamentos)"])

if aba == "📊 Dashboard & Analytics":
    try:
        response = requests.get(f"{API_URL}/analytics").json()
    except Exception:
        st.error("Erro crítico: Não foi possível estabelecer conexão com o Back-end FastAPI na porta 8000.")
        st.stop()
        
    if "KPIs" in response and response["KPIs"]:
        kpis = response["KPIs"]
        
        # Grid de KPIs principais idêntico à sua planilha antiga
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Investido", f"R$ {kpis['total_investido']:.2f}")
        c2.metric("Total Faturado", f"R$ {kpis['total_faturado']:.2f}")
        c3.metric("Quantidade de Vendas", f"{kpis['quantidade_vendas']} un")
        c4.metric("Ticket Médio", f"R$ {kpis['ticket_medio']:.2f}")
        
        # Cor de alerta dinâmico para ROI negativo/positivo
        roi_delta = f"R$ {kpis['lucro_total']:.2f}"
        c5.metric("ROI Geral", f"{kpis['roi_percentual']:.2f}%", delta=roi_delta)
        
        st.markdown("---")
        
        col_tab, col_graf = st.columns([3, 2])
        
        with col_tab:
            st.subheader("📋 Painel de Estoque e Margens")
            df_resumo = pd.DataFrame(response["produtos_detalhe"])
            if not df_resumo.empty:
                st.dataframe(
                    df_resumo.rename(columns={
                        'nome': 'Produto', 'categoria': 'Categoria', 
                        'estoque_atual': 'Estoque Atual', 'qtd_vendida': 'Vendido',
                        'faturamento_acumulado': 'Faturamento Acumulado (R$)', 
                        'lucro_real': 'Lucro Real (R$)', 'margem_percentual': 'Margem (%)'
                    }), 
                    use_container_width=True,
                    hide_index=True
                )
        
        with col_graf:
            st.subheader("🛒 Faturamento por Canal de Venda")
            if response["canais_venda"]:
                df_canais = pd.DataFrame(list(response["canais_venda"].items()), columns=['Canal de Venda', 'Volume Faturado (R$)'])
                st.bar_chart(data=df_canais, x='Canal de Venda', y='Volume Faturado (R$)', color='#29B5E8')
            else:
                st.info("Nenhuma venda processada até o momento.")
    else:
        st.info("O banco de dados do Postgres está vazio. Vá até o Painel Operacional para alimentar o sistema.")

elif aba == "📥 Painel Operacional (Lançamentos)":
    try:
        produtos = requests.get(f"{API_URL}/produtos").json()
        dict_prod = {p['nome']: p['id'] for p in produtos}
    except Exception:
        dict_prod = {}
        st.error("Erro ao puxar dimensão de produtos da API.")

    tab1, tab2, tab3 = st.tabs(["🆕 Novo Produto (SKU)", "🛒 Registrar Compra (Entrada)", "💰 Registrar Venda (Saída)"])
    
    with tab1:
        with st.form("form_prod", clear_on_submit=True):
            nome_p = st.text_input("Nome Descritivo do Produto")
            cat_p = st.selectbox("Categoria", ["Eletrônicos", "Ferramentas", "Casa & Cozinha", "Moda", "Outros"])
            if st.form_submit_button("Salvar no Postgres"):
                if nome_p:
                    res = requests.post(f"{API_URL}/produtos", json={"nome": nome_p, "categoria": cat_p})
                    if res.status_code == 200:
                        st.success(f"'{nome_p}' cadastrado com sucesso!")
                        st.experimental_rerun()
                else:
                    st.warning("O nome do SKU não pode ser vazio.")
                    
    with tab2:
        if dict_prod:
            with st.form("form_compra", clear_on_submit=True):
                prod_c = st.selectbox("Selecione o Produto", list(dict_prod.keys()), key="c_sku")
                qtd_c = st.number_input("Quantidade Comprada", min_value=1, step=1)
                val_c = st.number_input("Valor Unitário Pago (Já com desconto/cupom)", min_value=0.01, format="%.2f")
                frete_c = st.number_input("Valor do Frete do Lote", min_value=0.0, format="%.2f")
                
                if st.form_submit_button("Confirmar Entrada"):
                    custo_total_calculado = (qtd_c * val_c) + frete_c
                    payload = {
                        "produto_id": dict_prod[prod_c],
                        "quantidade": qtd_c,
                        "custo_total": custo_total_calculado
                    }
                    requests.post(f"{API_URL}/compras", json=payload)
                    st.success(f"Estoque abastecido com mais {qtd_c} unidades!")
        else:
            st.info("Cadastre um Produto primeiro antes de dar entrada de notas.")
            
    with tab3:
        if dict_prod:
            with st.form("form_venda", clear_on_submit=True):
                prod_v = st.selectbox("Selecione o Produto vendido", list(dict_prod.keys()), key="v_sku")
                qtd_v = st.number_input("Quantidade Vendida", min_value=1, step=1)
                val_v = st.number_input("Preço de Venda Unitário", min_value=0.01, format="%.2f")
                canal_v = st.selectbox("Canal de Venda", ["Facebook Marketplace", "Instagram", "Whatsapp", "Direto / Indicação"])
                cliente_v = st.text_input("Nome do Cliente local")
                
                if st.form_submit_button("Lançar Venda (Baixa de Estoque)"):
                    receita_total_calculada = qtd_v * val_v
                    payload = {
                        "produto_id": dict_prod[prod_v],
                        "quantidade": qtd_v,
                        "valor_venda_total": receita_total_calculada,
                        "canal_venda": canal_v,
                        "cliente": cliente_v
                    }
                    res = requests.post(f"{API_URL}/vendas", json=payload)
                    
                    if res.status_code == 200:
                        st.success("Venda processada com sucesso no Postgres!")
                    else:
                        st.error(res.json().get("detail", "Erro desconhecido ao validar estoque."))
        else:
            st.info("Cadastre um Produto primeiro antes de dar saída.")