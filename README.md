# Dashboard UESC - Custo de Oportunidade Agropecuário

Aplicativo Streamlit para consultar e visualizar o custo de oportunidade agropecuário.

## Arquivos no GitHub

Suba para o repositório apenas:

- `app.py`
- `requirements.txt`
- `Brasão_da_UESC.png`
- `README.md`

A base CSV grande **não precisa ir para o GitHub**. O app baixa automaticamente a base do Google Drive pelo ID configurado no código.

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar no Streamlit Community Cloud

1. Crie um repositório no GitHub.
2. Envie `app.py`, `requirements.txt`, `README.md` e `Brasão_da_UESC.png`.
3. No Streamlit Cloud, escolha esse repositório.
4. Em Main file path, use: `app.py`.
5. Clique em Deploy.

## Base de dados

A base é baixada do Google Drive:

`https://drive.google.com/file/d/1lLDopv0fFkshCFgZ-2jMsfm39akzp7Kn/view?usp=sharing`

O arquivo precisa estar com compartilhamento: qualquer pessoa com o link pode visualizar.
