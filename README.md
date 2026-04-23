# Plataforma de Atendimentos — Rio Verde GO

Aplicação Streamlit para consulta e análise dos atendimentos da plataforma gove.digital.

## Estrutura

```
.
├── app.py                        # Página principal (listagem + mensagens)
├── api_client.py                 # Wrapper da API gove.digital
├── requirements.txt
├── .gitignore
└── .streamlit/
    ├── config.toml               # Tema e configurações
    └── secrets.toml.example      # Modelo de secrets (não commitar o real)
```

## Configuração local

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/atendimentos.git
cd atendimentos

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure os secrets
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml e preencha o token da API

# 4. Rode localmente
streamlit run app.py
```

## Deploy no Streamlit Cloud

1. Suba o repositório no GitHub (sem o `secrets.toml`).
2. Acesse [share.streamlit.io](https://share.streamlit.io) e conecte o repositório.
3. Em **Settings → Secrets**, cole o conteúdo abaixo (ajuste o token):

```toml
[api]
base_url = "https://api.gove.digital/v2"
token = "SEU_TOKEN_AQUI"
```

4. Clique em **Deploy**.

## Funcionalidades

- Listagem paginada de atendimentos (25 por página)
- Filtros: ID, destinatário, UUID do atendente, datas de início e fim, ordenação
- Painel lateral com histórico de mensagens de cada atendimento
- Mensagens diferenciadas por direção (cidadão / atendente)
