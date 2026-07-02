# ============================================================
# DASHBOARD STREAMLIT - CUSTO DE OPORTUNIDADE AGROPECUÁRIO
# UESC | SIDRA / CENSO AGROPECUÁRIO 2017
# VERSÃO V4 - FORMATAÇÃO BR, MAPA BRASIL E HISTOGRAMA POR ESTRATO
# ============================================================
#
# Como rodar:
#
# 1) Instalar dependências:
#    pip install -r requirements_streamlit_sidra_v4.txt
#
# 2) Rodar:
#    streamlit run app_custo_oportunidade_sidra_streamlit_v4.py
#
# IMPORTANTE:
# - O app usa EXCLUSIVAMENTE a coluna de custo de oportunidade NÃO NEGATIVO:
#   custo_oportunidade_corrigido_r_ha_imputado_nao_negativo
#
# - A logo é carregada automaticamente se existir o arquivo:
#   Brasão_da_UESC.png
#   na mesma pasta deste app.
# ============================================================

from pathlib import Path
import re
import math
import copy
import html


import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from auth import check_password
from config import BASE_LOCAL_PATH, LOGO_PATH, COL_CUSTO_NAO_NEGATIVO, LIMITE_SUPERIOR_PADRAO
from download_base import garantir_base_local
from geojson_utils import (
    carregar_geojson_municipios,
    carregar_geojson_uf,
    carregar_geojson_micro,
    gerar_geojsons_se_necessario,
    juntar_dados_no_geojson,
)

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

st.set_page_config(
    page_title="UESC | Custo de Oportunidade Agropecuário",
    layout="wide",
    initial_sidebar_state="expanded",
)

ARQUIVO_BASE_PADRAO = str(BASE_LOCAL_PATH)

LOGO_PADRAO = str(LOGO_PATH)

COL_CUSTO_NAO_NEGATIVO = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
LIMITE_SUPERIOR_PADRAO = 15000

ESTRATOS_EXCLUIR = [
    "Total",
    "Total sem produtor sem área",
    "Produtor sem área",
]

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
    "1) De 5 a < 20 ha": [
        "De 5 a menos de 10 ha",
        "De 10 a menos de 20 ha",
    ],
    "2) De 20 a < 100 ha": [
        "De 20 a menos de 50 ha",
        "De 50 a menos de 100 ha",
    ],
    "3) De 100 a < 500 ha": [
        "De 100 a menos de 200 ha",
        "De 200 a menos de 500 ha",
    ],
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
    "50": "Centro-Oeste", "51": "Centro-Oeste", "52": "Centro-Oeste", "53": "Centro-Oeste",
}

# Limites aproximados do Brasil para folium.
BRASIL_BOUNDS = [[-34.0, -74.5], [6.0, -32.0]]


# ============================================================
# FORMATAÇÃO E PADRONIZAÇÃO
# ============================================================

def formatar_numero_br(x, casas=0):
    """Formata número no padrão brasileiro: milhar com ponto e decimal com vírgula."""
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
    """Gera tickvals e ticktext com formato brasileiro para eixos Plotly."""
    if pd.isna(max_valor) or max_valor <= 0:
        return [0], ["0"]

    max_valor = float(max_valor)
    bruto = max_valor / max(1, n_ticks - 1)

    if bruto <= 0:
        passo = 1
    else:
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

    limite = math.ceil(max_valor / passo) * passo
    ticks = list(np.arange(0, limite + passo, passo))
    ticks = [float(t) for t in ticks]
    textos = [formatar_numero_br(t, 0) for t in ticks]
    return ticks, textos


def aplicar_formato_br_plotly(fig, eixo_x=True, eixo_y=True):
    """Força separador de milhar com ponto e decimal com vírgula nos eixos."""
    fig.update_layout(
        font=dict(size=13),
        hoverlabel=dict(font_size=13),
    )

    if eixo_x:
        # Quando houver eixo numérico, os ticks serão ajustados depois em cada gráfico.
        fig.update_xaxes(title_font=dict(size=13), tickfont=dict(size=12))

    if eixo_y:
        fig.update_yaxes(title_font=dict(size=13), tickfont=dict(size=12))

    return fig


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


