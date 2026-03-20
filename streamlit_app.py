import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import tempfile
from datetime import datetime

st.set_page_config(page_title="Sistema PDV", page_icon="🏢", layout="centered")

# --- CONEXÃO COM GOOGLE SHEETS ---
# Essa linha mágica faz a ponte entre o seu app e o seu Google Drive
conn = st.connection("gsheets", type=GSheetsConnection)

def ler_produtos():
    return conn.read(worksheet="Produtos", ttl=0).dropna(how="all")

def salvar_produtos(df):
    conn.update(worksheet="Produtos", data=df)

def ler_vendas():
    return conn.read(worksheet="Vendas", ttl=0).dropna(how="all")

def salvar_vendas(df):
    conn.update(worksheet="Vendas", data=df)

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf(cliente, itens, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "ORCAMENTO / PEDIDO", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(0, 10, "-"*40, ln=True)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(15, 8, "Qtd", border=1)
    pdf.cell(85, 8, "Produto", border=1)
    pdf.cell(45, 8, "Vlr. Unitario", border=1)
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

# --- MEMÓRIA DO CARRINHO ---
if 'orcamento_itens' not in st.session_state:
    st.session_state.orcamento_itens = []

# --- INTERFACE ---
st.title("🏢 Gestão e PDV na Nuvem")

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Estoque", "➕ Novo", "🔄 Ajuste", "📝 Vender", "📈 Gráficos"])

# ================= ABA 1: ESTOQUE =================
with aba1:
    st.subheader("Estoque Atual")
    try:
        df = ler_produtos()
        if df.empty:
            st.info("Nenhum produto cadastrado na planilha.")
        else:
            df_mostrar = df[['Nome', 'Marca', 'Venda', 'Quantidade']].copy()
            df_mostrar['Venda'] = df_mostrar['Venda'].apply(lambda x: f"R$ {float(x):.2f}".replace('.', ','))
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning("Aguardando conexão com o Google Sheets...")

# ================= ABA 2: NOVO PRODUTO =================
with aba2:
    st.subheader("Cadastrar Produto")
    with st.form("form_produto", clear_on_submit=True):
        nome = st.text_input("Nome do Produto:")
        marca = st.text_input("Marca:")
        col1, col2 = st.columns(2)
        preco_custo = col1.number_input("Custo (R$):", min_value=0.0, step=0.50, format="%.2f")
        preco_venda = col2.number_input("Venda (R$):", min_value=0.0, step=0.50, format="%.2f")
        col3, col4 = st.columns(2)
        qtd_inicial = col3.number_input("Estoque Inicial:", min_value=0, step=1)
        alerta_min = col4.number_input("Alarme:", min_value=0, step=1)
        
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
                st.success("✅ Produto salvo direto no Google Sheets!")

# ================= ABA 3: AJUSTE MANUAL =================
with aba3:
    st.subheader("Entrada e Perdas")
    try:
        df_prod = ler_produtos()
        if not df_prod.empty:
            opcoes = dict(zip(df_prod['Nome'], df_prod['ID']))
            prod_sel = st.selectbox("Produto:", list(opcoes.keys()), key="ajuste_prod")
            qtd_mov = st.number_input("Qtd:", min_value=1, step=1)
            
            c1, c2 = st.columns(2)
            if c1.button("🟢 Entrada"):
                idx = df_prod.index[df_prod['ID'] == opcoes[prod_sel]].tolist()[0]
                df_prod.at[idx, 'Quantidade'] = int(df_prod.at[idx, 'Quantidade']) + qtd_mov
                salvar_produtos(df_prod)
                st.success("Estoque adicionado!")
                
            if c2.button("🔴 Saída (Perda)"):
                idx = df_prod.index[df_prod['ID'] == opcoes[prod_sel]].tolist()[0]
                nova_qtd = int(df_prod.at[idx, 'Quantidade']) - qtd_mov
                if nova_qtd < 0:
                    st.error("Estoque insuficiente!")
                else:
                    df_prod.at[idx, 'Quantidade'] = nova_qtd
                    salvar_produtos(df_prod)
                    st.success("Estoque reduzido!")
    except:
        st.write("Conecte a planilha para ver os produtos.")

# ================= ABA 4: VENDER / CARRINHO / PDF =================
with aba4:
    st.subheader("Orçamento e Venda")
    nome_cliente = st.text_input("Nome do Cliente:", placeholder="Ex: João da Silva")
    
    try:
        df_prod = ler_produtos()
        if not df_prod.empty:
            opcoes_orc = dict(zip(df_prod['Nome'], df_prod.to_dict('records')))
            c_prod, c_qtd = st.columns([2, 1])
            prod_selecionado = c_prod.selectbox("Produto:", list(opcoes_orc.keys()))
            qtd_orc = c_qtd.number_input("Qtd:", min_value=1, step=1, key="qtd_orc")
                
            if st.button("➕ Adicionar ao Carrinho", use_container_width=True):
                dados = opcoes_orc[prod_selecionado]
                if qtd_orc > int(dados['Quantidade']):
                    st.error(f"Estoque insuficiente! Só restam {dados['Quantidade']} unidades.")
                else:
                    st.session_state.orcamento_itens.append({
                        "ID": dados['ID'], "Produto": prod_selecionado, "Qtd": qtd_orc,
                        "Custo_Un": float(dados['Custo']), "Preco_Un": float(dados['Venda']),
                        "Subtotal": float(dados['Venda']) * qtd_orc
                    })
                    st.success("Adicionado!")
                
        # MOSTRA O CARRINHO
        if st.session_state.orcamento_itens:
            st.write("---")
            total_orcamento = sum(item['Subtotal'] for item in st.session_state.orcamento_itens)
            
            for item in st.session_state.orcamento_itens:
                st.write(f"▫️ {item['Qtd']}x {item['Produto']} | Un: R$ {item['Preco_Un']:.2f} | Sub: R$ {item['Subtotal']:.2f}")
                
            st.subheader(f"Total a Pagar: R$ {total_orcamento:.2f}")
            st.write("---")
            
            # PDF
            cliente_pdf = nome_cliente if nome_cliente else "Consumidor Final"
            pdf_bytes = gerar_pdf(cliente_pdf, st.session_state.orcamento_itens, total_orcamento)
            st.download_button(
                label="📄 Baixar PDF do Orçamento",
                data=pdf_bytes,
                file_name=f"Orcamento_{cliente_pdf.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
                
            # FINALIZAR VENDA
            if st.button("✅ Finalizar Venda", type="primary", use_container_width=True):
                mes_atual = datetime.now().strftime("%m/%Y")
                df_vendas = ler_vendas()
                
                novas_vendas = []
                for item in st.session_state.orcamento_itens:
                    # Baixa no estoque
                    idx = df_prod.index[df_prod['ID'] == item['ID']].tolist()[0]
                    df_prod.at[idx, 'Quantidade'] = int(df_prod.at[idx, 'Quantidade']) - item['Qtd']
                    
                    # Registra a venda
                    novo_id_venda = 1 if df_vendas.empty else int(df_vendas['ID'].max()) + 1
                    custo_total = item['Custo_Un'] * item['Qtd']
                    novas_vendas.append({
                        'ID': novo_id_venda, 'Produto_ID': item['ID'], 'Nome_Produto': item['Produto'],
                        'Quantidade': item['Qtd'], 'Custo_Total': custo_total, 
                        'Venda_Total': item['Subtotal'], 'Mes_Ano': mes_atual
                    })
                
                # Salva as duas planilhas
                salvar_produtos(df_prod)
                df_vendas_atualizado = pd.concat([df_vendas, pd.DataFrame(novas_vendas)], ignore_index=True)
                salvar_vendas(df_vendas_atualizado)
                
                st.session_state.orcamento_itens = []
                st.success("🎉 Venda salva na Planilha e estoque atualizado!")
                st.rerun()
                    
            if st.button("🗑️ Limpar Carrinho", use_container_width=True):
                st.session_state.orcamento_itens = []
                st.rerun()
    except Exception as e:
         pass # Ignora erros até a planilha estar conectada

# ================= ABA 5: GRÁFICOS E RELATÓRIOS =================
with aba5:
    st.subheader("Desempenho e Gráficos")
    try:
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
            c_m1.metric("Custo Mercadoria", f"R$ {custo:.2f}")
            c_m2.metric("Lucro Bruto", f"R$ {lucro:.2f}")
            
            st.write("---")
            st.write("📊 **Gráfico: Produtos Mais Vendidos**")
            
            ranking = dados_mes.groupby('Nome_Produto')['Quantidade'].sum().reset_index()
            ranking = ranking.sort_values(by='Quantidade', ascending=False)
            st.bar_chart(ranking.set_index('Nome_Produto'))
    except:
        st.write("Conecte a planilha para ver os relatórios.")
