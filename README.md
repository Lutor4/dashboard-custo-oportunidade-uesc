# Dashboard UESC - Custo de Oportunidade Agropecuário

## Arquivos para o GitHub

Obrigatórios:

- `app.py`
- `requirements.txt`
- `Brasão_da_UESC.png`

Para mapas:

- `geo_uf_simplificado.geojson`
- `geo_microrregioes_simplificado.geojson`
- `geo_municipios_simplificado.geojson` opcional, se ficar com menos de 25 MB.

A base CSV é baixada automaticamente do Google Drive.

## Como gerar os GeoJSONs

No seu computador, preferencialmente com Python 3.11 ou 3.12:

```bash
python -m pip install --upgrade pip
python -m pip install geopandas geobr shapely pyogrio
python gerar_geojsons.py
```

Depois envie os `.geojson` gerados para o GitHub.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Observação sobre a média e a mediana

O painel cria os estratos agregados e também o grupo geral `5) >= 5 ha`. Para evitar duplicação dos dados, o filtro de estrato vem por padrão selecionando apenas `5) >= 5 ha`.
