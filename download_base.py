from pathlib import Path
import streamlit as st
import gdown

from config import BASE_LOCAL_PATH, DEFAULT_GOOGLE_DRIVE_ID


def get_google_drive_id() -> str:
    """
    Obtém o ID do Google Drive definido nos Secrets.
    Caso não exista, utiliza o ID padrão definido no config.py.
    """
    return st.secrets.get("GOOGLE_DRIVE_ID", DEFAULT_GOOGLE_DRIVE_ID)


def garantir_base_local(forcar_download: bool = False) -> Path:
    """
    Baixa a base do Google Drive somente quando necessário.
    """

    BASE_LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Já existe?
    if BASE_LOCAL_PATH.exists() and not forcar_download:
        return BASE_LOCAL_PATH

    # Forçar atualização
    if BASE_LOCAL_PATH.exists():
        BASE_LOCAL_PATH.unlink()

    file_id = get_google_drive_id()

    # URL direta do Google Drive
    url = f"https://drive.google.com/uc?id={file_id}"

    with st.spinner("Baixando base de dados..."):
        gdown.download(
            url=url,
            output=str(BASE_LOCAL_PATH),
            quiet=False,
        )

    if (
        not BASE_LOCAL_PATH.exists()
        or BASE_LOCAL_PATH.stat().st_size == 0
    ):
        raise FileNotFoundError(
            "Não foi possível baixar a base do Google Drive.\n\n"
            "Verifique:\n"
            "• Se o arquivo está compartilhado como 'Qualquer pessoa com o link'.\n"
            "• Se o GOOGLE_DRIVE_ID está correto.\n"
            "• Se o arquivo ainda existe no Google Drive."
        )

    return BASE_LOCAL_PATH
