import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import tempfile
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="RODSTAR", page_icon="⚡", layout="centered")

# --- LIGAÇÃO NATIVA E DIRETA AO GOOGLE SHEETS ---
try:
    chave_bruta = st.secrets["segredos_do_google"]["chave"]
    credenciais = json.loads(chave_bruta, strict=False)
    url_planilha = st.secrets["segredos_do_google"]["planilha"]
    
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(credenciais, scopes=escopos)
    cliente = gspread.authorize(creds)
    
    planilha = cliente.open_by_url(url_planilha)
    aba_produtos = planilha.worksheet("Produtos")
    aba_vendas = planilha.worksheet("Vendas")
    
except Exception as e:
    st.error(f"🚨 Erro de Autenticação: {e}")
    st.stop()

# --- MEMÓRIA CACHE ---
@st.cache_data(ttl=30, show_spinner=False)
def ler_produtos():
    try:
        dados = aba_produtos.get_all_records()
        if not dados:
            return pd.DataFrame(columns=['ID', 'Nome', 'Marca', 'Custo', 'Venda', 'Quantidade', 'Alarme'])
        return pd.DataFrame(dados)
    except Exception:
        return pd.DataFrame(columns=['ID', 'Nome', 'Marca', 'Custo', 'Venda', 'Quantidade', 'Alarme'])

def salvar_produtos(df):
    df_save = df.copy()
    df_save.fillna("", inplace=True)
    dados = [df_save.columns.values.tolist()] + df_save.values.tolist()
    aba_produtos.clear()
    try:
        aba_produtos.update(values=dados, range_name="A1")
    except TypeError:
        aba_produtos.update("A1", dados)
    st.cache_data.clear()

@st.cache_data(ttl=30, show_spinner=False)
def ler_vendas():
    try:
        dados = aba_vendas.get_all_records()
        if not dados:
            return pd.DataFrame(columns=['ID', 'Produto_ID', 'Nome_Produto', 'Quantidade', 'Custo_Total', 'Venda_Total', 'Mes_Ano'])
        return pd.DataFrame(dados)
    except Exception:
        return pd.DataFrame(columns=['ID', 'Produto_ID', 'Nome_Produto', 'Quantidade', 'Custo_Total', 'Venda_Total', 'Mes_Ano'])

def salvar_vendas(df):
    df_save = df.copy()
    df_save.fillna("", inplace=True)
    dados = [df_save.columns.values.tolist()] + df_save.values.tolist()
    aba_vendas.clear()
    try:
        aba_vendas.update(values=dados, range_name="A1")
    except TypeError:
        aba_vendas.update("A1", dados)
    st.cache_data.clear()

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf(cliente_nome, itens, total):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Cabeçalho da Empresa
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 8, "RODSTAR", ln=True, align="C")
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, "WhatsApp: (69) 984178413", ln=True, align="C")
    pdf.cell(0, 5, "Endereco: Rua Pedro Americo, 55 - Bairro Pioneiros", ln=True, align="C")
    pdf.ln(5)
    
    # 2. Título e Cliente
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "ORCAMENTO / RECIBO", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, f"Cliente: {cliente_nome}", ln=True)
    pdf.cell(0, 8, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(0, 5, "-"*40, ln=True)
    
    # 3. Tabela de Produtos
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 8, "Qtd", border=1)
    pdf.cell(85, 8, "Produto", border=1)
    pdf.cell(45, 8, "Vlr. Unit", border=1)
    pdf.cell(45, 8, "Subtotal", border=1, ln=True)
    
    pdf.set_font("Arial", '', 10)
    for item in itens:
        pdf.cell(15, 8, str(item['Qtd']), border=1)
        nome_curto = str(item['Produto'])[:35]
        pdf.cell(85, 8, nome_curto, border=1)
        pdf.cell(45, 8, f"R$ {item['Preco_Un']:.2f}", border=1)
        pdf.cell(45, 8, f"R$ {item['Subtotal']:.2f}", border=1, ln=True)
        
    pdf.cell(0, 5, "", ln=True)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"VALOR TOTAL: R$ {total:.2f}", ln=True, align="R")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()

