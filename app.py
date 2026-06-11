# ============================================================
# DASHBOARD STREAMLIT - CUSTO DE OPORTUNIDADE AGROPECUÁRIO
# UESC | VERSÃO SEGURA PARA STREAMLIT CLOUD
# ============================================================
#
# Arquivos no GitHub:
# - app.py
# - requirements.txt
# - Brasão_da_UESC.png  (opcional, mas recomendado)
#
# A base NÃO precisa estar no GitHub.
# Ela será baixada automaticamente do Google Drive.
# ============================================================

from pathlib import Path
import re
import math

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

try:
    import gdown
except Exception:
    gdown = None


# ============================================================
# CONFIGURAÇÕES
# ============================================================

st.set_page_config(
    page_title="UESC | Custo de Oportunidade Agropecuário",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_PADRAO = "Brasão_da_UESC.png"

# Link informado pelo usuário:
GOOGLE_DRIVE_FILE_ID = "1lLDopv0fFkshCFgZ-2jMsfm39akzp7Kn"
ARQUIVO_BASE_LOCAL = "BASEFINAL_mun_sem_menores_5ha_sem_outliers_acima_15000.csv"

COL_CUSTO_NAO_NEGATIVO = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
LIMITE_SUPERIOR_PADRAO = 15000

ESTRATOS_EXCLUIR = ["Total", "Total sem produtor sem área", "Produtor sem área"]

ESTRATOS_MENORES_QUE_5HA = [
    "Mais de 0 a menos de 0,1 ha",
    "De 0,1 a menos de 0,2 ha",
    "De 0,2 a menos de 0,5 ha",
    "De 0,5 a menos de 1 ha",
    "De 1 a menos de 2 ha",
    "De 2 a menos de 3 ha",
    "De 3 a menos de 4 ha",
    "De 4 a menos de 5 ha",
]

DEFAULT_GRUPOS = {
    "1) De 5 a < 20 ha": ["De 5 a menos de 10 ha", "De 10 a menos de 20 ha"],
    "2) De 20 a < 100 ha": ["De 20 a menos de 50 ha", "De 50 a menos de 100 ha"],
    "3) De 100 a < 500 ha": ["De 100 a menos de 200 ha", "De 200 a menos de 500 ha"],
    "4) >= 500 ha": [
        "De 500 a menos de 1.000 ha",
        "De 1.000 a menos de 2.500 ha",
        "De 2.500 a menos de 10.000 ha",
        "De 10.000 ha e mais",
    ],
}

MAPA_SIGLAS_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

MAPA_REGIAO_UF = {
    "11": "Norte", "12": "Norte", "13": "Norte", "14": "Norte", "15": "Norte", "16": "Norte", "17": "Norte",
    "21": "Nordeste", "22": "Nordeste", "23": "Nordeste", "24": "Nordeste", "25": "Nordeste", "26": "Nordeste", "27": "Nordeste", "28": "Nordeste", "29": "Nordeste",
    "31": "Sudeste", "32": "Sudeste", "33": "Sudeste", "35": "Sudeste",
    "41": "Sul", "42": "Sul", "43": "Sul",
    "50": "Centro-Oeste", "51": "MT", "52": "Centro-Oeste", "53": "Centro-Oeste",
}
MAPA_REGIAO_UF["51"] = "Centro-Oeste"


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def formatar_numero_br(x, casas=0):
    if pd.isna(x):
        return ""
    try:
        x = float(x)
    except Exception:
        return str(x)

    if casas == 0:
        return f"{x:,.0f}".replace(",", ".")

    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_ticks_br(max_valor, n_ticks=6):
    if pd.isna(max_valor) or max_valor <= 0:
        return [0], ["0"]

    bruto = float(max_valor) / max(1, n_ticks - 1)
    magnitude = 10 ** math.floor(math.log10(bruto))
    residual = bruto / magnitude

    if residual <= 1:
        nice = 1
    elif residual <= 2:
        nice = 2
    elif residual <= 5:
        nice = 5
    else:
        nice = 10

    passo = nice * magnitude
    limite = math.ceil(float(max_valor) / passo) * passo
    ticks = [float(t) for t in np.arange(0, limite + passo, passo)]
    textos = [formatar_numero_br(t) for t in ticks]
    return ticks, textos


def padronizar_codigo_municipio(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(7)
    )


def padronizar_codigo_micro(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(5)
    )


def padronizar_regiao_nome(x):
    if pd.isna(x):
        return np.nan

    x = str(x).strip()

    mapa = {
        "Norte": "Norte",
        "Nordeste": "Nordeste",
        "Sudeste": "Sudeste",
        "Sul": "Sul",
        "Centro-Oeste": "Centro-Oeste",
        "Centro Oeste": "Centro-Oeste",
        "Centro-oeste": "Centro-Oeste",
    }

    return mapa.get(x, x)


def limpar_nome_microrregiao(nome):
    if pd.isna(nome):
        return nome

    txt = str(nome).strip()
    txt = re.sub(r"\s*-\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*/\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*\([A-Z]{2}\)$", "", txt)
    return txt.strip()


def encontrar_coluna(df, candidatos, obrigatoria=True):
    cols_lower = {c.lower(): c for c in df.columns}

    for cand in candidatos:
        if cand in df.columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]

    if obrigatoria:
        raise KeyError(f"Nenhuma das colunas foi encontrada: {candidatos}")

    return None