def padronizar_codigo_uf(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(2)
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
# CARREGAMENTO DA BASE
# ============================================================

@st.cache_data(show_spinner="Carregando base...")
def carregar_base(caminho_arquivo=None, arquivo_upload=None):
    if arquivo_upload is not None:
        df = pd.read_csv(
            arquivo_upload,
            sep=";",
            decimal=",",
            encoding="utf-8-sig",
            low_memory=False
        )
    else:
        if caminho_arquivo is None or str(caminho_arquivo).strip() == "":
            caminho = garantir_base_local()
        else:
            caminho = Path(caminho_arquivo)
            if not caminho.exists():
                caminho = garantir_base_local()
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
    col_regiao_imediata = encontrar_coluna(df, [
        "regiao_imediata", "região_imediata", "nome_regiao_imediata", "nome_região_imediata",
        "regiao_geografica_imediata", "região_geográfica_imediata", "regiao_imediata_nome",
        "imediata", "regiao_imed", "regiao_imediata_ibge"
    ], obrigatoria=False)
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

    if col_regiao_imediata is not None:
        df["regiao_imediata"] = df[col_regiao_imediata].astype(str).str.strip()
    else:
        df["regiao_imediata"] = "Não informada"

    df["estrato_area"] = df[col_estrato].astype(str).str.strip() if col_estrato is not None else "Sem estrato"

    # CUSTO NÃO NEGATIVO: variável central do app.
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

    meta = {"col_custo_usada": col_custo}
    return df, meta


# ============================================================
# MALHAS GEOGRÁFICAS
# ============================================================

@st.cache_data(show_spinner="Carregando malha municipal...")
def carregar_malha_municipal():
    return carregar_geojson_municipios()


@st.cache_data(show_spinner="Carregando malha de UF...")
def carregar_malha_uf():
    return carregar_geojson_uf()


@st.cache_data(show_spinner="Carregando malha de microrregião...")
def carregar_malha_micro():
    return carregar_geojson_micro()


# ============================================================
# ESTRATOS CONFIGURÁVEIS
# ============================================================

def configurar_estratos(df_base):
    estratos_disponiveis = sorted(df_base["estrato_area"].dropna().unique())

    st.sidebar.header("Configuração dos estratos")
    usar_estratos_padrao = st.sidebar.checkbox("Usar definição padrão dos estratos", value=True)

    grupos = {}

    if usar_estratos_padrao:
        grupos = DEFAULT_GRUPOS.copy()
    else:
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
                    key=f"estratos_grupo_{i}"
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

def converter_numero_legenda(texto):
    """Converte texto digitado em número, aceitando padrão brasileiro ou simples."""
    txt = str(texto).strip()
    if txt == "":
        raise ValueError("valor vazio")

    # Caso tenha vírgula, tratamos vírgula como separador decimal e ponto como milhar.
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    else:
        # Caso tenha apenas ponto e pareça milhar (ex.: 2.500), remove o ponto.
        partes = txt.split(".")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            txt = txt.replace(".", "")
    return float(txt)


def montar_limites_legenda(serie, limite_superior, metodo="Manual", n_classes=5, limites_manuais=""):
    """Monta limites da legenda conforme o método escolhido na barra lateral."""
    n_classes = int(max(3, min(8, n_classes)))

    try:
        limite = float(limite_superior)
    except Exception:
        limite = 15000.0
    if not np.isfinite(limite) or limite <= 0:
        limite = 15000.0

    valores = pd.to_numeric(serie, errors="coerce").dropna()
    valores = valores[(valores >= 0) & (valores <= limite)]

    if metodo == "Manual":
        try:
            limites = [
                converter_numero_legenda(x)
                for x in str(limites_manuais).split(",")
                if str(x).strip() != ""
            ]
            limites = sorted(set(limites))
            if len(limites) >= 2:
                return limites
        except Exception:
            pass
        return [0, 2500, 5000, 7500, 10000, 15000]

    if metodo == "Quantis" and len(valores) >= n_classes:
        try:
            probs = np.linspace(0, 1, n_classes + 1)
            limites = np.quantile(valores, probs)
            limites = [float(x) for x in limites]
            limites[0] = 0.0
            limites[-1] = limite
            limites = sorted(set(round(x, 6) for x in limites))
            if len(limites) >= 2:
                return limites
        except Exception:
            pass

    return [float(x) for x in np.linspace(0, limite, n_classes + 1)]


def aplicar_filtros(df_agregado):
    st.sidebar.header("Filtros")

    limite_superior = st.sidebar.number_input(
        "Limite superior do custo",
        min_value=0,
        max_value=1000000,
        value=LIMITE_SUPERIOR_PADRAO,
        step=500
    )

    st.sidebar.subheader("Faixas da legenda do mapa")
    metodo_legenda = st.sidebar.radio(
        "Classificação da legenda",
        ["Manual", "Intervalos iguais", "Quantis"],
        index=0,
        help=(
            "Manual usa os limites digitados. Intervalos iguais divide a escala em classes de mesmo tamanho. "
            "Quantis tenta distribuir quantidade semelhante de observações em cada classe."
        ),
    )

    n_classes_legenda = st.sidebar.number_input(
        "Número de classes",
        min_value=3,
        max_value=8,
        value=5,
        step=1,
        help="Usado em Intervalos iguais e Quantis. No modo Manual, o número de classes depende da quantidade de limites digitados.",
    )

    faixas_txt = ""
    if metodo_legenda == "Manual":
        faixas_txt = st.sidebar.text_input(
            "Limites manuais",
            value="0,2500,5000,7500,10000,15000",
            help="Ex.: 0,2500,5000,7500,10000,15000. Use ponto para milhar ou vírgula decimal, se necessário.",
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

    # Em vez de filtrar por município individual, usamos Região Imediata,
    # que é uma escala territorial intermediária mais útil para exploração.
    if "regiao_imediata" in df.columns and df["regiao_imediata"].notna().any():
        regioes_imediatas = sorted([x for x in df["regiao_imediata"].dropna().unique() if str(x).strip() and str(x) != "Não informada"])
        filtro_regiao_imediata = st.sidebar.multiselect("Região Imediata", regioes_imediatas, default=[])
        if filtro_regiao_imediata:
            df = df[df["regiao_imediata"].isin(filtro_regiao_imediata)].copy()

    estratos = sorted(df["estrato_agregado"].dropna().unique())
    filtro_estrato = st.sidebar.multiselect("Estrato agregado", estratos, default=estratos)
    df = df[df["estrato_agregado"].isin(filtro_estrato)].copy()

    faixa = st.sidebar.slider(
        "Faixa do custo de oportunidade não negativo",
        min_value=0.0,
        max_value=float(limite_superior),
        value=(0.0, float(limite_superior)),
        step=100.0
    )
    df = df[(df["custo_nao_negativo"] >= faixa[0]) & (df["custo_nao_negativo"] <= faixa[1])].copy()

    faixas_legenda = montar_limites_legenda(
        serie=df["custo_nao_negativo"],
        limite_superior=limite_superior,
        metodo=metodo_legenda,
        n_classes=int(n_classes_legenda),
        limites_manuais=faixas_txt,
    )

    with st.sidebar.expander("Prévia da legenda", expanded=False):
        st.caption("Faixas que serão usadas no mapa.")
        st.write(", ".join(formatar_numero_br(x, casas=0) for x in faixas_legenda))

    return df, limite_superior, faixas_legenda


def agregar(df, nivel, medida="median"):
    if nivel == "Município":
        group_cols = ["codigo_municipio", "municipio", "uf_sigla", "regiao"]
        if "regiao_imediata" in df.columns:
            group_cols.append("regiao_imediata")
    elif nivel == "Microrregião":
        # Inclui UF para que o ranking e o tooltip mostrem a UF de cada microrregião.
        group_cols = ["codigo_microrregiao", "microrregiao", "uf_sigla", "regiao"]
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
        candidatos_logo = [
            Path(LOGO_PADRAO),
            Path("assets/Brasão_da_UESC.png"),
            Path("Brasão_da_UESC.png"),
            Path("assets/Brasao_da_UESC.png"),
            Path("Brasao_da_UESC.png"),
        ]

        logo_encontrada = None
        for caminho_logo in candidatos_logo:
            if caminho_logo.exists():
                logo_encontrada = caminho_logo
                break

        if logo_encontrada is not None:
            st.image(str(logo_encontrada), width=150)
        else:
            st.markdown("### UESC")

    with col_texto:
        st.title("Dashboard do Custo de Oportunidade Agropecuário")
        st.markdown(
            "**Universidade Estadual de Santa Cruz (UESC)**  \n"
            "Análise municipal, microrregional, estadual e regional do custo de oportunidade agropecuário."
        )

    with st.expander("📖 Metodologia do indicador", expanded=False):
        st.subheader("Base de dados")

        st.markdown("""
        Este painel apresenta estimativas do **Custo de Oportunidade da Agropecuária Brasileira**, calculadas a partir dos dados do **Censo Agropecuário 2017**, disponibilizados pelo Sistema IBGE de Recuperação Automática (**SIDRA/IBGE**).
        
        Os valores monetários disponibilizados pelo SIDRA encontram-se expressos em **mil reais** e foram atualizados para **maio de 2026** utilizando o **Índice de Preços ao Produtor Amplo – Mercado (IPA-M)**, da Fundação Getulio Vargas (FGV), permitindo a comparação dos resultados em valores reais.
        """)
        
        st.subheader("Cálculo do indicador")
        
        st.latex(r"""
        CO_{2017}
        =
        \frac{(VP-VD)\times1000}{AU}
        """)
        
        st.markdown("""
        onde:
        
        - **VP** = Valor Bruto da Produção Agropecuária (mil R$);
        - **VD** = Valor das Despesas dos Estabelecimentos Agropecuários (mil R$);
        - **AU** = Área Utilizada dos Estabelecimentos Agropecuários (hectares).
        
        O fator **1000** converte os valores disponibilizados pelo SIDRA de **mil reais** para **reais**.
        """)
        
        st.latex(r"""
        CO_{2026}
        =
        CO_{2017}
        \times
        F_{IPA-M}
        """)
        
        st.markdown("""
        onde **F<sub>IPA-M</sub>** corresponde ao fator acumulado do **Índice de Preços ao Produtor Amplo – Mercado (IPA-M)** entre 2017 e maio de 2026.
        """, unsafe_allow_html=True)
        
        st.subheader("Área utilizada")
        
        st.markdown("""
        O denominador empregado no cálculo corresponde exclusivamente à **Área Utilizada dos Estabelecimentos Agropecuários**, obtida na **Tabela 6882 do SIDRA/IBGE**.
        
        Antes da etapa de imputação foram realizadas correções nas áreas dos pequenos estratos, garantindo maior consistência entre os registros utilizados no cálculo do indicador.
        """)
        
        st.subheader("Tratamento da base de dados")
        
        st.markdown("""
        Antes da construção do indicador foram realizados diversos procedimentos de tratamento e padronização da base de dados, incluindo:
        
        - atualização monetária dos valores para **maio de 2026** utilizando o **IPA-M**;
        - padronização dos códigos territoriais do IBGE;
        - padronização das nomenclaturas de municípios, microrregiões, unidades da federação e grandes regiões;
        - exclusão dos registros classificados como **Total**;
        - exclusão dos registros **Total sem produtor sem área**;
        - exclusão dos registros **Produtor sem área**;
        - exclusão dos estabelecimentos pertencentes aos estratos de área **inferiores a 5 hectares**;
        - correção das áreas utilizadas dos pequenos estratos antes da etapa de imputação.
        """)
        
        st.subheader("Procedimentos de imputação")
        
        st.markdown("""
        Em razão da existência de informações suprimidas por sigilo estatístico e da ausência de dados em determinados estratos municipais, foi desenvolvido um procedimento hierárquico de imputação para ampliar a cobertura espacial da base de dados.
        
        As imputações foram realizadas para as seguintes variáveis:
        
        - Valor Bruto da Produção;
        - Valor das Despesas;
        - Área Utilizada.
        
        A imputação foi realizada utilizando medidas robustas de tendência central (**mediana**), obedecendo à seguinte hierarquia territorial:
        
        1. Microrregião;
        2. Unidade da Federação (UF);
        3. Grande Região;
        4. Brasil.
        
        Sempre que existiam informações suficientes em um determinado nível territorial, a imputação era realizada e o processo era encerrado. Apenas na ausência de dados passava-se ao nível imediatamente superior.
        
        Após a imputação das variáveis básicas, o custo de oportunidade foi **recalculado integralmente**, utilizando os valores finais imputados de produção, despesas e área utilizada.
        """)
        
        st.subheader("Custo de oportunidade não negativo")
        
        st.latex(r"""
        CO^{+}
        =
        \max(CO_{2026},0)
        """)
        
        st.markdown("""
        Assim, valores originalmente negativos foram transformados em **0**, evitando que prejuízos distorçam as comparações espaciais do custo de oportunidade positivo.
        """)
        
        st.subheader("Observações")
        
        st.markdown("""
        - Base de dados: **Censo Agropecuário 2017 (SIDRA/IBGE)**;
        - Valores monetários atualizados para **maio de 2026** pelo **IPA-M (FGV)**;
        - Unidade do indicador: **R$/ha**;
        - O painel permite análises por **Grande Região**, **Unidade da Federação**, **Microrregião**, **Município** e **Estratos de Área**;
        - As estatísticas podem ser calculadas utilizando **média** ou **mediana**, conforme seleção do usuário.
        """)
        
        st.divider()
        
        st.caption("""
        Dashboard desenvolvido para análise espacial do custo de oportunidade da agropecuária brasileira utilizando dados do Censo Agropecuário 2017 (SIDRA/IBGE), com atualização monetária para maio de 2026 pelo IPA-M (FGV).
        """)

    with st.expander("👥 Créditos", expanded=False):
    
        st.markdown("""
    ### Desenvolvimento metodológico, científico e computacional
    
    Em ordem alfabética:
    
    - **Andréa da Silva Gomes**
    - **Helga Dulce Bispo Passos**
    - **Luciene Maria Torquato Cerqueira Batista**
    - **Mônica de Moura Pires**
    """)

def mostrar_indicadores(df):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Observações", formatar_numero_br(len(df)))
    col2.metric("Municípios", formatar_numero_br(df["codigo_municipio"].nunique()))
    col3.metric("Mediana", formatar_numero_br(df["custo_nao_negativo"].median()))
    col4.metric("Média", formatar_numero_br(df["custo_nao_negativo"].mean()))
    col5.metric("Máximo", formatar_numero_br(df["custo_nao_negativo"].max()))


def grafico_barras(df_agg, nivel, key_suffix=""):
    if len(df_agg) == 0:
        st.warning("Sem dados para gerar o gráfico.")
        return

    if nivel == "Município":
        cat, titulo = "municipio", "Ranking municipal"
    elif nivel == "Microrregião":
        cat, titulo = "microrregiao_uf", "Ranking por microrregião"
    elif nivel == "UF":
        cat, titulo = "uf_sigla", "Ranking por UF"
    else:
        cat, titulo = "regiao", "Ranking por Grande Região"

    top_n = st.slider(
        "Quantidade de barras no ranking",
        5,
        100,
        30,
        step=5,
        key=f"top_n_ranking_{key_suffix}_{nivel}",
    )

    dados = df_agg.sort_values("custo_agregado", ascending=False).head(top_n)
    dados = dados.sort_values("custo_agregado", ascending=True).copy()

    if nivel == "Microrregião":
        dados["microrregiao_uf"] = (
            dados["microrregiao"].astype(str)
            + " - "
            + dados["uf_sigla"].fillna("").astype(str)
        )

    # Rótulo do gráfico/mapa: milhar com ponto e sem casas decimais.
    dados["rotulo"] = dados["custo_agregado"].apply(lambda x: formatar_numero_br(x, casas=0))

    fig = px.bar(
        dados,
        x="custo_agregado",
        y=cat,
        orientation="h",
        text="rotulo",
        title=titulo,
        labels={"custo_agregado": "Custo de oportunidade não negativo", cat: ""},
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Custo: %{customdata}<extra></extra>",
        customdata=dados["rotulo"],
    )

    max_val = dados["custo_agregado"].max()
    tickvals, ticktext = gerar_ticks_br(max_val)
    fig.update_xaxes(tickvals=tickvals, ticktext=ticktext)

    fig.update_layout(height=max(450, 24 * len(dados)), title_x=0.02)
    aplicar_formato_br_plotly(fig)
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
        aplicar_formato_br_plotly(fig)
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
        aplicar_formato_br_plotly(fig)
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

        # Corrige o eixo Y: Plotly usa count; aqui padronizamos para Frequência.
        fig.update_yaxes(title_text="Frequência")

        fig.update_traces(
            hovertemplate="Custo: %{x}<br>Frequência: %{y}<extra></extra>"
        )

        aplicar_formato_br_plotly(fig)
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

        # Limpa títulos dos facet.
        fig.for_each_annotation(lambda a: a.update(text=a.text.replace("estrato_agregado=", "")))

        fig.update_layout(height=800)
        aplicar_formato_br_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)


def criar_faixas_mapa(limite_superior, n_faixas=6, faixas_personalizadas=None):
    """Cria faixas para o mapa, no padrão [início, fim]."""
    if faixas_personalizadas is not None and len(faixas_personalizadas)>=2:
        cores = ["#ffffe5", "#fff7bc", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#993404"]
        faixas=[]
        for i in range(len(faixas_personalizadas)-1):
            faixas.append({"inicio":faixas_personalizadas[i],"fim":faixas_personalizadas[i+1],"cor":cores[min(i,len(cores)-1)],"label":f"{formatar_numero_br(faixas_personalizadas[i],0)} a {formatar_numero_br(faixas_personalizadas[i+1],0)}"})
        return faixas
    try:
        limite = float(limite_superior)
    except Exception:
        limite = 0.0

    if limite <= 0:
        limite = 1.0

    cortes = np.linspace(0, limite, n_faixas + 1)
    cores = ["#ffffe5", "#fff7bc", "#fee391", "#fec44f", "#fe9929", "#cc4c02"]

    faixas = []
    for i in range(n_faixas):
        inicio = float(cortes[i])
        fim = float(cortes[i + 1])
        faixas.append({
            "inicio": inicio,
            "fim": fim,
            "cor": cores[i],
            "label": f"{formatar_numero_br(inicio, casas=0)} a {formatar_numero_br(fim, casas=0)}",
        })
    return faixas


def criar_legenda_mapa_html(limite_superior, faixas_personalizadas=None):
    """Cria legenda HTML por faixas, com ponto como separador de milhar."""
    faixas = criar_faixas_mapa(limite_superior, faixas_personalizadas=faixas_personalizadas)

    linhas = "".join(
        f"""
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:3px; white-space:nowrap;">
            <span style="display:inline-block; width:18px; height:12px; background:{faixa['cor']}; border:1px solid #999;"></span>
            <span>{faixa['label']}</span>
        </div>
        """
        for faixa in faixas
    )

    return f"""
    <div style="
        position: fixed;
        bottom: 35px;
        right: 35px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.94);
        padding: 10px 12px;
        border: 1px solid #888;
        border-radius: 6px;
        box-shadow: 0 1px 5px rgba(0,0,0,0.25);
        font-size: 12px;
        color: #222;
        max-width: 240px;
    ">
        <div style="font-weight: 700; margin-bottom: 6px;">Custo de Oportunidade</div>
        {linhas}
        <div style="font-size: 11px; margin-top: 4px; color:#555;">R$/ha</div>
    </div>
    """


def calcular_bounds_geojson(geojson):
    """Calcula limites aproximados para ajustar o zoom ao conjunto de geometrias exibido."""
    lats, lons = [], []

    def percorrer_coords(coords):
        if not coords:
            return
        if isinstance(coords[0], (int, float)) and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                lats.append(lat)
                lons.append(lon)
        else:
            for item in coords:
                percorrer_coords(item)

    for feat in geojson.get("features", []):
        geom = feat.get("geometry") or {}
        percorrer_coords(geom.get("coordinates"))

    if not lats or not lons:
        return BRASIL_BOUNDS

    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def filtrar_features_com_dados(geojson):
    """Mantém somente geometrias com valor de custo agregado."""
    geo = copy.deepcopy(geojson)
    feats = []
    for feat in geo.get("features", []):
        props = feat.setdefault("properties", {})
        valor = props.get("custo_agregado")
        try:
            tem_valor = valor is not None and not pd.isna(float(valor))
        except Exception:
            tem_valor = False
        if tem_valor:
            feats.append(feat)
    geo["features"] = feats
    return geo


def cor_mapa(valor, limite_superior, faixas_personalizadas=None):
    """Retorna uma cor por faixa, sem usar legenda automática do branca."""
    try:
        v = float(valor)
    except Exception:
        return "#f0f0f0"

    if pd.isna(v):
        return "#f0f0f0"

    faixas = criar_faixas_mapa(limite_superior, faixas_personalizadas=faixas_personalizadas)
    for i, faixa in enumerate(faixas):
        if i == len(faixas) - 1:
            if faixa["inicio"] <= v <= faixa["fim"]:
                return faixa["cor"]
        else:
            if faixa["inicio"] <= v < faixa["fim"]:
                return faixa["cor"]
    return faixas[-1]["cor"]


def montar_tooltip_feature(props, nivel):
    """Monta tooltip HTML manual. Não usa GeoJsonTooltip, evitando AssertionError."""
    valor_fmt = props.get("custo_agregado_formatado") or formatar_numero_br(props.get("custo_agregado"), casas=0)

    if nivel == "Município":
        titulo = props.get("municipio") or props.get("name_muni") or props.get("name_municipality") or "Município"
        linhas = [
            ("Município", titulo),
            ("UF", props.get("uf_sigla", "")),
            ("Custo de Oportunidade", valor_fmt),
        ]
    elif nivel == "Microrregião":
        titulo = props.get("microrregiao") or props.get("name_micro") or props.get("name_micro_region") or "Microrregião"
        linhas = [
            ("Microrregião", titulo),
            ("UF", props.get("uf_sigla", "")),
            ("Custo de Oportunidade", valor_fmt),
        ]
    elif nivel == "UF":
        titulo = props.get("uf_sigla") or props.get("abbrev_state") or props.get("name_state") or "UF"
        linhas = [
            ("UF", titulo),
            ("Custo de Oportunidade", valor_fmt),
        ]
    elif nivel == "Grande Região":
        titulo = props.get("regiao") or "Grande Região"
        linhas = [
            ("Grande Região", titulo),
            ("UF", props.get("uf_sigla", "")),
            ("Custo de Oportunidade", valor_fmt),
        ]
    else:
        titulo = props.get("regiao", nivel)
        linhas = [(nivel, titulo), ("Custo de Oportunidade", valor_fmt)]

    html_linhas = "".join(
        f"<div><b>{html.escape(str(rotulo))}:</b> {html.escape(str(valor))}</div>"
        for rotulo, valor in linhas
        if valor is not None and str(valor).strip() != ""
    )

    return f"""
    <div style="font-size: 12px; line-height: 1.35;">
        {html_linhas}
    </div>
    """


def mapa_folium(df_agg, nivel, limite_superior, renderizar_mapa=True, faixas_legenda=None):
    """
    Renderiza mapa sem GeoJsonTooltip e sem legenda automática.
    A legenda é por faixas e o tooltip é montado manualmente para cada feature.
    """
    if not renderizar_mapa:
        st.info("Mapa interativo desativado na barra lateral para acelerar o painel.")
        return

    if folium is None or st_folium is None:
        st.error(
            "Mapas interativos indisponíveis. Instale as dependências com: "
            "`pip install folium streamlit-folium branca`"
        )
        return

    if df_agg is None or len(df_agg) == 0:
        st.warning("Sem dados para gerar mapa.")
        return

    if nivel == "Município" and len(df_agg) > 2500:
        st.warning(
            "O mapa municipal geral possui muitas geometrias e pode demorar alguns segundos para carregar."
        )

    df_mapa = df_agg.copy()
    df_mapa["custo_agregado_formatado"] = df_mapa["custo_agregado"].apply(
        lambda x: formatar_numero_br(x, casas=0)
    )

    if nivel == "Município":
        geojson = carregar_malha_municipal()
        df_mapa["codigo_municipio"] = padronizar_codigo_municipio(df_mapa["codigo_municipio"])
        dados_por_codigo = df_mapa.set_index("codigo_municipio").to_dict(orient="index")
        mapa = juntar_dados_no_geojson(
            geojson,
            dados_por_codigo,
            "codigo_municipio",
            7,
            aliases_codigo=["code_muni"],
        )

    elif nivel == "Microrregião":
        geojson = carregar_malha_micro()
        df_mapa["codigo_microrregiao"] = padronizar_codigo_micro(df_mapa["codigo_microrregiao"])
        dados_por_codigo = df_mapa.set_index("codigo_microrregiao").to_dict(orient="index")
        mapa = juntar_dados_no_geojson(
            geojson,
            dados_por_codigo,
            "codigo_microrregiao",
            5,
            aliases_codigo=["code_micro"],
        )

    elif nivel == "UF":
        geojson = carregar_malha_uf()
        df_mapa["codigo_uf"] = padronizar_codigo_uf(df_mapa["codigo_uf"])
        dados_por_codigo = df_mapa.set_index("codigo_uf").to_dict(orient="index")
        mapa = juntar_dados_no_geojson(
            geojson,
            dados_por_codigo,
            "codigo_uf",
            2,
            aliases_codigo=["code_state"],
        )

    elif nivel == "Grande Região":
        # Não precisamos de GeoJSON específico de Grande Região.
        # Usamos a malha de UF e atribuímos o mesmo valor agregado a todas as UFs da região.
        geojson = copy.deepcopy(carregar_malha_uf())
        dados_por_regiao = df_mapa.set_index("regiao").to_dict(orient="index")
        features = []
        for feat in geojson.get("features", []):
            props = feat.setdefault("properties", {})
            cod_uf = str(props.get("codigo_uf") or props.get("code_state") or "")
            cod_uf = re.sub(r"\.0$", "", cod_uf)
            cod_uf = re.sub(r"\D", "", cod_uf).zfill(2)
            regiao = MAPA_REGIAO_UF.get(cod_uf)
            if regiao in dados_por_regiao:
                props["codigo_uf"] = cod_uf
                props["uf_sigla"] = MAPA_SIGLAS_UF.get(cod_uf, props.get("abbrev_state", ""))
                props["regiao"] = regiao
                for k, v in dados_por_regiao[regiao].items():
                    props[k] = v
                features.append(feat)
        geojson["features"] = features
        mapa = geojson

    else:
        st.info("Mapa interativo disponível para Município, Microrregião, UF e Grande Região.")
        return

    mapa = filtrar_features_com_dados(mapa)

    if not mapa.get("features"):
        st.warning("Não encontrei geometrias compatíveis com os códigos da base filtrada.")
        return

    bounds = calcular_bounds_geojson(mapa)

    m = folium.Map(
        location=[-14.2, -51.9],
        zoom_start=4,
        tiles=None,
        control_scale=True,
    )

    def style_function(feature):
        valor = feature.get("properties", {}).get("custo_agregado", None)
        return {
            "fillColor": cor_mapa(valor, limite_superior, faixas_legenda),
            "color": "white",
            "weight": 0.5,
            "fillOpacity": 0.9,
        }

    def highlight_function(feature):
        return {
            "weight": 2,
            "color": "#333333",
            "fillOpacity": 0.95,
        }

    # Uma camada por feature: permite tooltip manual específico e elimina GeoJsonTooltip.
    for feature in mapa.get("features", []):
        props = feature.get("properties", {})
        tooltip_html = montar_tooltip_feature(props, nivel)
        folium.GeoJson(
            feature,
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.Tooltip(tooltip_html, sticky=True),
            name=nivel,
        ).add_to(m)

    m.get_root().html.add_child(folium.Element(criar_legenda_mapa_html(limite_superior, faixas_legenda)))

    try:
        m.fit_bounds(bounds)
    except Exception:
        m.fit_bounds(BRASIL_BOUNDS)

    st_folium(m, width=None, height=650)


def tabela_dados(df):
    st.subheader("Tabela filtrada")
    cols_preferidas = [
        "codigo_municipio", "municipio", "uf_sigla", "regiao",
        "codigo_microrregiao", "microrregiao", "regiao_imediata",
        "estrato_area", "estrato_agregado", "custo_nao_negativo",
        "numero_estabelecimentos_com_producao",
        "area_estabelecimentos_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
    ]
    cols = [c for c in cols_preferidas if c in df.columns]
    mostrar = df[cols].copy()

    # Exibição na tela: vírgula para decimal e ponto para milhar.
    mostrar_formatada = mostrar.copy()
    for col in mostrar_formatada.select_dtypes(include=["float", "int", "int64", "float64"]).columns:
        casas = 2 if col != "numero_estabelecimentos_com_producao" else 0
        mostrar_formatada[col] = mostrar_formatada[col].apply(lambda x: formatar_numero_br(x, casas=casas))

    st.dataframe(mostrar_formatada, use_container_width=True, height=450)

    # Download: mantém os valores numéricos originais, com decimal em vírgula.
    csv = mostrar.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    st.download_button(
        "Baixar tabela filtrada em CSV",
        data=csv,
        file_name="dados_filtrados_custo_oportunidade_nao_negativo.csv",
        mime="text/csv"
    )


# ============================================================
# APP
# ============================================================

check_password()

with st.sidebar:
    st.header("Base de dados")
    st.caption("Por padrão, a base é baixada do Google Drive e salva em dados/.")
    uploaded = st.file_uploader("Carregar CSV manualmente (opcional)", type=["csv"])
    atualizar_base = st.button("Atualizar base do Google Drive")

    st.header("Desempenho")
    renderizar_mapa = st.checkbox("Renderizar mapa interativo", value=True)

try:
    if uploaded is not None:
        base_limpa, meta = carregar_base(arquivo_upload=uploaded)
    else:
        if atualizar_base:
            carregar_base.clear()
            garantir_base_local(forcar_download=True)
        base_limpa, meta = carregar_base(caminho_arquivo=str(garantir_base_local()))

    with st.spinner("Verificando malhas geográficas..."):
        gerar_geojsons_se_necessario()
except Exception as e:
    st.error(f"Erro ao carregar a base ou as malhas: {e}")
    st.stop()

grupos_config, incluir_geral = configurar_estratos(base_limpa)
base_agregada = criar_base_agregada_por_estrato(base_limpa, grupos_config, incluir_geral)

mostrar_cabecalho()

df_filtrado, limite_superior, faixas_legenda = aplicar_filtros(base_agregada)

st.write("### Indicadores gerais")
mostrar_indicadores(df_filtrado)

st.divider()

col_a, col_b = st.columns([1, 1])

with col_a:
    nivel = st.selectbox("Nível de análise", ["Município", "Microrregião", "UF", "Grande Região"], index=1)

with col_b:
    medida = st.selectbox("Medida de agregação", ["Mediana", "Média"], index=0)

medida_key = "mean" if medida == "Média" else "median"

# Quando a base filtrada contém apenas uma microrregião e o usuário escolhe
# "Microrregião", o painel passa a detalhar os municípios dessa microrregião.
# A visão geral continua preservada quando há mais de uma microrregião no filtro.
n_micros_filtradas = df_filtrado["codigo_microrregiao"].dropna().nunique() if "codigo_microrregiao" in df_filtrado.columns else 0
if nivel == "Microrregião" and n_micros_filtradas == 1:
    nivel_painel = "Município"
    nome_micro = df_filtrado["microrregiao"].dropna().iloc[0] if df_filtrado["microrregiao"].notna().any() else "microrregião selecionada"
    st.info(f"Análise detalhada dos municípios da microrregião: {nome_micro}")
else:
    nivel_painel = nivel

df_agg = agregar(df_filtrado, nivel=nivel_painel, medida=medida_key)

abas = st.tabs(["Mapa", "Ranking", "Boxplots", "Histograma por estrato", "Tabela", "Resumo"])

with abas[0]:
    st.subheader(f"Mapa por {nivel_painel}")

    modo_mapa_estrato = st.radio(
        "Modo de exibição do mapa",
        ["Mapa único", "Um mapa para cada estrato agregado"],
        horizontal=True,
        help=(
            "Mapa único combina os estratos selecionados. "
            "A opção por estrato gera um mapa separado para cada estrato agregado presente no filtro."
        ),
    )

    if modo_mapa_estrato == "Mapa único":
        mapa_folium(df_agg, nivel_painel, limite_superior, renderizar_mapa, faixas_legenda)
    else:
        estratos_mapa_disponiveis = sorted(df_filtrado["estrato_agregado"].dropna().unique())

        if not estratos_mapa_disponiveis:
            st.warning("Não há estratos disponíveis para gerar mapas separados.")
        else:
            estratos_mapa = st.multiselect(
                "Escolha os estratos que deseja mapear",
                estratos_mapa_disponiveis,
                default=estratos_mapa_disponiveis,
                help="Para melhorar o desempenho, você pode gerar apenas alguns estratos por vez.",
            )

            if not estratos_mapa:
                st.info("Selecione pelo menos um estrato para gerar o mapa.")
            else:
                for estrato in estratos_mapa:
                    dados_estrato = df_filtrado[df_filtrado["estrato_agregado"] == estrato].copy()

                    if dados_estrato.empty:
                        continue

                    df_agg_estrato = agregar(dados_estrato, nivel=nivel_painel, medida=medida_key)

                    with st.expander(f"Mapa — {estrato}", expanded=(len(estratos_mapa) == 1)):
                        st.caption(
                            f"Unidade territorial: {nivel_painel} | "
                            f"Medida: {medida} | "
                            f"Observações: {formatar_numero_br(len(dados_estrato), casas=0)}"
                        )
                        mapa_folium(
                            df_agg_estrato,
                            nivel_painel,
                            limite_superior,
                            renderizar_mapa,
                            faixas_legenda,
                        )

with abas[1]:
    st.subheader(f"Ranking por {nivel_painel}")

    modo_ranking_estrato = st.radio(
        "Modo de exibição do ranking",
        ["Ranking único", "Um ranking para cada estrato agregado"],
        horizontal=True,
        help=(
            "Ranking único combina os estratos selecionados. "
            "A opção por estrato gera um ranking separado para cada estrato agregado presente no filtro."
        ),
        key="modo_ranking_estrato",
    )

    if modo_ranking_estrato == "Ranking único":
        grafico_barras(df_agg, nivel_painel, key_suffix="unico")
    else:
        estratos_ranking_disponiveis = sorted(df_filtrado["estrato_agregado"].dropna().unique())

        if not estratos_ranking_disponiveis:
            st.warning("Não há estratos disponíveis para gerar rankings separados.")
        else:
            estratos_ranking = st.multiselect(
                "Escolha os estratos que deseja ranquear",
                estratos_ranking_disponiveis,
                default=estratos_ranking_disponiveis,
                help="Para melhorar a leitura, você pode gerar apenas alguns estratos por vez.",
                key="estratos_ranking",
            )

            if not estratos_ranking:
                st.info("Selecione pelo menos um estrato para gerar o ranking.")
            else:
                for i, estrato in enumerate(estratos_ranking):
                    dados_estrato = df_filtrado[df_filtrado["estrato_agregado"] == estrato].copy()

                    if dados_estrato.empty:
                        continue

                    df_agg_estrato = agregar(dados_estrato, nivel=nivel_painel, medida=medida_key)

                    with st.expander(f"Ranking — {estrato}", expanded=(len(estratos_ranking) == 1)):
                        st.caption(
                            f"Unidade territorial: {nivel_painel} | "
                            f"Medida: {medida} | "
                            f"Observações: {formatar_numero_br(len(dados_estrato), casas=0)}"
                        )
                        grafico_barras(
                            df_agg_estrato,
                            nivel_painel,
                            key_suffix=f"estrato_{i}",
                        )

with abas[2]:
    st.subheader("Boxplots")
    grafico_boxplot(df_filtrado)

with abas[3]:
    grafico_histograma_por_estrato(df_filtrado)

with abas[4]:
    tabela_dados(df_filtrado)

with abas[5]:
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
        resumo_estrato[col] = resumo_estrato[col].apply(lambda x: formatar_numero_br(x, casas=2))
        resumo_regiao[col] = resumo_regiao[col].apply(lambda x: formatar_numero_br(x, casas=2))

    resumo_estrato["n"] = resumo_estrato["n"].apply(lambda x: formatar_numero_br(x, casas=0))
    resumo_regiao["n"] = resumo_regiao["n"].apply(lambda x: formatar_numero_br(x, casas=0))

    st.write("#### Por estrato agregado")
    st.dataframe(resumo_estrato, use_container_width=True)

    st.write("#### Por Grande Região")
    st.dataframe(resumo_regiao, use_container_width=True)
