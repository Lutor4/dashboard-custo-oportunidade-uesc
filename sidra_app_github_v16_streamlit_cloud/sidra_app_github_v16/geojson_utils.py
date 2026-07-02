from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from config import GEOJSON_UF, GEOJSON_MICRO, GEOJSON_MUN


class GeoJSONNaoEncontrado(FileNotFoundError):
    pass


def _ler_geojson(caminho: Path) -> dict[str, Any]:
    if not caminho.exists():
        raise GeoJSONNaoEncontrado(
            f"GeoJSON não encontrado: {caminho}. "
            "Gere os arquivos localmente com scripts/gerar_geojsons_local.py e envie a pasta dados/ para o GitHub."
        )
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def gerar_geojsons_se_necessario() -> None:
    """No Streamlit Cloud, não gera malhas para evitar geobr/geopandas.

    Os arquivos GeoJSON devem estar no repositório em dados/.
    Esta função apenas valida se eles existem.
    """
    faltantes = [
        str(p) for p in [GEOJSON_UF, GEOJSON_MICRO, GEOJSON_MUN]
        if not p.exists()
    ]
    if faltantes:
        raise GeoJSONNaoEncontrado(
            "Faltam os GeoJSONs: " + ", ".join(faltantes) + ". "
            "Rode localmente scripts/gerar_geojsons_local.py e envie os arquivos gerados para dados/."
        )


def carregar_geojson_uf() -> dict[str, Any]:
    return _ler_geojson(GEOJSON_UF)


def carregar_geojson_micro() -> dict[str, Any]:
    return _ler_geojson(GEOJSON_MICRO)


def carregar_geojson_municipios() -> dict[str, Any]:
    return _ler_geojson(GEOJSON_MUN)


def _normalizar_codigo(valor: Any, tamanho: int) -> str:
    txt = "" if valor is None else str(valor)
    txt = txt.replace(".0", "")
    txt = "".join(ch for ch in txt if ch.isdigit())
    return txt.zfill(tamanho) if txt else ""


def juntar_dados_no_geojson(
    geojson: dict[str, Any],
    dados_por_codigo: dict[str, dict[str, Any]],
    propriedade_codigo: str,
    tamanho_codigo: int,
    aliases_codigo: list[str] | None = None,
) -> dict[str, Any]:
    """Insere os dados agregados dentro das propriedades do GeoJSON."""
    aliases_codigo = aliases_codigo or []
    saida = deepcopy(geojson)

    for feature in saida.get("features", []):
        props = feature.setdefault("properties", {})
        codigo = props.get(propriedade_codigo)
        if codigo is None:
            for alias in aliases_codigo:
                if props.get(alias) is not None:
                    codigo = props.get(alias)
                    break
        codigo_norm = _normalizar_codigo(codigo, tamanho_codigo)
        props[propriedade_codigo] = codigo_norm
        if codigo_norm in dados_por_codigo:
            props.update(dados_por_codigo[codigo_norm])

    return saida
