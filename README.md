# Dashboard do Custo de Oportunidade da Agropecuária Brasileira

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-green)

---

## Sobre o projeto

O **Dashboard do Custo de Oportunidade da Agropecuária Brasileira** é uma plataforma interativa desenvolvida para visualização e análise espacial do custo de oportunidade da atividade agropecuária brasileira.

O painel foi construído a partir dos dados do **Censo Agropecuário 2017**, disponibilizados pelo **Sistema IBGE de Recuperação Automática (SIDRA/IBGE)**, permitindo análises em diferentes escalas territoriais e por estratos de área dos estabelecimentos agropecuários.

O dashboard disponibiliza mapas temáticos, rankings, estatísticas descritivas, gráficos interativos e exportação de resultados, auxiliando pesquisadores, gestores públicos e tomadores de decisão na compreensão da distribuição espacial do custo de oportunidade da agropecuária brasileira.

---

## Objetivos

O projeto tem como principais objetivos:

- calcular o custo de oportunidade da agropecuária por hectare;
- disponibilizar análises espaciais em diferentes escalas geográficas;
- comparar resultados entre estratos de área;
- permitir análises estatísticas interativas;
- apoiar pesquisas científicas e estudos sobre economia agrícola.

---

## Base de dados

Os indicadores foram construídos utilizando dados do:

- **Censo Agropecuário 2017**;
- **Sistema IBGE de Recuperação Automática (SIDRA)**.

A base oficial do artigo foi corrigida monetariamente para **maio de 2026** utilizando o **Índice de Preços ao Produtor Amplo – Mercado (IPA-M)** da Fundação Getulio Vargas (FGV).

A base oficial não precisa ficar no GitHub. O aplicativo baixa automaticamente a base do Google Drive usando o ID informado nos Secrets do Streamlit Cloud.

---

## Fluxo metodológico

```text
Extração dos dados do SIDRA
            │
            ▼
Atualização monetária (IPA-M)
            │
            ▼
Tratamento da base
            │
            ▼
Correção das áreas
            │
            ▼
Imputação hierárquica
(Microrregião → UF → Grande Região → Brasil)
            │
            ▼
Recálculo do custo
            │
            ▼
Custo de oportunidade não negativo
            │
            ▼
Dashboard
```

---

## Metodologia

O custo de oportunidade foi calculado por hectare utilizando:

$$
CO_{2017} = \frac{(VP - VD) \times 1000}{AU}
$$

em que:

- **VP** = Valor Bruto da Produção Agropecuária;
- **VD** = Valor das Despesas Agropecuárias;
- **AU** = Área Utilizada.

Como os valores monetários do SIDRA encontram-se em milhares de reais, foi aplicada a multiplicação por **1000** para obtenção dos valores em reais.

Posteriormente, foi realizada a atualização monetária:

$$
CO_{2026} = CO_{2017} \times F_{IPA-M}
$$

em que **F_IPA-M** representa o fator acumulado do IPA-M entre 2017 e maio de 2026.

---

## Área utilizada

O cálculo utiliza exclusivamente a **Área Utilizada dos Estabelecimentos Agropecuários**, obtida na **Tabela 6882 do SIDRA**.

Antes da construção do indicador foram realizadas correções nas áreas dos pequenos estratos, aumentando a consistência das estimativas.

---

## Tratamento dos dados

Foram realizados:

- atualização monetária pelo IPA-M;
- padronização dos códigos territoriais do IBGE;
- padronização das nomenclaturas territoriais;
- exclusão dos registros **Total**;
- exclusão dos registros **Total sem produtor sem área**;
- exclusão dos registros **Produtor sem área**;
- exclusão dos estabelecimentos pertencentes aos estratos inferiores a **5 hectares**;
- correção das áreas utilizadas dos pequenos estratos.

---

## Procedimentos de imputação

Em função da existência de dados suprimidos por sigilo estatístico ou da inexistência de observações em determinados municípios e estratos de área, foi desenvolvido um procedimento hierárquico de imputação.

Foram imputadas:

- Valor Bruto da Produção;
- Valor das Despesas;
- Área Utilizada.

A estratégia empregada utilizou a **mediana**, obedecendo à seguinte hierarquia:

1. Microrregião;
2. Unidade da Federação;
3. Grande Região;
4. Brasil.

Sempre que um determinado nível territorial possuía informações suficientes, a imputação era realizada nesse nível. Apenas na ausência de dados era utilizado o nível imediatamente superior.

Após as imputações, todo o custo de oportunidade foi recalculado utilizando os valores finais imputados.

---

