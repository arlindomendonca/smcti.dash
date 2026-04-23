# Plataforma de Atendimentos — Rio Verde GO

Aplicação Streamlit para consulta, importação e análise dos atendimentos da plataforma gove.digital com armazenamento no Supabase.

## Estrutura

```
.
├── app.py                          # Página principal: listagem + integração
├── api_client.py                   # Wrapper da API gove.digital
├── supabase_client.py              # Integração com Supabase
├── pages/
│   └── 2_📊_Dashboard.py           # Dashboard de análise
├── requirements.txt
├── .gitignore
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

## Páginas

### 💬 Atendimentos (principal)
Lista os atendimentos da API com filtros e paginação. Botão **Integrar** importa todos os novos registros para o Supabase.

### 📊 Dashboard
Análise de performance com KPIs, gráficos, filtros avançados e insights automáticos:
- Composição de atendimentos (real, 2FA, abandonado, em aberto)
- Evolução diária
- Performance por departamento e atendente
- Análise de prazos e duração
- Mapa de calor dia × hora
- Análise de qualidade (avaliações)
- Insights automáticos para alocação de times

## Dependências
- `streamlit` — interface
- `requests` — chamadas HTTP
- `pandas` — manipulação tabular
- `altair` — gráficos interativos

## Configuração

```bash
git clone https://github.com/seu-usuario/atendimentos.git
cd atendimentos
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite secrets.toml com seus tokens
streamlit run app.py
```

## SQL no Supabase

Execute nesta ordem no SQL Editor:
1. `schema_supabase.sql` — cria as tabelas
2. `disable_rls_supabase.sql` — desabilita RLS (backend usa service_role)
3. `view_atendimento_enriquecido.sql` — cria a view usada pelo Dashboard

## Deploy no Streamlit Cloud

Em **Settings → Secrets**:

```toml
[api]
base_url = "https://api.gove.digital/v2"
token = "SEU_TOKEN_AQUI"

[supabase]
url = "https://xxxxxxxx.supabase.co"
service_key = "eyJ..."   # service_role key
```
