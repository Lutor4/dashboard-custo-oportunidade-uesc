from pathlib import Path

# ============================================================
# CONFIGURAÇÕES DO DASHBOARD
# ============================================================

APP_TITLE = "UESC | Custo de Oportunidade Agropecuário"
ANO_MAPA = 2017

# ID do arquivo no Google Drive:
# https://drive.google.com/file/d/1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9/view
DEFAULT_GOOGLE_DRIVE_ID = "1WlJh_NZQZpwi9Fp9aWghr1mhB2gHwaJ9"
BASE_FILENAME = "BASE_USADA_ARTIGO_sem_menores_5ha_sem_outliers_acima_15000_maio2026.csv"

ROOT_DIR = Path(__file__).resolve().parent
DADOS_DIR = ROOT_DIR / "dados"
ASSETS_DIR = ROOT_DIR / "assets"
DADOS_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

BASE_LOCAL_PATH = DADOS_DIR / BASE_FILENAME
LOGO_PATH = ASSETS_DIR / "Brasão_da_UESC.png"

GEOJSON_UF = DADOS_DIR / "geo_uf_simplificado.geojson"
GEOJSON_MICRO = DADOS_DIR / "geo_microrregioes_simplificado.geojson"
GEOJSON_MUN = DADOS_DIR / "geo_municipios_simplificado.geojson"

COL_CUSTO_NAO_NEGATIVO = "custo_oportunidade_corrigido_r_ha_imputado_nao_negativo"
LIMITE_SUPERIOR_PADRAO = 15000