## Custo de oportunidade não negativo

Além do indicador original foi construída uma segunda variável:

$$
CO^{+} = \max(CO_{2026}, 0)
$$

Valores negativos foram substituídos por zero, permitindo comparações espaciais focadas exclusivamente no potencial econômico positivo da atividade agropecuária.

---

## Atualização monetária pelo IPA-M

O aplicativo preserva a base oficial do artigo, originalmente corrigida para **maio/2026**, e permite criar uma base derivada atualizada pelo **IPA-M mais recente**.

Quando o botão **Atualizar valores pelo IPA-M mais recente** é acionado, o app:

1. consulta o histórico mensal do IPA-M no site Dados de Mercado;
2. atualiza o arquivo local `dados/indice_ipam.csv`;
3. calcula o fator incremental entre maio/2026 e o mês mais recente disponível;
4. recalcula produção corrigida, despesa corrigida, resultado líquido, custo de oportunidade e custo de oportunidade não negativo;
5. salva a base derivada em `dados/BASE_ATUALIZADA_IPAM.csv`;
6. passa a usar essa base para todos os usuários do app enquanto ela existir.

A base original no Google Drive **não é modificada**. Para voltar à referência oficial de maio/2026, use o botão **Restaurar base oficial de maio/2026**.

---

## Funcionalidades

O dashboard permite:

- mapas por Grande Região;
- mapas por Unidade da Federação;
- mapas por Microrregião;
- mapas por Município;
- mapas separados por estrato de área;
- legenda configurável por faixas manuais, quantis ou intervalos iguais;
- filtros territoriais;
- rankings gerais;
- rankings por estrato;
- boxplots;
- histogramas;
- estatísticas descritivas;
- exportação de tabelas em CSV e Excel;
- download de gráficos em PNG;
- download de mapas interativos em HTML;
- atualização monetária dinâmica pelo IPA-M.

---

## Estrutura do projeto

```text
dashboard-custo-oportunidade-uesc/

├── app.py
├── auth.py
├── config.py
├── download_base.py
├── geojson_utils.py
├── requirements.txt
│
├── assets/
│   └── Brasão_da_UESC.png
│
├── dados/
│   ├── geo_uf_simplificado.geojson
│   ├── geo_microrregioes_simplificado.geojson
│   └── geo_municipios_simplificado.geojson
│
├── scripts/
│   ├── gerar_base_custo_oportunidade_v15.py
│   ├── ajustar_mapas_e_ranking_microrregioes.py
│   └── gerar_geojsons_local.py
│
└── README.md
```

---

## Arquivos principais

| Arquivo | Descrição |
|---------|-----------|
| `app.py` | Aplicativo principal desenvolvido em Streamlit. |
| `auth.py` | Controle de autenticação por senha. |
| `config.py` | Configurações centrais do projeto. |
| `download_base.py` | Baixa automaticamente a base oficial quando necessário. |
| `geojson_utils.py` | Gera automaticamente os GeoJSONs simplificados na primeira execução e reutiliza-os nas execuções seguintes. |
| `requirements.txt` | Dependências do projeto. |

---

## Configuração do Streamlit Cloud

Adicionar os seguintes Secrets:

```toml
APP_PASSWORD = "sua_senha"
GOOGLE_DRIVE_ID = "SEU_ID_DO_GOOGLE_DRIVE"
```

> **Importante:** nunca publique sua senha nem os Secrets no repositório.

---

## Executando localmente

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute:

```bash
streamlit run app.py
```

Caso utilize autenticação local, crie o arquivo:

```text
.streamlit/secrets.toml
```

utilizando como referência:

```text
.streamlit/secrets.toml.example
```

---

## Créditos

### Desenvolvimento metodológico, científico e computacional

Em ordem alfabética:

- **Andréa da Silva Gomes**
- **Helga Dulce Bispo Passos**
- **Luciene Maria Torquato Cerqueira Batista**
- **Mônica de Moura Pires**

---

## Instituição

**Universidade Estadual de Santa Cruz (UESC)**

Departamento de Ciências Exatas e Tecnológicas

---

## Como citar

> BATISTA, L. M. T. C.; GOMES, A. S.; PASSOS, H. D. B.; PIRES, M. M. **Dashboard do Custo de Oportunidade da Agropecuária Brasileira.** Universidade Estadual de Santa Cruz (UESC), 2026.

---

## Licença

Este projeto foi desenvolvido para fins científicos, acadêmicos e de pesquisa.

Caso utilize este código ou a metodologia em trabalhos científicos, solicita-se que a fonte seja devidamente citada.
