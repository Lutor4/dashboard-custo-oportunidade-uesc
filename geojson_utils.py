from pathlib import Path
import geopandas as gpd
import geobr

from config import ANO_MAPA, GEOJSON_UF, GEOJSON_MICRO, GEOJSON_MUN


def _salvar_geojson(gdf, caminho: Path, cols: list[str], tolerancia: float) -> None:
    gdf = gdf.copy()
    gdf = gdf[cols + ["geometry"]].copy()
    gdf = gdf.to_crs(epsg=4326)
    gdf["geometry"] = gdf["geometry"].simplify(tolerancia, preserve_topology=True)
    caminho.parent.mkdir(exist_ok=True)
    gdf.to_file(caminho, driver="GeoJSON")


def gerar_geojsons_se_necessario() -> None:
    """Gera as malhas simplificadas apenas na primeira execução."""
    if GEOJSON_UF.exists() and GEOJSON_MICRO.exists() and GEOJSON_MUN.exists():
        return

    if not GEOJSON_UF.exists():
        uf = geobr.read_state(year=ANO_MAPA)
        uf["codigo_uf"] = uf["code_state"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
        _salvar_geojson(uf, GEOJSON_UF, ["codigo_uf", "abbrev_state", "name_state"], tolerancia=0.01)

    if not GEOJSON_MICRO.exists():
        micro = geobr.read_micro_region(year=ANO_MAPA)
        micro["codigo_microrregiao"] = micro["code_micro"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
        cols = ["codigo_microrregiao"]
        for c in ["name_micro", "name_micro_region", "name_region"]:
            if c in micro.columns:
                cols.append(c)
        _salvar_geojson(micro, GEOJSON_MICRO, cols, tolerancia=0.015)

    if not GEOJSON_MUN.exists():
        mun = geobr.read_municipality(year=ANO_MAPA)
        mun["codigo_municipio"] = mun["code_muni"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
        cols = ["codigo_municipio"]
        for c in ["name_muni", "name_municipality", "abbrev_state"]:
            if c in mun.columns:
                cols.append(c)
        _salvar_geojson(mun, GEOJSON_MUN, cols, tolerancia=0.04)


def carregar_geojson_uf():
    gerar_geojsons_se_necessario()
    gdf = gpd.read_file(GEOJSON_UF)
    # Compatibilidade com o app original.
    gdf["code_state"] = gdf["codigo_uf"].astype(str).str.zfill(2)
    return gdf


def carregar_geojson_micro():
    gerar_geojsons_se_necessario()
    gdf = gpd.read_file(GEOJSON_MICRO)
    gdf["code_micro"] = gdf["codigo_microrregiao"].astype(str).str.zfill(5)
    return gdf


def carregar_geojson_municipios():
    gerar_geojsons_se_necessario()
    gdf = gpd.read_file(GEOJSON_MUN)
    gdf["code_muni"] = gdf["codigo_municipio"].astype(str).str.zfill(7)
    return gdf
