from pathlib import Path
import streamlit as st
import gdown

from config import BASE_LOCAL_PATH, DEFAULT_GOOGLE_DRIVE_ID


def get_google_drive_id() -> str:
    """Usa o ID definido nos Secrets; se não existir, usa o ID padrão do projeto."""
    return st.secrets.get("GOOGLE_DRIVE_ID", DEFAULT_GOOGLE_DRIVE_ID)


def garantir_base_local(forcar_download: bool = False) -> Path:
    """Baixa a base do Google Drive apenas se ela ainda não existir localmente."""
    BASE_LOCAL_PATH.parent.mkdir(exist_ok=True)

    if BASE_LOCAL_PATH.exists() and not forcar_download:
        return BASE_LOCAL_PATH

    if BASE_LOCAL_PATH.exists() and forcar_download:
        BASE_LOCAL_PATH.unlink()

    file_id = get_google_drive_id()
    with st.spinner("Baixando a base oficial do Google Drive..."):
        gdown.download(id=file_id, output=str(BASE_LOCAL_PATH), quiet=False, fuzzy=True)

    if not BASE_LOCAL_PATH.exists() or BASE_LOCAL_PATH.stat().st_size == 0:
        raise FileNotFoundError(
            "Não consegui baixar a base do Google Drive. Verifique se o arquivo está compartilhado "
            "com permissão de leitura por link ou se o GOOGLE_DRIVE_ID está correto."
        )

    return BASE_LOCAL_PATH
