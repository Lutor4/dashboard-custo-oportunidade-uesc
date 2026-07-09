# ============================================================
# GERADOR DE GEOJSONS SIMPLIFICADOS PARA O DASHBOARD
# Rode este arquivo LOCALMENTE no seu computador.
#
# Instalar:
# python -m pip install --upgrade pip
# python -m pip install geopandas geobr shapely pyogrio
#
# Rodar:
# python scripts/gerar_geojsons_local.py
#
# Depois envie os .geojson gerados para a pasta dados/ no GitHub.
# ============================================================

from pathlib import Path
import geobr

ANO = 2017
PASTA_DADOS = Path("dados")
PASTA_DADOS.mkdir(exist_ok=True)


def _limpar_codigo(serie, tamanho):
    return (
        serie.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(tamanho)
    )


def salvar_geojson(gdf, caminho, cols, tolerancia_metros):
    caminho = Path(caminho)
    gdf = gdf.copy()
    gdf = gdf[cols + ["geometry"]].copy()

    # Simplifica em projeção métrica. Isso evita distorções fortes no zoom.
    gdf = gdf.to_crs(epsg=5880)
    gdf["geometry"] = gdf["geometry"].make_valid()
    gdf["geometry"] = gdf["geometry"].simplify(
        tolerancia_metros,
        preserve_topology=True,
    )
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    # Volta para latitude/longitude, padrão esperado pelo Folium/Leaflet.
    gdf = gdf.to_crs(epsg=4326)

    # COORDINATE_PRECISION reduz o tamanho do arquivo sem deformar como a
    # simplificação excessiva em graus fazia.
    try:
        gdf.to_file(caminho, driver="GeoJSON", COORDINATE_PRECISION=5)
    except Exception:
        gdf.to_file(caminho, driver="GeoJSON")

    tamanho_mb = caminho.stat().st_size / (1024 * 1024)
    print(f"Salvo: {caminho} ({tamanho_mb:.2f} MB)")


print("Baixando malha de UF...")
uf = geobr.read_state(year=ANO)
uf["codigo_uf"] = _limpar_codigo(uf["code_state"], 2)
salvar_geojson(
    uf,
    PASTA_DADOS / "geo_uf_simplificado.geojson",
    ["codigo_uf", "abbrev_state", "name_state"],
    tolerancia_metros=3000,
)


print("Baixando malha de microrregiões...")
micro = geobr.read_micro_region(year=ANO)
micro["codigo_microrregiao"] = _limpar_codigo(micro["code_micro"], 5)
cols_micro = ["codigo_microrregiao"]
for c in ["name_micro", "name_micro_region", "name_region"]:
    if c in micro.columns:
        cols_micro.append(c)
salvar_geojson(
    micro,
    PASTA_DADOS / "geo_microrregioes_simplificado.geojson",
    cols_micro,
    tolerancia_metros=500,
)


print("Baixando malha de regiões intermediárias...")
inter = geobr.read_intermediate_region(year=ANO)
inter["codigo_regiao_intermediaria"] = _limpar_codigo(inter["code_intermediate"], 4)
cols_inter = ["codigo_regiao_intermediaria"]
for c in ["name_intermediate", "name_intermediate_region", "name_region"]:
    if c in inter.columns:
        cols_inter.append(c)
salvar_geojson(
    inter,
    PASTA_DADOS / "geo_regioes_intermediarias_simplificado.geojson",
    cols_inter,
    tolerancia_metros=500,
)


print("Baixando malha de municípios...")
mun = geobr.read_municipality(year=ANO)
mun["codigo_municipio"] = _limpar_codigo(mun["code_muni"], 7)
cols_mun = ["codigo_municipio"]
for c in ["name_muni", "name_municipality", "abbrev_state"]:
    if c in mun.columns:
        cols_mun.append(c)

# 200 m preserva bem o desenho municipal no zoom. Se o arquivo passar do limite
# do GitHub pelo navegador, tente 300 ou 400 m, mas evite 700 m ou mais.
salvar_geojson(
    mun,
    PASTA_DADOS / "geo_municipios_simplificado.geojson",
    cols_mun,
    tolerancia_metros=200,
)


print("Finalizado.")
print("Envie para o GitHub, dentro da pasta dados/:")
print("- geo_uf_simplificado.geojson")
print("- geo_microrregioes_simplificado.geojson")
print("- geo_regioes_intermediarias_simplificado.geojson")
print("- geo_municipios_simplificado.geojson")