# --- FUNÇÃO 2 EM 1 (VENDA + PDF) ---
def processar_venda_callback(itens):
    mes_atual = datetime.now().strftime("%m/%Y")
    df_prod = ler_produtos()
    df_vendas = ler_vendas()
    
    novas_vendas = []
    for item in itens:
        idx = df_prod.index[df_prod['ID'] == item['ID']].tolist()[0]
        df_prod.at[idx, 'Quantidade'] = int(df_prod.at[idx, 'Quantidade']) - item['Qtd']
        
        novo_id_venda = 1 if df_vendas.empty else int(df_vendas['ID'].max()) + 1 + len(novas_vendas)
        custo_total = item['Custo_Un'] * item['Qtd']
        novas_vendas.append({
            'ID': novo_id_venda, 'Produto_ID': item['ID'], 'Nome_Produto': item['Produto'],
            'Quantidade': item['Qtd'], 'Custo_Total': custo_total, 
            'Venda_Total': item['Subtotal'], 'Mes_Ano': mes_atual
        })
    
    salvar_produtos(df_prod)
    if novas_vendas:
        df_vendas_atualizado = pd.concat([df_vendas, pd.DataFrame(novas_vendas)], ignore_index=True)
        salvar_vendas(df_vendas_atualizado)
    
    st.session_state.orcamento_itens = []
    st.session_state.mostrar_sucesso_venda = True

# --- MEMÓRIA DO CARRINHO E CLIENTE ---
if 'orcamento_itens' not in st.session_state:
    st.session_state.orcamento_itens = []
    
# --- BANNER PERSONALIZADO ---
st.markdown("""
    <div style="background-color: #1E3A8A; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 25px;">
        <h1 style="color: white; margin-bottom: 5px; font-size: 32px;">⚡ RODSTAR</h1>
        <p style="color: #60A5FA; margin: 0; font-size: 18px; font-weight: bold;">📱 WhatsApp: (69) 984178413</p>
        <p style="color: white; margin: 5px 0 0 0; font-size: 16px;">📍 Rua Pedro Américo, nº 55 - Bairro Pioneiros</p>
    </div>
""", unsafe_allow_html=True)

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Estoque", "➕ Novo", "✏️ Editar", "📝 Vender", "📈 Gráficos"])

