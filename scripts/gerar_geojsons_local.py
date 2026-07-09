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
# Depois envie os .geojson gerados para a pasta dados/ do GitHub.
# ============================================================

from pathlib import Path
import geobr

ANO = 2017
PASTA_SAIDA = Path(__file__).resolve().parents[1] / "dados"
PASTA_SAIDA.mkdir(exist_ok=True)


def salvar_geojson(gdf, caminho, cols, tolerancia_metros):
    caminho = PASTA_SAIDA / caminho
    gdf = gdf.copy()
    gdf = gdf[cols + ["geometry"]].copy()

    # Simplifica em projeção métrica. Evita deformar polígonos em zooms locais.
    gdf = gdf.to_crs(epsg=5880)
    gdf["geometry"] = gdf["geometry"].make_valid()
    gdf["geometry"] = gdf["geometry"].simplify(
        tolerancia_metros,
        preserve_topology=True,
    )
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    # Folium/Leaflet usa latitude/longitude.
    gdf = gdf.to_crs(epsg=4326)
    gdf.to_file(caminho, driver="GeoJSON")

    tamanho_mb = caminho.stat().st_size / (1024 * 1024)
    print(f"Salvo: {caminho} ({tamanho_mb:.2f} MB)")


print("Baixando malha de UF...")
uf = geobr.read_state(year=ANO)
uf["codigo_uf"] = uf["code_state"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
salvar_geojson(
    uf,
    "geo_uf_simplificado.geojson",
    ["codigo_uf", "abbrev_state", "name_state"],
    tolerancia_metros=3000,
)

print("Baixando malha de microrregiões...")
micro = geobr.read_micro_region(year=ANO)
micro["codigo_microrregiao"] = micro["code_micro"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
cols_micro = ["codigo_microrregiao"]
for c in ["name_micro", "name_micro_region", "name_region"]:
    if c in micro.columns:
        cols_micro.append(c)
salvar_geojson(
    micro,
    "geo_microrregioes_simplificado.geojson",
    cols_micro,
    tolerancia_metros=700,
)

print("Baixando malha de regiões intermediárias...")
inter = geobr.read_intermediate_region(year=ANO)
inter["codigo_regiao_intermediaria"] = (
    inter["code_intermediate"]
    .astype(str)
    .str.replace(r"\.0$", "", regex=True)
    .str.zfill(4)
)
cols_inter = ["codigo_regiao_intermediaria"]
for c in ["name_intermediate", "name_intermediate_region", "name_region"]:
    if c in inter.columns:
        cols_inter.append(c)
salvar_geojson(
    inter,
    "geo_regioes_intermediarias_simplificado.geojson",
    cols_inter,
    tolerancia_metros=700,
)

print("Baixando malha de municípios...")
mun = geobr.read_municipality(year=ANO)
mun["codigo_municipio"] = mun["code_muni"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
cols_mun = ["codigo_municipio"]
for c in ["name_muni", "name_municipality", "abbrev_state"]:
    if c in mun.columns:
        cols_mun.append(c)
salvar_geojson(
    mun,
    "geo_municipios_simplificado.geojson",
    cols_mun,
    # Se o arquivo municipal ficar grande para o GitHub, aumente para 1000.
    tolerancia_metros=700,
)

print("Finalizado.")
print("Envie para o GitHub os arquivos da pasta dados/:")
print("- geo_uf_simplificado.geojson")
print("- geo_microrregioes_simplificado.geojson")
print("- geo_regioes_intermediarias_simplificado.geojson")
print("- geo_municipios_simplificado.geojson")
