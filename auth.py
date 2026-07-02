import streamlit as st


def check_password() -> bool:
    """Bloqueia o app até o usuário informar a senha definida no Streamlit Secrets."""
    if "APP_PASSWORD" not in st.secrets:
        st.error(
            "Senha não configurada. No Streamlit Cloud, vá em Settings > Secrets e adicione: "
            "APP_PASSWORD = \"sua_senha\""
        )
        st.stop()

    if st.session_state.get("password_ok"):
        return True

    st.title("Acesso restrito")
    senha = st.text_input("Digite a senha de acesso", type="password")

    if st.button("Entrar"):
        if senha == st.secrets["APP_PASSWORD"]:
            st.session_state["password_ok"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    st.stop()
