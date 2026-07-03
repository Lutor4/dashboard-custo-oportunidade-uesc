# ============================================================
# AJUSTES PONTUAIS - MAPAS E GRÁFICO DE MICRORREGIÕES
# ============================================================
#
# Este script NÃO baixa SIDRA e NÃO refaz imputação.
# Ele apenas lê a BASE OFICIAL já gerada e recria:
#
# 1) mapa por UF com siglas sem caixa branca, usando contorno branco no texto;
# 2) mapa por Grande Região com siglas sem caixa branca;
# 3) gráfico de barras das microrregiões com sigla da UF no rótulo.
#
# Objetivo:
# - resolver o problema do DF ficar escondido pelo fundo branco do rótulo;
# - melhorar a localização das microrregiões no ranking.
#
# Instalar, se necessário:
#   python -m pip install pandas numpy matplotlib geopandas geobr
#
# Ajuste apenas ARQUIVO_BASE, se necessário.
# ============================================================

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import zipfile
import unicodedata
import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

try:
    import geobr
except Exception as e:
    raise ImportError("Instale com: python -m pip install geobr geopandas shapely pyogrio") from e


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ARQUIVO_BASE = r"C:\Users\rvabreu\Downloads\SIDRA\resultado_final_v14_nova_metodologia\BASEFINAL_mun_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv"

COL_CUSTO = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"

PASTA_SAIDA = Path("ajustes_mapas_e_ranking_microrregioes")
PASTA_SAIDA.mkdir(exist_ok=True)

ANO_MAPA = 2017

LIMITE_SUPERIOR = 15000
BINS_CUSTO = [0, 500, 1000, 2500, 5000, 10000, 15000]

TAMANHO_FONTE_TITULO = 17
TAMANHO_FONTE_LEGENDA = 15
TAMANHO_FONTE_SIGLA_UF = 13
TAMANHO_FONTE_SIGLA_REGIAO = 24

TOP_N_MICRORREGIOES = 30

MAPA_UF = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
    "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF"
}

MAPA_REGIAO = {
    "RO": "Norte", "AC": "Norte", "AM": "Norte", "RR": "Norte", "PA": "Norte", "AP": "Norte", "TO": "Norte",
    "MA": "Nordeste", "PI": "Nordeste", "CE": "Nordeste", "RN": "Nordeste", "PB": "Nordeste", "PE": "Nordeste", "AL": "Nordeste", "SE": "Nordeste", "BA": "Nordeste",
    "MG": "Sudeste", "ES": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "SC": "Sul", "RS": "Sul",
    "MS": "Centro-Oeste", "MT": "Centro-Oeste", "GO": "Centro-Oeste", "DF": "Centro-Oeste"
}

MAPA_SIGLAS_REGIAO = {
    "Norte": "N",
    "Nordeste": "NE",
    "Sudeste": "SE",
    "Sul": "S",
    "Centro-Oeste": "CO",
}


# ============================================================
# FUNÇÕES
# ============================================================

def normalizar_texto(txt):
    if pd.isna(txt):
        return ""
    txt = str(txt).strip().lower()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = txt.replace("-", " ")
    txt = " ".join(txt.split())
    return txt


def padronizar_regiao(x):
    tx = normalizar_texto(x)
    if tx == "norte":
        return "Norte"
    if tx == "nordeste":
        return "Nordeste"
    if tx == "sudeste":
        return "Sudeste"
    if tx == "sul":
        return "Sul"
    if tx in ["centro oeste", "centrooeste"]:
        return "Centro-Oeste"
    return x