# ================= ABA 1: ESTOQUE E ALERTAS =================
with aba1:
    df = ler_produtos()
    if df.empty:
        st.info("Nenhum produto cadastrado na planilha.")
    else:
        st.subheader("⚠️ Alertas de Estoque")
        
        df['Qtd_Num'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0)
        df['Alarme_Num'] = pd.to_numeric(df['Alarme'], errors='coerce').fillna(0)
        
        df_alertas = df[(df['Qtd_Num'] <= df['Alarme_Num']) | (df['Qtd_Num'] <= 1)].copy()
        
        if df_alertas.empty:
            st.success("✅ Estoque saudável! Nenhum produto em falta ou atingiu o alarme.")
        else:
            st.error("Os produtos abaixo atingiram o limite de alarme ou estão quase esgotados:")
            df_alertas_mostrar = df_alertas[['Nome', 'Marca', 'Quantidade', 'Alarme']].copy()
            st.dataframe(df_alertas_mostrar, use_container_width=True, hide_index=True)
            
        st.write("---")
        
        st.subheader("📦 Estoque Completo")
        pesquisa = st.text_input("🔍 Pesquisar produto por nome:", "")
        df_mostrar = df[['Nome', 'Marca', 'Custo', 'Venda', 'Quantidade']].copy()
        
        if pesquisa:
            df_mostrar = df_mostrar[df_mostrar['Nome'].str.contains(pesquisa, case=False, na=False)]
            
        if df_mostrar.empty:
            st.warning("Nenhum produto encontrado com esse nome.")
        else:
            df_mostrar['Total em Estoque'] = df_mostrar['Venda'].astype(float) * df_mostrar['Quantidade'].astype(int)
            df_mostrar['Custo'] = df_mostrar['Custo'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
            df_mostrar['Venda'] = df_mostrar['Venda'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
            df_mostrar['Total em Estoque'] = df_mostrar['Total em Estoque'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

# ================= ABA 2: NOVO PRODUTO =================
with aba2:
    st.subheader("Cadastrar Novo Produto")
    with st.form("form_produto", clear_on_submit=True):
        nome = st.text_input("Nome do Produto:")
        marca = st.text_input("Marca:")
        col1, col2 = st.columns(2)
        preco_custo = col1.number_input("Custo (R$):", min_value=0.0, step=0.50, format="%.2f")
        preco_venda = col2.number_input("Venda (R$):", min_value=0.0, step=0.50, format="%.2f")
        
        st.write("---")
        st.markdown("**Configurações de Estoque**")
        col3, col4 = st.columns(2)
        qtd_inicial = col3.number_input("Estoque Inicial:", min_value=0, step=1)
        alerta_min = col4.number_input("🚨 Disparar Alarme se chegar a:", min_value=0, step=1, help="O sistema avisará se o estoque chegar neste número.")
        
        if st.form_submit_button("Salvar Produto", use_container_width=True):
            if nome:
                df_prod = ler_produtos()
                novo_id = 1 if df_prod.empty else int(df_prod['ID'].max()) + 1
                novo_produto = pd.DataFrame([{
                    'ID': novo_id, 'Nome': nome, 'Marca': marca, 
                    'Custo': preco_custo, 'Venda': preco_venda, 
                    'Quantidade': qtd_inicial, 'Alarme': alerta_min
                }])
                df_atualizado = pd.concat([df_prod, novo_produto], ignore_index=True)
                salvar_produtos(df_atualizado)
                st.success("✅ Produto salvo diretamente no Google Sheets!")
                st.rerun()

# ================= ABA 3: EDITAR PRODUTO =================
with aba3:
    st.subheader("Editar ou Excluir Produto")
    df_prod = ler_produtos()
    
    if not df_prod.empty:
        opcoes = dict(zip(df_prod['Nome'], df_prod['ID']))
        prod_sel = st.selectbox("Selecione o Produto para Editar:", list(opcoes.keys()), key="edit_prod")
        
        idx = df_prod.index[df_prod['ID'] == opcoes[prod_sel]].tolist()[0]
        linha_atual = df_prod.iloc[idx]
        
        with st.form("form_editar_produto"):
            st.markdown(f"**Atualizando:** {linha_atual['Nome']}")
            
            novo_nome = st.text_input("Nome do Produto:", value=str(linha_atual['Nome']))
            nova_marca = st.text_input("Marca:", value=str(linha_atual['Marca']))
            
            c1, c2 = st.columns(2)
            novo_custo = c1.number_input("Custo (R$):", value=float(linha_atual['Custo']), step=0.50, format="%.2f")
            novo_venda = c2.number_input("Venda (R$):", value=float(linha_atual['Venda']), step=0.50, format="%.2f")
            
            c3, c4 = st.columns(2)
            nova_qtd = c3.number_input("Estoque Atual:", value=int(linha_atual['Quantidade']), step=1)
            novo_alarme = c4.number_input("Alarme:", value=int(linha_atual['Alarme']), step=1)
            
            if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                df_prod.at[idx, 'Nome'] = novo_nome
                df_prod.at[idx, 'Marca'] = nova_marca
                df_prod.at[idx, 'Custo'] = novo_custo
                df_prod.at[idx, 'Venda'] = novo_venda
                df_prod.at[idx, 'Quantidade'] = nova_qtd
                df_prod.at[idx, 'Alarme'] = novo_alarme
                
                salvar_produtos(df_prod)
                st.success("✅ Produto atualizado com sucesso!")
                st.rerun()
                
        st.write("---")
        with st.expander("⚠️ Área de Risco: Excluir Produto"):
            st.warning(f"Você está prestes a apagar o produto **{linha_atual['Nome']}** do sistema permanentemente.")
            if st.button("🗑️ Sim, apagar este produto", type="primary", use_container_width=True):
                df_prod = df_prod.drop(index=idx)
                salvar_produtos(df_prod)
                st.success("🗑️ Produto excluído com sucesso!")
                st.rerun()
    else:
        st.info("Cadastre um produto primeiro para poder editá-lo.")

# ================= ABA 4: VENDER / CARRINHO / PDF =================
with aba4:
    st.subheader("Orçamento e Venda")
    
    # Mensagem de sucesso após finalizar a venda
    if st.session_state.get('mostrar_sucesso_venda'):
        st.success("🎉 Venda finalizada! Estoque atualizado e Recibo salvo no seu celular.")
        st.session_state.mostrar_sucesso_venda = False
        
    nome_cliente = st.text_input("Nome do Cliente:", placeholder="Ex: João da Silva", key="cliente_venda_memoria")
    
    df_prod = ler_produtos()
    if not df_prod.empty:
        pesquisa_venda = st.text_input("🔍 Buscar produto para vender:", key="busca_venda")
        
        if pesquisa_venda:
            df_venda_filtrado = df_prod[df_prod['Nome'].str.contains(pesquisa_venda, case=False, na=False)]
        else:
            df_venda_filtrado = df_prod
            
        if df_venda_filtrado.empty:
            st.warning("Nenhum produto encontrado com esse nome.")
        else:
            opcoes_orc = dict(zip(df_venda_filtrado['Nome'], df_venda_filtrado.to_dict('records')))
            c_prod, c_qtd = st.columns([2, 1])
            prod_selecionado = c_prod.selectbox("Produto:", list(opcoes_orc.keys()))
            
            dados_prod = opcoes_orc[prod_selecionado]
            estoque_atual = int(dados_prod['Quantidade'])
            
            try:
                alarme_configurado = int(dados_prod['Alarme'])
            except:
                alarme_configurado = 0
                
            # 🚨 SISTEMA DE ALERTAS NA VENDA
            if estoque_atual == 0:
                st.error(f"❌ ESGOTADO! Sem unidades no estoque.")
            elif estoque_atual == 1:
                st.warning("⚠️ ATENÇÃO: Resta apenas 1 unidade no estoque!")
            elif estoque_atual <= alarme_configurado:
                st.warning(f"⚠️ ESTOQUE BAIXO: Restam apenas {estoque_atual} unidades.")

            # 🔒 BLOQUEIO DA QUANTIDADE MÁXIMA
            max_permitido = estoque_atual if estoque_atual > 0 else 1
            qtd_orc = c_qtd.number_input("Qtd:", min_value=1, max_value=max_permitido, step=1, key="qtd_orc")
                
            if st.button("➕ Adicionar ao Carrinho", use_container_width=True):
                if estoque_atual == 0:
                    st.error("Não é possível adicionar um produto esgotado!")
                elif qtd_orc > estoque_atual:
                    st.error(f"Estoque insuficiente! Só restam {estoque_atual} unidades.")
                else:
                    st.session_state.orcamento_itens.append({
                        "ID": dados_prod['ID'], "Produto": prod_selecionado, "Qtd": qtd_orc,
                        "Custo_Un": float(dados_prod['Custo']), "Preco_Un": float(dados_prod['Venda']),
                        "Subtotal": float(dados_prod['Venda']) * qtd_orc
                    })
                    st.success("Adicionado!")
                
    # MOSTRA O CARRINHO COM DESTAQUE E EDIÇÃO
    if st.session_state.orcamento_itens:
        st.write("---")
        
        if st.session_state.cliente_venda_memoria:
            st.markdown(f"<h3 style='color: #1E3A8A; text-align: center;'>🛒 Carrinho de: <span style='color: #EAB308;'>{st.session_state.cliente_venda_memoria}</span></h3>", unsafe_allow_html=True)
        else:
            st.markdown("<h3 style='color: #1E3A8A; text-align: center;'>🛒 Carrinho</h3>", unsafe_allow_html=True)
            
        total_orcamento = 0.0
        
        for i, item in enumerate(st.session_state.orcamento_itens):
            st.markdown(f"**{item['Qtd']}x - {item['Produto']}**")
            
            col_preco, col_sub, col_del = st.columns([3, 3, 2])
            
            novo_preco = col_preco.number_input("Preço Un.", value=float(item['Preco_Un']), step=1.0, format="%.2f", key=f"preco_edit_{i}")
            
            novo_subtotal = novo_preco * item['Qtd']
            col_sub.markdown(f"<div style='margin-top:32px; font-size: 16px;'>Sub: <b>R$ {novo_subtotal:.2f}</b></div>", unsafe_allow_html=True)
            
            st.session_state.orcamento_itens[i]['Preco_Un'] = novo_preco
            st.session_state.orcamento_itens[i]['Subtotal'] = novo_subtotal
            total_orcamento += novo_subtotal
            
            st.markdown("""<style>div.stButton > button:first-child { margin-top: 22px; }</style>""", unsafe_allow_html=True)
            if col_del.button("🗑️", key=f"del_{i}", use_container_width=True, help="Remover item"):
                st.session_state.orcamento_itens.pop(i)
                st.rerun()
                
            st.write("---")
            
        st.subheader(f"Total a Pagar: R$ {total_orcamento:.2f}")
        
        # GERAÇÃO DO PDF PARA OS BOTÕES
        cliente_pdf = st.session_state.cliente_venda_memoria if st.session_state.cliente_venda_memoria else "Consumidor Final"
        pdf_bytes = gerar_pdf(cliente_pdf, st.session_state.orcamento_itens, total_orcamento)
        
        # BOTÕES LADO A LADO
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            st.download_button(
                label="📄 Apenas Orçamento",
                data=pdf_bytes,
                file_name=f"Orcamento_{cliente_pdf.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with col_btn2:
            st.download_button(
                label="✅ Finalizar Venda e Recibo",
                data=pdf_bytes,
                file_name=f"Recibo_Venda_{cliente_pdf.replace(' ', '_')}.pdf",
                mime="application/pdf",
                on_click=processar_venda_callback,
                args=(st.session_state.orcamento_itens,),
                type="primary",
                use_container_width=True
            )
                
        if st.button("🗑️ Limpar Carrinho", use_container_width=True):
            st.session_state.orcamento_itens = []
            st.rerun()

# ================= ABA 5: GRÁFICOS E RELATÓRIOS =================
with aba5:
    st.subheader("Desempenho e Inteligência")
    df_vendas = ler_vendas()
    if df_vendas.empty:
        st.info("Nenhuma venda finalizada ainda.")
    else:
        meses = df_vendas['Mes_Ano'].unique()
        mes_selecionado = st.selectbox("Selecione o Mês:", meses)
        
        dados_mes = df_vendas[df_vendas['Mes_Ano'] == mes_selecionado]
        faturamento = dados_mes['Venda_Total'].astype(float).sum()
        custo = dados_mes['Custo_Total'].astype(float).sum()
        lucro = faturamento - custo
        
        st.metric("Faturamento Mensal", f"R$ {faturamento:.2f}")
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("Custo da Mercadoria", f"R$ {custo:.2f}")
        c_m2.metric("Lucro Bruto", f"R$ {lucro:.2f}")
        
        st.write("---")
        
        ranking = dados_mes.groupby('Nome_Produto').agg({
            'Quantidade': 'sum',
            'Venda_Total': 'sum'
        }).reset_index()
        
        st.write("📈 **Top Produtos MAIS Vendidos**")
        mais_vendidos = ranking.sort_values(by='Quantidade', ascending=False).head(10)
        mais_vendidos['Venda_Total'] = mais_vendidos['Venda_Total'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
        st.dataframe(mais_vendidos.rename(columns={'Nome_Produto': 'Produto', 'Quantidade': 'Qtd Vendida', 'Venda_Total': 'Receita (R$)'}), hide_index=True, use_container_width=True)
        
        st.write("---")
        st.write("📉 **Top Produtos MENOS Vendidos**")
        menos_vendidos = ranking.sort_values(by='Quantidade', ascending=True).head(10)
        menos_vendidos['Venda_Total'] = menos_vendidos['Venda_Total'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
        st.dataframe(menos_vendidos.rename(columns={'Nome_Produto': 'Produto', 'Quantidade': 'Qtd Vendida', 'Venda_Total': 'Receita (R$)'}), hide_index=True, use_container_width=True)
        
        st.write("---")
        st.write("📊 **Gráfico Visual de Vendas**")
        st.bar_chart(ranking.set_index('Nome_Produto')['Quantidade'])
