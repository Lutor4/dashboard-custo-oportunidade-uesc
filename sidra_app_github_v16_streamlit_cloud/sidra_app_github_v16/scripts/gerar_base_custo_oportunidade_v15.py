# VERSÃO V15 - arquivo único consolidado, sem dependências de GitHub/Streamlit
# ============================================================
# CENSO AGROPECUÁRIO 2017 - CUSTO DE OPORTUNIDADE DA TERRA
# MUNICÍPIOS - ÁREA DENOMINADOR 6882 E IMPUTAÇÃO POR ESTABELECIMENTO - V12
# Pronto para rodar em Windows/VSCode ou Colab
# ============================================================

import pandas as pd
import numpy as np
import requests
import csv
import zipfile
from pathlib import Path
import re

import matplotlib.pyplot as plt

try:
    import geobr
except Exception:
    geobr = None

try:
    from google.colab import files
except Exception:
    files = None

# ============================================================
# 0. CONFIGURAÇÕES
# ============================================================

ANO_BASE = 2017

# Produção e despesas
TABELA_PRODUCAO = 6898
TABELA_DESPESA = 6900

# Nova tabela para área utilizada por utilização das terras
TABELA_AREA_UTILIZADA = 6882

# Variáveis SIDRA
COD_DESPESA = "1996"
COD_AREA = "184"

# Classificações SIDRA
# IMPORTANTE:
# No endereço da API, o parâmetro c recebe o código da CLASSIFICAÇÃO.
# Para a tabela 6882, as classificações continuam sendo:
#   c222 = Utilização das terras
#   c220 = Grupos de área total
# Os códigos longos observados no retorno, como 110087, 113470 etc., são
# CATEGORIAS da classificação 222, não códigos de classificação.
CLASS_AREA = "220"
CLASS_UTILIZACAO_TERRAS = "222"

# Classificação de grupo de área usada também nas tabelas 6898 e 6900.
CLASS_AREA_PRODUCAO_DESPESA = "220"

# Categorias "Total" observadas no retorno da 6882. Mantidas apenas para
# documentação e eventuais validações; não são usadas como código de classificação.
COD_TOTAL_AREA_6882 = "110085"
COD_TOTAL_UTILIZACAO_6882 = "110087"

# Arquivo do índice IPA-M/IPAM
# Ajuste o caminho, se necessário.
ARQUIVO_INDICE = "indice.csv"  # use caminho local; ex.: r"C:\\Users\\rvabreu\\Downloads\\SIDRA\\indice.csv"
ARQUIVO_INDICE_FALLBACK = "indice.csv"

# Arquivos gerados na etapa de microrregião e mapa município -> microrregião.
# Deixe os arquivos na mesma pasta do script ou altere os caminhos abaixo.
ARQUIVO_MAPA_MUNICIPIO_MICRO = "mun_mapa_municipio_microrregiao_usado.csv"
ARQUIVO_BASE_MICRORREGIAO = "mi_base_imputada_area_utilizada_6882.csv"
ARQUIVO_REFERENCIA_MICRORREGIAO = "referencia_microrregiao.csv"


ANO_INICIO_CORRECAO = 2017
MES_INICIO_CORRECAO = 10
ANO_FIM_CORRECAO = 2026
MES_FIM_CORRECAO = 5

# Saídas finais consolidadas para o artigo
LIMITE_SUPERIOR_OUTLIER = 15000
PASTA_SAIDA_FINAL = Path("resultado_final_v14_nova_metodologia")
PASTA_SAIDA_FINAL.mkdir(exist_ok=True)
GERAR_MAPAS_E_GRAFICOS = True


# Nível territorial SIDRA
# n6 = Município
NIVEL_MUNICIPIO = "n6/all"

MAPA_UF = {
    "11":"RO", "12":"AC", "13":"AM", "14":"RR", "15":"PA", "16":"AP", "17":"TO",
    "21":"MA", "22":"PI", "23":"CE", "24":"RN", "25":"PB", "26":"PE", "27":"AL", "28":"SE", "29":"BA",
    "31":"MG", "32":"ES", "33":"RJ", "35":"SP",
    "41":"PR", "42":"SC", "43":"RS",
    "50":"MS", "51":"MT", "52":"GO", "53":"DF"
}

CODIGOS_UF = list(MAPA_UF.keys())

# Códigos da classificação 220 (Grupos de área total) usados para quebrar
# a consulta municipal da tabela 6882 e não ultrapassar o limite de 50.000
# valores por requisição da API SIDRA.
CODIGOS_ESTRATOS_AREA_220 = [
    "1101",  # Total
    "1102",  # Mais de 0 a menos de 0,1 ha
    "1103",  # De 0,1 a menos de 0,2 ha
    "1104",  # De 0,2 a menos de 0,5 ha
    "1105",  # De 0,5 a menos de 1 ha
    "1106",  # De 1 a menos de 2 ha
    "1107",  # De 2 a menos de 3 ha
    "1108",  # De 3 a menos de 4 ha
    "1109",  # De 4 a menos de 5 ha
    "1110",  # De 5 a menos de 10 ha
    "1111",  # De 10 a menos de 20 ha
    "1112",  # De 20 a menos de 50 ha
    "1113",  # De 50 a menos de 100 ha
    "1114",  # De 100 a menos de 200 ha
    "1115",  # De 200 a menos de 500 ha
    "1116",  # De 500 a menos de 1.000 ha
    "1117",  # De 1.000 a menos de 2.500 ha
    "1118",  # De 2.500 a menos de 10.000 ha
    "1119",  # De 10.000 ha e mais
    "1120",  # Produtor sem área
]

# Códigos reais da classificação 110087 (Utilização das terras) da tabela 6882.
# A extração municipal da 6882 é feita por UF × utilização, trazendo todos os
# grupos de área total da classificação 110085. Isso evita o limite de 50.000
# valores e evita o erro de Valor = "..." observado quando se usa c220/c222.
CODIGOS_UTILIZACAO_TERRAS_6882 = [
    "110087",  # Total
    "113470",  # Lavouras - permanentes
    "113471",  # Lavouras - temporárias
    "40677",   # Lavouras - área para cultivo de flores
    "113472",  # Pastagens - naturais
    "113469",  # Pastagens - plantadas em boas condições
    "40678",   # Pastagens - pastagens plantadas em más condições
    "40679",   # Matas ou florestas - preservação permanente/reserva legal
    "40680",   # Matas ou florestas - matas e/ou florestas naturais
    "40681",   # Matas ou florestas - florestas plantadas
    "113476",  # Sistemas agroflorestais
    "40682",   # Lâmina d'água, benfeitorias, terras degradadas/inaproveitáveis
]

# Quando a tabela 6882 é baixada por UF × estrato, o SIDRA pode preencher
# apenas "Grupos de área total (Código)" e deixar "Grupos de área total" vazio.
# Este mapa reconstrói o nome do estrato a partir do código, evitando que a
# rotina de preparo descarte todas as linhas de área.
MAPA_CODIGO_ESTRATO_AREA_220 = {
    # Códigos antigos observados nas tabelas 6898/6900 e em algumas chamadas da 6882
    "1101": "Total",
    "1102": "Mais de 0 a menos de 0,1 ha",
    "1103": "De 0,1 a menos de 0,2 ha",
    "1104": "De 0,2 a menos de 0,5 ha",
    "1105": "De 0,5 a menos de 1 ha",
    "1106": "De 1 a menos de 2 ha",
    "1107": "De 2 a menos de 3 ha",
    "1108": "De 3 a menos de 4 ha",
    "1109": "De 4 a menos de 5 ha",
    "1110": "De 5 a menos de 10 ha",
    "1111": "De 10 a menos de 20 ha",
    "1112": "De 20 a menos de 50 ha",
    "1113": "De 50 a menos de 100 ha",
    "1114": "De 100 a menos de 200 ha",
    "1115": "De 200 a menos de 500 ha",
    "1116": "De 500 a menos de 1.000 ha",
    "1117": "De 1.000 a menos de 2.500 ha",
    "1118": "De 2.500 a menos de 10.000 ha",
    "1119": "De 10.000 ha e mais",
    "1120": "Produtor sem área",

    # Códigos retornados pela tabela 6882 no nível municipal
    "110085": "Total",
    "111543": "Mais de 0 a menos de 0,1 ha",
    "111544": "De 0,1 a menos de 0,2 ha",
    "111545": "De 0,2 a menos de 0,5 ha",
    "111546": "De 0,5 a menos de 1 ha",
    "111547": "De 1 a menos de 2 ha",
    "111548": "De 2 a menos de 3 ha",
    "111549": "De 3 a menos de 4 ha",
    "111550": "De 4 a menos de 5 ha",
    "111551": "De 5 a menos de 10 ha",
    "111552": "De 10 a menos de 20 ha",
    "111553": "De 20 a menos de 50 ha",
    "111554": "De 50 a menos de 100 ha",
    "111555": "De 100 a menos de 200 ha",
    "111556": "De 200 a menos de 500 ha",
    "111557": "De 500 a menos de 1.000 ha",
    "111558": "De 1.000 a menos de 2.500 ha",
    "111559": "De 2.500 a menos de 10.000 ha",
    "111560": "De 10.000 ha e mais",
    "111561": "Produtor sem área",
}

MAPA_REGIAO = {
    "RO":"Norte", "AC":"Norte", "AM":"Norte", "RR":"Norte", "PA":"Norte", "AP":"Norte", "TO":"Norte",
    "MA":"Nordeste", "PI":"Nordeste", "CE":"Nordeste", "RN":"Nordeste",
    "PB":"Nordeste", "PE":"Nordeste", "AL":"Nordeste", "SE":"Nordeste", "BA":"Nordeste",
    "MG":"Sudeste", "ES":"Sudeste", "RJ":"Sudeste", "SP":"Sudeste",
    "PR":"Sul", "SC":"Sul", "RS":"Sul",
    "MS":"Centro-Oeste", "MT":"Centro-Oeste", "GO":"Centro-Oeste", "DF":"Centro-Oeste"
}

SIMBOLOS_ZERO = ["-", "--"]
SIMBOLOS_IMPUTAR = ["X", "x", "...", ".."]

ESTRATOS_EXCLUIR_TOTAL = ["Total", "Total sem produtor sem área"]

# Categorias de utilização das terras consideradas no denominador do custo.
# Regra metodológica atualizada:
#   Método principal = soma direta das categorias produtivas/úteis abaixo.
#   Método de conferência = Total - categorias não consideradas no denominador.
# Observação importante: "Matas ou florestas - florestas plantadas" entra no denominador.
CATEGORIAS_AREA_UTILIZADA = [
    "Lavouras - permanentes",
    "Lavouras - temporárias",
    "Lavouras - área para cultivo de flores",
    "Pastagens - naturais",
    "Pastagens - plantadas em boas condições",
    "Pastagens - pastagens plantadas em más condições",
    "Sistemas agroflorestais - área cultivada com espécies florestais também usada para lavouras e pastoreio por animais",
    "Matas ou florestas - florestas plantadas",
]

# Categorias retiradas do total no método alternativo por diferença.
# Não incluir aqui "Matas ou florestas - florestas plantadas", pois essa categoria
# agora compõe a área do denominador.
CATEGORIAS_AREA_NAO_UTILIZADA = [
    "Matas ou florestas - matas ou florestas naturais destinadas à preservação permanente ou reserva legal",
    "Matas ou florestas - matas e/ou florestas naturais",
    "Lâmina d'água, tanques, lagos, açudes, área de águas públicas para aquicultura, de construções, benfeitorias ou caminhos, de terras degradadas e de terras inaproveitáveis",
]

# ============================================================
# 1. FUNÇÕES GERAIS
# ============================================================

def converter_sidra_para_numero(serie):
    serie = serie.astype(str).str.strip()
    serie = serie.replace(SIMBOLOS_ZERO, "0")
    serie = serie.replace(SIMBOLOS_IMPUTAR, np.nan)
    serie = serie.str.replace(",", ".", regex=False)
    return pd.to_numeric(serie, errors="coerce")


def identificar_precisa_imputar(serie):
    serie = serie.astype(str).str.strip()
    return serie.isin(SIMBOLOS_IMPUTAR)


def baixar_sidra(tabela, nivel_sidra, ano=2017, variavel="all", classificacoes=None, timeout=240):
    """Baixa dados do SIDRA com uma ou mais classificações.

    classificacoes deve ser lista de códigos, exemplo: ["220"] ou ["222", "220"].
    """
    url = (
        f"https://apisidra.ibge.gov.br/values/"
        f"t/{tabela}/{nivel_sidra}/v/{variavel}/p/{ano}"
    )

    if classificacoes:
        for class_cod in classificacoes:
            url += f"/c{class_cod}/all"

    url += "?formato=json"
    print("Baixando:", url)

    r = requests.get(url, timeout=timeout)
    if r.status_code != 200:
        raise Exception(f"Erro SIDRA {r.status_code}: {url}\n{r.text[:500]}")

    dados = r.json()
    if len(dados) <= 1:
        return pd.DataFrame()

    df = pd.DataFrame(dados[1:])
    df.columns = list(dados[0].values())
    return df



def baixar_sidra_municipios_por_uf(
    tabela,
    ano=2017,
    variavel="all",
    classificacoes=None,
    timeout=240
):
    """Baixa dados de municípios por UF para evitar o limite de 50.000 valores da API SIDRA.

    Retorna um único DataFrame nacional, concatenando todas as UFs.
    """

    bases = []

    for cod_uf in CODIGOS_UF:

        nivel_sidra = f"n9/in%20n3%20{cod_uf}"

        url = (
            f"https://apisidra.ibge.gov.br/values/"
            f"t/{tabela}/{nivel_sidra}/v/{variavel}/p/{ano}"
        )

        if classificacoes:
            for class_cod in classificacoes:
                url += f"/c{class_cod}/all"

        url += "?formato=json"
        print("Baixando:", url)

        try:
            r = requests.get(url, timeout=timeout)
        except Exception as e:
            print(f"Erro de conexão na UF {cod_uf}: {e}")
            continue

        if r.status_code != 200:
            print(f"Erro SIDRA na UF {cod_uf}: {r.status_code}")
            print(r.text[:500])
            continue

        dados = r.json()

        if len(dados) <= 1:
            print(f"Sem dados na UF {cod_uf}")
            continue

        df = pd.DataFrame(dados[1:])
        df.columns = list(dados[0].values())
        bases.append(df)

    if len(bases) == 0:
        raise Exception("Nenhuma UF retornou dados para municípios.")

    return pd.concat(bases, ignore_index=True)


def baixar_sidra_municipios_por_uf(
    tabela,
    ano=2017,
    variavel="all",
    classificacoes=None,
    timeout=240
):
    """Baixa dados municipais por UF para evitar limite da API SIDRA."""
    bases = []

    for cod_uf in CODIGOS_UF:
        nivel_sidra = f"n6/in%20n3%20{cod_uf}"
        url = (
            f"https://apisidra.ibge.gov.br/values/"
            f"t/{tabela}/{nivel_sidra}/v/{variavel}/p/{ano}"
        )

        if classificacoes is not None:
            for classif in classificacoes:
                url += f"/c{classif}/all"

        url += "?formato=json"
        print("Baixando:", url)

        r = requests.get(url, timeout=timeout)

        if r.status_code != 200:
            print(f"Erro na UF {cod_uf}: {r.status_code}")
            print(r.text[:300])
            continue

        dados = r.json()
        if len(dados) <= 1:
            print(f"Sem dados na UF {cod_uf}")
            continue

        df = pd.DataFrame(dados[1:])
        df.columns = list(dados[0].values())
        bases.append(df)

    if len(bases) == 0:
        raise Exception("Nenhuma UF retornou dados municipais.")

    return pd.concat(bases, ignore_index=True)



def baixar_sidra_municipios_6882_por_uf_e_estrato(
    tabela,
    ano=2017,
    variavel="184",
    timeout=240
):
    """Baixa a tabela 6882 em blocos UF × utilização das terras.

    Correção importante desta versão:
    - na URL do SIDRA, c222 e c220 são os códigos das classificações;
    - 110087, 113470, 113471 etc. são categorias da classificação c222;
    - a consulta é quebrada por UF × categoria de utilização das terras,
      trazendo todos os grupos de área total em c220/all;
    - isso evita o limite da API e evita o erro de usar c110087, que é
      incompatível porque 110087 não é classificação, é categoria.
    """
    bases = []

    for cod_uf in CODIGOS_UF:
        for cod_utilizacao in CODIGOS_UTILIZACAO_TERRAS_6882:
            nivel_sidra = f"n6/in%20n3%20{cod_uf}"
            url = (
                f"https://apisidra.ibge.gov.br/values/"
                f"t/{tabela}/{nivel_sidra}/v/{variavel}/p/{ano}"
                f"/c{CLASS_UTILIZACAO_TERRAS}/{cod_utilizacao}"
                f"/c{CLASS_AREA}/all"
                f"?formato=json"
            )
            print("Baixando:", url)

            try:
                r = requests.get(url, timeout=timeout)
            except Exception as e:
                print(f"Erro de conexão na UF {cod_uf}, utilização {cod_utilizacao}: {e}")
                continue

            if r.status_code != 200:
                print(f"Erro SIDRA na UF {cod_uf}, utilização {cod_utilizacao}: {r.status_code}")
                print(r.text[:300])
                continue

            try:
                dados = r.json()
            except Exception as e:
                print(f"Erro ao converter resposta em JSON na UF {cod_uf}, utilização {cod_utilizacao}: {e}")
                print(r.text[:500])
                continue

            if len(dados) <= 1:
                continue

            df = pd.DataFrame(dados[1:])
            df.columns = list(dados[0].values())
            bases.append(df)

    if len(bases) == 0:
        raise Exception("Nenhuma UF retornou dados municipais da tabela 6882.")

    out = pd.concat(bases, ignore_index=True)

    # Validação forte: se todos os valores vierem como '...', a URL ainda está incorreta.
    if "Valor" in out.columns:
        n_valores_reais = (~out["Valor"].astype(str).str.strip().isin(["...", "..", "X", "x", "-"])).sum()
        if n_valores_reais == 0:
            raise Exception(
                "A tabela 6882 foi baixada, mas todos os valores vieram como '...'. "
                "Isso indica consulta incompatível. Verifique se a URL está usando "
                "c222/<categoria_de_utilizacao>/c220/all. Teste confirmado: c222/all/c220/all retorna valores."
            )

    return out

def identificar_colunas_territorio(df):
    colunas_excluir = {
        "Nível Territorial (Código)", "Nível Territorial",
        "Unidade de Medida (Código)", "Unidade de Medida",
        "Valor", "Variável (Código)", "Variável",
        "Ano (Código)", "Ano",
        "Grupos de área total (Código)", "Grupos de área total",
        "Utilização das terras (Código)", "Utilização das terras"
    }

    candidatos_codigo = [
        col for col in df.columns
        if col.endswith("(Código)") and col not in colunas_excluir
    ]

    if len(candidatos_codigo) == 0:
        raise Exception("Coluna territorial não encontrada.")

    col_codigo = candidatos_codigo[0]
    col_nome = col_codigo.replace(" (Código)", "")
    return col_codigo, col_nome


def manter_total_nas_outras_classificacoes(df):
    """Mantém Total nas classificações auxiliares, exceto área e utilização das terras."""
    df2 = df.copy()
    colunas_nao_filtrar = [
        "Nível Territorial", "Unidade de Medida", "Valor", "Variável", "Ano",
        "Grupos de área total", "Grupos de área total (Código)",
        "Utilização das terras", "Utilização das terras (Código)"
    ]

    for col in df2.columns:
        if col in colunas_nao_filtrar or "(Código)" in col:
            continue

        valores = df2[col].dropna().astype(str).str.strip()
        if valores.eq("Total").any():
            df2 = df2[df2[col].astype(str).str.strip() == "Total"].copy()

    return df2


def padronizar_estrato_original(nome):
    nome = str(nome).strip()
    if nome == "" or nome.lower() in ["nan", "none"]:
        return np.nan
    nome_lower = nome.lower()
    if "produtor sem área" in nome_lower or "produtor sem area" in nome_lower:
        return np.nan
    return nome


def reconstruir_nome_estrato_area(nome, codigo):
    """Usa o nome do estrato quando existe; caso contrário, usa o código 1101-1120.

    Necessário para a tabela 6882 municipal, pois ao baixar UF × estrato o SIDRA
    pode deixar a coluna "Grupos de área total" em branco, mantendo apenas
    "Grupos de área total (Código)".
    """
    nome_txt = "" if pd.isna(nome) else str(nome).strip()
    if nome_txt and nome_txt.lower() not in ["nan", "none"]:
        return nome_txt

    cod_txt = "" if pd.isna(codigo) else str(codigo).strip().replace(".0", "")
    return MAPA_CODIGO_ESTRATO_AREA_220.get(cod_txt, np.nan)


def padronizar_texto_categoria(txt):
    if pd.isna(txt):
        return ""
    return str(txt).strip().replace("–", "-").replace("—", "-")

# ============================================================
# 2. PREPARAÇÃO DE VARIÁVEIS DE PRODUÇÃO E DESPESA
# ============================================================

def preparar_variavel_por_estrato(df, nome_variavel):
    df2 = manter_total_nas_outras_classificacoes(df)
    col_territorio_cod, col_territorio_nome = identificar_colunas_territorio(df2)

    base = df2[[col_territorio_cod, col_territorio_nome, "Grupos de área total", "Valor"]].copy()
    base = base.rename(columns={
        col_territorio_cod: "codigo_territorio",
        col_territorio_nome: "territorio",
        "Grupos de área total": "estrato_area",
        "Valor": f"{nome_variavel}_original"
    })

    base["codigo_territorio"] = (
        base["codigo_territorio"].astype(str).str.replace(r"\.0$", "", regex=True)
    )

    base[f"{nome_variavel}_precisa_imputar"] = identificar_precisa_imputar(base[f"{nome_variavel}_original"])
    base[nome_variavel] = converter_sidra_para_numero(base[f"{nome_variavel}_original"])

    base["estrato_area"] = base["estrato_area"].apply(padronizar_estrato_original)
    base = base.dropna(subset=["estrato_area"]).copy()

    # Código de município possui 7 dígitos. Os dois primeiros indicam a UF.
    base["uf"] = base["codigo_territorio"].astype(str).str[:2].map(MAPA_UF)
    base["regiao"] = base["uf"].map(MAPA_REGIAO)

    base = (
        base
        .groupby(["codigo_territorio", "territorio", "uf", "regiao", "estrato_area"], as_index=False, dropna=False)
        .agg({
            nome_variavel: lambda x: x.sum(min_count=1),
            f"{nome_variavel}_precisa_imputar": "max",
            f"{nome_variavel}_original": lambda x: (
                pd.Series(x).dropna().astype(str).iloc[0]
                if pd.Series(x).dropna().shape[0] > 0 else np.nan
            )
        })
    )
    return base


