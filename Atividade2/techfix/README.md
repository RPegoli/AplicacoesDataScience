# TechFix Informática — Sistema de Ordens de Serviço

Substitui o atendimento em papel por duas aplicações web (PC e celular) que compartilham o mesmo banco no Supabase:

```
[Celular / Navegador]                 [Navegador do Gerente]
        |                                      |
App Gradio (cadastro)            App Streamlit (gerenciamento)
        |          supabase-py (API REST)      |
        +-------------> SUPABASE <-------------+
                   (PostgreSQL na nuvem)
```

| Arquivo | Função |
|---|---|
| `sql/schema.sql` | Tabelas `clientes` e `ordens_servico`, restrições, índices, trigger, RLS e dados fictícios |
| `app_gradio.py` | Atendimento no balcão/celular: cadastra cliente (ou reaproveita pelo e-mail) e abre a OS |
| `app_streamlit.py` | Painel do gerente: Consultar, Cadastrar, Editar/Excluir, Indicadores + exportar CSV |
| `.env.example` / `.streamlit/secrets.toml.example` | Nomes das variáveis, sem valores |
| `evidencias/` | Prints das telas e das tabelas no Supabase |

## 1. Banco de dados (Supabase)

1. Crie um projeto gratuito em [supabase.com](https://supabase.com).
2. Abra **SQL Editor**, cole o conteúdo de `sql/schema.sql` e clique em **Run**.
3. Em **Project Settings → API** copie a **Project URL** e a chave **anon public**.

Modelo:

- `clientes` — `id` (PK identity), `nome`, `endereco`, `email` (**UNIQUE**, formato validado por regex, sempre minúsculo), `celular_whatsapp` (somente dígitos, 10 a 13), `data_cadastro` (default `now()`).
- `ordens_servico` — `id` (PK), `cliente_id` (**FK → clientes, ON DELETE CASCADE**), `modelo_computador`, `problema_relatado`, `status` (**CHECK**: Aberto, Em análise, Aguardando peça, Concluído, Entregue), `data_abertura` (default `now()`), `data_atualizacao` (atualizada por trigger).
- RLS ligado nas duas tabelas, com políticas liberando a chave `anon` (projeto acadêmico, sem login).

## 2. Instalação

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
```

Credenciais (nunca no código):

```bash
copy .env.example .env                                         # preencha SUPABASE_URL e SUPABASE_KEY
copy .streamlit\secrets.toml.example .streamlit\secrets.toml   # idem (opcional: o Streamlit também lê o .env)
```

Os dois arquivos preenchidos estão no `.gitignore`.

## 3. Execução

```bash
python app_gradio.py              # http://127.0.0.1:7860 + link público *.gradio.live para o celular
streamlit run app_streamlit.py    # http://localhost:8501
```

## 4. Funcionalidades

**Gradio (atendimento)**
- `gr.Blocks` com `gr.Row`/`gr.Column` (as colunas empilham no celular), labels e placeholders em todos os campos.
- Validação antes do envio: obrigatórios, formato do e-mail, celular só com números (10–13 dígitos).
- E-mail já existente → reaproveita o cliente; senão cria. A OS nasce com status `Aberto` e o número gerado é exibido.
- Botão **Limpar**; `share=True` gera link público temporário.

**Streamlit (gerente)**
- **Consultar**: `st.dataframe` com OS + dados do cliente; filtros na sidebar (nome, e-mail, status); **exportar CSV** dos dados filtrados (bônus).
- **Cadastrar**: nova OS para cliente existente ou novo cliente.
- **Editar/Excluir**: alterar status/equipamento/problema da OS e nome/endereço/e-mail/celular do cliente; exclusão de OS ou cliente com diálogo de confirmação (avisa quantas OS serão apagadas junto).
- **Indicadores**: `st.metric` por status, em andamento, total de clientes; gráficos de OS por status e por dia.

## 5. Boas práticas

- Chaves em `.env` / `secrets.toml` (fora do git); entregue apenas `.env.example`.
- Todo acesso ao banco está em `try/except`, com mensagens amigáveis (e-mail duplicado, validação, RLS, falta de conexão).
- Somente dados fictícios (domínio `example.com`, celulares `119000000xx`) — LGPD.

## 6. Evidências

Ver pasta [`evidencias/`](evidencias/).
