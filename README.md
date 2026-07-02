# Dashboard SIDRA - Custo de Oportunidade Agropecuário

Projeto Streamlit para visualizar o custo de oportunidade agropecuário por município, microrregião, UF e Grande Região.

## Arquivos principais

- `app.py`: aplicativo Streamlit.
- `auth.py`: controle de senha.
- `config.py`: caminhos, ID do Google Drive e parâmetros centrais.
- `download_base.py`: baixa a base do Google Drive somente quando necessário.
- `geojson_utils.py`: gera os GeoJSONs simplificados na primeira execução e reaproveita depois.
- `requirements.txt`: dependências do Streamlit Cloud.
- `scripts/gerar_base_custo_oportunidade_v15.py`: código original para gerar a base pela nova metodologia.
- `scripts/ajustar_mapas_e_ranking_microrregioes.py`: script auxiliar de ajustes dos mapas e ranking.

## Base de dados

A base oficial **não precisa ficar no GitHub**. O app baixa automaticamente do Google Drive usando o ID:

`1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9`

Nome esperado do arquivo:

`BASE_USADA_ARTIGO_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv`

O arquivo será salvo automaticamente em `dados/` na primeira execução.

## Senha no Streamlit Cloud

Em **Settings > Secrets**, adicione:

```toml
APP_PASSWORD = "sua_senha_aqui"
GOOGLE_DRIVE_ID = "1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9"
```

Não coloque a senha real no GitHub.

## Como rodar localmente

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Para testar localmente, crie `.streamlit/secrets.toml` a partir de `.streamlit/secrets.toml.example`.

## GeoJSONs

Os arquivos abaixo são criados automaticamente na primeira execução, caso não existam:

- `dados/geo_uf_simplificado.geojson`
- `dados/geo_microrregioes_simplificado.geojson`
- `dados/geo_municipios_simplificado.geojson`

Depois disso, o app reaproveita os arquivos salvos e não chama o `geobr` novamente.
