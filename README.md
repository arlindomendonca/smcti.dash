# Plataforma de Atendimentos — Rio Verde GO

Aplicação Streamlit para consulta e importação dos atendimentos da plataforma gove.digital para o Supabase.

## Estrutura

```
.
├── app.py                        # Página principal
├── api_client.py                 # Wrapper da API gove.digital
├── supabase_client.py            # Integração com o Supabase (upsert idempotente)
├── requirements.txt
├── .gitignore
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example      # Modelo — NÃO commitar o arquivo real
```

## Configuração local

```bash
git clone https://github.com/seu-usuario/atendimentos.git
cd atendimentos
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite secrets.toml com seus tokens
streamlit run app.py
```

## Deploy no Streamlit Cloud

1. Suba o repositório no GitHub (sem o `secrets.toml`).
2. Em [share.streamlit.io](https://share.streamlit.io), conecte o repositório.
3. Em **Settings → Secrets**, cole:

```toml
[api]
base_url = "https://api.gove.digital/v2"
token = "SEU_TOKEN_AQUI"

[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

> Use a **service_role key** do Supabase (Project Settings → API), não a anon key.

## Como funciona a importação

- A lista exibe apenas atendimentos **ainda não importados** no Supabase.
- O botão **⬆️ Integrar** percorre **todas as páginas** da API com os filtros ativos.
- Para cada atendimento novo: faz upsert de departamento → atendente → atendimento → mensagens.
- Upserts são **idempotentes** (chave `uuid` / `id`): rodar duas vezes não duplica dados.
- Após importação, os registros somem da lista automaticamente.