# ============================================================
# DOWNLOAD DA BASE PELO GOOGLE DRIVE
# ============================================================

@st.cache_data(show_spinner="Baixando base do Google Drive...")
def baixar_base_google_drive():
    saida = Path(ARQUIVO_BASE_LOCAL)

    if saida.exists() and saida.stat().st_size > 1000:
        return str(saida)

    if gdown is None:
        raise RuntimeError(
            "O pacote gdown não está instalado. Verifique se ele está no requirements.txt."
        )

    url = f"https://drive.google.com/uc?id={GOOGLE_DRIVE_FILE_ID}"
    gdown.download(url, str(saida), quiet=False)

    if not saida.exists() or saida.stat().st_size < 1000:
        raise RuntimeError(
            "Não foi possível baixar a base. Confirme se o arquivo no Google Drive está compartilhado como 'Qualquer pessoa com o link'."
        )

    return str(saida)


# ============================================================
# CARREGAMENTO DA BASE
# ============================================================

@st.cache_data(show_spinner="Carregando base...")
def carregar_base(usar_drive=True, arquivo_upload=None):
    if arquivo_upload is not None:
        df = pd.read_csv(
            arquivo_upload,
            sep=";",
            decimal=",",
            encoding="utf-8-sig",
            low_memory=False
        )
    else:
        if usar_drive:
            caminho = baixar_base_google_drive()
        else:
            caminho = ARQUIVO_BASE_LOCAL

        df = pd.read_csv(
            caminho,
            sep=";",
            decimal=",",
            encoding="utf-8-sig",
            low_memory=False
        )

    col_custo = encontrar_coluna(df, [
        COL_CUSTO_NAO_NEGATIVO,
        "custo_oportunidade_corrigido_r_ha_sem_negativos",
        "custo_oportunidade_r_ha_sem_negativos",
        "custo_sem_negativos",
        "mediana_custo_municipio",
    ])

    col_mun = encontrar_coluna(df, ["codigo_territorio", "codigo_municipio", "cod_municipio", "code_muni"])
    col_territorio = encontrar_coluna(df, ["territorio", "municipio", "nome_municipio", "nome_municipio_ibge"], obrigatoria=False)
    col_micro = encontrar_coluna(df, ["codigo_microrregiao", "codigo_micro", "cod_micro", "microrregiao_codigo"], obrigatoria=False)
    col_nome_micro = encontrar_coluna(df, ["microrregiao", "nome_microrregiao", "micro", "name_micro"], obrigatoria=False)
    col_regiao = encontrar_coluna(df, ["regiao", "regiao_mapa", "grande_regiao"], obrigatoria=False)
    col_estrato = encontrar_coluna(df, ["estrato_area", "grupo_estrato", "estrato"], obrigatoria=False)

    df = df.copy()
    df["codigo_municipio"] = padronizar_codigo_municipio(df[col_mun])
    df["codigo_uf"] = df["codigo_municipio"].str[:2]
    df["uf_sigla"] = df["codigo_uf"].map(MAPA_SIGLAS_UF)
    df["municipio"] = df[col_territorio].astype(str) if col_territorio is not None else df["codigo_municipio"]

    if col_micro is not None:
        df["codigo_microrregiao"] = padronizar_codigo_micro(df[col_micro])
    else:
        df["codigo_microrregiao"] = np.nan

    if col_nome_micro is not None:
        df["microrregiao"] = df[col_nome_micro].astype(str).apply(limpar_nome_microrregiao)
    else:
        df["microrregiao"] = df["codigo_microrregiao"]

    if col_regiao is not None:
        df["regiao"] = df[col_regiao].apply(padronizar_regiao_nome)
    else:
        df["regiao"] = df["codigo_uf"].map(MAPA_REGIAO_UF)

    df["estrato_area"] = df[col_estrato].astype(str).str.strip() if col_estrato is not None else "Sem estrato"

    # Variável central do painel: custo não negativo.
    df["custo_nao_negativo"] = pd.to_numeric(df[col_custo], errors="coerce").clip(lower=0)

    df = df[
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR))
        &
        (~df["estrato_area"].isin(ESTRATOS_MENORES_QUE_5HA))
    ].copy()

    df = df[df["custo_nao_negativo"].notna()].copy()

    for col in [
        "numero_estabelecimentos_com_producao",
        "area_estabelecimentos_ha_imputado",
        "area_utilizada_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, {"col_custo_usada": col_custo}


# ============================================================
# ESTRATOS
# ============================================================

def configurar_estratos(df_base):
    estratos_disponiveis = sorted(df_base["estrato_area"].dropna().unique())

    st.sidebar.header("Configuração dos estratos")
    usar_estratos_padrao = st.sidebar.checkbox("Usar definição padrão dos estratos", value=True)

    if usar_estratos_padrao:
        grupos = DEFAULT_GRUPOS.copy()
    else:
        grupos = {}
        with st.sidebar.expander("Editar grupos de estratos", expanded=True):
            n_grupos = st.number_input("Quantidade de grupos agregados", min_value=1, max_value=8, value=4, step=1)

            for i in range(int(n_grupos)):
                nome_padrao = list(DEFAULT_GRUPOS.keys())[i] if i < len(DEFAULT_GRUPOS) else f"{i+1}) Grupo {i+1}"
                default_estratos = DEFAULT_GRUPOS.get(nome_padrao, [])

                nome_grupo = st.text_input(f"Nome do grupo {i+1}", value=nome_padrao, key=f"nome_grupo_{i}")
                selecao = st.multiselect(
                    f"Estratos do grupo {i+1}",
                    estratos_disponiveis,
                    default=[e for e in default_estratos if e in estratos_disponiveis],
                    key=f"estratos_grupo_{i}",
                )
                grupos[nome_grupo] = selecao

    incluir_grupo_geral = st.sidebar.checkbox("Incluir grupo geral: >= 5 ha", value=True)
    return grupos, incluir_grupo_geral


def criar_base_agregada_por_estrato(df_base, grupos, incluir_grupo_geral=True):
    partes = []

    for nome_grupo, estratos in grupos.items():
        if not estratos:
            continue

        temp = df_base[df_base["estrato_area"].isin(estratos)].copy()
        temp["estrato_agregado"] = nome_grupo
        partes.append(temp)

    if incluir_grupo_geral:
        geral = df_base.copy()
        geral["estrato_agregado"] = "5) >= 5 ha"
        partes.append(geral)

    if not partes:
        return df_base.iloc[0:0].copy()

    return pd.concat(partes, ignore_index=True)


# ============================================================
# FILTROS E AGREGAÇÕES
# ============================================================

def aplicar_filtros(df_agregado):
    st.sidebar.header("Filtros")

    limite_superior = st.sidebar.number_input(
        "Limite superior do custo",
        min_value=0,
        max_value=1000000,
        value=LIMITE_SUPERIOR_PADRAO,
        step=500,
    )

    df = df_agregado[df_agregado["custo_nao_negativo"] <= limite_superior].copy()

    regioes = sorted(df["regiao"].dropna().unique())
    filtro_regiao = st.sidebar.multiselect("Grande Região", regioes, default=regioes)
    df = df[df["regiao"].isin(filtro_regiao)].copy()

    ufs = sorted(df["uf_sigla"].dropna().unique())
    filtro_uf = st.sidebar.multiselect("UF", ufs, default=ufs)
    df = df[df["uf_sigla"].isin(filtro_uf)].copy()

    micros = sorted(df["microrregiao"].dropna().unique())
    filtro_micro = st.sidebar.multiselect("Microrregião", micros, default=[])
    if filtro_micro:
        df = df[df["microrregiao"].isin(filtro_micro)].copy()

    municipios = sorted(df["municipio"].dropna().unique())
    filtro_municipio = st.sidebar.multiselect("Município", municipios, default=[])
    if filtro_municipio:
        df = df[df["municipio"].isin(filtro_municipio)].copy()

    estratos = sorted(df["estrato_agregado"].dropna().unique())
    filtro_estrato = st.sidebar.multiselect("Estrato agregado", estratos, default=estratos)
    df = df[df["estrato_agregado"].isin(filtro_estrato)].copy()

    faixa = st.sidebar.slider(
        "Faixa do custo de oportunidade não negativo",
        min_value=0.0,
        max_value=float(limite_superior),
        value=(0.0, float(limite_superior)),
        step=100.0,
    )
    df = df[(df["custo_nao_negativo"] >= faixa[0]) & (df["custo_nao_negativo"] <= faixa[1])].copy()

    return df, limite_superior


def agregar(df, nivel, medida="median"):
    if nivel == "Município":
        group_cols = ["codigo_municipio", "municipio", "uf_sigla", "regiao"]
    elif nivel == "Microrregião":
        group_cols = ["codigo_microrregiao", "microrregiao", "regiao"]
    elif nivel == "UF":
        group_cols = ["codigo_uf", "uf_sigla", "regiao"]
    elif nivel == "Grande Região":
        group_cols = ["regiao"]
    else:
        group_cols = ["municipio"]

    if medida == "mean":
        out = df.groupby(group_cols, as_index=False, observed=True)["custo_nao_negativo"].mean()
    else:
        out = df.groupby(group_cols, as_index=False, observed=True)["custo_nao_negativo"].median()

    return out.rename(columns={"custo_nao_negativo": "custo_agregado"})


# ============================================================
# VISUALIZAÇÕES
# ============================================================

def mostrar_cabecalho():
    col_logo, col_texto = st.columns([1, 5])

    with col_logo:
        if Path(LOGO_PADRAO).exists():
            st.image(LOGO_PADRAO, width=170)
        else:
            st.markdown("### UESC")

    with col_texto:
        st.title("Dashboard do Custo de Oportunidade Agropecuário")
        st.markdown(
            "**Universidade Estadual de Santa Cruz (UESC)**  \n"
            "Análise municipal, microrregional, estadual e regional do custo de oportunidade agropecuário."
        )

    with st.expander("Metodologia do indicador", expanded=False):
        st.markdown(
            """
            Este painel utiliza o **custo de oportunidade corrigido para abril de 2026**, com base no índice de correção utilizado na metodologia do projeto.

            A medida foi construída a partir do resultado líquido agropecuário por hectare.
            """
        )

        st.latex(
            r"""
            \text{Custo de oportunidade}
            =
            \frac{
            (\text{Valor da produção corrigido} - \text{Valor das despesas corrigido}) \times 1000
            }{
            \text{Área utilizada ou área dos estabelecimentos em hectares}
            }
            """
        )

        st.markdown(
            """
            Como os valores monetários originais do SIDRA estavam em **mil reais**, multiplicou-se por **1000** para obter o valor em reais.

            Para esta versão do painel, utiliza-se exclusivamente o **custo de oportunidade não negativo**:
            """
        )

        st.latex(
            r"""
            \text{Custo não negativo}
            =
            \max(\text{Custo de oportunidade}, 0)
            """
        )


def mostrar_indicadores(df):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Observações", formatar_numero_br(len(df)))
    col2.metric("Municípios", formatar_numero_br(df["codigo_municipio"].nunique()))
    col3.metric("Mediana", formatar_numero_br(df["custo_nao_negativo"].median()))
    col4.metric("Média", formatar_numero_br(df["custo_nao_negativo"].mean()))
    col5.metric("Máximo", formatar_numero_br(df["custo_nao_negativo"].max()))


def consulta_municipio(df_base):
    st.subheader("Consulta rápida por município")

    municipios = sorted(df_base["municipio"].dropna().unique())

    termo = st.selectbox(
        "Pesquisar município",
        municipios,
        index=None,
        placeholder="Digite o nome do município..."
    )

    if termo is None:
        st.info("Digite ou selecione um município para ver o custo de oportunidade.")
        return

    dados = df_base[df_base["municipio"] == termo].copy()

    if dados.empty:
        st.warning("Município não encontrado.")
        return

    resumo = (
        dados
        .groupby(["municipio", "uf_sigla", "regiao"], as_index=False)["custo_nao_negativo"]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", n="count")
    )

    r = resumo.iloc[0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Município", r["municipio"])
    c2.metric("UF", r["uf_sigla"])
    c3.metric("Mediana", formatar_numero_br(r["mediana"]))
    c4.metric("Média", formatar_numero_br(r["media"]))
    c5.metric("Observações", formatar_numero_br(r["n"]))

    por_estrato = (
        dados
        .groupby("estrato_area", as_index=False)["custo_nao_negativo"]
        .median()
        .rename(columns={"custo_nao_negativo": "mediana_custo"})
        .sort_values("mediana_custo", ascending=False)
    )

    por_estrato["rotulo"] = por_estrato["mediana_custo"].apply(formatar_numero_br)

    fig = px.bar(
        por_estrato.sort_values("mediana_custo", ascending=True),
        x="mediana_custo",
        y="estrato_area",
        orientation="h",
        text="rotulo",
        title=f"Custo de oportunidade não negativo por estrato — {termo}",
        labels={"mediana_custo": "Mediana do custo", "estrato_area": ""},
    )

    fig.update_traces(textposition="outside")

    max_val = por_estrato["mediana_custo"].max()
    tickvals, ticktext = gerar_ticks_br(max_val)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)

    fig.update_layout(height=max(450, 28 * len(por_estrato)))
    st.plotly_chart(fig, use_container_width=True)


def grafico_barras(df_agg, nivel):
    if len(df_agg) == 0:
        st.warning("Sem dados para gerar o gráfico.")
        return

    if nivel == "Município":
        cat, titulo = "municipio", "Ranking municipal"
    elif nivel == "Microrregião":
        cat, titulo = "microrregiao", "Ranking por microrregião"
    elif nivel == "UF":
        cat, titulo = "uf_sigla", "Ranking por UF"
    else:
        cat, titulo = "regiao", "Ranking por Grande Região"

    top_n = st.slider("Quantidade de barras no ranking", 5, 100, 30, step=5)

    dados = df_agg.sort_values("custo_agregado", ascending=False).head(top_n)
    dados = dados.sort_values("custo_agregado", ascending=True)
    dados["rotulo"] = dados["custo_agregado"].apply(formatar_numero_br)

    fig = px.bar(
        dados,
        x="custo_agregado",
        y=cat,
        orientation="h",
        text="rotulo",
        title=titulo,
        labels={"custo_agregado": "Custo de oportunidade não negativo", cat: ""},
    )

    fig.update_traces(textposition="outside")

    max_val = dados["custo_agregado"].max()
    tickvals, ticktext = gerar_ticks_br(max_val)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)

    fig.update_layout(height=max(450, 24 * len(dados)), title_x=0.02)
    st.plotly_chart(fig, use_container_width=True)