def ler_base_flexivel(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    tentativas = [
        {"sep": ";", "decimal": ",", "encoding": "utf-8-sig"},
        {"sep": ",", "decimal": ".", "encoding": "utf-8-sig"},
        {"sep": ";", "decimal": ".", "encoding": "utf-8-sig"},
    ]

    for params in tentativas:
        try:
            df = pd.read_csv(caminho, low_memory=False, **params)
            if df.shape[1] > 1:
                return df
        except Exception:
            pass

    return pd.read_csv(caminho, sep=None, engine="python", encoding="utf-8-sig", low_memory=False)


def salvar_csv(df, nome):
    caminho = PASTA_SAIDA / nome
    df.to_csv(caminho, sep=";", decimal=",", encoding="utf-8-sig", index=False)
    print(f"Salvo: {caminho}")


def salvar_fig(nome):
    caminho = PASTA_SAIDA / nome
    plt.savefig(caminho, dpi=300, bbox_inches="tight")
    print(f"Salvo: {caminho}")
    plt.close()


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


def encontrar_coluna(df, candidatos, obrigatoria=True):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidatos:
        if cand in df.columns:
            return cand
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    if obrigatoria:
        print("Colunas disponíveis:")
        print(df.columns.tolist())
        raise KeyError(f"Nenhuma das colunas foi encontrada: {candidatos}")
    return None


def formatar_numero_br(x):
    if pd.isna(x):
        return ""
    return f"{float(x):,.0f}".replace(",", ".")


def limpar_nome_microrregiao(nome):
    if pd.isna(nome):
        return ""
    txt = str(nome).strip()
    txt = re.sub(r"\s*-\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*/\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*\([A-Z]{2}\)$", "", txt)
    return txt.strip()


def criar_classes(gdf, coluna_valor):
    gdf = gdf.copy()
    valores = pd.to_numeric(gdf[coluna_valor], errors="coerce").clip(lower=0)
    valores = valores.where(valores <= LIMITE_SUPERIOR, np.nan)

    labels = [
        f"{formatar_numero_br(BINS_CUSTO[i])} a {formatar_numero_br(BINS_CUSTO[i + 1])}"
        for i in range(len(BINS_CUSTO) - 1)
    ]

    gdf[coluna_valor] = valores
    gdf["classe_custo"] = pd.cut(
        valores,
        bins=BINS_CUSTO,
        labels=labels,
        include_lowest=True,
        right=True
    )
    return gdf


def ajustar_legenda(ax):
    legend = ax.get_legend()
    if legend is None:
        return

    try:
        legend.set_title("")
        legend.get_frame().set_alpha(0.90)
    except Exception:
        pass

    for text in legend.get_texts():
        text.set_fontsize(TAMANHO_FONTE_LEGENDA)
        text.set_fontweight("normal")

    title = legend.get_title()
    if title is not None:
        title.set_fontsize(TAMANHO_FONTE_LEGENDA)


def texto_com_contorno(ax, x, y, texto, fontsize, ha="center", va="center"):
    t = ax.text(
        x,
        y,
        texto,
        fontsize=fontsize,
        fontweight="bold",
        color="black",
        ha=ha,
        va=va,
        zorder=10,
    )
    t.set_path_effects([
        pe.withStroke(linewidth=2.8, foreground="white")
    ])
    return t


def adicionar_siglas_uf_sem_caixa(ax, gdf):
    for _, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        sigla = None

        for c in ["abbrev_state", "abbrev", "uf", "sigla_uf"]:
            if c in gdf.columns and pd.notna(row.get(c, np.nan)):
                sigla = str(row[c]).strip()
                break

        if sigla is None or sigla == "":
            code = str(row.get("code_state", "")).zfill(2)
            sigla = MAPA_UF.get(code, "")

        if sigla == "":
            continue

        ponto = row.geometry.representative_point()

        if sigla == "DF":
            texto_com_contorno(
                ax,
                ponto.x + 0.5,
                ponto.y + 0.25,
                sigla,
                fontsize=TAMANHO_FONTE_SIGLA_UF,
                ha="left",
                va="bottom",
            )
        else:
            texto_com_contorno(
                ax,
                ponto.x,
                ponto.y,
                sigla,
                fontsize=TAMANHO_FONTE_SIGLA_UF,
            )


def adicionar_siglas_regiao_sem_caixa(ax, gdf):
    for _, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        reg = padronizar_regiao(row.get("regiao", ""))
        sigla = MAPA_SIGLAS_REGIAO.get(reg, "")

        if sigla == "":
            continue

        ponto = row.geometry.representative_point()

        texto_com_contorno(
            ax,
            ponto.x,
            ponto.y,
            sigla,
            fontsize=TAMANHO_FONTE_SIGLA_REGIAO,
        )


def plotar_mapa(gdf, coluna_valor, titulo, nome_arquivo, rotulos=None, linewidth=0.5):
    gdf = gdf.copy()
    gdf[coluna_valor] = pd.to_numeric(gdf[coluna_valor], errors="coerce").clip(lower=0)
    gdf.loc[gdf[coluna_valor] > LIMITE_SUPERIOR, coluna_valor] = np.nan
    gdf = criar_classes(gdf, coluna_valor)

    fig, ax = plt.subplots(figsize=(14, 13))

    gdf.plot(
        column="classe_custo",
        categorical=True,
        cmap="YlOrBr",
        legend=True,
        legend_kwds={
            "loc": "lower left",
            "fontsize": TAMANHO_FONTE_LEGENDA,
            "title_fontsize": TAMANHO_FONTE_LEGENDA,
            "frameon": True,
            "borderpad": 0.7,
            "labelspacing": 0.85,
            "handlelength": 1.7,
            "handleheight": 1.1,
        },
        linewidth=linewidth,
        edgecolor="white",
        missing_kwds={"color": "lightgrey", "label": "Sem dados"},
        ax=ax
    )

    if rotulos == "uf":
        adicionar_siglas_uf_sem_caixa(ax, gdf)
    elif rotulos == "regiao":
        adicionar_siglas_regiao_sem_caixa(ax, gdf)

    ajustar_legenda(ax)

    ax.set_title(titulo, fontsize=TAMANHO_FONTE_TITULO)
    ax.axis("off")
    plt.tight_layout()
    salvar_fig(nome_arquivo)


def grafico_barras_microrregioes(df, nome_arquivo):
    dados = df.copy()
    dados = dados.sort_values("mediana_custo", ascending=False).head(TOP_N_MICRORREGIOES)
    dados = dados.sort_values("mediana_custo", ascending=True)

    if dados.empty:
        print("Sem dados para gráfico de microrregiões.")
        return

    plt.figure(figsize=(13, max(8, len(dados) * 0.34)))
    plt.barh(dados["microrregiao_uf"], dados["mediana_custo"])

    plt.title(
        f"{TOP_N_MICRORREGIOES} microrregiões com maiores medianas do custo de oportunidade",
        fontsize=15
    )
    plt.xlabel("Mediana do custo de oportunidade")
    plt.ylabel("")
    plt.xticks(fontsize=11)
    plt.yticks(fontsize=10)

    max_valor = pd.to_numeric(dados["mediana_custo"], errors="coerce").max()
    margem = max_valor * 0.14 if pd.notna(max_valor) and max_valor > 0 else 1

    for i, v in enumerate(dados["mediana_custo"]):
        plt.text(
            v + margem * 0.04,
            i,
            formatar_numero_br(v),
            va="center",
            fontsize=9
        )

    plt.xlim(0, max_valor + margem if pd.notna(max_valor) else 1)
    plt.tight_layout()
    salvar_fig(nome_arquivo)


# ============================================================
# EXECUÇÃO
# ============================================================

print("=" * 80)
print("AJUSTES PONTUAIS: MAPAS UF/REGIÃO E GRÁFICO DE MICRORREGIÕES")
print("=" * 80)

base = ler_base_flexivel(ARQUIVO_BASE)
print("Base carregada:", base.shape)

col_custo = encontrar_coluna(base, [
    COL_CUSTO,
    "custo_oportunidade_corrigido_r_ha_sem_negativos",
    "custo_oportunidade_r_ha_sem_negativos",
    "custo_sem_negativos",
])

col_mun = encontrar_coluna(base, [
    "codigo_territorio",
    "codigo_municipio",
    "cod_municipio",
    "code_muni",
])

col_micro = encontrar_coluna(base, [
    "codigo_microrregiao",
    "codigo_micro",
    "cod_micro",
    "microrregiao_codigo",
])

col_nome_micro = encontrar_coluna(base, [
    "microrregiao",
    "nome_microrregiao",
    "micro",
    "name_micro",
], obrigatoria=False)

col_uf = encontrar_coluna(base, ["uf", "UF", "sigla_uf"], obrigatoria=False)
col_regiao = encontrar_coluna(base, ["regiao", "regiao_mapa", "grande_regiao"], obrigatoria=False)

base = base.copy()
base[col_mun] = padronizar_codigo_municipio(base[col_mun])
base[col_micro] = padronizar_codigo_micro(base[col_micro])
base["codigo_uf"] = base[col_mun].str[:2]

if col_uf is not None:
    base["uf_final"] = base[col_uf].astype(str).str.strip()
else:
    base["uf_final"] = base["codigo_uf"].map(MAPA_UF)

if col_regiao is not None:
    base["regiao_final"] = base[col_regiao].apply(padronizar_regiao)
else:
    base["regiao_final"] = base["uf_final"].map(MAPA_REGIAO)

base[col_custo] = pd.to_numeric(base[col_custo], errors="coerce").clip(lower=0)
base = base[base[col_custo].notna() & (base[col_custo] <= LIMITE_SUPERIOR)].copy()

# ============================================================
# 1. MAPA POR UF
# ============================================================

uf = (
    base
    .groupby(["codigo_uf", "uf_final", "regiao_final"], as_index=False)[col_custo]
    .median()
    .rename(columns={col_custo: "mediana_custo"})
)

uf["codigo_uf"] = padronizar_codigo_uf(uf["codigo_uf"])
uf = uf.rename(columns={"uf_final": "uf", "regiao_final": "regiao"})

salvar_csv(uf, "mediana_custo_por_uf_ajustado.csv")

print("Lendo malha de UFs...")
mapa_uf = geobr.read_state(year=ANO_MAPA)
mapa_uf["code_state"] = padronizar_codigo_uf(mapa_uf["code_state"])

mapa_uf_plot = mapa_uf.merge(
    uf,
    left_on="code_state",
    right_on="codigo_uf",
    how="left"
)

plotar_mapa(
    mapa_uf_plot,
    "mediana_custo",
    "Mediana geral do custo de oportunidade por UF\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
    "mapa_geral_uf_siglas_sem_caixa.png",
    rotulos="uf",
    linewidth=0.5
)

# ============================================================
# 2. MAPA POR GRANDE REGIÃO
# ============================================================

regiao = (
    base
    .groupby("regiao_final", as_index=False)[col_custo]
    .median()
    .rename(columns={"regiao_final": "regiao", col_custo: "mediana_custo"})
)

regiao["regiao"] = regiao["regiao"].apply(padronizar_regiao)

salvar_csv(regiao, "mediana_custo_por_regiao_ajustado.csv")

print("Lendo malha de Grandes Regiões...")
try:
    mapa_regiao = geobr.read_region(year=ANO_MAPA)
except Exception:
    mapa_regiao = geobr.read_geographic_region(year=ANO_MAPA)

col_nome_regiao = None
for c in ["name_region", "nome_regiao", "name", "nome", "regiao"]:
    if c in mapa_regiao.columns:
        col_nome_regiao = c
        break

if col_nome_regiao is None:
    print("Colunas da malha de região:")
    print(mapa_regiao.columns.tolist())
    raise KeyError("Não encontrei coluna de nome da Grande Região.")

mapa_regiao["regiao"] = mapa_regiao[col_nome_regiao].apply(padronizar_regiao)

mapa_regiao_plot = mapa_regiao.merge(regiao, on="regiao", how="left")

salvar_csv(
    mapa_regiao_plot[["regiao", "mediana_custo"]].drop_duplicates(),
    "diagnostico_merge_regiao_ajustado.csv"
)

plotar_mapa(
    mapa_regiao_plot,
    "mediana_custo",
    "Mediana geral do custo de oportunidade por Grande Região\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
    "mapa_geral_regiao_siglas_sem_caixa.png",
    rotulos="regiao",
    linewidth=0.8
)

# ============================================================
# 3. GRÁFICO DE MICRORREGIÕES COM SIGLA DA UF
# ============================================================

if col_nome_micro is not None:
    cols_group = [col_micro, col_nome_micro, "uf_final", "regiao_final"]
    micro = (
        base
        .groupby(cols_group, as_index=False)[col_custo]
        .median()
        .rename(columns={
            col_micro: "codigo_microrregiao",
            col_nome_micro: "microrregiao",
            "uf_final": "uf",
            "regiao_final": "regiao",
            col_custo: "mediana_custo"
        })
    )
else:
    micro = (
        base
        .groupby([col_micro, "uf_final", "regiao_final"], as_index=False)[col_custo]
        .median()
        .rename(columns={
            col_micro: "codigo_microrregiao",
            "uf_final": "uf",
            "regiao_final": "regiao",
            col_custo: "mediana_custo"
        })
    )
    micro["microrregiao"] = micro["codigo_microrregiao"]

micro["codigo_microrregiao"] = padronizar_codigo_micro(micro["codigo_microrregiao"])
micro["microrregiao_limpa"] = micro["microrregiao"].apply(limpar_nome_microrregiao)
micro["microrregiao_uf"] = micro["microrregiao_limpa"].astype(str) + " - " + micro["uf"].astype(str)

salvar_csv(micro, "mediana_custo_por_microrregiao_com_uf_ajustado.csv")

grafico_barras_microrregioes(
    micro,
    f"grafico_barra_top{TOP_N_MICRORREGIOES}_microrregioes_com_uf.png"
)

# ============================================================
# ZIP FINAL
# ============================================================

zip_path = Path("ajustes_mapas_e_ranking_microrregioes.zip")

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for arq in PASTA_SAIDA.glob("*"):
        if arq.is_file():
            zipf.write(arq, arcname=arq.name)

print("=" * 80)
print("FINALIZADO")
print(f"Pasta de saída: {PASTA_SAIDA.resolve()}")
print(f"ZIP gerado: {zip_path.resolve()}")
print("=" * 80)