def filtrar_variavel_por_nome_unidade(df, texto_variavel, unidade):
    filtro = (
        df["Variável"].astype(str).str.contains(texto_variavel, case=False, na=False)
        & df["Unidade de Medida"].astype(str).str.contains(unidade, case=False, na=False)
    )
    out = df[filtro].copy()
    if out.empty:
        print(df[["Variável (Código)", "Variável", "Unidade de Medida"]].drop_duplicates().head(50))
        raise Exception(f"Não encontrei variável {texto_variavel}")
    return out


def preparar_producao_6898(df):
    df_num_estab = filtrar_variavel_por_nome_unidade(
        df,
        texto_variavel="Número de estabelecimentos agropecuários com produção",
        unidade="Unidades"
    )
    df_valor_prod = filtrar_variavel_por_nome_unidade(
        df,
        texto_variavel="Valor da produção dos estabelecimentos agropecuários",
        unidade="Mil Reais"
    )

    num_estab = preparar_variavel_por_estrato(df_num_estab, "numero_estabelecimentos_com_producao")
    valor_prod = preparar_variavel_por_estrato(df_valor_prod, "valor_producao_mil_reais")

    chaves = ["codigo_territorio", "territorio", "uf", "regiao", "estrato_area"]
    return num_estab.merge(valor_prod, on=chaves, how="outer")

# ============================================================
# 3. ÁREA UTILIZADA - TABELA 6882
# ============================================================