def grafico_boxplot(df):
    if len(df) == 0:
        st.warning("Sem dados para gerar boxplot.")
        return

    col1, col2 = st.columns(2)

    with col1:
        fig = px.box(
            df,
            x="estrato_agregado",
            y="custo_nao_negativo",
            points=False,
            title="Boxplot por estrato agregado",
            labels={"estrato_agregado": "Estrato agregado", "custo_nao_negativo": "Custo não negativo"},
        )

        fig.update_layout(xaxis_tickangle=-30)
        tickvals, ticktext = gerar_ticks_br(df["custo_nao_negativo"].max())
        fig.update_yaxes(tickvals=tickvals, ticktext=ticktext)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.box(
            df,
            x="regiao",
            y="custo_nao_negativo",
            points=False,
            title="Boxplot por Grande Região",
            labels={"regiao": "Grande Região", "custo_nao_negativo": "Custo não negativo"},
        )

        tickvals, ticktext = gerar_ticks_br(df["custo_nao_negativo"].max())
        fig.update_yaxes(tickvals=tickvals, ticktext=ticktext)
        st.plotly_chart(fig, use_container_width=True)


def grafico_histograma_por_estrato(df):
    if len(df) == 0:
        st.warning("Sem dados para gerar histograma.")
        return

    st.write("#### Histograma por estrato agregado")

    modo = st.radio(
        "Tipo de histograma",
        ["Um estrato por vez", "Painel com todos os estratos"],
        horizontal=True
    )

    if modo == "Um estrato por vez":
        estratos = sorted(df["estrato_agregado"].dropna().unique())
        estrato_sel = st.selectbox("Escolha o estrato", estratos)
        dados = df[df["estrato_agregado"] == estrato_sel].copy()

        fig = px.histogram(
            dados,
            x="custo_nao_negativo",
            nbins=60,
            title=f"Distribuição do custo de oportunidade não negativo — {estrato_sel}",
            labels={"custo_nao_negativo": "Custo não negativo"},
        )

        max_x = dados["custo_nao_negativo"].max()
        tickvals_x, ticktext_x = gerar_ticks_br(max_x)
        fig.update_xaxes(tickvals=tickvals_x, ticktext=ticktext_x, title_text="Custo não negativo")
        fig.update_yaxes(title_text="Frequência")
        st.plotly_chart(fig, use_container_width=True)

    else:
        fig = px.histogram(
            df,
            x="custo_nao_negativo",
            nbins=50,
            facet_col="estrato_agregado",
            facet_col_wrap=2,
            title="Distribuição do custo de oportunidade não negativo por estrato agregado",
            labels={"custo_nao_negativo": "Custo não negativo"},
        )

        max_x = df["custo_nao_negativo"].max()
        tickvals_x, ticktext_x = gerar_ticks_br(max_x)
        fig.update_xaxes(tickvals=tickvals_x, ticktext=ticktext_x, title_text="Custo não negativo")
        fig.update_yaxes(title_text="Frequência")
        fig.for_each_annotation(lambda a: a.update(text=a.text.replace("estrato_agregado=", "")))
        fig.update_layout(height=800)
        st.plotly_chart(fig, use_container_width=True)


