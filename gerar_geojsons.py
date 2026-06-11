# ============================================================
# GERADOR DE GEOJSONS SIMPLIFICADOS PARA O DASHBOARD
# Rode este arquivo LOCALMENTE no seu computador.
#
# Recomendação:
# Use Python 3.11 ou 3.12 para instalar geobr/geopandas com menos erro.
#
# Instalar:
# python -m pip install --upgrade pip
# python -m pip install geopandas geobr shapely pyogrio
#
# Rodar:
# python gerar_geojsons.py
#
# Depois envie os .geojson gerados para o GitHub.
# ============================================================

from pathlib import Path
import geobr

ANO = 2017

def salvar_geojson(gdf, caminho, cols, tolerancia):
    gdf = gdf.copy()
    gdf = gdf[cols + ["geometry"]].copy()
    gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerancia, preserve_topology=True)
    gdf.to_file(caminho, driver="GeoJSON")
    tamanho_mb = Path(caminho).stat().st_size / (1024 * 1024)
    print(f"Salvo: {caminho} ({tamanho_mb:.2f} MB)")

print("Baixando malha de UF...")
uf = geobr.read_state(year=ANO)
uf["codigo_uf"] = uf["code_state"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
salvar_geojson(
    uf,
    "geo_uf_simplificado.geojson",
    ["codigo_uf", "abbrev_state", "name_state"],
    tolerancia=0.01
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
    tolerancia=0.015
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
    tolerancia=0.04
)

print("Finalizado.")
print("Envie para o GitHub:")
print("- geo_uf_simplificado.geojson")
print("- geo_microrregioes_simplificado.geojson")
print("- geo_municipios_simplificado.geojson, se ficar com menos de 25 MB")
