# Dashboard Custo de Oportunidade Agropecuário — UESC

Projeto pronto para publicar no Streamlit Cloud.

## Estrutura

```text
app.py
auth.py
config.py
download_base.py
geojson_utils.py
requirements.txt
README.md
.streamlit/config.toml
.streamlit/secrets.toml.example
dados/.gitkeep
scripts/gerar_geojsons_local.py
scripts/gerar_base_custo_oportunidade_v15.py
scripts/ajustar_mapas_e_ranking_microrregioes.py
```

## O que deve ir para o GitHub

Envie todos os arquivos e pastas desta pasta para o repositório.

A pasta `.streamlit` precisa ir com `config.toml`.

A pasta `dados` precisa ir com os GeoJSONs depois de gerados:

```text
dados/geo_uf_simplificado.geojson
dados/geo_microrregioes_simplificado.geojson
dados/geo_municipios_simplificado.geojson
```

O arquivo `.gitkeep` existe apenas para o GitHub aceitar a pasta `dados` enquanto ela ainda está vazia.

## Base de dados

A base principal NÃO precisa ir para o GitHub. O app baixa automaticamente do Google Drive.

Arquivo esperado:

```text
BASE_USADA_ARTIGO_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv
```

ID configurado:

```text
1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9
```

## Senha no Streamlit Cloud

No Streamlit Cloud, abra:

```text
App > Settings > Secrets
```

Cole:

```toml
APP_PASSWORD = "sua_senha_aqui"
GOOGLE_DRIVE_ID = "1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9"
```

Nunca coloque a senha real em `secrets.toml` no GitHub.

## Por que esta versão não usa geobr/geopandas no app?

O Streamlit Cloud estava usando Python 3.14 e apresentou erro de instalação em `geobr/lxml/geopandas`. Por isso, esta versão carrega GeoJSONs prontos com `json` puro. Isso deixa o deploy mais estável.

## Como gerar os GeoJSONs

No seu computador, dentro da pasta do projeto, rode:

```bash
pip install geopandas geobr shapely pyogrio
python scripts/gerar_geojsons_local.py
```

Depois mova os três `.geojson` gerados para a pasta `dados/` e envie essa pasta para o GitHub.

## Requirements do app

O `requirements.txt` do Streamlit Cloud ficou leve:

```text
streamlit
pandas
numpy
plotly
folium
streamlit-folium
branca
gdown
```