def aviso_mapa():
    st.info(
        "Nesta versão de deploy leve, os mapas interativos foram desativados para evitar erro de instalação no Streamlit Cloud. "
        "Use as abas de consulta, ranking, boxplot, histograma e tabela. "
        "Se desejar, os mapas estáticos em PNG podem ser incorporados depois."
    )


def tabela_dados(df):
    st.subheader("Tabela filtrada")

    cols_preferidas = [
        "codigo_municipio", "municipio", "uf_sigla", "regiao",
        "codigo_microrregiao", "microrregiao",
        "estrato_area", "estrato_agregado", "custo_nao_negativo",
        "numero_estabelecimentos_com_producao",
        "area_estabelecimentos_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
    ]

    cols = [c for c in cols_preferidas if c in df.columns]
    mostrar = df[cols].copy()

    st.dataframe(mostrar, use_container_width=True, height=450)

    csv = mostrar.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    st.download_button(
        "Baixar tabela filtrada em CSV",
        data=csv,
        file_name="dados_filtrados_custo_oportunidade_nao_negativo.csv",
        mime="text/csv",
    )


# ============================================================
# APP
# ============================================================

with st.sidebar:
    st.header("Base de dados")
    uploaded = st.file_uploader("Carregar CSV manualmente", type=["csv"])
    usar_drive = st.checkbox("Baixar base automaticamente do Google Drive", value=True)

