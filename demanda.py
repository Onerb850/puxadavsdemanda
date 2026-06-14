import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(layout="wide", page_title="Gestão de Puxada")
st.title("📦 Acompanhamento de Puxada vs Demanda (HL)")

# ==========================================
# TRATAMENTO E CARREGAMENTO DOS DADOS (VIA GOOGLE DRIVE)
# ==========================================
@st.cache_data(ttl=600) # O cache expira a cada 10 minutos para garantir dados atualizados
def carregar_dados():
    try:
        # 1. Carregar DEMANDA do Google Drive
        id_demanda = '1Ijnhb4vnXv62Rwma52wPzx4GOcK2PxDu'
        url_demanda = f'https://drive.google.com/uc?id={id_demanda}'
        df_demanda = pd.read_csv(url_demanda, sep=';', encoding='utf-8-sig')
        
        df_demanda.columns = df_demanda.columns.str.strip()
        df_demanda = df_demanda[['Cod SKU', 'Descrição SKU', 'Demanda Final']]
        df_demanda = df_demanda.rename(columns={'Cod SKU': 'SKU', 'Demanda Final': 'Demanda_HL'})
        df_demanda['Demanda_HL'] = pd.to_numeric(df_demanda['Demanda_HL'].astype(str).str.replace(',', '.'), errors='coerce')
        
        # 2. Carregar PUXADO do Google Drive
        id_puxado = '1OYW9k-p2ZqJHw7I0gC9lHRuHVpDiKvzs'
        url_puxado = f'https://drive.google.com/uc?id={id_puxado}'
        df_puxado = pd.read_csv(url_puxado, sep=';', encoding='latin1')
        
        df_puxado.columns = df_puxado.columns.str.strip()
        df_puxado = df_puxado[['Data Puxada', 'Cód. Prod', 'Quantidade HL']]
        df_puxado = df_puxado.rename(columns={'Cód. Prod': 'SKU', 'Quantidade HL': 'Puxado_HL'})
        df_puxado['Puxado_HL'] = pd.to_numeric(df_puxado['Puxado_HL'].astype(str).str.replace(',', '.'), errors='coerce')
        
        # 3. Tratar a Data 
        df_puxado['Data Puxada'] = pd.to_datetime(df_puxado['Data Puxada'], dayfirst=True, format='mixed', errors='coerce')
        df_puxado['Semana'] = 'S' + ((df_puxado['Data Puxada'].dt.day - 1) // 7 + 1).astype(str)
        
        df_puxado_total = df_puxado.groupby('SKU')['Puxado_HL'].sum().reset_index()
        df_final = pd.merge(df_demanda, df_puxado_total, on='SKU', how='left')
        df_final['Puxado_HL'] = df_final['Puxado_HL'].fillna(0)
        df_final['Demanda_HL'] = df_final['Demanda_HL'].fillna(0)
        
        # 4. Cálculos e Status
        df_final['% Atendido'] = 0.0
        mask = df_final['Demanda_HL'] > 0
        df_final.loc[mask, '% Atendido'] = (df_final.loc[mask, 'Puxado_HL'] / df_final.loc[mask, 'Demanda_HL']) * 100
        
        def classificar_faixa(row):
            if row['Demanda_HL'] == 0:
                return '🔵 Puxada Não Planejada' if row['Puxado_HL'] > 0 else 'Sem Demanda'
            val = row['% Atendido']
            if val < 50: return '< 50% (Crítico)'
            elif val <= 80: return '50% - 80% (Atenção)'
            else: return '> 80% (Saudável)'
            
        df_final['Faixa'] = df_final.apply(classificar_faixa, axis=1)
        return df_final, df_puxado

    except Exception as e:
        st.error(f"❌ Erro ao carregar os dados: {e}")
        st.stop()

df_resumo, df_historico_puxada = carregar_dados()

# ==========================================
# 1. KPIs GLOBAIS
# ==========================================
total_demanda = df_resumo['Demanda_HL'].sum()
total_puxado = df_resumo['Puxado_HL'].sum()
percentual_geral = (total_puxado / total_demanda) * 100 if total_demanda > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("Demanda Total (HL)", f"{total_demanda:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
col2.metric("Volume Puxado (HL)", f"{total_puxado:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
col3.metric("Atendimento Geral do Mês", f"{percentual_geral:.1f}%")

st.divider()

# ==========================================
# 2. RANKING DE PRODUTOS
# ==========================================
st.subheader("📊 Ranking de Produtos")

# Botões de alternância direta do Ranking
opcoes_filtro = ["Abaixo da Demanda (Menores %)", "Acima da Demanda (Maiores %)"]
filtro_ranking = st.radio("Selecione a visualização do ranking:", opcoes_filtro, horizontal=True)

# Filtra SKUs sem planejamento/sem demanda 
df_valido = df_resumo[~df_resumo['Faixa'].isin(['Sem Demanda', '🔵 Puxada Não Planejada'])].copy()

if filtro_ranking == "Abaixo da Demanda (Menores %)":
    df_filtrado = df_valido[df_valido['% Atendido'] < 100].sort_values(by=['% Atendido', 'Demanda_HL'], ascending=[False, False])
    cor_texto = '#B22222' # Vermelho escuro
else:
    df_filtrado = df_valido[df_valido['% Atendido'] >= 100].sort_values(by=['% Atendido', 'Demanda_HL'], ascending=[False, False])
    cor_texto = '#006400' # Verde escuro

# Função de estilo para colorir a fonte da coluna "% Atendido"
def cor_condicional(val):
    return f'color: {cor_texto}; font-weight: bold;'

styler = df_filtrado[['Descrição SKU', 'Demanda_HL', 'Puxado_HL', '% Atendido']].style\
    .format({
        'Demanda_HL': '{:.1f}', 
        'Puxado_HL': '{:.1f}', 
        '% Atendido': '{:.1f}%'
    })\
    .map(cor_condicional, subset=['% Atendido'])

# Aplicação do dataframe com column_config para centralização absoluta
st.dataframe(
    styler, 
    use_container_width=True, 
    hide_index=True, 
    height=400,
    column_config={
        "Descrição SKU": st.column_config.Column("Descrição SKU", alignment="center"),
        "Demanda_HL": st.column_config.Column("Demanda_HL", alignment="center"),
        "Puxado_HL": st.column_config.Column("Puxado_HL", alignment="center"),
        "% Atendido": st.column_config.Column("% Atendido", alignment="center")
    }
)

st.divider()

# ==========================================
# 3. CONSULTA INDIVIDUAL DE PRODUTO
# ==========================================
st.subheader("🔎 Consulta Individual de Produto")
st.markdown("Selecione um produto para acompanhar o atingimento exato da demanda VS puxada.")

lista_produtos = df_resumo['Descrição SKU'].dropna().unique().tolist()
lista_produtos.sort()
produto_selecionado = st.selectbox("Selecione o SKU:", lista_produtos)
df_prod = df_resumo[df_resumo['Descrição SKU'] == produto_selecionado].iloc[0]

# Métricas individuais em cartões
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Demanda Total (HL)", f"{df_prod['Demanda_HL']:.1f}".replace('.', ','))
col_m2.metric("Puxado (HL)", f"{df_prod['Puxado_HL']:.1f}".replace('.', ','))
col_m3.metric("Atingimento", f"{df_prod['% Atendido']:.1f}%" if df_prod['Demanda_HL'] > 0 else "N/A")
with col_m4:
    status = df_prod['Faixa']
    if "Crítico" in status: st.error(f"**Status:** {status}")
    elif "Atenção" in status: st.warning(f"**Status:** {status}")
    elif "Não Planejada" in status: st.info(f"**Status:** {status}")
    else: st.success(f"**Status:** {status}")

st.write("") 

# Histórico Semanal estruturado
sku_codigo = df_prod['SKU']
df_hist_prod = df_historico_puxada[df_historico_puxada['SKU'] == sku_codigo]
df_semanal_real = df_hist_prod.groupby('Semana')['Puxado_HL'].sum().reset_index()

lista_dados = []
# Mês Atual
lista_dados.append({
    'Categoria': 'Mês Atual', 
    'Demanda': df_prod['Demanda_HL'], 
    'Puxado': df_prod['Puxado_HL'],
    'Status_Tipo': 'Planejado' if df_prod['Demanda_HL'] > 0 else ('Puxada_Nao_Planejada' if df_prod['Puxado_HL'] > 0 else 'Vazio')
})

# Desdobramento das 4 Semanas
meta_semanal = df_prod['Demanda_HL'] / 4
for sem in ['S1', 'S2', 'S3', 'S4']:
    pux = df_semanal_real[df_semanal_real['Semana'] == sem]['Puxado_HL'].sum()
    lista_dados.append({
        'Categoria': f'Semana {sem[1]}', 
        'Demanda': meta_semanal, 
        'Puxado': pux, 
        'Status_Tipo': 'Planejado' if df_prod['Demanda_HL'] > 0 else ('Puxada_Nao_Planejada' if pux > 0 else 'Vazio')
    })

df_plot = pd.DataFrame(lista_dados)

fig = go.Figure()

for i, row in df_plot.iterrows():
    if row['Status_Tipo'] == 'Puxada_Nao_Planejada':
        cor = '#1f77b4' 
        valor_bar = 100
        texto = f"{row['Puxado']:,.0f} HL Puxados (Sem demanda cadastrada)"
    elif row['Status_Tipo'] == 'Vazio':
        cor = '#E8E8E8'
        valor_bar = 0
        texto = "Sem demanda planejada"
    else:
        perc = (row['Puxado'] / row['Demanda'] * 100) if row['Demanda'] > 0 else 0
        cor = '#8BC34A' # Verde Claro 
        valor_bar = min(perc, 100) 
        texto = f"{row['Puxado']:,.0f} / {row['Demanda']:,.0f} HL ({perc:.1f}%)"

    fig.add_trace(go.Bar(y=[row['Categoria']], x=[100], orientation='h', marker_color='#E8E8E8', showlegend=False, hoverinfo='skip'))
    
    fig.add_trace(go.Bar(
        y=[row['Categoria']], 
        x=[valor_bar], 
        orientation='h', 
        marker_color=cor, 
        text=[texto], 
        textposition='auto', 
        textfont=dict(size=14, color='#333333', family='Segoe UI, Arial, sans-serif', weight='bold'),
        showlegend=False, 
        hoverinfo='text'
    ))

fig.update_layout(
    barmode='overlay', 
    title=dict(text="Ritmo de Puxada", font=dict(size=20, family='Segoe UI, Arial, sans-serif', color='#1f2c56')),
    plot_bgcolor='rgba(0,0,0,0)', 
    paper_bgcolor='rgba(0,0,0,0)', 
    margin=dict(t=60, b=20, l=120, r=120), 
    xaxis=dict(
        range=[0, 110], 
        showticklabels=False, 
        showgrid=False, 
        zeroline=False
    ), 
    yaxis=dict(
        autorange="reversed",
        tickfont=dict(size=14, family='Segoe UI, Arial, sans-serif')
    )
)

st.plotly_chart(fig, use_container_width=True)