def preparar_area_utilizada_6882(df_area_6882):
    """Calcula área total, utilizada e não utilizada a partir da tabela 6882.

    Regra principal desta versão:
    - A tabela 6882 é aberta por categoria de utilização das terras.
    - A coluna "Total" da utilização das terras representa:

          área total = área utilizada + área não utilizada

    - Quando alguma categoria utilizada ou não utilizada vem com X/...,
      o código NÃO descarta a linha nem substitui por zero.
      Primeiro soma todas as categorias observadas; depois calcula:

          diferença = área total - soma(categorias observadas utilizadas e não utilizadas)

      Essa diferença é distribuída entre os grupos que possuem X, preservando a identidade:

          área total = área utilizada + área não utilizada

    - A distribuição é proporcional aos totais observados dos grupos que possuem X.
      Quando não existe peso observável, usa a quantidade de categorias com X como peso.

    Assim, a área utilizada e a área não utilizada finais são sempre coerentes com
    o total da própria tabela 6882, sempre que o total estiver disponível.
    """

    df2 = manter_total_nas_outras_classificacoes(df_area_6882)
    col_territorio_cod, col_territorio_nome = identificar_colunas_territorio(df2)

    cols = [
        col_territorio_cod,
        col_territorio_nome,
        "Grupos de área total (Código)",
        "Grupos de área total",
        "Utilização das terras",
        "Valor"
    ]

    base = df2[cols].copy()
    base = base.rename(columns={
        col_territorio_cod: "codigo_territorio",
        col_territorio_nome: "territorio",
        "Grupos de área total (Código)": "estrato_area_codigo",
        "Grupos de área total": "estrato_area_nome_sidra",
        "Utilização das terras": "utilizacao_terras",
        "Valor": "area_6882_original"
    })

    base["codigo_territorio"] = (
        base["codigo_territorio"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    )

    # Correção principal: quando o nome do grupo de área vem vazio, recupera pelo código.
    base["estrato_area"] = [
        reconstruir_nome_estrato_area(nome, cod)
        for nome, cod in zip(base["estrato_area_nome_sidra"], base["estrato_area_codigo"])
    ]
    base["estrato_area"] = base["estrato_area"].apply(padronizar_estrato_original)
    base = base.dropna(subset=["estrato_area"]).copy()

    base["utilizacao_terras_pad"] = base["utilizacao_terras"].apply(padronizar_texto_categoria)
    base["area_6882_precisa_imputar"] = identificar_precisa_imputar(base["area_6882_original"])
    base["area_6882_num"] = converter_sidra_para_numero(base["area_6882_original"])

    base["uf"] = base["codigo_territorio"].astype(str).str[:2].map(MAPA_UF)
    base["regiao"] = base["uf"].map(MAPA_REGIAO)

    cats_util = [padronizar_texto_categoria(c) for c in CATEGORIAS_AREA_UTILIZADA]
    cats_nao = [padronizar_texto_categoria(c) for c in CATEGORIAS_AREA_NAO_UTILIZADA]

    base["eh_area_utilizada"] = base["utilizacao_terras_pad"].isin(cats_util)
    base["eh_area_nao_utilizada"] = base["utilizacao_terras_pad"].isin(cats_nao)
    base["eh_total_utilizacao"] = base["utilizacao_terras_pad"].eq("Total")

    base["area_6882_original_categoria"] = (
        base["utilizacao_terras_pad"].astype(str)
        + "="
        + base["area_6882_original"].astype(str)
    )

    chaves = ["codigo_territorio", "territorio", "uf", "regiao", "estrato_area"]

    def juntar_categorias(x):
        return " | ".join(x.dropna().astype(str))

    # --------------------------------------------------------
    # Total da utilização das terras
    # --------------------------------------------------------
    area_total_6882 = (
        base[base["eh_total_utilizacao"]]
        .groupby(chaves, as_index=False, dropna=False)
        .agg(
            area_total_6882_ha=("area_6882_num", lambda x: x.sum(min_count=1)),
            area_total_6882_precisa_imputar=("area_6882_precisa_imputar", "max"),
            area_total_6882_original=("area_6882_original", lambda x: (
                pd.Series(x).dropna().astype(str).iloc[0]
                if pd.Series(x).dropna().shape[0] > 0 else np.nan
            ))
        )
    )

    # --------------------------------------------------------
    # Categorias utilizadas
    # --------------------------------------------------------
    area_utilizada = (
        base[base["eh_area_utilizada"]]
        .groupby(chaves, as_index=False, dropna=False)
        .agg(
            area_utilizada_observada_ha=("area_6882_num", lambda x: x.sum(min_count=1)),
            area_utilizada_precisa_imputar=("area_6882_precisa_imputar", "max"),
            n_x_area_utilizada=("area_6882_precisa_imputar", "sum"),
            sidra_area_utilizada_6882=("area_6882_original_categoria", juntar_categorias),
            categorias_utilizadas_encontradas=("utilizacao_terras_pad", lambda x: " | ".join(sorted(set(x.dropna().astype(str)))))
        )
    )

    # --------------------------------------------------------
    # Categorias não utilizadas
    # --------------------------------------------------------
    area_nao_utilizada = (
        base[base["eh_area_nao_utilizada"]]
        .groupby(chaves, as_index=False, dropna=False)
        .agg(
            area_nao_utilizada_observada_ha=("area_6882_num", lambda x: x.sum(min_count=1)),
            area_nao_utilizada_precisa_imputar=("area_6882_precisa_imputar", "max"),
            n_x_area_nao_utilizada=("area_6882_precisa_imputar", "sum"),
            sidra_area_nao_utilizada_6882=("area_6882_original_categoria", juntar_categorias),
            categorias_nao_utilizadas_encontradas=("utilizacao_terras_pad", lambda x: " | ".join(sorted(set(x.dropna().astype(str)))))
        )
    )

    area = (
        area_total_6882
        .merge(area_utilizada, on=chaves, how="outer")
        .merge(area_nao_utilizada, on=chaves, how="outer")
    )

    # Nulos de soma observada são tratados como zero apenas para fins de reconstrução.
    # O flag de imputação continua preservado nas colunas *_precisa_imputar.
    area["area_utilizada_observada_ha"] = pd.to_numeric(area["area_utilizada_observada_ha"], errors="coerce")
    area["area_nao_utilizada_observada_ha"] = pd.to_numeric(area["area_nao_utilizada_observada_ha"], errors="coerce")
    area["area_total_6882_ha"] = pd.to_numeric(area["area_total_6882_ha"], errors="coerce")

    area["n_x_area_utilizada"] = area["n_x_area_utilizada"].fillna(0).astype(int)
    area["n_x_area_nao_utilizada"] = area["n_x_area_nao_utilizada"].fillna(0).astype(int)

    util_obs = area["area_utilizada_observada_ha"].fillna(0)
    nao_obs = area["area_nao_utilizada_observada_ha"].fillna(0)
    soma_obs = util_obs + nao_obs

    area["diferenca_total_menos_categorias_observadas_6882"] = (
        area["area_total_6882_ha"] - soma_obs
    )

    tem_total_valido = (
        area["area_total_6882_ha"].notna()
        & (~area["area_total_6882_precisa_imputar"].fillna(False).astype(bool))
    )

    tem_x_util = area["n_x_area_utilizada"] > 0
    tem_x_nao = area["n_x_area_nao_utilizada"] > 0
    tem_x = tem_x_util | tem_x_nao

    diff = area["diferenca_total_menos_categorias_observadas_6882"]
    diff_pos = diff.where(diff > 0, 0)

    # Distribuição da diferença entre TODAS as categorias com X.
    # A área total da 6882 é a âncora contábil: total = utilizada + não utilizada.
    # Assim, quando há X em categorias utilizadas e/ou não utilizadas, a diferença
    # entre o total e a soma das categorias observadas é distribuída igualmente
    # entre os X. Depois, cada bloco recebe a parcela correspondente ao seu número
    # de categorias com X.
    total_x = area["n_x_area_utilizada"] + area["n_x_area_nao_utilizada"]

    parcela_util = np.where(
        tem_total_valido & tem_x & (total_x > 0),
        diff_pos * (area["n_x_area_utilizada"] / total_x),
        0
    )
    parcela_nao = np.where(
        tem_total_valido & tem_x & (total_x > 0),
        diff_pos * (area["n_x_area_nao_utilizada"] / total_x),
        0
    )

    # Área final por componentes.
    # Se há total válido, o total é a âncora. Se há X, redistribui a diferença.
    area["area_utilizada_ha"] = np.where(
        tem_total_valido,
        util_obs + parcela_util,
        np.where(~tem_x_util, area["area_utilizada_observada_ha"], np.nan)
    )

    area["area_nao_utilizada_ha"] = np.where(
        tem_total_valido,
        nao_obs + parcela_nao,
        np.where(~tem_x_nao, area["area_nao_utilizada_observada_ha"], np.nan)
    )

    # Quando não há X e existe total válido, garante fechamento contábil por arredondamento.
    sem_x_com_total = tem_total_valido & (~tem_x)
    area.loc[sem_x_com_total, "area_nao_utilizada_ha"] = (
        area.loc[sem_x_com_total, "area_total_6882_ha"]
        - area.loc[sem_x_com_total, "area_utilizada_ha"]
    )

    # Se há total válido e a distribuição deixou pequena diferença de arredondamento,
    # ajusta a área não utilizada para fechar a identidade.
    fechamento_valido = tem_total_valido & area["area_utilizada_ha"].notna() & area["area_nao_utilizada_ha"].notna()
    area.loc[fechamento_valido, "area_nao_utilizada_ha"] = (
        area.loc[fechamento_valido, "area_total_6882_ha"]
        - area.loc[fechamento_valido, "area_utilizada_ha"]
    )

    # Evita negativos gerados por arredondamento ou inconsistência residual.
    area.loc[area["area_nao_utilizada_ha"].notna() & (area["area_nao_utilizada_ha"] < 0), "area_nao_utilizada_ha"] = np.nan
    area.loc[area["area_utilizada_ha"].notna() & (area["area_utilizada_ha"] < 0), "area_utilizada_ha"] = np.nan

    area["area_estabelecimentos_ha"] = area["area_utilizada_ha"]

    cond_redistribuida = tem_total_valido & tem_x & area["area_estabelecimentos_ha"].notna()
    cond_soma_direta = (~tem_x) & area["area_estabelecimentos_ha"].notna()
    cond_sem_total_mas_util_completa = (~tem_total_valido) & (~tem_x_util) & area["area_estabelecimentos_ha"].notna()

    area["metodo_area_utilizada"] = np.select(
        [
            cond_redistribuida,
            cond_soma_direta,
            cond_sem_total_mas_util_completa,
        ],
        [
            "redistribuicao_diferenca_total_6882_entre_x",
            "soma_categorias_utilizadas_6882",
            "soma_categorias_utilizadas_sem_total_6882",
        ],
        default="area_utilizada_precisa_imputar"
    )

    # A área ainda precisa de imputação apenas se a área utilizada final ficou ausente.
    area["area_estabelecimentos_ha_precisa_imputar"] = area["area_estabelecimentos_ha"].isna()

    # Guarda método no campo de auditoria; os valores brutos estão em sidra_area_*.
    area["area_estabelecimentos_ha_original"] = area["metodo_area_utilizada"]

    return area

def corrigir_areas_pequenos_estratos(base, coluna_area="area_estabelecimentos_ha"):
    """Corrige área zero nos dois menores estratos usando ponto médio × nº de estabelecimentos.

    Regras:
    - Só corrige quando há número de estabelecimentos positivo.
    - Para "Mais de 0 a menos de 0,1 ha", usa 0,05 × n_estabelecimentos.
    - Para "De 0,1 a menos de 0,2 ha", usa 0,15 × n_estabelecimentos.
    - Não cria área positiva quando n_estabelecimentos é zero ou ausente.
    """
    base = base.copy()

    if coluna_area not in base.columns:
        return base

    if "numero_estabelecimentos_com_producao" in base.columns:
        col_n = "numero_estabelecimentos_com_producao"
    elif "numero_estabelecimentos_com_producao" in base.columns:
        col_n = "numero_estabelecimentos_com_producao"
    else:
        return base

    base[col_n] = pd.to_numeric(base[col_n], errors="coerce")
    base[coluna_area] = pd.to_numeric(base[coluna_area], errors="coerce")

    estrato = base["estrato_area"].astype(str).str.strip()
    filtro_tem_estab = base[col_n].notna() & (base[col_n] > 0)

    filtro_005 = (
        estrato.eq("Mais de 0 a menos de 0,1 ha")
        & base[coluna_area].notna()
        & (base[coluna_area] == 0)
        & filtro_tem_estab
    )
    base.loc[filtro_005, coluna_area] = 0.05 * base.loc[filtro_005, col_n]

    filtro_015 = (
        estrato.eq("De 0,1 a menos de 0,2 ha")
        & base[coluna_area].notna()
        & (base[coluna_area] == 0)
        & filtro_tem_estab
    )
    base.loc[filtro_015, coluna_area] = 0.15 * base.loc[filtro_015, col_n]

    return base

# ============================================================
# 4. IPA-M
# ============================================================

def ler_indice_ipam_arquivo(caminho_arquivo=ARQUIVO_INDICE):
    """Lê o arquivo indice.csv do IPA-M de forma robusta.

    Esta função aceita o formato:

        ,"Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez","Ano"
        2026,"0,34%","-1,18%","0,61%","3,49%","0,91%","--",...,"4,18%"

    Regras:
    - a primeira coluna vazia é tratada como Ano_Base;
    - as colunas Jan...Dez são usadas no cálculo mensal composto;
    - a coluna final "Ano", que é o acumulado anual, é ignorada;
    - valores "--" são tratados como ausentes;
    - funciona mesmo se alguma linha vier inteira entre aspas, como às vezes acontece em exportações do Excel.
    """
    import csv

    caminho = Path(caminho_arquivo)

    if not caminho.exists():
        caminho_fallback = Path(ARQUIVO_INDICE_FALLBACK)
        if caminho_fallback.exists():
            caminho = caminho_fallback
        else:
            raise FileNotFoundError(
                f"Arquivo de índice não encontrado: {caminho_arquivo}. "
                f"Também tentei: {ARQUIVO_INDICE_FALLBACK}."
            )

    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    linhas_processadas = []

    with open(caminho, "r", encoding="utf-8-sig") as f:
        for linha in f.read().splitlines():
            linha = linha.strip()

            if not linha:
                continue

            if len(linha) >= 2 and linha[0] == '"' and linha[-1] == '"':
                linha = linha[1:-1]

            linha = linha.replace('""', '"')

            row = next(csv.reader([linha], delimiter=",", quotechar='"'))

            if len(row) == 1 and ";" in linha:
                row = next(csv.reader([linha], delimiter=";", quotechar='"'))

            row = [str(x).strip().replace('"', "") for x in row]

            if not row or all(x == "" for x in row):
                continue

            linhas_processadas.append(row)

    if len(linhas_processadas) < 2:
        raise ValueError(
            f"O arquivo {caminho} não tem linhas suficientes para leitura do IPA-M."
        )

    cabecalho = [str(c).strip().replace('"', "") for c in linhas_processadas[0]]
    dados_originais = linhas_processadas[1:]

    if len(cabecalho) == 1:
        cabecalho = [c.strip().replace('"', "") for c in cabecalho[0].split(",")]

    if len(cabecalho) == 0:
        raise ValueError("Cabeçalho do arquivo de índice está vazio.")

    cabecalho[0] = "Ano_Base"
    cabecalho = [str(c).strip().replace("\ufeff", "") for c in cabecalho]

    pos = {"Ano_Base": 0}

    for i, c in enumerate(cabecalho):
        c_limpo = str(c).strip().replace('"', "")
        for mes in meses:
            if c_limpo.lower() == mes.lower():
                pos[mes] = i

    faltantes = [m for m in meses if m not in pos]

    if faltantes:
        raise KeyError(
            "O arquivo de índice não possui todas as colunas mensais esperadas. "
            f"Faltantes: {faltantes}. "
            f"Cabeçalho lido: {cabecalho}. "
            "O formato esperado é: ,Jan,Fev,Mar,Abr,Mai,Jun,Jul,Ago,Set,Out,Nov,Dez,Ano"
        )

    registros = []

    for row in dados_originais:
        if len(row) == 1 and "," in str(row[0]):
            row = next(csv.reader([row[0]], delimiter=",", quotechar='"'))
            row = [str(x).strip().replace('"', "") for x in row]

        reg = {}

        for col in ["Ano_Base"] + meses:
            idx = pos[col]
            reg[col] = row[idx] if idx < len(row) else ""

        registros.append(reg)

    indice = pd.DataFrame(registros, columns=["Ano_Base"] + meses)

    indice["Ano_Base"] = (
        indice["Ano_Base"].astype(str)
        .str.replace('"', "", regex=False)
        .str.strip()
    )

    indice = indice[indice["Ano_Base"].notna() & (indice["Ano_Base"] != "")].copy()

    indice["Ano_Base"] = pd.to_numeric(indice["Ano_Base"], errors="coerce")
    indice = indice[indice["Ano_Base"].notna()].copy()
    indice["Ano_Base"] = indice["Ano_Base"].astype(int)

    if indice.empty:
        raise ValueError("Não foi possível identificar anos válidos no arquivo de índice.")

    print(f"Arquivo IPA-M lido corretamente: {caminho}")
    print("Colunas usadas:", ["Ano_Base"] + meses)
    print("Anos disponíveis:", int(indice["Ano_Base"].min()), "a", int(indice["Ano_Base"].max()))

    return indice


def calcular_fator_correcao_ipam():
    indice = ler_indice_ipam_arquivo()
    indice.columns = indice.columns.astype(str).str.replace('"', '', regex=False).str.strip()

    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    mapa_mes = {m: i+1 for i, m in enumerate(meses)}

    indice_long = indice.melt(id_vars="Ano_Base", value_vars=meses, var_name="Mes", value_name="Taxa")
    indice_long["Ano_Base"] = pd.to_numeric(indice_long["Ano_Base"], errors="coerce")
    indice_long["Mes_Num"] = indice_long["Mes"].map(mapa_mes)
    indice_long["Taxa"] = (
        indice_long["Taxa"].astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    indice_long["Taxa"] = pd.to_numeric(indice_long["Taxa"], errors="coerce")
    indice_long = indice_long.dropna()
    indice_long["Data"] = pd.to_datetime(dict(
        year=indice_long["Ano_Base"].astype(int),
        month=indice_long["Mes_Num"].astype(int),
        day=1
    ))

    data_inicio = pd.Timestamp(year=ANO_INICIO_CORRECAO, month=MES_INICIO_CORRECAO, day=1)
    data_fim = pd.Timestamp(year=ANO_FIM_CORRECAO, month=MES_FIM_CORRECAO, day=1)

    indice_periodo = indice_long[(indice_long["Data"] >= data_inicio) & (indice_long["Data"] <= data_fim)].sort_values("Data")

    if indice_periodo.empty:
        raise Exception(
            "Nenhuma taxa do IPA-M foi encontrada para o período de correção. "
            f"Verifique o arquivo {ARQUIVO_INDICE} e o intervalo "
            f"{MES_INICIO_CORRECAO:02d}/{ANO_INICIO_CORRECAO} a {MES_FIM_CORRECAO:02d}/{ANO_FIM_CORRECAO}."
        )

    indice_periodo["Fator_Mensal"] = 1 + indice_periodo["Taxa"] / 100
    indice_periodo["Fator_Acumulado"] = indice_periodo["Fator_Mensal"].cumprod()
    fator = indice_periodo["Fator_Acumulado"].iloc[-1]

    if pd.isna(fator) or fator <= 0:
        raise Exception("Fator de correção inválido. Verifique as taxas do arquivo de índice.")

    print(f"Período de correção: {MES_INICIO_CORRECAO:02d}/{ANO_INICIO_CORRECAO} a {MES_FIM_CORRECAO:02d}/{ANO_FIM_CORRECAO}")
    print("Fator:", fator)
    return fator, indice_periodo

# ============================================================
# 5. MONTAR BASE MUNICÍPIO
# ============================================================

def carregar_mapa_municipio_micro():
    """Carrega o arquivo auxiliar município -> microrregião.

    O arquivo esperado é definido em ARQUIVO_MAPA_MUNICIPIO_MICRO e deve conter,
    preferencialmente, as colunas:
        codigo_territorio; nome_municipio_ibge; codigo_microrregiao;
        microrregiao; uf_mapa; regiao_mapa

    A função padroniza os códigos para evitar erro de merge:
    - município com 7 dígitos;
    - microrregião com 5 dígitos.
    """
    caminho = Path(ARQUIVO_MAPA_MUNICIPIO_MICRO)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo de mapa município-microrregião não encontrado: {ARQUIVO_MAPA_MUNICIPIO_MICRO}. "
            "Coloque esse arquivo na mesma pasta do script ou ajuste a variável ARQUIVO_MAPA_MUNICIPIO_MICRO."
        )

    mapa = pd.read_csv(
        caminho,
        sep=";",
        decimal=",",
        encoding="utf-8-sig",
        dtype=str
    )

    # Normaliza nomes de colunas para aceitar variações simples.
    mapa.columns = mapa.columns.astype(str).str.strip()

    renomear = {}
    if "codigo_municipio" in mapa.columns and "codigo_territorio" not in mapa.columns:
        renomear["codigo_municipio"] = "codigo_territorio"
    if "municipio" in mapa.columns and "nome_municipio_ibge" not in mapa.columns:
        renomear["municipio"] = "nome_municipio_ibge"
    if "nome_municipio" in mapa.columns and "nome_municipio_ibge" not in mapa.columns:
        renomear["nome_municipio"] = "nome_municipio_ibge"
    if "codigo_micro" in mapa.columns and "codigo_microrregiao" not in mapa.columns:
        renomear["codigo_micro"] = "codigo_microrregiao"
    if "micro" in mapa.columns and "microrregiao" not in mapa.columns:
        renomear["micro"] = "microrregiao"
    if "uf" in mapa.columns and "uf_mapa" not in mapa.columns:
        renomear["uf"] = "uf_mapa"
    if "regiao" in mapa.columns and "regiao_mapa" not in mapa.columns:
        renomear["regiao"] = "regiao_mapa"

    if renomear:
        mapa = mapa.rename(columns=renomear)

    obrigatorias = ["codigo_territorio", "codigo_microrregiao"]
    faltantes = [c for c in obrigatorias if c not in mapa.columns]
    if faltantes:
        raise KeyError(
            f"O mapa município-microrregião está sem as colunas obrigatórias: {faltantes}. "
            f"Colunas encontradas: {list(mapa.columns)}"
        )

    mapa["codigo_territorio"] = (
        mapa["codigo_territorio"].astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(7)
    )

    mapa["codigo_microrregiao"] = (
        mapa["codigo_microrregiao"].astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(5)
    )

    if "uf_mapa" not in mapa.columns:
        mapa["uf_mapa"] = mapa["codigo_territorio"].str[:2].map(MAPA_UF)
    if "regiao_mapa" not in mapa.columns:
        mapa["regiao_mapa"] = mapa["uf_mapa"].map(MAPA_REGIAO)
    if "nome_municipio_ibge" not in mapa.columns:
        mapa["nome_municipio_ibge"] = np.nan
    if "microrregiao" not in mapa.columns:
        mapa["microrregiao"] = np.nan

    # Remove duplicidades acidentais no arquivo auxiliar.
    mapa = mapa.drop_duplicates(subset=["codigo_territorio"], keep="first").copy()

    return mapa


def montar_base_municipio():
    print("=" * 80)
    print("PROCESSANDO MUNICÍPIOS - ÁREA UTILIZADA 6882")
    print("=" * 80)

    mapa_mun_micro = carregar_mapa_municipio_micro()
    mapa_mun_micro.to_csv("mun_mapa_municipio_microrregiao_usado.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    df_prod_bruta = baixar_sidra_municipios_por_uf(
        tabela=TABELA_PRODUCAO,
        ano=ANO_BASE,
        variavel="all",
        classificacoes=[CLASS_AREA_PRODUCAO_DESPESA]
    )
    df_prod_bruta.to_csv("mun_sidra_bruto_producao.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    producao = preparar_producao_6898(df_prod_bruta)

    df_desp = baixar_sidra_municipios_por_uf(
        tabela=TABELA_DESPESA,
        ano=ANO_BASE,
        variavel=COD_DESPESA,
        classificacoes=[CLASS_AREA_PRODUCAO_DESPESA]
    )
    df_desp.to_csv("mun_sidra_bruto_despesa.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    desp = preparar_variavel_por_estrato(df_desp, "valor_despesa_mil_reais")

    df_area_6882 = baixar_sidra_municipios_6882_por_uf_e_estrato(
        tabela=TABELA_AREA_UTILIZADA,
        ano=ANO_BASE,
        variavel=COD_AREA
    )
    df_area_6882.to_csv("mun_sidra_bruto_area_utilizacao_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    area = preparar_area_utilizada_6882(df_area_6882)

    # Validação obrigatória: evita rodar horas com a área vazia.
    if area.empty or area["area_total_6882_ha"].notna().sum() == 0:
        raise Exception(
            "Erro crítico: a tabela 6882 foi baixada, mas nenhuma área total foi preparada. "
            "A causa mais comum é a coluna 'Grupos de área total' vir vazia; "
            "nesta versão o nome do estrato é reconstruído pelo código 1101-1120."
        )

    print("Área 6882 preparada:", area.shape)
    print("Linhas com área total preenchida:", area["area_total_6882_ha"].notna().sum())
    print("Linhas com área utilizada preenchida:", area["area_utilizada_ha"].notna().sum())

    # Padroniza códigos antes do merge.
    for df_tmp in [producao, desp, area]:
        df_tmp["codigo_territorio"] = (
            df_tmp["codigo_territorio"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
        )

    chaves = ["codigo_territorio", "territorio", "uf", "regiao", "estrato_area"]
    base = producao.merge(desp, on=chaves, how="outer").merge(area, on=chaves, how="outer")

    # Se o nome do município divergir entre bases, refaz a junção da área sem usar o nome como chave.
    if base["area_total_6882_ha"].notna().sum() == 0:
        print("Aviso: merge com 'territorio' não trouxe área. Tentando merge por código, UF, região e estrato.")
        chaves_sem_nome = ["codigo_territorio", "uf", "regiao", "estrato_area"]
        base = producao.merge(desp, on=chaves, how="outer")
        area_sem_nome = area.drop(columns=["territorio"], errors="ignore")
        base = base.merge(area_sem_nome, on=chaves_sem_nome, how="outer")

    if base["area_total_6882_ha"].notna().sum() == 0:
        raise Exception(
            "Erro crítico: a área foi preparada, mas não entrou na base final. "
            "Provável incompatibilidade nas chaves de merge."
        )

    base["codigo_territorio"] = (
        base["codigo_territorio"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    )

    base = base.merge(
        mapa_mun_micro[["codigo_territorio", "codigo_microrregiao", "microrregiao"]],
        on="codigo_territorio",
        how="left"
    )

    # Reorganiza identificação territorial.
    cols_id = ["codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area"]
    outras = [c for c in base.columns if c not in cols_id]
    base = base[cols_id + outras]

    return base

# ============================================================
# 6. CÁLCULO DO CUSTO
# ============================================================

def adicionar_indicadores_por_estabelecimento(base, sufixo=""):
    """Cria indicadores por estabelecimento para referência/imputação futura.

    Regras desta versão:
    - as medidas por estabelecimento NÃO entram no cálculo do custo de oportunidade;
    - produção, despesa e resultado por estabelecimento usam os valores corrigidos monetariamente;
    - valores monetários não corrigidos por estabelecimento não são criados, para evitar confusão;
    - a área por estabelecimento usa a área utilizada final que entra no denominador do custo.
    """
    base = base.copy()

    # Número de estabelecimentos não é imputado; usa sempre a coluna observada.
    col_n = "numero_estabelecimentos_com_producao"

    if col_n not in base.columns:
        return base

    denom = base[col_n].replace(0, np.nan)

    col_area = f"area_estabelecimentos_ha{sufixo}"
    col_area_total = f"area_total_6882_ha{sufixo}"
    col_area_nao_utilizada = f"area_nao_utilizada_ha{sufixo}"

    col_prod_corr = f"valor_producao_corrigido_mil_reais{sufixo}"
    col_desp_corr = f"valor_despesa_corrigido_mil_reais{sufixo}"
    col_res_corr = f"resultado_liquido_corrigido_mil_reais{sufixo}"

    if col_area in base.columns:
        # Área utilizada final, isto é, a área que entra no denominador do custo.
        base[f"area_ha_por_estabelecimento{sufixo}"] = base[col_area] / denom

    if col_area_total in base.columns:
        base[f"area_total_ha_por_estabelecimento{sufixo}"] = base[col_area_total] / denom

    if col_area_nao_utilizada in base.columns:
        base[f"area_nao_utilizada_ha_por_estabelecimento{sufixo}"] = base[col_area_nao_utilizada] / denom

    # Variáveis monetárias por estabelecimento: sempre corrigidas monetariamente.
    if col_prod_corr in base.columns:
        base[f"valor_producao_corrigido_mil_reais_por_estabelecimento{sufixo}"] = (
            base[col_prod_corr] / denom
        )

    if col_desp_corr in base.columns:
        base[f"valor_despesa_corrigido_mil_reais_por_estabelecimento{sufixo}"] = (
            base[col_desp_corr] / denom
        )

    if col_res_corr in base.columns:
        base[f"resultado_liquido_corrigido_mil_reais_por_estabelecimento{sufixo}"] = (
            base[col_res_corr] / denom
        )

    return base


def calcular_custos(base, fator_correcao, sufixo=""):
    """Calcula o custo de oportunidade.

    Regra metodológica desta versão:
    - o custo de oportunidade usa produção total e despesa total do estrato;
    - o denominador é a área utilizada/produtiva final do estrato, calculada pela tabela 6882;
    - primeiro calcula o custo em valores originais do Censo 2017;
    - depois atualiza o custo final por hectare pelo fator acumulado do IPA-M;
    - por equivalência algébrica, também mantém produção/despesa/resultado corrigidos;
    - também é criada uma versão do custo corrigido com valores negativos substituídos por zero.
    """
    base = base.copy()

    col_prod = f"valor_producao_mil_reais{sufixo}"
    col_desp = f"valor_despesa_mil_reais{sufixo}"

    col_area_utilizada = f"area_utilizada_ha{sufixo}"
    col_area_estab = f"area_estabelecimentos_ha{sufixo}"

    # A área usada no custo é sempre a área utilizada/produtiva final.
    # Mantém a coluna area_estabelecimentos_ha apenas como espelho do denominador,
    # para compatibilidade com partes antigas do código.
    if col_area_utilizada in base.columns:
        base[col_area_estab] = base[col_area_utilizada]
        col_area = col_area_utilizada
    else:
        col_area = col_area_estab

    # Número de estabelecimentos não é imputado; usa sempre a coluna observada.
    col_n = "numero_estabelecimentos_com_producao"

    col_prod_corr = f"valor_producao_corrigido_mil_reais{sufixo}"
    col_desp_corr = f"valor_despesa_corrigido_mil_reais{sufixo}"
    col_res_original = f"resultado_liquido_mil_reais{sufixo}"
    col_res = f"resultado_liquido_corrigido_mil_reais{sufixo}"
    col_custo_original = f"custo_oportunidade_r_ha_2017{sufixo}"
    col_custo = f"custo_oportunidade_corrigido_r_ha{sufixo}"
    col_custo_nao_negativo = f"custo_oportunidade_corrigido_r_ha{sufixo}_nao_negativo"

    # Valores originais do Censo: mil reais de 2017.
    base[col_res_original] = base[col_prod] - base[col_desp]

    # Custo original por hectare: transforma mil reais em reais multiplicando por 1000.
    base[col_custo_original] = (base[col_res_original] * 1000) / base[col_area]

    # Correção monetária conforme a metodologia: aplica o fator acumulado ao custo final por hectare.
    base[col_custo] = base[col_custo_original] * fator_correcao

    # Mantém os valores monetários corrigidos para conferência e tabelas auxiliares.
    # Isso é algebricamente equivalente a corrigir o custo final, pois a área não é corrigida.
    base[col_prod_corr] = base[col_prod] * fator_correcao
    base[col_desp_corr] = base[col_desp] * fator_correcao
    base[col_res] = base[col_res_original] * fator_correcao

    filtro_invalido = (
        base[col_prod].isna()
        | base[col_desp].isna()
        | base[col_area].isna()
        | (base[col_area] <= 0)
        | np.isinf(base[col_custo])
        | np.isinf(base[col_custo_original])
    )

    if col_n in base.columns:
        filtro_invalido = filtro_invalido | base[col_n].isna() | (base[col_n] <= 0)

    base.loc[filtro_invalido, [col_custo_original, col_custo]] = np.nan

    # Versão para mapas/estatísticas conservadoras: custos negativos viram 0.
    base[col_custo_nao_negativo] = base[col_custo].clip(lower=0)

    base = adicionar_indicadores_por_estabelecimento(base, sufixo=sufixo)

    return base

# ============================================================
# 7. TOTAIS SEM PRODUTOR SEM ÁREA
# ============================================================

def criar_total_sem_area_sem_imputacao(base, fator_correcao):
    """Cria a linha Total sem produtor sem área a partir da soma dos estratos reais.

    Importante: o custo NÃO é somado. Primeiro somamos produção, despesa e áreas
    dos estratos válidos e depois recalculamos o custo agregado.
    A área não utilizada é reconstruída como total - utilizada para manter
    a identidade contábil: área total = área utilizada + área não utilizada.
    """
    base_estratos = base[~base["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL)].copy()
    chaves = ["codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao"]

    total = (
        base_estratos
        .groupby(chaves, as_index=False, dropna=False)
        .agg(
            numero_estabelecimentos_com_producao=("numero_estabelecimentos_com_producao", lambda x: x.sum(min_count=1)),
            valor_producao_mil_reais=("valor_producao_mil_reais", lambda x: x.sum(min_count=1)),
            valor_despesa_mil_reais=("valor_despesa_mil_reais", lambda x: x.sum(min_count=1)),
            area_total_6882_ha=("area_total_6882_ha", lambda x: x.sum(min_count=1)),
            area_utilizada_ha=("area_estabelecimentos_ha", lambda x: x.sum(min_count=1)),
        )
    )

    total["area_nao_utilizada_ha"] = (
        total["area_total_6882_ha"] - total["area_utilizada_ha"]
    )

    total.loc[
        total["area_nao_utilizada_ha"] < 0,
        "area_nao_utilizada_ha"
    ] = np.nan

    total["area_estabelecimentos_ha"] = total["area_utilizada_ha"]
    total["metodo_area_utilizada"] = "soma_dos_estratos_validos"
    total["estrato_area"] = "Total sem produtor sem área"

    return calcular_custos(total, fator_correcao, sufixo="")


def criar_total_sem_area_imputado(base_imp, fator_correcao):
    """Cria a linha Total sem produtor sem área para a base imputada.

    Usa apenas estratos reais. Soma produção, despesa, estabelecimentos, área
    total e área utilizada; reconstrói área não utilizada por diferença.
    """
    base_estratos = base_imp[~base_imp["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL)].copy()
    chaves = ["codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao"]

    total = (
        base_estratos
        .groupby(chaves, as_index=False, dropna=False)
        .agg(
            numero_estabelecimentos_com_producao=("numero_estabelecimentos_com_producao", lambda x: x.sum(min_count=1)),
            valor_producao_mil_reais_imputado=("valor_producao_mil_reais_imputado", lambda x: x.sum(min_count=1)),
            valor_despesa_mil_reais_imputado=("valor_despesa_mil_reais_imputado", lambda x: x.sum(min_count=1)),
            area_total_6882_ha_imputado=("area_total_6882_ha_imputado", lambda x: x.sum(min_count=1)),
            area_utilizada_ha_imputado=("area_estabelecimentos_ha_imputado", lambda x: x.sum(min_count=1)),
        )
    )

    total["area_nao_utilizada_ha_imputado"] = (
        total["area_total_6882_ha_imputado"] - total["area_utilizada_ha_imputado"]
    )

    total.loc[
        total["area_nao_utilizada_ha_imputado"] < 0,
        "area_nao_utilizada_ha_imputado"
    ] = np.nan

    total["area_estabelecimentos_ha_imputado"] = total["area_utilizada_ha_imputado"]
    total["metodo_imputacao_area"] = "soma_dos_estratos_validos"
    total["metodo_imputacao_area_componentes"] = "soma_dos_estratos_validos"
    total["estrato_area"] = "Total sem produtor sem área"

    return calcular_custos(total, fator_correcao, sufixo="_imputado")

# ============================================================
# 8. IMPUTAÇÃO
# ============================================================

def _serie_bool_segura(serie, index=None):
    """Converte uma Series para booleano sem FutureWarning do pandas."""
    if serie is None:
        if index is None:
            return pd.Series(dtype=bool)
        return pd.Series(False, index=index, dtype=bool)

    s = pd.Series(serie).copy()
    if index is not None:
        s = s.reindex(index)

    s = s.where(s.notna(), False)

    if s.dtype == object:
        s = (
            s.astype(str)
            .str.strip()
            .str.lower()
            .map({
                "true": True,
                "false": False,
                "1": True,
                "0": False,
                "sim": True,
                "não": False,
                "nao": False,
                "nan": False,
                "none": False,
                "": False,
            })
            .fillna(False)
        )

    return s.astype(bool)


def _normalizar_flag_bool(df, coluna_flag_imputar):
    if coluna_flag_imputar not in df.columns:
        df[coluna_flag_imputar] = False
    df[coluna_flag_imputar] = _serie_bool_segura(
        df[coluna_flag_imputar],
        index=df.index
    )
    return df


def _int_zero_se_nan(valor):
    """Converte contagens de X para int, tratando NaN como 0."""
    if pd.isna(valor):
        return 0
    try:
        return int(valor)
    except Exception:
        try:
            return int(float(str(valor).replace(',', '.')))
        except Exception:
            return 0


def imputar_por_diferenca_do_total(df, coluna_valor, coluna_flag_imputar, coluna_imputada, coluna_metodo):
    """Imputa por diferença do total SIDRA quando há exatamente um estrato faltante.

    Regra adicional: se a linha faltante possui nº de estabelecimentos igual a zero
    ou ausente, nada é imputado naquela linha.
    """
    df = _normalizar_flag_bool(df, coluna_flag_imputar)
    territorios = df["codigo_territorio"].dropna().unique()

    if "numero_estabelecimentos_com_producao" in df.columns:
        col_n = "numero_estabelecimentos_com_producao"
    elif "numero_estabelecimentos_com_producao" in df.columns:
        col_n = "numero_estabelecimentos_com_producao"
    else:
        col_n = None

    for territorio in territorios:
        filtro_territorio = df["codigo_territorio"] == territorio
        filtro_total = filtro_territorio & (df["estrato_area"] == "Total")
        if filtro_total.sum() == 0:
            continue

        valor_total = df.loc[filtro_total, coluna_valor].dropna()
        if len(valor_total) == 0:
            continue
        valor_total = valor_total.iloc[0]

        filtro_estratos_reais = filtro_territorio & (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        filtro_faltante_variavel = filtro_estratos_reais & (df[coluna_flag_imputar] == True)

        if filtro_faltante_variavel.sum() != 1:
            continue

        idx_faltante = df.loc[filtro_faltante_variavel].index[0]

        if col_n is not None and coluna_valor != "numero_estabelecimentos_com_producao":
            n_estab = pd.to_numeric(df.loc[idx_faltante, col_n], errors="coerce")
            if pd.isna(n_estab) or n_estab <= 0:
                df.loc[idx_faltante, coluna_metodo] = "nao_imputado_sem_estabelecimentos"
                continue

        soma_conhecidos = df.loc[
            filtro_estratos_reais & (~df[coluna_flag_imputar]) & df[coluna_valor].notna(),
            coluna_valor
        ].sum()

        valor_imputado = valor_total - soma_conhecidos
        if pd.isna(valor_imputado) or valor_imputado < 0:
            continue

        df.loc[filtro_faltante_variavel, coluna_imputada] = valor_imputado
        df.loc[filtro_faltante_variavel, coluna_metodo] = "diferenca_total_sidra"
        df.loc[filtro_faltante_variavel, coluna_flag_imputar] = False

    return df


def _calcular_mediana_por_estabelecimento(df, coluna_valor, coluna_flag_imputar, filtro_base):
    """Calcula mediana do valor por estabelecimento em um conjunto de referência."""
    col_n = "numero_estabelecimentos_com_producao"
    if col_n not in df.columns:
        col_n = "numero_estabelecimentos_com_producao"

    filtro = (
        filtro_base
        & (~df[coluna_flag_imputar])
        & df[coluna_valor].notna()
        & df[col_n].notna()
        & (df[col_n] > 0)
    )

    valores = df.loc[filtro, coluna_valor] / df.loc[filtro, col_n]

    if coluna_valor == "area_estabelecimentos_ha":
        valores = valores[valores > 0]

    valores = valores.replace([np.inf, -np.inf], np.nan).dropna()

    if len(valores) == 0:
        return np.nan

    return valores.median()



# ============================================================
# REFERÊNCIAS DA ETAPA DE MICRORREGIÃO PARA IMPUTAÇÃO MUNICIPAL
# ============================================================

_BASE_MICRORREGIAO_REF_CACHE = None


def criar_referencia_microrregiao_a_partir_base_municipal(base_municipal):
    """Cria automaticamente a referência de imputação por microrregião.

    A referência é construída a partir da própria base municipal sem imputação,
    usando apenas valores observados. Assim, o código não depende mais de
    mi_base_imputada_area_utilizada_6882.csv nem de referencia_microrregiao.csv.
    A hierarquia de imputação continua sendo: microrregião -> UF -> região -> Brasil.
    """
    df = base_municipal.copy()

    # Garante código de microrregião usando o arquivo município -> microrregião.
    if "codigo_microrregiao" not in df.columns or df["codigo_microrregiao"].isna().all():
        try:
            mapa = carregar_mapa_municipio_micro()
            cols_mapa = [c for c in ["codigo_territorio", "codigo_microrregiao", "microrregiao"] if c in mapa.columns]
            df = df.merge(
                mapa[cols_mapa].drop_duplicates("codigo_territorio"),
                on="codigo_territorio",
                how="left",
                suffixes=("", "_mapa")
            )
            if "codigo_microrregiao_mapa" in df.columns:
                if "codigo_microrregiao" not in df.columns:
                    df["codigo_microrregiao"] = df["codigo_microrregiao_mapa"]
                else:
                    df["codigo_microrregiao"] = df["codigo_microrregiao"].fillna(df["codigo_microrregiao_mapa"])
            if "microrregiao_mapa" in df.columns:
                if "microrregiao" not in df.columns:
                    df["microrregiao"] = df["microrregiao_mapa"]
                else:
                    df["microrregiao"] = df["microrregiao"].fillna(df["microrregiao_mapa"])
        except Exception as e:
            print(f"Aviso: não consegui carregar o mapa município-microrregião para criar a referência interna: {e}")

    if "codigo_microrregiao" not in df.columns:
        print("Aviso: a base municipal não possui codigo_microrregiao. A referência interna por microrregião não foi criada.")
        return pd.DataFrame()

    df["codigo_microrregiao"] = df["codigo_microrregiao"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)

    for col in [
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais",
        "valor_despesa_mil_reais",
        "area_estabelecimentos_ha",
        "area_total_6882_ha",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    for flag in [
        "valor_producao_mil_reais_precisa_imputar",
        "valor_despesa_mil_reais_precisa_imputar",
        "area_estabelecimentos_ha_precisa_imputar",
        "area_total_6882_precisa_imputar",
    ]:
        if flag not in df.columns:
            df[flag] = False
        else:
            df = _normalizar_flag_bool(df, flag)

    filtro_base = (
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & df["codigo_microrregiao"].notna()
        & df["numero_estabelecimentos_com_producao"].notna()
        & (df["numero_estabelecimentos_com_producao"] > 0)
    )

    ref = df.loc[filtro_base, [
        "codigo_microrregiao", "uf", "regiao", "estrato_area",
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais", "valor_despesa_mil_reais",
        "area_estabelecimentos_ha", "area_total_6882_ha",
        "valor_producao_mil_reais_precisa_imputar",
        "valor_despesa_mil_reais_precisa_imputar",
        "area_estabelecimentos_ha_precisa_imputar",
        "area_total_6882_precisa_imputar",
    ]].copy()

    n = ref["numero_estabelecimentos_com_producao"].replace(0, np.nan)

    ref["producao_mil_reais_por_estabelecimento_ref"] = np.where(
        (~ref["valor_producao_mil_reais_precisa_imputar"].fillna(False).astype(bool)) & ref["valor_producao_mil_reais"].notna(),
        ref["valor_producao_mil_reais"] / n,
        np.nan
    )
    ref["despesa_mil_reais_por_estabelecimento_ref"] = np.where(
        (~ref["valor_despesa_mil_reais_precisa_imputar"].fillna(False).astype(bool)) & ref["valor_despesa_mil_reais"].notna(),
        ref["valor_despesa_mil_reais"] / n,
        np.nan
    )
    ref["area_ha_por_estabelecimento_ref"] = np.where(
        (~ref["area_estabelecimentos_ha_precisa_imputar"].fillna(False).astype(bool))
        & ref["area_estabelecimentos_ha"].notna()
        & (ref["area_estabelecimentos_ha"] > 0),
        ref["area_estabelecimentos_ha"] / n,
        np.nan
    )
    ref["prop_area_utilizada_ref"] = np.where(
        (~ref["area_estabelecimentos_ha_precisa_imputar"].fillna(False).astype(bool))
        & (~ref["area_total_6882_precisa_imputar"].fillna(False).astype(bool))
        & ref["area_estabelecimentos_ha"].notna()
        & ref["area_total_6882_ha"].notna()
        & (ref["area_total_6882_ha"] > 0),
        ref["area_estabelecimentos_ha"] / ref["area_total_6882_ha"].replace(0, np.nan),
        np.nan
    )
    ref["prop_area_utilizada_ref"] = pd.to_numeric(ref["prop_area_utilizada_ref"], errors="coerce").clip(lower=0, upper=1)

    ref_agregada = (
        ref.groupby(["codigo_microrregiao", "uf", "regiao", "estrato_area"], as_index=False, dropna=False)
        .agg(
            producao_mil_reais_por_estabelecimento_ref=("producao_mil_reais_por_estabelecimento_ref", "median"),
            despesa_mil_reais_por_estabelecimento_ref=("despesa_mil_reais_por_estabelecimento_ref", "median"),
            area_ha_por_estabelecimento_ref=("area_ha_por_estabelecimento_ref", "median"),
            prop_area_utilizada_ref=("prop_area_utilizada_ref", "median"),
            n_municipios_referencia=("codigo_microrregiao", "size"),
        )
    )
    ref_agregada = ref_agregada.replace([np.inf, -np.inf], np.nan)
    return ref_agregada


def definir_referencia_microrregiao_interna(base_municipal):
    """Define a referência de microrregião em memória antes da imputação."""
    global _BASE_MICRORREGIAO_REF_CACHE
    ref = criar_referencia_microrregiao_a_partir_base_municipal(base_municipal)
    if ref.empty:
        print("Aviso: referência interna de microrregião vazia. O código seguirá com UF, região e Brasil quando possível.")
    else:
        _BASE_MICRORREGIAO_REF_CACHE = ref
        try:
            ref.to_csv(
                PASTA_SAIDA_FINAL / "referencia_microrregiao_criada_da_base_municipal.csv",
                index=False,
                encoding="utf-8-sig",
                sep=";",
                decimal=","
            )
        except Exception:
            pass
        print("Referência de microrregião criada automaticamente a partir da base municipal observada.")
        print(f"Linhas da referência interna: {len(ref)}")
    return ref


def carregar_base_microrregiao_referencia():
    """Carrega a base imputada da microrregião para usar como referência municipal.

    O arquivo preferencial é mi_base_imputada_area_utilizada_6882.csv, pois contém
    valores absolutos por microrregião e estrato. A partir dele são calculados:
    - produção por estabelecimento em mil reais de 2017;
    - despesa por estabelecimento em mil reais de 2017;
    - área utilizada por estabelecimento;
    - proporção área utilizada / área total.
    """
    global _BASE_MICRORREGIAO_REF_CACHE

    if _BASE_MICRORREGIAO_REF_CACHE is not None:
        return _BASE_MICRORREGIAO_REF_CACHE

    caminhos = [
        Path(ARQUIVO_BASE_MICRORREGIAO),
        Path(ARQUIVO_REFERENCIA_MICRORREGIAO)
    ]

    caminho_usado = None
    for caminho in caminhos:
        if caminho.exists():
            caminho_usado = caminho
            break

    if caminho_usado is None:
        _BASE_MICRORREGIAO_REF_CACHE = pd.DataFrame()
        return _BASE_MICRORREGIAO_REF_CACHE

    ref = pd.read_csv(
        caminho_usado,
        sep=";",
        decimal=",",
        encoding="utf-8-sig"
    )

    ref = ref.rename(columns={
        "codigo_territorio": "codigo_microrregiao",
        "territorio": "microrregiao",
        "area_por_estabelecimento": "area_ha_por_estabelecimento_ref",
        "area_ha_por_estabelecimento_imputado": "area_ha_por_estabelecimento_ref",
        "producao_corrigida_por_estabelecimento": "producao_corrigida_por_estabelecimento_ref",
        "despesa_corrigida_por_estabelecimento": "despesa_corrigida_por_estabelecimento_ref",
    })

    if "codigo_microrregiao" not in ref.columns:
        print(
            f"Atenção: {caminho_usado} não possui código de microrregião. "
            "Referência externa não será usada."
        )
        _BASE_MICRORREGIAO_REF_CACHE = pd.DataFrame()
        return _BASE_MICRORREGIAO_REF_CACHE

    ref["codigo_microrregiao"] = (
        ref["codigo_microrregiao"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
    )

    if "estrato_area" not in ref.columns:
        raise Exception(f"{caminho_usado} não possui a coluna estrato_area.")

    # Normaliza numéricos esperados.
    possiveis_num = [
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais_imputado",
        "valor_despesa_mil_reais_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "area_total_6882_ha_imputado",
        "area_utilizada_ha_imputado",
        "area_estabelecimentos_ha_imputado",
        "area_nao_utilizada_ha_imputado",
        "area_ha_por_estabelecimento_ref",
        "producao_corrigida_por_estabelecimento_ref",
        "despesa_corrigida_por_estabelecimento_ref",
    ]

    for col in possiveis_num:
        if col in ref.columns:
            ref[col] = pd.to_numeric(ref[col], errors="coerce")

    denom = ref.get("numero_estabelecimentos_com_producao")
    if denom is not None:
        denom = denom.replace(0, np.nan)

        # Preferencialmente usa valores originais em mil reais de 2017, pois o fluxo
        # municipal corrige monetariamente depois. Se a referência disponível vier
        # apenas corrigida, ela será usada somente se o fator global estiver definido
        # e será trazida de volta para a base 2017 para evitar dupla correção.
        if "valor_producao_mil_reais_imputado" in ref.columns:
            ref["producao_mil_reais_por_estabelecimento_ref"] = (
                ref["valor_producao_mil_reais_imputado"] / denom
            )
        elif "producao_corrigida_por_estabelecimento_ref" in ref.columns:
            fator_global = globals().get("FATOR_CORRECAO_IPAM_GLOBAL", np.nan)
            if pd.notna(fator_global) and fator_global > 0:
                ref["producao_mil_reais_por_estabelecimento_ref"] = (
                    ref["producao_corrigida_por_estabelecimento_ref"] / fator_global
                )

        if "valor_despesa_mil_reais_imputado" in ref.columns:
            ref["despesa_mil_reais_por_estabelecimento_ref"] = (
                ref["valor_despesa_mil_reais_imputado"] / denom
            )
        elif "despesa_corrigida_por_estabelecimento_ref" in ref.columns:
            fator_global = globals().get("FATOR_CORRECAO_IPAM_GLOBAL", np.nan)
            if pd.notna(fator_global) and fator_global > 0:
                ref["despesa_mil_reais_por_estabelecimento_ref"] = (
                    ref["despesa_corrigida_por_estabelecimento_ref"] / fator_global
                )

        if "area_ha_por_estabelecimento_ref" not in ref.columns:
            if "area_utilizada_ha_imputado" in ref.columns:
                ref["area_ha_por_estabelecimento_ref"] = (
                    ref["area_utilizada_ha_imputado"] / denom
                )
            elif "area_estabelecimentos_ha_imputado" in ref.columns:
                ref["area_ha_por_estabelecimento_ref"] = (
                    ref["area_estabelecimentos_ha_imputado"] / denom
                )

    # Proporção utilizada/total para imputação dos componentes da área municipal.
    if {
        "area_total_6882_ha_imputado",
        "area_utilizada_ha_imputado"
    }.issubset(ref.columns):
        ref["prop_area_utilizada_ref"] = (
            ref["area_utilizada_ha_imputado"] / ref["area_total_6882_ha_imputado"].replace(0, np.nan)
        )
        ref["prop_area_utilizada_ref"] = ref["prop_area_utilizada_ref"].clip(lower=0, upper=1)

    # Remove linhas de total para referências por estrato real.
    ref = ref[~ref["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL)].copy()

    _BASE_MICRORREGIAO_REF_CACHE = ref
    print(f"Referência de microrregião carregada: {caminho_usado}")
    return _BASE_MICRORREGIAO_REF_CACHE


def _filtrar_referencia_externa(row, nivel):
    ref = carregar_base_microrregiao_referencia()
    if ref.empty:
        return ref

    filtro = ref["estrato_area"].astype(str).eq(str(row["estrato_area"]))

    if nivel == "microrregiao":
        if "codigo_microrregiao" not in ref.columns or pd.isna(row.get("codigo_microrregiao")):
            return ref.iloc[0:0]
        filtro = filtro & ref["codigo_microrregiao"].astype(str).str.zfill(5).eq(str(row.get("codigo_microrregiao")).zfill(5))
    elif nivel == "uf":
        if "uf" not in ref.columns:
            return ref.iloc[0:0]
        filtro = filtro & ref["uf"].astype(str).eq(str(row["uf"]))
    elif nivel == "regiao":
        if "regiao" not in ref.columns:
            return ref.iloc[0:0]
        filtro = filtro & ref["regiao"].astype(str).eq(str(row["regiao"]))
    elif nivel == "brasil":
        pass
    else:
        return ref.iloc[0:0]

    return ref.loc[filtro].copy()


def _buscar_referencia_externa_por_estabelecimento(row, tipo):
    """Busca referência externa por estabelecimento para produção, despesa ou área.

    tipo:
    - 'producao_mil_reais'
    - 'despesa_mil_reais'
    - 'area_ha'
    """
    mapa_col = {
        "producao_mil_reais": "producao_mil_reais_por_estabelecimento_ref",
        "despesa_mil_reais": "despesa_mil_reais_por_estabelecimento_ref",
        "area_ha": "area_ha_por_estabelecimento_ref",
    }

    col = mapa_col.get(tipo)
    if col is None:
        return np.nan, "sem_tipo_referencia"

    for nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        ref = _filtrar_referencia_externa(row, nivel)
        if ref.empty or col not in ref.columns:
            continue
        valores = pd.to_numeric(ref[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        valores = valores[valores >= 0]
        if len(valores) > 0:
            return valores.median(), f"referencia_{nivel}_estrato_por_estabelecimento"

    return np.nan, "sem_referencia_externa"


def _buscar_prop_area_utilizada_externa(row):
    for nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        ref = _filtrar_referencia_externa(row, nivel)
        if ref.empty or "prop_area_utilizada_ref" not in ref.columns:
            continue
        valores = pd.to_numeric(ref["prop_area_utilizada_ref"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        valores = valores[(valores >= 0) & (valores <= 1)]
        if len(valores) > 0:
            return valores.median(), f"proporcao_area_utilizada_referencia_{nivel}"
    return np.nan, "sem_proporcao_externa"


def imputar_por_hierarquia_estrato(df, coluna_valor, coluna_flag_imputar, coluna_imputada, coluna_metodo):
    """Imputa produção/despesa usando referência da microrregião e estrato.

    Regra:
    - não imputa quando número de estabelecimentos é zero ou ausente;
    - para produção e despesa, usa primeiro a referência externa da microrregião
      gerada no código regional, no mesmo estrato;
    - se a microrregião não tiver referência, usa UF, Região e Brasil;
    - a referência é por estabelecimento e é multiplicada pelo número de
      estabelecimentos do município.
    """
    df = _normalizar_flag_bool(df, coluna_flag_imputar)

    col_n = "numero_estabelecimentos_com_producao"
    if col_n not in df.columns:
        df[col_n] = np.nan
    df[col_n] = pd.to_numeric(df[col_n], errors="coerce")

    filtro_imputar = (
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & (df[coluna_flag_imputar] == True)
        & df[col_n].notna()
        & (df[col_n] > 0)
    )

    indices_imputar = df.loc[filtro_imputar].index

    for idx in indices_imputar:
        row = df.loc[idx]
        uf = row["uf"]
        regiao = row["regiao"]
        estrato = row["estrato_area"]
        n_estab = row[col_n]

        tipo_ref = None
        if coluna_valor == "valor_producao_mil_reais":
            tipo_ref = "producao_mil_reais"
        elif coluna_valor == "valor_despesa_mil_reais":
            tipo_ref = "despesa_mil_reais"
        elif coluna_valor == "area_estabelecimentos_ha":
            tipo_ref = "area_ha"

        ref_por_estab = np.nan
        metodo = "sem_referencia"

        if tipo_ref is not None:
            ref_por_estab, metodo = _buscar_referencia_externa_por_estabelecimento(row, tipo_ref)

        # Fallback: usa a própria base municipal observada, com hierarquia territorial.
        if pd.isna(ref_por_estab):
            codigo_micro = row.get("codigo_microrregiao", np.nan)
            if "codigo_microrregiao" in df.columns and pd.notna(codigo_micro):
                ref_por_estab = _calcular_mediana_por_estabelecimento(
                    df,
                    coluna_valor,
                    coluna_flag_imputar,
                    (df["codigo_microrregiao"].astype(str).str.zfill(5) == str(codigo_micro).zfill(5))
                    & (df["estrato_area"] == estrato)
                )
                metodo = "mediana_municipios_da_microrregiao_estrato_por_estabelecimento"

        if pd.isna(ref_por_estab):
            ref_por_estab = _calcular_mediana_por_estabelecimento(
                df,
                coluna_valor,
                coluna_flag_imputar,
                (df["uf"] == uf) & (df["estrato_area"] == estrato)
            )
            metodo = "mediana_municipios_uf_estrato_por_estabelecimento"

        if pd.isna(ref_por_estab):
            ref_por_estab = _calcular_mediana_por_estabelecimento(
                df,
                coluna_valor,
                coluna_flag_imputar,
                (df["regiao"] == regiao) & (df["estrato_area"] == estrato)
            )
            metodo = "mediana_municipios_regiao_estrato_por_estabelecimento"

        if pd.isna(ref_por_estab):
            ref_por_estab = _calcular_mediana_por_estabelecimento(
                df,
                coluna_valor,
                coluna_flag_imputar,
                (df["estrato_area"] == estrato)
            )
            metodo = "mediana_municipios_brasil_estrato_por_estabelecimento"

        if pd.notna(ref_por_estab):
            valor_imputado = ref_por_estab * n_estab
        else:
            valor_imputado = np.nan
            metodo = "nao_imputado_sem_referencia"

        df.loc[idx, coluna_imputada] = valor_imputado
        df.loc[idx, coluna_metodo] = metodo

    filtro_sem_estab = (
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & (df[coluna_flag_imputar] == True)
        & (df[col_n].isna() | (df[col_n] <= 0))
    )
    df.loc[filtro_sem_estab, coluna_metodo] = "nao_imputado_sem_estabelecimentos"

    return df


def _referencia_prop_area_utilizada(df, idx, nivel):
    """Retorna proporção área utilizada / área total no mesmo estrato.

    Primeiro tenta usar a base de microrregião gerada na etapa regional.
    Se não houver referência externa, usa a própria base municipal observada.
    """
    row = df.loc[idx]
    estrato = row["estrato_area"]

    # Referência externa da etapa de microrregião, priorizando microrregião -> UF -> Região -> Brasil.
    if nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        prop_ext, metodo_ext = _buscar_prop_area_utilizada_externa(row)
        if pd.notna(prop_ext):
            # A chamada externa já segue a hierarquia completa; só devolve quando o nível pedido
            # é compatível com a busca principal.
            return prop_ext

    filtro = (
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & (df["estrato_area"] == estrato)
        & df["area_total_6882_ha"].notna()
        & df["area_estabelecimentos_ha"].notna()
        & (df["area_total_6882_ha"] > 0)
        & (df["area_estabelecimentos_ha"] >= 0)
        & (~df["area_total_6882_precisa_imputar"].fillna(False).astype(bool))
        & (~df["area_estabelecimentos_ha_precisa_imputar"].fillna(False).astype(bool))
    )

    if nivel == "microrregiao" and "codigo_microrregiao" in df.columns:
        filtro = filtro & (df["codigo_microrregiao"] == row.get("codigo_microrregiao"))
    elif nivel == "uf":
        filtro = filtro & (df["uf"] == row["uf"])
    elif nivel == "regiao":
        filtro = filtro & (df["regiao"] == row["regiao"])
    elif nivel == "brasil":
        pass
    else:
        return np.nan

    total = df.loc[filtro, "area_total_6882_ha"].sum(min_count=1)
    utilizada = df.loc[filtro, "area_estabelecimentos_ha"].sum(min_count=1)

    if pd.isna(total) or total <= 0 or pd.isna(utilizada):
        return np.nan

    prop = utilizada / total

    if pd.isna(prop):
        return np.nan

    return float(np.clip(prop, 0, 1))


def _referencia_area_utilizada_por_estabelecimento(df, idx, nivel):
    """Retorna mediana da área utilizada por estabelecimento no mesmo estrato.

    Primeiro tenta usar a base de microrregião gerada na etapa regional.
    """
    row = df.loc[idx]
    estrato = row["estrato_area"]

    if nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        valor_ext, metodo_ext = _buscar_referencia_externa_por_estabelecimento(row, "area_ha")
        if pd.notna(valor_ext):
            return valor_ext

    if "numero_estabelecimentos_com_producao" in df.columns:
        col_n = "numero_estabelecimentos_com_producao"
    else:
        col_n = "numero_estabelecimentos_com_producao"

    filtro = (
        (~df["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & (df["estrato_area"] == estrato)
        & df["area_estabelecimentos_ha"].notna()
        & (df["area_estabelecimentos_ha"] > 0)
        & df[col_n].notna()
        & (df[col_n] > 0)
        & (~df["area_estabelecimentos_ha_precisa_imputar"].fillna(False).astype(bool))
    )

    if nivel == "microrregiao" and "codigo_microrregiao" in df.columns:
        filtro = filtro & (df["codigo_microrregiao"] == row.get("codigo_microrregiao"))
    elif nivel == "uf":
        filtro = filtro & (df["uf"] == row["uf"])
    elif nivel == "regiao":
        filtro = filtro & (df["regiao"] == row["regiao"])
    elif nivel == "brasil":
        pass
    else:
        return np.nan

    valores = (df.loc[filtro, "area_estabelecimentos_ha"] / df.loc[filtro, col_n]).replace([np.inf, -np.inf], np.nan).dropna()
    valores = valores[valores > 0]

    if len(valores) == 0:
        return np.nan

    return valores.median()


def _buscar_prop_area_utilizada(df, idx):
    for nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        prop = _referencia_prop_area_utilizada(df, idx, nivel)
        if pd.notna(prop):
            return prop, f"proporcao_area_utilizada_{nivel}"
    return np.nan, "sem_proporcao_referencia"


def _buscar_area_por_estabelecimento(df, idx):
    for nivel in ["microrregiao", "uf", "regiao", "brasil"]:
        valor = _referencia_area_utilizada_por_estabelecimento(df, idx, nivel)
        if pd.notna(valor):
            return valor, f"area_por_estabelecimento_{nivel}"
    return np.nan, "sem_area_por_estabelecimento_referencia"


def imputar_area_utilizada_componentes(base_imp):
    """Imputa/reconstrói os componentes de área preservando coerência contábil.

    Regras centrais:
    0) Se não há estabelecimentos, não imputa.
    1) A área usada no custo é area_estabelecimentos_ha_imputado, equivalente
       à área utilizada final.
    2) Quando a 6882 traz total e há X nas categorias, a diferença do total é
       distribuída igualmente entre todos os X, tanto nas categorias utilizadas
       quanto nas não utilizadas.
    3) Para os dois menores estratos, quando o total observado é zero/ausente
       mas há estabelecimentos e X nas categorias, usa-se o ponto médio do
       estrato multiplicado pelo número de estabelecimentos como total imputado.
       Esse total é repartido entre área utilizada e não utilizada pela proporção
       territorial de referência (UF -> Região -> Brasil), com meio a meio apenas
       como último recurso.
    4) As colunas por estabelecimento são recalculadas sempre após a imputação,
       para evitar inconsistência entre área total, área utilizada e área usada
       no custo.
    """
    base_imp = base_imp.copy()

    col_n = "numero_estabelecimentos_com_producao"
    if col_n not in base_imp.columns:
        base_imp[col_n] = np.nan
    base_imp[col_n] = pd.to_numeric(base_imp[col_n], errors="coerce")

    for col in [
        "area_total_6882_ha", "area_utilizada_ha", "area_nao_utilizada_ha",
        "area_estabelecimentos_ha",
        "area_total_6882_ha_imputado", "area_utilizada_ha_imputado",
        "area_nao_utilizada_ha_imputado", "area_estabelecimentos_ha_imputado",
        "n_x_area_utilizada", "n_x_area_nao_utilizada"
    ]:
        if col not in base_imp.columns:
            base_imp[col] = np.nan
        base_imp[col] = pd.to_numeric(base_imp[col], errors="coerce")

    # Inicialmente, os valores imputados recebem os valores já observados/reconstruídos.
    base_imp["area_total_6882_ha_imputado"] = base_imp["area_total_6882_ha"]
    base_imp["area_utilizada_ha_imputado"] = base_imp["area_utilizada_ha"]
    base_imp["area_nao_utilizada_ha_imputado"] = base_imp["area_nao_utilizada_ha"]
    base_imp["area_estabelecimentos_ha_imputado"] = base_imp["area_utilizada_ha"]

    if "metodo_imputacao_area_componentes" not in base_imp.columns:
        base_imp["metodo_imputacao_area_componentes"] = "observado_ou_reconstruido_6882"
    else:
        base_imp["metodo_imputacao_area_componentes"] = base_imp["metodo_imputacao_area_componentes"].fillna("observado_ou_reconstruido_6882")

    flag_total = _serie_bool_segura(
        base_imp.get("area_total_6882_precisa_imputar"),
        index=base_imp.index
    )
    flag_util = _serie_bool_segura(
        base_imp.get("area_utilizada_precisa_imputar"),
        index=base_imp.index
    )
    flag_nao = _serie_bool_segura(
        base_imp.get("area_nao_utilizada_precisa_imputar"),
        index=base_imp.index
    )

    indices = base_imp.loc[
        (~base_imp["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & (
            flag_total | flag_util | flag_nao
            | base_imp["area_total_6882_ha_imputado"].isna()
            | base_imp["area_utilizada_ha_imputado"].isna()
            | base_imp["area_nao_utilizada_ha_imputado"].isna()
            | base_imp["area_estabelecimentos_ha_imputado"].isna()
        )
    ].index

    for idx in indices:
        n_estab = base_imp.loc[idx, col_n]
        if pd.isna(n_estab) or n_estab <= 0:
            base_imp.loc[idx, [
                "area_total_6882_ha_imputado",
                "area_utilizada_ha_imputado",
                "area_nao_utilizada_ha_imputado",
                "area_estabelecimentos_ha_imputado"
            ]] = np.nan
            base_imp.loc[idx, "metodo_imputacao_area"] = "nao_imputado_sem_estabelecimentos"
            base_imp.loc[idx, "metodo_imputacao_area_componentes"] = "nao_imputado_sem_estabelecimentos"
            continue

        total_obs = base_imp.loc[idx, "area_total_6882_ha"]
        util_obs = base_imp.loc[idx, "area_utilizada_ha"]
        nao_obs = base_imp.loc[idx, "area_nao_utilizada_ha"]
        nx_util = _int_zero_se_nan(base_imp.loc[idx, "n_x_area_utilizada"])
        nx_nao = _int_zero_se_nan(base_imp.loc[idx, "n_x_area_nao_utilizada"])
        total_x = nx_util + nx_nao
        estrato = str(base_imp.loc[idx, "estrato_area"]).strip()

        metodo = None

        # Ajuste especial para estratos muito pequenos: se o total da 6882 veio zero/ausente,
        # mas existem estabelecimentos e categorias com X, usa ponto médio × número de estabelecimentos
        # como total imputado. Esse total é repartido entre área utilizada e não utilizada pela
        # proporção territorial de referência (UF -> Região -> Brasil). Se não houver referência,
        # usa-se meio a meio apenas como último recurso.
        total = total_obs
        ponto_medio_aplicado = False
        if (pd.isna(total) or total <= 0) and total_x > 0:
            if estrato == "Mais de 0 a menos de 0,1 ha":
                total = 0.05 * n_estab
                metodo = "ponto_medio_0_01"
                ponto_medio_aplicado = True
            elif estrato == "De 0,1 a menos de 0,2 ha":
                total = 0.15 * n_estab
                metodo = "ponto_medio_01_02"
                ponto_medio_aplicado = True

        util_base = 0 if pd.isna(util_obs) else util_obs
        nao_base = 0 if pd.isna(nao_obs) else nao_obs

        if ponto_medio_aplicado and pd.notna(total) and total >= 0:
            prop, metodo_prop = _buscar_prop_area_utilizada(base_imp, idx)
            if pd.notna(prop):
                util = total * prop
                nao = total - util
                metodo = f"{metodo}_proporcao_{metodo_prop}"
            else:
                util = total * 0.5
                nao = total * 0.5
                metodo = f"{metodo}_meio_a_meio_sem_referencia"

        # Se há total válido e X em alguma categoria, distribui a diferença igualmente
        # entre todos os X das categorias utilizadas e não utilizadas.
        elif pd.notna(total) and total >= 0 and total_x > 0:
            diff = total - (util_base + nao_base)
            if pd.isna(diff):
                diff = np.nan
            if pd.notna(diff) and diff < 0:
                # Se por arredondamento/inconsistência a soma observada ultrapassa o total,
                # usa os valores observados e recalcula o total como soma das partes.
                util = util_base
                nao = nao_base
                total = util + nao
                metodo = metodo or "ajuste_total_para_soma_observada_6882"
            elif pd.notna(diff):
                parcela_unitaria = diff / total_x
                util = util_base + parcela_unitaria * nx_util
                nao = nao_base + parcela_unitaria * nx_nao
                metodo = metodo or "redistribuicao_diferenca_total_6882_entre_x_igualitaria"
            else:
                util = np.nan
                nao = np.nan
        else:
            # Sem X: apenas preserva/reconstrói por identidade quando possível.
            util = util_obs
            nao = nao_obs

            if pd.notna(total) and pd.notna(util) and pd.isna(nao):
                nao = total - util
                metodo = "identidade_total_menos_utilizada"
            elif pd.notna(total) and pd.notna(nao) and pd.isna(util):
                util = total - nao
                metodo = "identidade_total_menos_nao_utilizada"
            elif pd.isna(total) and pd.notna(util) and pd.notna(nao):
                total = util + nao
                metodo = "identidade_utilizada_mais_nao_utilizada"

            # Se ainda falta utilizada e há total, usa proporção territorial como fallback.
            if pd.notna(total) and total >= 0 and (pd.isna(util) or pd.isna(nao)):
                prop, metodo_prop = _buscar_prop_area_utilizada(base_imp, idx)
                if pd.notna(prop):
                    util = total * prop
                    nao = total - util
                    metodo = metodo_prop

            # Se as três faltam, usa área por estabelecimento como fallback.
            if pd.isna(total) and pd.isna(util) and pd.isna(nao):
                area_por_estab, metodo_area_estab = _buscar_area_por_estabelecimento(base_imp, idx)
                prop, metodo_prop = _buscar_prop_area_utilizada(base_imp, idx)
                if pd.notna(area_por_estab):
                    util = area_por_estab * n_estab
                    if pd.notna(prop) and prop > 0:
                        total = util / prop
                        nao = total - util
                        metodo = f"{metodo_area_estab}_e_{metodo_prop}"
                    else:
                        metodo = metodo_area_estab

        # Validações finais.
        if pd.notna(util) and util < 0:
            util = np.nan
        if pd.notna(nao) and nao < 0:
            nao = np.nan
        if pd.notna(total) and pd.notna(util) and pd.notna(nao):
            # Fecha a identidade exatamente.
            total = util + nao

        base_imp.loc[idx, "area_total_6882_ha_imputado"] = total
        base_imp.loc[idx, "area_utilizada_ha_imputado"] = util
        base_imp.loc[idx, "area_nao_utilizada_ha_imputado"] = nao
        base_imp.loc[idx, "area_estabelecimentos_ha_imputado"] = util

        if metodo:
            base_imp.loc[idx, "metodo_imputacao_area"] = metodo
            base_imp.loc[idx, "metodo_imputacao_area_componentes"] = metodo

    # Reforça a equivalência metodológica: a área usada no custo é a área utilizada.
    base_imp["area_estabelecimentos_ha_imputado"] = base_imp["area_utilizada_ha_imputado"]

    filtro_sem_area = (
        (~base_imp["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL))
        & base_imp["area_estabelecimentos_ha_imputado"].isna()
        & base_imp[col_n].notna()
        & (base_imp[col_n] > 0)
    )
    base_imp.loc[filtro_sem_area, "metodo_imputacao_area"] = "nao_imputado_sem_referencia_area"
    base_imp.loc[filtro_sem_area, "metodo_imputacao_area_componentes"] = "nao_imputado_sem_referencia_area"

    return base_imp

def corrigir_areas_imputadas_pequenos_estratos(base):
    # A correção dos pequenos estratos agora é feita dentro de
    # imputar_area_utilizada_componentes, atualizando simultaneamente
    # área total, utilizada, não utilizada e área usada no custo.
    return base


def imputar_e_recalcular(base, fator_correcao):
    base_imp = base.copy()

    variaveis = [
        (
            "valor_producao_mil_reais",
            "valor_producao_mil_reais_precisa_imputar",
            "valor_producao_mil_reais_imputado",
            "metodo_imputacao_producao"
        ),
        (
            "valor_despesa_mil_reais",
            "valor_despesa_mil_reais_precisa_imputar",
            "valor_despesa_mil_reais_imputado",
            "metodo_imputacao_despesa"
        ),
        (
            "area_estabelecimentos_ha",
            "area_estabelecimentos_ha_precisa_imputar",
            "area_estabelecimentos_ha_imputado",
            "metodo_imputacao_area"
        )
    ]

    for coluna_valor, coluna_flag, coluna_imputada, coluna_metodo in variaveis:
        base_imp[coluna_imputada] = base_imp[coluna_valor]
        base_imp[coluna_metodo] = "observado"

        base_imp = imputar_por_diferenca_do_total(
            base_imp,
            coluna_valor,
            coluna_flag,
            coluna_imputada,
            coluna_metodo
        )

        # Área utilizada recebe uma função própria para preservar a identidade:
        # área total = área utilizada + área não utilizada.
        if coluna_valor != "area_estabelecimentos_ha":
            base_imp = imputar_por_hierarquia_estrato(
                base_imp,
                coluna_valor,
                coluna_flag,
                coluna_imputada,
                coluna_metodo
            )

    base_imp = imputar_area_utilizada_componentes(base_imp)
    base_imp = corrigir_areas_imputadas_pequenos_estratos(base_imp)
    base_imp = calcular_custos(base_imp, fator_correcao, sufixo="_imputado")

    return base_imp

# ============================================================
# 9. TABELAS DE REFERÊNCIA TERRITORIAL POR ESTABELECIMENTO
# ============================================================

def gerar_tabela_referencia_territorial(base_imp, fator_correcao):
    """Gera tabela com valores por município, UF e Brasil.

    Correção desta versão:
    - a base municipal pode chegar com ou sem as colunas codigo_microrregiao e microrregiao;
    - para os níveis UF e Brasil essas colunas são preenchidas com vazio/Brasil;
    - evita KeyError ao selecionar as colunas finais.
    """
    base_ref = base_imp[~base_imp["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL)].copy()

    # Garante a existência das colunas de microrregião.
    # Elas devem vir do mapa_municipio_micro.csv; caso não existam, ficam vazias
    # para não quebrar a geração das tabelas de referência.
    if "codigo_microrregiao" not in base_ref.columns:
        base_ref["codigo_microrregiao"] = ""
    if "microrregiao" not in base_ref.columns:
        base_ref["microrregiao"] = ""

    def agrega(df, grupo_cols, nivel):
        out = (
            df.groupby(grupo_cols, as_index=False, dropna=False)
            .agg(
                numero_estabelecimentos_com_producao=("numero_estabelecimentos_com_producao", lambda x: x.sum(min_count=1)),
                valor_producao_mil_reais_imputado=("valor_producao_mil_reais_imputado", lambda x: x.sum(min_count=1)),
                valor_despesa_mil_reais_imputado=("valor_despesa_mil_reais_imputado", lambda x: x.sum(min_count=1)),
                area_estabelecimentos_ha_imputado=("area_estabelecimentos_ha_imputado", lambda x: x.sum(min_count=1)),
            )
        )
        out["nivel"] = nivel
        out = calcular_custos(out, fator_correcao, sufixo="_imputado")
        return out

    cols_ref_mun = [
        "codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area",
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais_imputado",
        "valor_despesa_mil_reais_imputado",
        "area_estabelecimentos_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo",
        "area_ha_por_estabelecimento_imputado",
        "area_total_ha_por_estabelecimento_imputado",
        "area_nao_utilizada_ha_por_estabelecimento_imputado",
        "valor_producao_corrigido_mil_reais_por_estabelecimento_imputado",
        "valor_despesa_corrigido_mil_reais_por_estabelecimento_imputado",
        "resultado_liquido_corrigido_mil_reais_por_estabelecimento_imputado",
    ]

    # Garante colunas eventualmente ausentes, sem interromper a execução.
    for c in cols_ref_mun:
        if c not in base_ref.columns:
            base_ref[c] = np.nan

    ref_mi = base_ref[cols_ref_mun].copy()
    ref_mi["nivel"] = "Município"

    ref_uf = agrega(base_ref, ["regiao", "uf", "estrato_area"], "UF")
    ref_uf["codigo_territorio"] = "UF"
    ref_uf["territorio"] = ref_uf["uf"]
    ref_uf["codigo_microrregiao"] = ""
    ref_uf["microrregiao"] = ""

    ref_brasil = agrega(base_ref, ["estrato_area"], "Brasil")
    ref_brasil["codigo_territorio"] = "Brasil"
    ref_brasil["territorio"] = "Brasil"
    ref_brasil["codigo_microrregiao"] = "Brasil"
    ref_brasil["microrregiao"] = "Brasil"
    ref_brasil["uf"] = "Brasil"
    ref_brasil["regiao"] = "Brasil"

    cols = [
        "nivel", "codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area",
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais_imputado",
        "valor_despesa_mil_reais_imputado",
        "area_estabelecimentos_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo",
        "area_ha_por_estabelecimento_imputado",
        "area_total_ha_por_estabelecimento_imputado",
        "area_nao_utilizada_ha_por_estabelecimento_imputado",
        "valor_producao_corrigido_mil_reais_por_estabelecimento_imputado",
        "valor_despesa_corrigido_mil_reais_por_estabelecimento_imputado",
        "resultado_liquido_corrigido_mil_reais_por_estabelecimento_imputado",
    ]

    tabela = pd.concat([ref_mi, ref_uf, ref_brasil], ignore_index=True)
    for c in cols:
        if c not in tabela.columns:
            tabela[c] = np.nan

    return tabela[cols]

# ============================================================
# 9. ESTATÍSTICAS E RESUMOS
# ============================================================

def gerar_estatisticas(base_imp):
    base_stats = base_imp.copy()
    col = "custo_oportunidade_corrigido_r_ha_imputado"
    base_stats[col] = base_stats[col].replace([np.inf, -np.inf], np.nan)

    def resumo_grupo(df, grupo_cols, nivel_nome):
        out = (
            df.groupby(grupo_cols, dropna=False)[col]
            .agg(
                media=lambda x: x.dropna().mean(),
                mediana=lambda x: x.dropna().median(),
                q1=lambda x: x.dropna().quantile(0.25),
                q3=lambda x: x.dropna().quantile(0.75),
                minimo=lambda x: x.dropna().min(),
                maximo=lambda x: x.dropna().max(),
                desvio_padrao=lambda x: x.dropna().std(),
                n_validos=lambda x: x.dropna().shape[0],
                n_total="size",
                n_invalidos=lambda x: x.isna().sum()
            ).reset_index()
        )
        out["nivel"] = nivel_nome
        return out

    estat_brasil = resumo_grupo(base_stats, ["estrato_area"], "Brasil")
    estat_brasil["codigo_territorio"] = "Brasil"
    estat_brasil["territorio"] = "Brasil"
    estat_brasil["codigo_microrregiao"] = "Brasil"
    estat_brasil["microrregiao"] = "Brasil"
    estat_brasil["uf"] = "Brasil"
    estat_brasil["regiao"] = "Brasil"

    estat_regiao = resumo_grupo(base_stats, ["regiao", "estrato_area"], "Região")
    estat_regiao["codigo_territorio"] = "Região"
    estat_regiao["territorio"] = estat_regiao["regiao"]
    estat_regiao["codigo_microrregiao"] = ""
    estat_regiao["microrregiao"] = ""
    estat_regiao["uf"] = ""

    estat_uf = resumo_grupo(base_stats, ["regiao", "uf", "estrato_area"], "UF")
    estat_uf["codigo_territorio"] = "UF"
    estat_uf["territorio"] = estat_uf["uf"]
    estat_uf["codigo_microrregiao"] = ""
    estat_uf["microrregiao"] = ""

    estat_mi = resumo_grupo(base_stats, ["codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area"], "Município")

    estatisticas = pd.concat([estat_brasil, estat_regiao, estat_uf, estat_mi], ignore_index=True)
    return estatisticas[[
        "nivel", "codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area",
        "media", "mediana", "q1", "q3", "minimo", "maximo", "desvio_padrao", "n_validos", "n_total", "n_invalidos"
    ]]



def gerar_estatisticas_custo_nao_negativo(base_imp):
    """Gera estatísticas usando o custo de oportunidade com negativos substituídos por zero."""
    base_stats = base_imp.copy()
    col = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"

    if col not in base_stats.columns:
        base_stats[col] = base_stats["custo_oportunidade_corrigido_r_ha_imputado"].clip(lower=0)

    base_stats[col] = base_stats[col].replace([np.inf, -np.inf], np.nan)

    def resumo_grupo(df, grupo_cols, nivel_nome):
        out = (
            df.groupby(grupo_cols, dropna=False)[col]
            .agg(
                media=lambda x: x.dropna().mean(),
                mediana=lambda x: x.dropna().median(),
                q1=lambda x: x.dropna().quantile(0.25),
                q3=lambda x: x.dropna().quantile(0.75),
                minimo=lambda x: x.dropna().min(),
                maximo=lambda x: x.dropna().max(),
                desvio_padrao=lambda x: x.dropna().std(),
                n_validos=lambda x: x.dropna().shape[0],
                n_total="size",
                n_invalidos=lambda x: x.isna().sum()
            ).reset_index()
        )
        out["nivel"] = nivel_nome
        out["variavel_estatistica"] = col
        return out

    estat_brasil = resumo_grupo(base_stats, ["estrato_area"], "Brasil")
    estat_brasil["codigo_territorio"] = "Brasil"
    estat_brasil["territorio"] = "Brasil"
    estat_brasil["codigo_microrregiao"] = "Brasil"
    estat_brasil["microrregiao"] = "Brasil"
    estat_brasil["uf"] = "Brasil"
    estat_brasil["regiao"] = "Brasil"

    estat_regiao = resumo_grupo(base_stats, ["regiao", "estrato_area"], "Região")
    estat_regiao["codigo_territorio"] = "Região"
    estat_regiao["territorio"] = estat_regiao["regiao"]
    estat_regiao["codigo_microrregiao"] = ""
    estat_regiao["microrregiao"] = ""
    estat_regiao["uf"] = ""

    estat_uf = resumo_grupo(base_stats, ["regiao", "uf", "estrato_area"], "UF")
    estat_uf["codigo_territorio"] = "UF"
    estat_uf["territorio"] = estat_uf["uf"]
    estat_uf["codigo_microrregiao"] = ""
    estat_uf["microrregiao"] = ""

    estat_mi = resumo_grupo(
        base_stats,
        ["codigo_territorio", "territorio", "uf", "regiao", "estrato_area"],
        "Município"
    )

    estatisticas = pd.concat([estat_brasil, estat_regiao, estat_uf, estat_mi], ignore_index=True)
    return estatisticas[[
        "nivel", "codigo_territorio", "territorio", "codigo_microrregiao", "microrregiao", "uf", "regiao", "estrato_area", "variavel_estatistica",
        "media", "mediana", "q1", "q3", "minimo", "maximo", "desvio_padrao", "n_validos", "n_total", "n_invalidos"
    ]]


def gerar_resumo_imputacao(base_imp):
    base_resumo = base_imp[~base_imp["estrato_area"].isin(ESTRATOS_EXCLUIR_TOTAL)].copy()
    metodos_mediana = [
        "mediana_uf_estrato_por_estabelecimento",
        "mediana_regiao_estrato_por_estabelecimento",
        "mediana_brasil_estrato_por_estabelecimento"
    ]

    def conta_metodo(col, metodo):
        return (col == metodo).sum()

    def conta_mediana(col):
        return col.isin(metodos_mediana).sum()

    def montar_resumo_por(grupo_cols, nivel_nome):
        resumo = (
            base_resumo.groupby(grupo_cols, as_index=False, dropna=False)
            .agg(
                n_total=("territorio", "count"),
                n_com_custo=("custo_oportunidade_corrigido_r_ha_imputado", lambda x: x.notna().sum()),
                n_sem_custo=("custo_oportunidade_corrigido_r_ha_imputado", lambda x: x.isna().sum()),
                producao_imputada_diferenca=("metodo_imputacao_producao", lambda x: conta_metodo(x, "diferenca_total_sidra")),
                despesa_imputada_diferenca=("metodo_imputacao_despesa", lambda x: conta_metodo(x, "diferenca_total_sidra")),
                area_imputada_diferenca=("metodo_imputacao_area", lambda x: conta_metodo(x, "diferenca_total_sidra")),
                producao_imputada_mediana=("metodo_imputacao_producao", conta_mediana),
                despesa_imputada_mediana=("metodo_imputacao_despesa", conta_mediana),
                area_imputada_mediana=("metodo_imputacao_area", conta_mediana),
            )
        )
        resumo["nivel"] = nivel_nome
        resumo["total_imputado_diferenca"] = resumo["producao_imputada_diferenca"] + resumo["despesa_imputada_diferenca"] + resumo["area_imputada_diferenca"]
        resumo["total_imputado_mediana"] = resumo["producao_imputada_mediana"] + resumo["despesa_imputada_mediana"] + resumo["area_imputada_mediana"]
        resumo["total_geral_imputado"] = resumo["total_imputado_diferenca"] + resumo["total_imputado_mediana"]
        return resumo

    resumo_uf = montar_resumo_por(["regiao", "uf", "estrato_area"], "UF")

    resumo_brasil_estrato = montar_resumo_por(["estrato_area"], "Brasil por estrato")
    resumo_brasil_estrato["regiao"] = "Brasil"
    resumo_brasil_estrato["uf"] = "Brasil"

    resumo_brasil_total = pd.DataFrame({
        "nivel": ["Brasil total"],
        "regiao": ["Brasil"],
        "uf": ["Brasil"],
        "estrato_area": ["Todos os estratos"],
        "n_total": [base_resumo.shape[0]],
        "n_com_custo": [base_resumo["custo_oportunidade_corrigido_r_ha_imputado"].notna().sum()],
        "n_sem_custo": [base_resumo["custo_oportunidade_corrigido_r_ha_imputado"].isna().sum()],
        "producao_imputada_diferenca": [(base_resumo["metodo_imputacao_producao"] == "diferenca_total_sidra").sum()],
        "despesa_imputada_diferenca": [(base_resumo["metodo_imputacao_despesa"] == "diferenca_total_sidra").sum()],
        "area_imputada_diferenca": [(base_resumo["metodo_imputacao_area"] == "diferenca_total_sidra").sum()],
        "producao_imputada_mediana": [base_resumo["metodo_imputacao_producao"].isin(metodos_mediana).sum()],
        "despesa_imputada_mediana": [base_resumo["metodo_imputacao_despesa"].isin(metodos_mediana).sum()],
        "area_imputada_mediana": [base_resumo["metodo_imputacao_area"].isin(metodos_mediana).sum()],
    })
    resumo_brasil_total["total_imputado_diferenca"] = resumo_brasil_total["producao_imputada_diferenca"] + resumo_brasil_total["despesa_imputada_diferenca"] + resumo_brasil_total["area_imputada_diferenca"]
    resumo_brasil_total["total_imputado_mediana"] = resumo_brasil_total["producao_imputada_mediana"] + resumo_brasil_total["despesa_imputada_mediana"] + resumo_brasil_total["area_imputada_mediana"]
    resumo_brasil_total["total_geral_imputado"] = resumo_brasil_total["total_imputado_diferenca"] + resumo_brasil_total["total_imputado_mediana"]

    resumo = pd.concat([resumo_uf, resumo_brasil_estrato, resumo_brasil_total], ignore_index=True)
    return resumo[[
        "nivel", "regiao", "uf", "estrato_area",
        "n_total", "n_com_custo", "n_sem_custo",
        "producao_imputada_diferenca", "despesa_imputada_diferenca", "area_imputada_diferenca", "total_imputado_diferenca",
        "producao_imputada_mediana", "despesa_imputada_mediana", "area_imputada_mediana", "total_imputado_mediana",
        "total_geral_imputado"
    ]]

# ============================================================
# 10. BASE SEM IMPUTAÇÃO
# ============================================================

def criar_base_sem_imputacao_para_conferencia(base_mi, total_sem_area_sem_imputacao):
    """Cria base de conferência sem substituir colunas numéricas por texto.

    As colunas *_original são mantidas para auditoria, mas as colunas principais
    permanecem numéricas. Isso evita que textos como "Contém categoria(s)..."
    apareçam na coluna area_estabelecimentos_ha.
    """
    base_conf = base_mi.copy()
    return pd.concat([base_conf, total_sem_area_sem_imputacao], ignore_index=True)


def remover_colunas_auxiliares_e_ordenar(base):
    """Organiza a base final em ordem lógica e remove colunas auxiliares.

    A base final começa com os valores brutos do SIDRA, preservando os
    caracteres originais para conferência. Depois aparecem os valores numéricos
    convertidos, os valores imputados, as correções monetárias e, por último,
    o custo de oportunidade.
    """
    base = base.copy()

    # Colunas auxiliares que não devem aparecer na base principal.
    colunas_remover = [
        "area_utilizada_por_diferenca_ha",
        "diferenca_area_utilizada_soma_vs_diferenca",
        "diferenca_total_menos_categorias_observadas_6882",
        "area_utilizada_observada_ha",
        "area_nao_utilizada_observada_ha",
        "n_x_area_utilizada",
        "n_x_area_nao_utilizada",
        "area_soma_valida",
        "area_diferenca_valida",
        "categorias_utilizadas_encontradas",
        "categorias_nao_utilizadas_encontradas",
        "area_utilizada_ha_por_estabelecimento",
        "valor_producao_corrigido_mil_reais",
        "valor_despesa_corrigido_mil_reais",
        "resultado_liquido_corrigido_mil_reais",
        "custo_oportunidade_corrigido_r_ha",
        "custo_oportunidade_corrigido_r_ha_nao_negativo",
        "area_ha_por_estabelecimento",
        "area_total_ha_por_estabelecimento",
        "area_nao_utilizada_ha_por_estabelecimento",
        "valor_producao_mil_reais_por_estabelecimento",
        "valor_despesa_mil_reais_por_estabelecimento",
        "resultado_liquido_mil_reais_por_estabelecimento",
        "valor_producao_corrigido_mil_reais_por_estabelecimento",
        "valor_despesa_corrigido_mil_reais_por_estabelecimento",
        "valor_producao_corrigido_reais_por_estabelecimento",
        "valor_despesa_corrigido_reais_por_estabelecimento",
        "resultado_liquido_corrigido_reais_por_estabelecimento",
        "area_utilizada_ha_por_estabelecimento_imputado",
        "resultado_liquido_corrigido_mil_reais_por_estabelecimento_imputado",
    ]

    base = base.drop(
        columns=[c for c in colunas_remover if c in base.columns],
        errors="ignore"
    )

    # Renomeia colunas brutas para deixar claro que são valores originais do SIDRA.
    renomear = {
        "numero_estabelecimentos_com_producao_original": "sidra_numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais_original": "sidra_valor_producao_mil_reais",
        "valor_despesa_mil_reais_original": "sidra_valor_despesa_mil_reais",
        "area_total_6882_original": "sidra_area_total_6882",
        "area_estabelecimentos_ha_original": "sidra_metodo_area_utilizada",
    }
    base = base.rename(columns={k: v for k, v in renomear.items() if k in base.columns})

    colunas_ordenadas = [
        # Identificação territorial
        "codigo_territorio", "territorio", "uf", "regiao", "estrato_area",

        # Valores brutos SIDRA, com caracteres originais para conferência
        "sidra_numero_estabelecimentos_com_producao",
        "sidra_valor_producao_mil_reais",
        "sidra_valor_despesa_mil_reais",
        "sidra_area_total_6882",
        "sidra_area_utilizada_6882",
        "sidra_area_nao_utilizada_6882",
        "sidra_metodo_area_utilizada",

        # Flags de ausência/sigilo do SIDRA
        "valor_producao_mil_reais_precisa_imputar",
        "valor_despesa_mil_reais_precisa_imputar",
        "area_total_6882_precisa_imputar",
        "area_utilizada_precisa_imputar",
        "area_nao_utilizada_precisa_imputar",
        "area_estabelecimentos_ha_precisa_imputar",

        # Valores convertidos/observados
        "numero_estabelecimentos_com_producao",
        "valor_producao_mil_reais",
        "valor_despesa_mil_reais",
        "area_total_6882_ha",
        "area_utilizada_ha",
        "area_nao_utilizada_ha",
        "area_estabelecimentos_ha",
        "metodo_area_utilizada",

        # Valores finais imputados
        "valor_producao_mil_reais_imputado",
        "metodo_imputacao_producao",
        "valor_despesa_mil_reais_imputado",
        "metodo_imputacao_despesa",
        "area_total_6882_ha_imputado",
        "area_utilizada_ha_imputado",
        "area_nao_utilizada_ha_imputado",
        "area_estabelecimentos_ha_imputado",
        "metodo_imputacao_area",
        "metodo_imputacao_area_componentes",

        # Valores originais e corrigidos / indicadores intermediários
        "resultado_liquido_mil_reais_imputado",
        "custo_oportunidade_r_ha_2017_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
        "area_ha_por_estabelecimento_imputado",
        "area_total_ha_por_estabelecimento_imputado",
        "area_nao_utilizada_ha_por_estabelecimento_imputado",
        "valor_producao_corrigido_mil_reais_por_estabelecimento_imputado",
        "valor_despesa_corrigido_mil_reais_por_estabelecimento_imputado",
        "resultado_liquido_corrigido_mil_reais_por_estabelecimento_imputado",

        # Custos por último, seguindo a cronologia do cálculo
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo",
    ]

    colunas_existentes = [c for c in colunas_ordenadas if c in base.columns]
    outras = [c for c in base.columns if c not in colunas_existentes]

    # Mantém outras colunas não previstas antes dos custos finais.
    custos_finais = [
        c for c in [
            "custo_oportunidade_corrigido_r_ha_imputado",
            "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
        ]
        if c in colunas_existentes
    ]
    if custos_finais:
        colunas_sem_custo = [c for c in colunas_existentes if c not in custos_finais]
        outras_sem_custo = [c for c in outras if c not in custos_finais]
        return base[colunas_sem_custo + outras_sem_custo + custos_finais].copy()

    return base[colunas_existentes + outras].copy()


def selecionar_colunas_base_principal(base):
    return remover_colunas_auxiliares_e_ordenar(base)


# ============================================================
# 11. TABELAS DE REFERÊNCIA PARA IMPUTAÇÃO MUNICIPAL
# ============================================================

def criar_tabelas_referencia_imputacao(base_mun_imputada):
    """Cria quatro tabelas de referência para a etapa municipal.

    - referencia_microrregiao.csv: valores absolutos e por estabelecimento por município.
    - referencia_uf.csv: medianas por estabelecimento por UF e estrato.
    - referencia_regiao.csv: medianas por estabelecimento por grande região e estrato.
    - referencia_brasil.csv: medianas por estabelecimento no Brasil por estrato.
    """

    base_ref = base_mun_imputada.copy()
    base_ref = base_ref[
        ~base_ref["estrato_area"].isin(["Total", "Total sem produtor sem área"])
    ].copy()

    colunas_num = [
        "numero_estabelecimentos_com_producao",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
        "area_estabelecimentos_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo",
    ]

    for col in colunas_num:
        if col in base_ref.columns:
            base_ref[col] = pd.to_numeric(base_ref[col], errors="coerce")

    denom = base_ref["numero_estabelecimentos_com_producao"].replace(0, np.nan)

    base_ref["area_por_estabelecimento"] = base_ref["area_estabelecimentos_ha_imputado"] / denom
    base_ref["producao_corrigida_por_estabelecimento"] = (
        base_ref["valor_producao_corrigido_mil_reais_imputado"] / denom
    )
    base_ref["despesa_corrigida_por_estabelecimento"] = (
        base_ref["valor_despesa_corrigido_mil_reais_imputado"] / denom
    )
    base_ref["resultado_corrigido_por_estabelecimento"] = (
        base_ref["resultado_liquido_corrigido_mil_reais_imputado"] / denom
    )

    cols_ref = [
        "codigo_territorio", "territorio", "uf", "regiao", "estrato_area",
        "numero_estabelecimentos_com_producao",
        "area_estabelecimentos_ha_imputado",
        "area_total_6882_ha_imputado",
        "area_utilizada_ha_imputado",
        "area_nao_utilizada_ha_imputado",
        "valor_producao_corrigido_mil_reais_imputado",
        "valor_despesa_corrigido_mil_reais_imputado",
        "resultado_liquido_corrigido_mil_reais_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo",
        "area_por_estabelecimento",
        "producao_corrigida_por_estabelecimento",
        "despesa_corrigida_por_estabelecimento",
        "resultado_corrigido_por_estabelecimento",
    ]

    referencia_microrregiao = base_ref[cols_ref].copy().rename(columns={
        "codigo_territorio": "codigo_microrregiao",
        "territorio": "microrregiao",
    })

    def mediana_ref(grupo_cols):
        return (
            base_ref
            .groupby(grupo_cols, as_index=False, dropna=False)
            .agg(
                mediana_area_por_estabelecimento=("area_por_estabelecimento", "median"),
                mediana_producao_corrigida_por_estabelecimento=("producao_corrigida_por_estabelecimento", "median"),
                mediana_despesa_corrigida_por_estabelecimento=("despesa_corrigida_por_estabelecimento", "median"),
                mediana_resultado_corrigido_por_estabelecimento=("resultado_corrigido_por_estabelecimento", "median"),
                mediana_custo_oportunidade_corrigido_r_ha=("custo_oportunidade_corrigido_r_ha_imputado", "median"),
                mediana_custo_oportunidade_corrigido_r_ha_nao_negativo=("custo_oportunidade_corrigido_r_ha_imputado_nao_negativo", "median"),
                n_municipios_referencia=("codigo_territorio", "count"),
            )
        )

    referencia_uf = mediana_ref(["uf", "regiao", "estrato_area"])
    referencia_regiao = mediana_ref(["regiao", "estrato_area"])
    referencia_brasil = mediana_ref(["estrato_area"])
    referencia_brasil["regiao"] = "Brasil"
    referencia_brasil["uf"] = "Brasil"
    referencia_brasil = referencia_brasil[
        [
            "uf", "regiao", "estrato_area",
            "mediana_area_por_estabelecimento",
            "mediana_producao_corrigida_por_estabelecimento",
            "mediana_despesa_corrigida_por_estabelecimento",
            "mediana_resultado_corrigido_por_estabelecimento",
            "mediana_custo_oportunidade_corrigido_r_ha",
            "mediana_custo_oportunidade_corrigido_r_ha_nao_negativo",
            "n_municipios_referencia",
        ]
    ]

    referencia_microrregiao.to_csv("referencia_microrregiao.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    referencia_uf.to_csv("referencia_uf.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    referencia_regiao.to_csv("referencia_regiao.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    referencia_brasil.to_csv("referencia_brasil.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")

    return referencia_microrregiao, referencia_uf, referencia_regiao, referencia_brasil


# ============================================================
# 11. VALIDAÇÃO DE CONSISTÊNCIA DA BASE FINAL
# ============================================================

def validar_consistencia_base(base):
    """Gera uma tabela curta com validações da base final.

    Esta validação confirma que:
    - o custo corrigido é o custo original por hectare multiplicado pelo fator IPA-M;
    - o denominador do custo é a área utilizada/produtiva do estrato;
    - indicadores por estabelecimento são apenas auxiliares;
    - a identidade área total = área utilizada + área não utilizada está preservada.
    """
    b = base.copy()

    checks = []

    if {
        "area_total_6882_ha_imputado",
        "area_utilizada_ha_imputado",
        "area_nao_utilizada_ha_imputado"
    }.issubset(b.columns):
        dif_area = (
            b["area_total_6882_ha_imputado"]
            - b["area_utilizada_ha_imputado"]
            - b["area_nao_utilizada_ha_imputado"]
        ).replace([np.inf, -np.inf], np.nan)
        checks.append({
            "validacao": "area_total_menos_utilizada_menos_nao_utilizada",
            "max_abs_diferenca": dif_area.abs().max(),
            "n_linhas_com_diferenca_maior_1ha": (dif_area.abs() > 1).sum()
        })

    if {
        "resultado_liquido_corrigido_mil_reais_imputado",
        "area_utilizada_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado"
    }.issubset(b.columns):
        custo_calc = (
            b["resultado_liquido_corrigido_mil_reais_imputado"] * 1000
        ) / b["area_utilizada_ha_imputado"]
        dif_custo = (
            b["custo_oportunidade_corrigido_r_ha_imputado"] - custo_calc
        ).replace([np.inf, -np.inf], np.nan)
        dif_custo = dif_custo[b["custo_oportunidade_corrigido_r_ha_imputado"].notna()]
        checks.append({
            "validacao": "custo_usa_resultado_total_dividido_area_utilizada",
            "max_abs_diferenca": dif_custo.abs().max(),
            "n_linhas_com_diferenca_maior_001": (dif_custo.abs() > 0.01).sum()
        })

    if {
        "custo_oportunidade_r_ha_2017_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado"
    }.issubset(b.columns):
        fator_global = globals().get("FATOR_CORRECAO_IPAM_GLOBAL", np.nan)
        if pd.notna(fator_global) and fator_global > 0:
            dif_corr = (
                b["custo_oportunidade_corrigido_r_ha_imputado"]
                - b["custo_oportunidade_r_ha_2017_imputado"] * fator_global
            ).replace([np.inf, -np.inf], np.nan)
            dif_corr = dif_corr[b["custo_oportunidade_corrigido_r_ha_imputado"].notna()]
            checks.append({
                "validacao": "custo_corrigido_igual_custo_2017_vezes_fator_ipam",
                "max_abs_diferenca": dif_corr.abs().max(),
                "n_linhas_com_diferenca_maior_001": (dif_corr.abs() > 0.01).sum()
            })

    if {
        "custo_oportunidade_corrigido_r_ha_imputado",
        "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
    }.issubset(b.columns):
        custo_nn_calc = b["custo_oportunidade_corrigido_r_ha_imputado"].clip(lower=0)
        dif_nn = (
            b["custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"] - custo_nn_calc
        ).replace([np.inf, -np.inf], np.nan)
        dif_nn = dif_nn[b["custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"].notna()]
        checks.append({
            "validacao": "custo_nao_negativo_substitui_negativos_por_zero",
            "max_abs_diferenca": dif_nn.abs().max(),
            "n_linhas_com_diferenca_maior_001": (dif_nn.abs() > 0.01).sum()
        })

    return pd.DataFrame(checks)

# ============================================================
# 11. EXECUÇÃO
# ============================================================


# ============================================================
# 12. PÓS-PROCESSAMENTO FINAL E FIGURAS PARA O ARTIGO
# ============================================================

ESTRATOS_MENORES_QUE_5HA_FINAL = [
    "Mais de 0 a menos de 0,1 ha",
    "De 0,1 a menos de 0,2 ha",
    "De 0,2 a menos de 0,5 ha",
    "De 0,5 a menos de 1 ha",
    "De 1 a menos de 2 ha",
    "De 2 a menos de 3 ha",
    "De 3 a menos de 4 ha",
    "De 4 a menos de 5 ha",
]

ESTRATOS_EXCLUIR_ANALISE_FINAL = [
    "Total",
    "Total sem produtor sem área",
    "Produtor sem área",
]

MAPA_GRUPOS_ESTRATOS_FINAL = {
    "De 5 a menos de 10 ha": "1) De 5 a < 20 ha",
    "De 10 a menos de 20 ha": "1) De 5 a < 20 ha",
    "De 20 a menos de 50 ha": "2) De 20 a < 100 ha",
    "De 50 a menos de 100 ha": "2) De 20 a < 100 ha",
    "De 100 a menos de 200 ha": "3) De 100 a < 500 ha",
    "De 200 a menos de 500 ha": "3) De 100 a < 500 ha",
    "De 500 a menos de 1.000 ha": "4) >= 500 ha",
    "De 1.000 a menos de 2.500 ha": "4) >= 500 ha",
    "De 2.500 a menos de 10.000 ha": "4) >= 500 ha",
    "De 10.000 ha e mais": "4) >= 500 ha",
}

ORDEM_GRUPOS_FINAL = [
    "1) De 5 a < 20 ha",
    "2) De 20 a < 100 ha",
    "3) De 100 a < 500 ha",
    "4) >= 500 ha",
    "5) >= 5 ha",
]

BINS_CUSTO_FINAL = [0, 500, 1000, 2500, 5000, 10000, 15000]
TAMANHO_FONTE_TITULO_FINAL = 18
TAMANHO_FONTE_LEGENDA_FINAL = 18
TAMANHO_FONTE_SIGLA_UF_FINAL = 16
TAMANHO_FONTE_SIGLA_REGIAO_FINAL = 28
TOP_N_RANKING_FINAL = 30

MAPA_SIGLAS_REGIAO_FINAL = {
    "Norte": "N",
    "Nordeste": "NE",
    "Sudeste": "SE",
    "Sul": "S",
    "Centro-Oeste": "CO",
}


def _salvar_csv_final(df, nome):
    caminho = PASTA_SAIDA_FINAL / nome
    df.to_csv(caminho, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    print(f"Salvo: {caminho}")
    return caminho


def _salvar_fig_final(nome):
    caminho = PASTA_SAIDA_FINAL / nome
    plt.savefig(caminho, dpi=300, bbox_inches="tight")
    print(f"Salvo: {caminho}")
    return caminho


def _formatar_numero_br_final(x):
    if pd.isna(x):
        return ""
    return f"{float(x):,.0f}".replace(",", ".")


def _nome_arquivo_seguro_final(txt):
    txt = str(txt).lower().strip()
    substituicoes = {
        " ": "_", "-": "", "–": "", "—": "", ",": "", ";": "", ":": "",
        "/": "_", "\\": "_", "ã": "a", "á": "a", "à": "a", "â": "a",
        "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "õ": "o",
        "ú": "u", "ç": "c", "(": "", ")": "", ">": "maior", "<": "menor",
        "=": "", "≥": "maior_igual"
    }
    for k, v in substituicoes.items():
        txt = txt.replace(k, v)
    return txt


def _padronizar_codigo_municipio_final(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(7)
    )


def _padronizar_codigo_micro_final(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(5)
    )


def _padronizar_codigo_uf_final(s):
    return (
        s.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(2)
    )


def _limpar_nome_microrregiao_final(nome):
    if pd.isna(nome):
        return nome
    txt = str(nome).strip()
    txt = re.sub(r"\s*-\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*/\s*[A-Z]{2}$", "", txt)
    txt = re.sub(r"\s*\([A-Z]{2}\)$", "", txt)
    return txt.strip()


def _preparar_base_final_artigo(base_mun_imputada):
    b = selecionar_colunas_base_principal(base_mun_imputada).copy()

    col = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
    if col not in b.columns:
        b[col] = b["custo_oportunidade_corrigido_r_ha_imputado"].clip(lower=0)

    b[col] = pd.to_numeric(b[col], errors="coerce").clip(lower=0)

    b["codigo_territorio"] = _padronizar_codigo_municipio_final(b["codigo_territorio"])
    if "codigo_microrregiao" in b.columns:
        b["codigo_microrregiao"] = _padronizar_codigo_micro_final(b["codigo_microrregiao"])

    b["codigo_uf"] = b["codigo_territorio"].str[:2]

    # Base sem menores de 5 ha, mas COM outliers, para auditoria dos limites.
    b_sem_menores = b[
        (~b["estrato_area"].isin(ESTRATOS_EXCLUIR_ANALISE_FINAL))
        & (~b["estrato_area"].isin(ESTRATOS_MENORES_QUE_5HA_FINAL))
        & b[col].notna()
    ].copy()

    _salvar_csv_final(b_sem_menores, "BASEFINAL_mun_sem_menores_5ha_COM_outliers_maio2026.csv")

    # Estatísticas com outliers, para justificar o corte.
    estat_com_outliers = (
        b_sem_menores
        .groupby("estrato_area", as_index=False)[col]
        .agg(
            media="mean",
            mediana="median",
            q1=lambda x: x.quantile(0.25),
            q3=lambda x: x.quantile(0.75),
            p90=lambda x: x.quantile(0.90),
            p95=lambda x: x.quantile(0.95),
            p99=lambda x: x.quantile(0.99),
            minimo="min",
            maximo="max",
            desvio_padrao="std",
            n_validos="count",
        )
    )
    estat_com_outliers["iqr"] = estat_com_outliers["q3"] - estat_com_outliers["q1"]
    estat_com_outliers["limite_superior_iqr"] = estat_com_outliers["q3"] + 1.5 * estat_com_outliers["iqr"]
    estat_com_outliers["limite_superior_adotado"] = LIMITE_SUPERIOR_OUTLIER
    estat_com_outliers["diferenca_limite_iqr_menos_15000"] = estat_com_outliers["limite_superior_iqr"] - LIMITE_SUPERIOR_OUTLIER
    _salvar_csv_final(estat_com_outliers, "estatisticas_com_outliers_custo_nao_negativo_por_estrato_maio2026.csv")

    # Histogramas com outliers para auditoria.
    for estrato, g in b_sem_menores.groupby("estrato_area", dropna=False):
        valores = pd.to_numeric(g[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if len(valores) == 0:
            continue
        nome = _nome_arquivo_seguro_final(estrato)
        q1 = valores.quantile(0.25)
        q3 = valores.quantile(0.75)
        ls = q3 + 1.5 * (q3 - q1)

        plt.figure(figsize=(10, 6))
        plt.hist(valores, bins=80)
        plt.axvline(ls, linestyle="--", label=f"Limite IQR: {_formatar_numero_br_final(ls)}")
        plt.axvline(LIMITE_SUPERIOR_OUTLIER, linestyle=":", label="15.000")
        plt.title(f"Histograma com outliers do custo não negativo\n{estrato}", fontsize=TAMANHO_FONTE_TITULO_FINAL)
        plt.xlabel("Custo de oportunidade corrigido, negativos = 0")
        plt.ylabel("Frequência")
        plt.legend()
        plt.tight_layout()
        _salvar_fig_final(f"histograma_com_outliers_{nome}.png")
        plt.close()

    # Base final oficial: sem menores de 5 ha e sem outliers acima de 15.000.
    b_final = b_sem_menores[
        b_sem_menores[col].notna()
        & (b_sem_menores[col] <= LIMITE_SUPERIOR_OUTLIER)
    ].copy()

    _salvar_csv_final(b_final, "BASEFINAL_mun_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv")
    _salvar_csv_final(b_final, "mun_base_final_sem_menores_5ha_sem_outliers_acima_15000.csv")

    estat_sem_outliers = (
        b_final
        .groupby("estrato_area", as_index=False)[col]
        .agg(
            media="mean",
            mediana="median",
            q1=lambda x: x.quantile(0.25),
            q3=lambda x: x.quantile(0.75),
            minimo="min",
            maximo="max",
            desvio_padrao="std",
            n_validos="count",
        )
    )
    _salvar_csv_final(estat_sem_outliers, "estatisticas_sem_outliers_custo_nao_negativo_por_estrato_maio2026.csv")

    return b_final


def _criar_classes_final(gdf, coluna_valor):
    gdf = gdf.copy()
    valores = pd.to_numeric(gdf[coluna_valor], errors="coerce").clip(lower=0)
    valores = valores.where(valores <= LIMITE_SUPERIOR_OUTLIER, np.nan)

    labels = []
    for i in range(len(BINS_CUSTO_FINAL) - 1):
        labels.append(f"{_formatar_numero_br_final(BINS_CUSTO_FINAL[i])} a {_formatar_numero_br_final(BINS_CUSTO_FINAL[i + 1])}")

    gdf[coluna_valor] = valores
    gdf["classe_custo"] = pd.cut(
        valores,
        bins=BINS_CUSTO_FINAL,
        labels=labels,
        include_lowest=True,
        right=True,
    )
    return gdf


def _ajustar_legenda_final(ax):
    legend = ax.get_legend()
    if legend is None:
        return

    try:
        legend.set_title("")
    except Exception:
        pass

    for text in legend.get_texts():
        text.set_fontsize(TAMANHO_FONTE_LEGENDA_FINAL)
        text.set_fontweight("normal")

    handles = []
    if hasattr(legend, "legend_handles"):
        handles = legend.legend_handles
    elif hasattr(legend, "legendHandles"):
        handles = legend.legendHandles

    for handle in handles:
        try:
            if hasattr(handle, "_markersize"):
                handle._markersize = 24
            if hasattr(handle, "set_markersize"):
                handle.set_markersize(24)
            if hasattr(handle, "set_sizes"):
                handle.set_sizes([24 ** 2])
            if hasattr(handle, "set_linewidth"):
                handle.set_linewidth(8)
        except Exception:
            pass


def _adicionar_rotulos_uf_final(ax, mapa_uf_plot):
    for _, row in mapa_uf_plot.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        sigla = None
        for col in ["abbrev_state", "abbrev", "sigla_uf", "uf"]:
            if col in row.index and pd.notna(row[col]):
                sigla = str(row[col]).strip()
                break
        if not sigla:
            code = str(row.get("code_state", "")).zfill(2)
            sigla = MAPA_UF.get(code, "")
        if not sigla:
            continue
        ponto = row.geometry.representative_point()
        ax.text(
            ponto.x,
            ponto.y,
            sigla,
            fontsize=TAMANHO_FONTE_SIGLA_UF_FINAL,
            fontweight="bold",
            ha="center",
            va="center",
            color="black",
            bbox=dict(facecolor="white", alpha=0.78, edgecolor="none", pad=2.2),
        )


def _padronizar_regiao_final(x):
    """Padroniza nomes de Grandes Regiões para evitar erro no merge com geobr."""
    if pd.isna(x):
        return np.nan

    txt = str(x).strip()
    txt_norm = (
        txt.lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
        .replace("-", " ")
        .replace("_", " ")
    )
    txt_norm = " ".join(txt_norm.split())

    if txt_norm == "norte":
        return "Norte"
    if txt_norm == "nordeste":
        return "Nordeste"
    if txt_norm == "sudeste":
        return "Sudeste"
    if txt_norm == "sul":
        return "Sul"
    if txt_norm in ["centro oeste", "centro-oeste", "centrooeste"]:
        return "Centro-Oeste"

    return txt

def _adicionar_rotulos_regiao_final(ax, mapa_regiao_plot):
    for _, row in mapa_regiao_plot.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue
        reg = row.get("regiao", None)
        sigla = MAPA_SIGLAS_REGIAO_FINAL.get(reg, "")
        if not sigla:
            continue
        ponto = row.geometry.representative_point()
        ax.text(
            ponto.x,
            ponto.y,
            sigla,
            fontsize=TAMANHO_FONTE_SIGLA_REGIAO_FINAL,
            fontweight="bold",
            ha="center",
            va="center",
            color="black",
            bbox=dict(facecolor="white", alpha=0.82, edgecolor="none", pad=3.2),
        )


def _plotar_mapa_final(gdf, coluna_valor, titulo, nome_arquivo, linewidth=0.08, rotulos=None, figsize=(20, 18)):
    gdf = gdf.copy()
    gdf[coluna_valor] = pd.to_numeric(gdf[coluna_valor], errors="coerce").clip(lower=0)
    gdf.loc[gdf[coluna_valor] > LIMITE_SUPERIOR_OUTLIER, coluna_valor] = np.nan

    if gdf[coluna_valor].notna().sum() == 0:
        print(f"Sem valores para gerar: {titulo}")
        return

    gdf = _criar_classes_final(gdf, coluna_valor)

    fig, ax = plt.subplots(figsize=figsize)
    gdf.plot(
        column="classe_custo",
        categorical=True,
        cmap="YlOrBr",
        legend=True,
        legend_kwds={
            "loc": "lower left",
            "fontsize": TAMANHO_FONTE_LEGENDA_FINAL,
            "title_fontsize": TAMANHO_FONTE_LEGENDA_FINAL,
            "frameon": True,
            "borderpad": 0.8,
            "labelspacing": 1.1,
            "handlelength": 2.8,
            "handleheight": 1.8,
        },
        linewidth=linewidth,
        edgecolor="white",
        missing_kwds={"color": "lightgrey", "label": "Sem dados"},
        ax=ax,
    )

    if rotulos == "uf":
        _adicionar_rotulos_uf_final(ax, gdf)
    elif rotulos == "regiao":
        _adicionar_rotulos_regiao_final(ax, gdf)

    _ajustar_legenda_final(ax)
    ax.set_title(titulo, fontsize=TAMANHO_FONTE_TITULO_FINAL)
    ax.axis("off")
    plt.tight_layout()
    _salvar_fig_final(nome_arquivo)
    plt.close()


def _grafico_barras_final(df, categoria, valor, titulo, xlabel, nome_arquivo, altura=9, fontsize_y=11):
    dados = df.copy().sort_values(valor, ascending=True)
    if dados.empty:
        print(f"Sem dados para gráfico: {titulo}")
        return

    plt.figure(figsize=(13, altura))
    plt.barh(dados[categoria], dados[valor])
    plt.title(titulo, fontsize=TAMANHO_FONTE_TITULO_FINAL)
    plt.xlabel(xlabel, fontsize=13)
    plt.ylabel("")
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=fontsize_y)

    max_valor = pd.to_numeric(dados[valor], errors="coerce").max()
    margem = max_valor * 0.12 if pd.notna(max_valor) and max_valor > 0 else 1

    for i, v in enumerate(dados[valor]):
        plt.text(v + margem * 0.04, i, _formatar_numero_br_final(v), va="center", fontsize=10)

    plt.xlim(0, max_valor + margem if pd.notna(max_valor) else 1)
    plt.tight_layout()
    _salvar_fig_final(nome_arquivo)
    plt.close()


def _gerar_boxplot_final(df, coluna_grupo, coluna_valor, titulo, nome_arquivo, figsize=(14, 8), rotation=25):
    dados = df[[coluna_grupo, coluna_valor]].dropna().copy()
    if dados.empty:
        return

    grupos = [g for g in ORDEM_GRUPOS_FINAL if g in set(dados[coluna_grupo].astype(str))]
    if not grupos:
        grupos = sorted(dados[coluna_grupo].dropna().astype(str).unique())

    valores = [dados.loc[dados[coluna_grupo].astype(str) == g, coluna_valor].dropna().values for g in grupos]

    plt.figure(figsize=figsize)
    try:
        # Matplotlib mais recente usa tick_labels.
        plt.boxplot(valores, tick_labels=grupos, showfliers=False)
    except TypeError:
        # Compatibilidade com versões antigas do Matplotlib.
        plt.boxplot(valores, labels=grupos, showfliers=False)
    plt.title(titulo, fontsize=TAMANHO_FONTE_TITULO_FINAL)
    plt.ylabel("Custo de oportunidade corrigido, negativos = 0")
    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    _salvar_fig_final(nome_arquivo)
    plt.close()


def _gerar_histogramas_por_grupo_final(df, coluna_grupo, coluna_valor):
    for grupo, g in df.groupby(coluna_grupo, dropna=False):
        valores = pd.to_numeric(g[coluna_valor], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        valores = valores[(valores >= 0) & (valores <= LIMITE_SUPERIOR_OUTLIER)]
        if len(valores) == 0:
            continue
        nome = _nome_arquivo_seguro_final(grupo)
        plt.figure(figsize=(10, 6))
        plt.hist(valores, bins=60)
        plt.title(f"Histograma do custo de oportunidade\n{grupo}", fontsize=TAMANHO_FONTE_TITULO_FINAL)
        plt.xlabel("Custo de oportunidade corrigido, negativos = 0")
        plt.ylabel("Frequência")
        plt.tight_layout()
        _salvar_fig_final(f"histograma_custo_{nome}.png")
        plt.close()


def _gerar_mapas_e_graficos_final(base_final):
    if not GERAR_MAPAS_E_GRAFICOS:
        print("Mapas e gráficos desativados em GERAR_MAPAS_E_GRAFICOS=False.")
        return

    if geobr is None:
        print("Aviso: geobr não está instalado. Bases finais foram geradas, mas os mapas não serão gerados.")
        print("Instale com: python -m pip install geobr geopandas shapely pyogrio")
        return

    col = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
    b = base_final.copy()

    # ------------------------------------------------------------
    # Padronização e conferências
    # ------------------------------------------------------------
    b[col] = pd.to_numeric(b[col], errors="coerce").clip(lower=0)
    b = b[b[col].notna() & (b[col] <= LIMITE_SUPERIOR_OUTLIER)].copy()

    b["codigo_territorio"] = _padronizar_codigo_municipio_final(b["codigo_territorio"])
    b["codigo_uf"] = b["codigo_territorio"].str[:2]

    if "uf" not in b.columns:
        b["uf"] = b["codigo_uf"].map(MAPA_UF)

    if "regiao" not in b.columns:
        b["regiao"] = b["uf"].map(MAPA_REGIAO)

    b["regiao"] = b["regiao"].apply(_padronizar_regiao_final)

    if "codigo_microrregiao" in b.columns:
        b["codigo_microrregiao"] = _padronizar_codigo_micro_final(b["codigo_microrregiao"])
    else:
        raise KeyError("A base final precisa da coluna codigo_microrregiao para gerar mapas por microrregião.")

    print("Lendo malha municipal...")
    mapa_mun = geobr.read_municipality(year=ANO_BASE)
    mapa_mun["code_muni"] = _padronizar_codigo_municipio_final(mapa_mun["code_muni"])

    print("Lendo malha de microrregiões...")
    mapa_micro = geobr.read_micro_region(year=ANO_BASE)
    mapa_micro["code_micro"] = _padronizar_codigo_micro_final(mapa_micro["code_micro"])

    print("Lendo malha de UFs...")
    mapa_uf = geobr.read_state(year=ANO_BASE)
    mapa_uf["code_state"] = _padronizar_codigo_uf_final(mapa_uf["code_state"])

    print("Lendo malha de Grandes Regiões...")
    try:
        mapa_regiao = geobr.read_region(year=ANO_BASE)
    except Exception:
        mapa_regiao = geobr.read_geographic_region(year=ANO_BASE)

    col_nome_regiao = None
    for c in ["name_region", "nome_regiao", "name", "nome", "regiao"]:
        if c in mapa_regiao.columns:
            col_nome_regiao = c
            break

    if col_nome_regiao is None:
        raise KeyError("Não encontrei a coluna com nome da região na malha do geobr.")

    mapa_regiao["regiao"] = mapa_regiao[col_nome_regiao].apply(_padronizar_regiao_final)

    # ------------------------------------------------------------
    # Grupos agregados de estrato
    # ------------------------------------------------------------
    b["grupo_estrato_agregado"] = b["estrato_area"].map(MAPA_GRUPOS_ESTRATOS_FINAL)

    b_grupos_1a4 = b[b["grupo_estrato_agregado"].notna()].copy()

    b_grupo_5 = b.copy()
    b_grupo_5["grupo_estrato_agregado"] = "5) >= 5 ha"

    b_mapas = pd.concat([b_grupos_1a4, b_grupo_5], ignore_index=True)
    _salvar_csv_final(b_mapas, "base_usada_mapas_municipais_por_estrato_agregado_maio2026.csv")

    # ------------------------------------------------------------
    # MAPAS GERAIS
    # Mediana calculada diretamente sobre as observações município-estrato.
    # Assim, a mediana por microrregião/UF/região é a mediana dos custos
    # dos estratos observados naquele território, como definido na análise.
    # ------------------------------------------------------------

    cols_mun = ["codigo_territorio"]
    if "territorio" in b.columns:
        cols_mun.append("territorio")
    cols_mun += ["codigo_microrregiao", "codigo_uf", "uf", "regiao"]
    if "microrregiao" in b.columns:
        cols_mun.insert(2, "microrregiao")
    cols_mun = [c for c in cols_mun if c in b.columns]

    mun_geral = (
        b.groupby(cols_mun, as_index=False, dropna=False)[col]
        .median()
        .rename(columns={col: "mediana_custo"})
    )
    _salvar_csv_final(mun_geral, "mediana_geral_custo_por_municipio_maio2026.csv")

    _plotar_mapa_final(
        mapa_mun.merge(mun_geral, left_on="code_muni", right_on="codigo_territorio", how="left"),
        "mediana_custo",
        "Mediana geral do custo de oportunidade por município\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
        "mapa_geral_municipio.png",
        linewidth=0.03,
    )

    cols_micro = ["codigo_microrregiao"]
    if "microrregiao" in b.columns:
        cols_micro.append("microrregiao")
    cols_micro += ["regiao"]
    cols_micro = [c for c in cols_micro if c in b.columns]

    micro = (
        b.groupby(cols_micro, as_index=False, dropna=False)[col]
        .median()
        .rename(columns={col: "mediana_custo"})
    )

    micro["codigo_microrregiao"] = _padronizar_codigo_micro_final(micro["codigo_microrregiao"])

    if "microrregiao" not in micro.columns:
        micro["microrregiao"] = micro["codigo_microrregiao"]

    micro["microrregiao"] = micro["microrregiao"].fillna(micro["codigo_microrregiao"])
    micro["microrregiao_limpa"] = micro["microrregiao"].apply(_limpar_nome_microrregiao_final)

    _salvar_csv_final(micro, "mediana_geral_custo_por_microrregiao_maio2026.csv")

    _plotar_mapa_final(
        mapa_micro.merge(micro, left_on="code_micro", right_on="codigo_microrregiao", how="left"),
        "mediana_custo",
        "Mediana geral do custo de oportunidade por microrregião\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
        "mapa_geral_microrregiao.png",
        linewidth=0.05,
    )

    uf = (
        b.groupby(["codigo_uf", "uf", "regiao"], as_index=False, dropna=False)[col]
        .median()
        .rename(columns={col: "mediana_custo"})
    )
    uf["codigo_uf"] = _padronizar_codigo_uf_final(uf["codigo_uf"])
    uf["uf"] = uf["uf"].fillna(uf["codigo_uf"].map(MAPA_UF))
    uf["regiao"] = uf["regiao"].apply(_padronizar_regiao_final)

    _salvar_csv_final(uf, "mediana_geral_custo_por_uf_maio2026.csv")

    _plotar_mapa_final(
        mapa_uf.merge(uf, left_on="code_state", right_on="codigo_uf", how="left"),
        "mediana_custo",
        "Mediana geral do custo de oportunidade por UF\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
        "mapa_geral_uf.png",
        linewidth=0.5,
        rotulos="uf",
    )

    regiao = (
        b.groupby("regiao", as_index=False, dropna=False)[col]
        .median()
        .rename(columns={col: "mediana_custo"})
    )

    regiao["regiao"] = regiao["regiao"].apply(_padronizar_regiao_final)

    _salvar_csv_final(regiao, "mediana_geral_custo_por_regiao_maio2026.csv")

    mapa_regiao_plot = mapa_regiao.merge(regiao, on="regiao", how="left")

    _salvar_csv_final(
        mapa_regiao_plot[["regiao", "mediana_custo"]].copy(),
        "diagnostico_merge_mapa_regiao_maio2026.csv"
    )

    _plotar_mapa_final(
        mapa_regiao_plot,
        "mediana_custo",
        "Mediana geral do custo de oportunidade por Grande Região\nNova metodologia, maio/2026, sem <5 ha e sem outliers >15.000",
        "mapa_geral_regiao.png",
        linewidth=0.8,
        rotulos="regiao",
    )

    # ------------------------------------------------------------
    # MAPAS MUNICIPAIS POR ESTRATO AGREGADO
    # ------------------------------------------------------------
    municipio_grupo = (
        b_mapas.groupby(["codigo_territorio", "grupo_estrato_agregado"], as_index=False, dropna=False)[col]
        .median()
        .rename(columns={col: "mediana_custo"})
    )

    municipio_grupo["codigo_territorio"] = _padronizar_codigo_municipio_final(municipio_grupo["codigo_territorio"])
    municipio_grupo["mediana_custo"] = pd.to_numeric(municipio_grupo["mediana_custo"], errors="coerce").clip(lower=0)
    municipio_grupo = municipio_grupo[municipio_grupo["mediana_custo"].notna() & (municipio_grupo["mediana_custo"] <= LIMITE_SUPERIOR_OUTLIER)].copy()

    _salvar_csv_final(municipio_grupo, "mediana_custo_municipio_por_estrato_agregado_maio2026.csv")

    for grupo in ORDEM_GRUPOS_FINAL:
        dados_grupo = municipio_grupo[municipio_grupo["grupo_estrato_agregado"].astype(str) == grupo].copy()

        if dados_grupo.empty:
            print(f"Sem dados para o grupo: {grupo}")
            continue

        nome = _nome_arquivo_seguro_final(grupo)

        _plotar_mapa_final(
            mapa_mun.merge(dados_grupo, left_on="code_muni", right_on="codigo_territorio", how="left"),
            "mediana_custo",
            f"Mediana do custo de oportunidade por município\n{grupo}",
            f"mapa_municipal_{nome}.png",
            linewidth=0.03,
        )

    # ------------------------------------------------------------
    # GRÁFICOS DE BARRAS
    # ------------------------------------------------------------
    uf_barra = uf.sort_values("mediana_custo", ascending=True).copy()
    _grafico_barras_final(
        uf_barra,
        "uf",
        "mediana_custo",
        "Mediana geral do custo de oportunidade por UF",
        "Mediana do custo de oportunidade",
        "grafico_barra_mediana_custo_por_uf.png",
        altura=9,
        fontsize_y=12,
    )

    regiao_barra = regiao.sort_values("mediana_custo", ascending=True).copy()
    _grafico_barras_final(
        regiao_barra,
        "regiao",
        "mediana_custo",
        "Mediana geral do custo de oportunidade por Grande Região",
        "Mediana do custo de oportunidade",
        "grafico_barra_mediana_custo_por_regiao.png",
        altura=5,
        fontsize_y=12,
    )

    micro_barra = (
        micro.sort_values("mediana_custo", ascending=False)
        .head(TOP_N_RANKING_FINAL)
        .sort_values("mediana_custo", ascending=True)
    )

    _grafico_barras_final(
        micro_barra,
        "microrregiao_limpa",
        "mediana_custo",
        f"{TOP_N_RANKING_FINAL} microrregiões com maiores medianas",
        "Mediana do custo de oportunidade",
        f"grafico_barra_top{TOP_N_RANKING_FINAL}_mediana_custo_por_microrregiao.png",
        altura=12,
        fontsize_y=10,
    )

    if "territorio" not in mun_geral.columns:
        mun_geral["territorio"] = mun_geral["codigo_territorio"]

    mun_barra = (
        mun_geral.sort_values("mediana_custo", ascending=False)
        .head(TOP_N_RANKING_FINAL)
        .sort_values("mediana_custo", ascending=True)
    )

    _grafico_barras_final(
        mun_barra,
        "territorio",
        "mediana_custo",
        f"{TOP_N_RANKING_FINAL} municípios com maiores medianas",
        "Mediana do custo de oportunidade",
        f"grafico_barra_top{TOP_N_RANKING_FINAL}_mediana_custo_por_municipio.png",
        altura=12,
        fontsize_y=10,
    )

    # ------------------------------------------------------------
    # BOXPLOTS, HISTOGRAMAS E ESTATÍSTICAS FINAIS
    # ------------------------------------------------------------
    _gerar_boxplot_final(
        b_mapas,
        "grupo_estrato_agregado",
        col,
        "Boxplot do custo de oportunidade por estrato agregado",
        "boxplot_custo_por_estrato_agregado.png",
    )

    _gerar_boxplot_final(
        b,
        "regiao",
        col,
        "Boxplot do custo de oportunidade por Grande Região",
        "boxplot_custo_por_grande_regiao.png",
        rotation=15,
    )

    _gerar_histogramas_por_grupo_final(b_mapas, "grupo_estrato_agregado", col)

    estat_estrato = (
        b_mapas.groupby("grupo_estrato_agregado", as_index=False, dropna=False)[col]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", desvio_padrao="std", n_validos="count")
    )
    _salvar_csv_final(estat_estrato, "estatisticas_custo_por_estrato_agregado_maio2026.csv")

    estat_regiao = (
        b.groupby("regiao", as_index=False, dropna=False)[col]
        .agg(media="mean", mediana="median", minimo="min", maximo="max", desvio_padrao="std", n_validos="count")
    )
    _salvar_csv_final(estat_regiao, "estatisticas_custo_por_grande_regiao_maio2026.csv")


# ============================================================
# 13.1. COMPLEMENTOS V14 - BASES, ESTATÍSTICAS, DIAGNÓSTICO E IPIAÚ
# ============================================================

def _salvar_bases_principais_v14(base_sem_imputacao, base_imputada, base_final):
    _salvar_csv_final(base_sem_imputacao, "BASE_COMPLETA_sem_imputacao_todos_estratos_com_outliers_maio2026.csv")
    _salvar_csv_final(base_imputada, "BASE_COMPLETA_com_imputacao_todos_estratos_com_outliers_maio2026.csv")
    _salvar_csv_final(base_final, "BASE_USADA_ARTIGO_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv")


def _estatisticas_descritivas_v14(df, grupo_cols, coluna_valor):
    dados = df.copy()
    dados[coluna_valor] = pd.to_numeric(dados[coluna_valor], errors="coerce")
    out = (
        dados.groupby(grupo_cols, as_index=False, dropna=False)[coluna_valor]
        .agg(
            media="mean",
            mediana="median",
            q1=lambda x: x.quantile(0.25),
            q3=lambda x: x.quantile(0.75),
            p90=lambda x: x.quantile(0.90),
            p95=lambda x: x.quantile(0.95),
            p99=lambda x: x.quantile(0.99),
            minimo="min",
            maximo="max",
            desvio_padrao="std",
            n_validos="count",
        )
    )
    out["iqr"] = out["q3"] - out["q1"]
    out["limite_superior_iqr"] = out["q3"] + 1.5 * out["iqr"]
    return out


def _criar_base_com_grupo_estrato_v14(base_final):
    b = base_final.copy()
    b["grupo_estrato_agregado"] = b["estrato_area"].map(MAPA_GRUPOS_ESTRATOS_FINAL)
    b1a4 = b[b["grupo_estrato_agregado"].notna()].copy()
    b5 = b.copy()
    b5["grupo_estrato_agregado"] = "5) >= 5 ha"
    return pd.concat([b1a4, b5], ignore_index=True)


def _gerar_estatisticas_territoriais_v14(base_final):
    """Gera estatísticas territoriais com a mediana dos estratos.

    Aqui a unidade de análise é a observação município-estrato.
    Portanto, por microrregião, UF ou região, a mediana é calculada
    sobre os custos dos estratos existentes naquele território.

    Também são geradas tabelas por território x grupo de estrato agregado,
    que são as principais para interpretação por estrato.
    """
    b = base_final.copy()
    col = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"

    b[col] = pd.to_numeric(b[col], errors="coerce").clip(lower=0)
    b = b[b[col].notna() & (b[col] <= LIMITE_SUPERIOR_OUTLIER)].copy()

    b["codigo_territorio"] = _padronizar_codigo_municipio_final(b["codigo_territorio"])
    b["codigo_uf"] = b["codigo_territorio"].str[:2]

    if "uf" not in b.columns:
        b["uf"] = b["codigo_uf"].map(MAPA_UF)

    if "regiao" not in b.columns:
        b["regiao"] = b["uf"].map(MAPA_REGIAO)

    b["regiao"] = b["regiao"].apply(_padronizar_regiao_final)

    if "codigo_microrregiao" in b.columns:
        b["codigo_microrregiao"] = _padronizar_codigo_micro_final(b["codigo_microrregiao"])

    # Estatísticas gerais territoriais, usando observações município-estrato.
    _salvar_csv_final(
        _estatisticas_descritivas_v14(b, ["regiao"], col),
        "estatisticas_oficiais_por_regiao_maio2026.csv"
    )

    _salvar_csv_final(
        _estatisticas_descritivas_v14(b, ["codigo_uf", "uf", "regiao"], col),
        "estatisticas_oficiais_por_uf_maio2026.csv"
    )

    if "codigo_microrregiao" in b.columns:
        cols = ["codigo_microrregiao"]
        if "microrregiao" in b.columns:
            cols.append("microrregiao")
        cols += ["uf", "regiao"]

        _salvar_csv_final(
            _estatisticas_descritivas_v14(b, cols, col),
            "estatisticas_oficiais_por_microrregiao_maio2026.csv"
        )

    cols = ["codigo_territorio"]
    if "territorio" in b.columns:
        cols.append("territorio")
    if "codigo_microrregiao" in b.columns:
        cols.append("codigo_microrregiao")
    if "microrregiao" in b.columns:
        cols.append("microrregiao")
    cols += ["uf", "regiao"]

    _salvar_csv_final(
        _estatisticas_descritivas_v14(b, cols, col),
        "estatisticas_oficiais_por_municipio_maio2026.csv"
    )

    # Estatísticas por estrato agregado.
    bg = _criar_base_com_grupo_estrato_v14(b)

    _salvar_csv_final(
        _estatisticas_descritivas_v14(bg, ["grupo_estrato_agregado"], col),
        "estatisticas_oficiais_por_estrato_agregado_maio2026.csv"
    )

    _salvar_csv_final(
        _estatisticas_descritivas_v14(bg, ["regiao", "grupo_estrato_agregado"], col),
        "estatisticas_oficiais_por_regiao_e_estrato_maio2026.csv"
    )

    _salvar_csv_final(
        _estatisticas_descritivas_v14(bg, ["codigo_uf", "uf", "regiao", "grupo_estrato_agregado"], col),
        "estatisticas_oficiais_por_uf_e_estrato_maio2026.csv"
    )

    if "codigo_microrregiao" in bg.columns:
        cols = ["codigo_microrregiao"]
        if "microrregiao" in bg.columns:
            cols.append("microrregiao")
        cols += ["uf", "regiao", "grupo_estrato_agregado"]

        _salvar_csv_final(
            _estatisticas_descritivas_v14(bg, cols, col),
            "estatisticas_oficiais_por_microrregiao_e_estrato_maio2026.csv"
        )

    cols = ["codigo_territorio"]
    if "territorio" in bg.columns:
        cols.append("territorio")
    cols += ["uf", "regiao", "grupo_estrato_agregado"]

    _salvar_csv_final(
        _estatisticas_descritivas_v14(bg, cols, col),
        "estatisticas_oficiais_por_municipio_e_estrato_maio2026.csv"
    )

def _gerar_relatorio_diagnostico_imputacao_v14(base_sem_imputacao, base_imputada, resumo_imputacao=None, validacao_consistencia=None):
    b = base_imputada.copy()
    partes = []
    for tipo, col in [
        ("producao", "metodo_imputacao_producao"),
        ("despesa", "metodo_imputacao_despesa"),
        ("area", "metodo_imputacao_area"),
        ("area_componentes", "metodo_imputacao_area_componentes"),
    ]:
        if col in b.columns:
            tmp = b.groupby(col, dropna=False).size().reset_index(name="n_linhas").rename(columns={col: "metodo"})
            tmp["tipo_variavel"] = tipo
            partes.append(tmp[["tipo_variavel", "metodo", "n_linhas"]])
    if partes:
        _salvar_csv_final(pd.concat(partes, ignore_index=True), "diagnostico_imputacao_resumo_por_metodo_maio2026.csv")

    agg = {}
    for col in ["metodo_imputacao_producao", "metodo_imputacao_despesa", "metodo_imputacao_area"]:
        if col in b.columns:
            agg[f"n_{col}_observado"] = (col, lambda x: x.astype(str).str.lower().eq("observado").sum())
            agg[f"n_{col}_nao_observado"] = (col, lambda x: (~x.astype(str).str.lower().eq("observado")).sum())
    if agg and {"uf", "regiao", "estrato_area"}.issubset(b.columns):
        _salvar_csv_final(b.groupby(["uf", "regiao", "estrato_area"], as_index=False, dropna=False).agg(**agg), "diagnostico_imputacao_por_uf_e_estrato_maio2026.csv")

    if "custo_oportunidade_corrigido_r_ha_imputado" in b.columns:
        _salvar_csv_final(b[b["custo_oportunidade_corrigido_r_ha_imputado"].isna()].copy(), "diagnostico_linhas_sem_custo_apos_imputacao_maio2026.csv")
    if resumo_imputacao is not None:
        _salvar_csv_final(resumo_imputacao, "diagnostico_imputacao_resumo_original_codigo_maio2026.csv")
    if validacao_consistencia is not None:
        _salvar_csv_final(validacao_consistencia, "diagnostico_validacao_consistencia_maio2026.csv")


def _buscar_municipios_regiao_imediata_ipiau_v14(mapa_mun):
    mm = mapa_mun.copy()
    mm["code_muni"] = _padronizar_codigo_municipio_final(mm["code_muni"])
    nome_col = next((c for c in ["name_muni", "name_municipality", "nome_municipio", "name"] if c in mm.columns), None)
    if nome_col:
        nomes_norm = mm[nome_col].astype(str).str.normalize("NFKD").str.encode("ascii", errors="ignore").str.decode("utf-8")
        filtro_ipiau = nomes_norm.str.contains("Ipiau", case=False, na=False)
    else:
        filtro_ipiau = mm["code_muni"].eq("2913903")
    if not filtro_ipiau.any():
        filtro_ipiau = mm["code_muni"].eq("2913903")
    if not filtro_ipiau.any():
        raise ValueError("Não consegui localizar Ipiaú na malha municipal.")
    ipiau = mm.loc[filtro_ipiau].iloc[0]

    # Se a malha municipal já tiver região imediata, usa isso.
    for c in ["code_immediate", "code_immediate_region", "code_immediate_geographic_region", "code_rgint"]:
        if c in mm.columns and pd.notna(ipiau.get(c)):
            cod = str(ipiau[c]).replace(".0", "")
            codigos = mm.loc[mm[c].astype(str).str.replace(".0", "", regex=False).eq(cod), "code_muni"].tolist()
            nome = "Região imediata de Ipiaú"
            for nc in ["name_immediate", "name_immediate_region", "name_immediate_geographic_region", "name_rgint"]:
                if nc in mm.columns:
                    vals = mm.loc[mm[c].astype(str).str.replace(".0", "", regex=False).eq(cod), nc].dropna().astype(str)
                    if len(vals) > 0:
                        nome = vals.iloc[0]
                    break
            return sorted(set(codigos)), nome

    # Fallback: tenta malha de região imediata.
    try:
        try:
            reg_imed = geobr.read_immediate_region(year=ANO_BASE)
        except Exception:
            reg_imed = geobr.read_immediate_geographic_region(year=ANO_BASE)
        if reg_imed.crs != mm.crs:
            reg_imed = reg_imed.to_crs(mm.crs)
        p = ipiau.geometry.representative_point()
        reg = reg_imed[reg_imed.geometry.contains(p)]
        if reg.empty:
            reg = reg_imed[reg_imed.geometry.intersects(p)]
        if reg.empty:
            raise ValueError("região imediata não encontrada")
        geom = reg.iloc[0].geometry
        nome = "Região imediata de Ipiaú"
        for nc in ["name_immediate", "name_immediate_region", "name_region", "name", "nome"]:
            if nc in reg.columns:
                nome = str(reg.iloc[0][nc])
                break
        centros = mm.geometry.representative_point()
        codigos = mm.loc[centros.within(geom), "code_muni"].tolist()
        return sorted(set(codigos)), nome
    except Exception:
        # Último fallback manual mínimo: usa Ipiaú se não encontrar a região.
        print("Aviso: não consegui identificar automaticamente todos os municípios da região imediata de Ipiaú; será usado apenas Ipiaú.")
        return ["2913903"], "Região imediata de Ipiaú"


def _gerar_analise_regiao_imediata_ipiau_v14(base_final):
    col = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
    b = base_final.copy()
    b["codigo_territorio"] = _padronizar_codigo_municipio_final(b["codigo_territorio"])
    b[col] = pd.to_numeric(b[col], errors="coerce").clip(lower=0)

    print("Lendo malha municipal para análise da Região Imediata de Ipiaú-BA...")
    mapa_mun = geobr.read_municipality(year=ANO_BASE)
    mapa_mun["code_muni"] = _padronizar_codigo_municipio_final(mapa_mun["code_muni"])
    codigos, nome_regiao = _buscar_municipios_regiao_imediata_ipiau_v14(mapa_mun)
    mapa_ipiau = mapa_mun[mapa_mun["code_muni"].isin(codigos)].copy()
    b_ipiau = b[b["codigo_territorio"].isin(codigos)].copy()
    if b_ipiau.empty:
        print("Aviso: sem dados para a Região Imediata de Ipiaú após filtros da base final.")
        return
    b_ipiau["regiao_imediata_referencia"] = nome_regiao
    _salvar_csv_final(b_ipiau, "IPIAU_base_final_regiao_imediata_maio2026.csv")

    cols_mun = ["codigo_territorio"]
    if "territorio" in b_ipiau.columns:
        cols_mun.append("territorio")
    cols_mun += ["uf", "regiao"]
    _salvar_csv_final(_estatisticas_descritivas_v14(b_ipiau, cols_mun, col), "IPIAU_estatisticas_por_municipio_maio2026.csv")

    b_ipiau_g = _criar_base_com_grupo_estrato_v14(b_ipiau)
    _salvar_csv_final(b_ipiau_g, "IPIAU_base_por_estrato_agregado_maio2026.csv")
    _salvar_csv_final(_estatisticas_descritivas_v14(b_ipiau_g, ["grupo_estrato_agregado"], col), "IPIAU_estatisticas_por_estrato_agregado_maio2026.csv")

    med = b_ipiau.groupby("codigo_territorio", as_index=False)[col].median().rename(columns={col: "mediana_custo"})
    if "territorio" in b_ipiau.columns:
        med = med.merge(b_ipiau[["codigo_territorio", "territorio"]].drop_duplicates("codigo_territorio"), on="codigo_territorio", how="left")
    _salvar_csv_final(med, "IPIAU_mediana_custo_por_municipio_maio2026.csv")
    _plotar_mapa_final(
        mapa_ipiau.merge(med, left_on="code_muni", right_on="codigo_territorio", how="left"),
        "mediana_custo",
        f"Mediana do custo de oportunidade por município\n{nome_regiao} - Bahia",
        "IPIAU_mapa_regiao_imediata_municipios.png",
        linewidth=0.6,
        figsize=(12, 10),
    )

    med_g = b_ipiau_g.groupby(["codigo_territorio", "grupo_estrato_agregado"], as_index=False)[col].median().rename(columns={col: "mediana_custo"})
    _salvar_csv_final(med_g, "IPIAU_mediana_custo_municipio_por_estrato_agregado_maio2026.csv")
    for grupo in ORDEM_GRUPOS_FINAL:
        dg = med_g[med_g["grupo_estrato_agregado"].astype(str).eq(grupo)].copy()
        if dg.empty:
            continue
        nome = _nome_arquivo_seguro_final(grupo)
        _plotar_mapa_final(
            mapa_ipiau.merge(dg, left_on="code_muni", right_on="codigo_territorio", how="left"),
            "mediana_custo",
            f"Mediana do custo de oportunidade por município\n{nome_regiao} - {grupo}",
            f"IPIAU_mapa_municipal_{nome}.png",
            linewidth=0.6,
            figsize=(12, 10),
        )

    if "territorio" not in med.columns:
        med["territorio"] = med["codigo_territorio"]
    med_rank = med.sort_values("mediana_custo", ascending=True)
    _grafico_barras_final(med_rank, "territorio", "mediana_custo", f"Mediana do custo de oportunidade - {nome_regiao}", "Mediana do custo de oportunidade", "IPIAU_grafico_barra_municipios.png", altura=max(6, 0.35 * len(med_rank)), fontsize_y=10)
    _gerar_boxplot_final(b_ipiau_g, "grupo_estrato_agregado", col, f"Boxplot do custo por estrato agregado\n{nome_regiao}", "IPIAU_boxplot_por_estrato_agregado.png", rotation=25)
    _gerar_histogramas_por_grupo_final(b_ipiau_g, "grupo_estrato_agregado", col)


def _compactar_resultados_v13():
    arquivos_raiz = [
        "mun_sidra_bruto_producao.csv",
        "mun_sidra_bruto_despesa.csv",
        "mun_sidra_bruto_area_utilizacao_6882.csv",
        "mun_base_sem_imputacao_area_utilizada_6882.csv",
        "mun_base_imputada_area_utilizada_6882.csv",
        "mun_base_imputada_area_utilizada_6882_completa.csv",
        "mun_estatisticas_area_utilizada_6882.csv",
        "mun_estatisticas_custo_nao_negativo_area_utilizada_6882.csv",
        "mun_resumo_imputacao_area_utilizada_6882.csv",
        "mun_tabela_referencia_territorial_por_estabelecimento.csv",
        "mun_validacao_consistencia_area_utilizada_6882.csv",
        "referencia_microrregiao.csv",
        "referencia_uf.csv",
        "referencia_regiao.csv",
        "referencia_brasil.csv",
        "mun_tabela_ipam_utilizada.csv",
        "mun_mapa_municipio_microrregiao_usado.csv",
    ]

    zip_path = Path("resultado_completo_v14_nova_metodologia_maio2026.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for arq in arquivos_raiz:
            if Path(arq).exists():
                zipf.write(arq)
        for arq in PASTA_SAIDA_FINAL.glob("*"):
            if arq.is_file():
                zipf.write(arq, arcname=f"{PASTA_SAIDA_FINAL.name}/{arq.name}")

    print(f"ZIP final gerado: {zip_path.resolve()}")


# ============================================================
# 13. EXECUÇÃO ÚNICA - V14
# ============================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EXECUÇÃO V14 - NOVA METODOLOGIA, IPA-M ATÉ MAIO/2026")
    print("=" * 80)

    fator_correcao, tabela_ipam_usada = calcular_fator_correcao_ipam()
    globals()["FATOR_CORRECAO_IPAM_GLOBAL"] = fator_correcao

    print("\n1) Montando base municipal a partir do SIDRA...")
    base_mi = montar_base_municipio()
    base_mi = corrigir_areas_pequenos_estratos(base_mi, coluna_area="area_estabelecimentos_ha")
    base_mi = calcular_custos(base_mi, fator_correcao, sufixo="")

    print("\n1.1) Criando referência interna de microrregião para imputação...")
    definir_referencia_microrregiao_interna(base_mi)

    print("\n2) Criando base sem imputação para conferência...")
    total_sem_area_sem_imputacao = criar_total_sem_area_sem_imputacao(base_mi, fator_correcao)
    base_mun_sem_imputacao_saida = criar_base_sem_imputacao_para_conferencia(base_mi, total_sem_area_sem_imputacao)

    print("\n3) Imputando produção, despesa e área e recalculando custos...")
    base_mun_imputada = imputar_e_recalcular(base_mi, fator_correcao)

    print("\n4) Criando Total sem produtor sem área imputado...")
    total_sem_area_imputado = criar_total_sem_area_imputado(base_mun_imputada, fator_correcao)
    base_mun_imputada = base_mun_imputada[base_mun_imputada["estrato_area"] != "Total sem produtor sem área"].copy()
    base_mun_imputada = pd.concat([base_mun_imputada, total_sem_area_imputado], ignore_index=True)

    print("\n5) Gerando tabelas estatísticas e de auditoria...")
    estatisticas = gerar_estatisticas(base_mun_imputada)
    estatisticas_custo_nao_negativo = gerar_estatisticas_custo_nao_negativo(base_mun_imputada)
    resumo_imputacao = gerar_resumo_imputacao(base_mun_imputada)
    tabela_referencia_territorial = gerar_tabela_referencia_territorial(base_mun_imputada, fator_correcao)
    referencia_microrregiao, referencia_uf, referencia_regiao, referencia_brasil = criar_tabelas_referencia_imputacao(base_mun_imputada)

    print("\n6) Salvando bases principais...")
    base_mun_sem_imputacao_saida = remover_colunas_auxiliares_e_ordenar(base_mun_sem_imputacao_saida)
    base_mun_sem_imputacao_saida.to_csv("mun_base_sem_imputacao_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    base_mun_imputada_completa_organizada = remover_colunas_auxiliares_e_ordenar(base_mun_imputada)
    base_mun_imputada_completa_organizada.to_csv("mun_base_imputada_area_utilizada_6882_completa.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    base_mun_imputada_limpa = selecionar_colunas_base_principal(base_mun_imputada)
    base_mun_imputada_limpa.to_csv("mun_base_imputada_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    validacao_consistencia = validar_consistencia_base(base_mun_imputada)
    validacao_consistencia.to_csv("mun_validacao_consistencia_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    estatisticas.to_csv("mun_estatisticas_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    estatisticas_custo_nao_negativo.to_csv("mun_estatisticas_custo_nao_negativo_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    resumo_imputacao.to_csv("mun_resumo_imputacao_area_utilizada_6882.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    tabela_referencia_territorial.to_csv("mun_tabela_referencia_territorial_por_estabelecimento.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
    tabela_ipam_usada.to_csv("mun_tabela_ipam_utilizada.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")

    if not Path("mun_mapa_municipio_microrregiao_usado.csv").exists():
        try:
            mapa_mun_micro_check = carregar_mapa_municipio_micro()
            mapa_mun_micro_check.to_csv("mun_mapa_municipio_microrregiao_usado.csv", index=False, encoding="utf-8-sig", sep=";", decimal=",")
        except Exception as e:
            print(f"Aviso: não foi possível salvar mun_mapa_municipio_microrregiao_usado.csv: {e}")

    print("\n7) Criando base final oficial sem menores de 5 ha e sem outliers > 15.000...")
    base_final_artigo = _preparar_base_final_artigo(base_mun_imputada)

    print("\n8) Salvando as três bases solicitadas: sem imputação, com imputação e base oficial do artigo...")
    _salvar_bases_principais_v14(
        base_sem_imputacao=base_mun_sem_imputacao_saida,
        base_imputada=base_mun_imputada_completa_organizada,
        base_final=base_final_artigo,
    )

    print("\n9) Gerando estatísticas territoriais oficiais...")
    _gerar_estatisticas_territoriais_v14(base_final_artigo)

    print("\n10) Gerando relatório de diagnóstico da imputação...")
    _gerar_relatorio_diagnostico_imputacao_v14(
        base_sem_imputacao=base_mun_sem_imputacao_saida,
        base_imputada=base_mun_imputada_completa_organizada,
        resumo_imputacao=resumo_imputacao,
        validacao_consistencia=validacao_consistencia,
    )

    print("\n11) Gerando mapas, gráficos e rankings nacionais...")
    _gerar_mapas_e_graficos_final(base_final_artigo)

    print("\n12) Gerando análise específica da Região Imediata de Ipiaú-BA...")
    _gerar_analise_regiao_imediata_ipiau_v14(base_final_artigo)

    print("\n13) Compactando resultados...")
    _compactar_resultados_v13()

    print("=" * 80)
    print("PROCESSAMENTO V14 CONCLUÍDO")
    print(f"Fator IPA-M utilizado: {fator_correcao}")
    print(f"Pasta final: {PASTA_SAIDA_FINAL.resolve()}")
    print("Base final oficial:")
    print((PASTA_SAIDA_FINAL / "BASEFINAL_mun_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv").resolve())
    print("=" * 80)