try:
    base_limpa, meta = carregar_base(usar_drive=usar_drive, arquivo_upload=uploaded)
except Exception as e:
    st.error(f"Erro ao carregar a base: {e}")
    st.stop()

grupos_config, incluir_geral = configurar_estratos(base_limpa)
base_agregada = criar_base_agregada_por_estrato(base_limpa, grupos_config, incluir_geral)

mostrar_cabecalho()

df_filtrado, limite_superior = aplicar_filtros(base_agregada)

st.write("### Indicadores gerais")
mostrar_indicadores(df_filtrado)

st.divider()

col_a, col_b = st.columns([1, 1])

with col_a:
    nivel = st.selectbox("Nível de análise", ["Município", "Microrregião", "UF", "Grande Região"], index=1)

with col_b:
    medida = st.selectbox("Medida de agregação", ["Mediana", "Média"], index=0)

medida_key = "mean" if medida == "Média" else "median"
df_agg = agregar(df_filtrado, nivel=nivel, medida=medida_key)

abas = st.tabs(["Consulta município", "Mapa", "Ranking", "Boxplots", "Histograma por estrato", "Tabela", "Resumo"])

with abas[0]:
    consulta_municipio(base_limpa)

with abas[1]:
    aviso_mapa()

with abas[2]:
    st.subheader(f"Ranking por {nivel}")
    grafico_barras(df_agg, nivel)

with abas[3]:
    st.subheader("Boxplots")
    grafico_boxplot(df_filtrado)

with abas[4]:
    grafico_histograma_por_estrato(df_filtrado)

with abas[5]:
    tabela_dados(df_filtrado)

with abas[6]:
    st.subheader("Resumo da base filtrada")

    resumo_estrato = (
        df_filtrado
        .groupby("estrato_agregado", as_index=False, observed=True)["custo_nao_negativo"]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", n="count")
    )

    resumo_regiao = (
        df_filtrado
        .groupby("regiao", as_index=False)["custo_nao_negativo"]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", n="count")
    )

    for col in ["media", "mediana", "minimo", "maximo"]:
        resumo_estrato[col] = resumo_estrato[col].apply(formatar_numero_br)
        resumo_regiao[col] = resumo_regiao[col].apply(formatar_numero_br)

    st.write("#### Por estrato agregado")
    st.dataframe(resumo_estrato, use_container_width=True)

    st.write("#### Por Grande Região")
    st.dataframe(resumo_regiao, use_container_width=True)
