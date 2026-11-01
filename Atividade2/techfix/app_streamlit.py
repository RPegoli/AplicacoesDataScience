"""
TechFix Informática — Painel do Gerente (Streamlit)

CRUD completo das ordens de serviço e clientes, com filtros na barra lateral,
indicadores por status e exportação CSV.

Credenciais: .streamlit/secrets.toml (SUPABASE_URL / SUPABASE_KEY) ou,
como alternativa, variáveis de ambiente / arquivo .env.
Executar:  streamlit run app_streamlit.py
"""

import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

# Usa os certificados do sistema operacional (necessário quando um antivírus,
# como o Norton, inspeciona o HTTPS com uma raiz própria). Não desliga a verificação.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

STATUS = ["Aberto", "Em análise", "Aguardando peça", "Concluído", "Entregue"]
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CELULAR_RE = re.compile(r"^[0-9]{10,13}$")

st.set_page_config(page_title="TechFix — Painel", page_icon="🛠️", layout="wide")


# ---------------------------------------------------------------------------
# Conexão e acesso ao banco
# ---------------------------------------------------------------------------
def ler_credencial(nome: str) -> str | None:
    """Procura a chave em secrets.toml e, se não houver, nas variáveis de ambiente."""
    try:
        if nome in st.secrets:
            return st.secrets[nome]
    except Exception:  # noqa: BLE001 — secrets.toml ausente não é erro
        pass
    return os.getenv(nome)


@st.cache_resource
def get_supabase() -> Client:
    url, key = ler_credencial("SUPABASE_URL"), ler_credencial("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Credenciais não configuradas. Preencha .streamlit/secrets.toml "
            "(ou .env) com SUPABASE_URL e SUPABASE_KEY."
        )
    return create_client(url, key)


def mensagem_amigavel(erro: Exception) -> str:
    texto = str(erro)
    if "Credenciais" in texto:
        return texto
    if "23505" in texto or "duplicate key" in texto:
        return "Já existe um cliente com este e-mail."
    if "23514" in texto or "check constraint" in texto:
        return "Os dados não passaram na validação do banco (e-mail, celular, status ou campo vazio)."
    if "23503" in texto or "foreign key" in texto:
        return "Cliente inexistente para esta OS."
    if "42501" in texto or "row-level security" in texto:
        return "Sem permissão no banco. Verifique as políticas RLS do schema.sql."
    if "getaddrinfo" in texto or "Connect" in texto or "timed out" in texto:
        return "Não foi possível conectar ao Supabase. Verifique a internet e a SUPABASE_URL."
    return f"Erro inesperado: {texto}"


@st.cache_data(ttl=60, show_spinner="Carregando dados do Supabase...")
def carregar_ordens() -> pd.DataFrame:
    resp = (
        get_supabase()
        .table("ordens_servico")
        .select("*, clientes(nome, email, celular_whatsapp, endereco)")
        .order("id", desc=True)
        .execute()
    )
    linhas = []
    for r in resp.data:
        cli = r.pop("clientes") or {}
        linhas.append(
            {
                "OS": r["id"],
                "Status": r["status"],
                "Cliente": cli.get("nome"),
                "E-mail": cli.get("email"),
                "Celular": cli.get("celular_whatsapp"),
                "Endereço": cli.get("endereco"),
                "Equipamento": r["modelo_computador"],
                "Problema": r["problema_relatado"],
                "Abertura": r["data_abertura"],
                "Atualização": r["data_atualizacao"],
                "cliente_id": r["cliente_id"],
            }
        )
    df = pd.DataFrame(
        linhas,
        columns=["OS", "Status", "Cliente", "E-mail", "Celular", "Endereço", "Equipamento",
                 "Problema", "Abertura", "Atualização", "cliente_id"],
    )
    for col in ("Abertura", "Atualização"):
        df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601").dt.tz_convert("America/Sao_Paulo")
    return df


@st.cache_data(ttl=60, show_spinner=False)
def carregar_clientes() -> pd.DataFrame:
    resp = get_supabase().table("clientes").select("*").order("nome").execute()
    return pd.DataFrame(
        resp.data,
        columns=["id", "nome", "endereco", "email", "celular_whatsapp", "data_cadastro"],
    )


def executar(acao, msg_sucesso: str) -> bool:
    """Roda uma operação de escrita com try/except, mostra o resultado e limpa o cache."""
    try:
        acao()
    except Exception as erro:  # noqa: BLE001
        st.error(f"❌ {mensagem_amigavel(erro)}")
        return False
    st.cache_data.clear()
    st.session_state["flash"] = msg_sucesso
    return True


def validar_cliente(nome, endereco, email, celular) -> list[str]:
    erros = []
    if not all([nome, endereco, email, celular]):
        erros.append("Preencha nome, endereço, e-mail e celular.")
    if email and not EMAIL_RE.match(email):
        erros.append("E-mail em formato inválido.")
    if celular and not CELULAR_RE.match(celular):
        erros.append("Celular deve ter apenas números, de 10 a 13 dígitos.")
    return erros


# ---------------------------------------------------------------------------
# Diálogos de confirmação de exclusão
# ---------------------------------------------------------------------------
@st.dialog("Confirmar exclusão da OS")
def confirmar_exclusao_os(os_id: int, descricao: str):
    st.warning(f"Excluir definitivamente a **OS nº {os_id}** ({descricao})?")
    c1, c2 = st.columns(2)
    if c1.button("Sim, excluir", type="primary", width="stretch"):
        ok = executar(
            lambda: get_supabase().table("ordens_servico").delete().eq("id", os_id).execute(),
            f"🗑️ OS nº {os_id} excluída.",
        )
        if ok:
            st.rerun()
    if c2.button("Cancelar", width="stretch"):
        st.rerun()


@st.dialog("Confirmar exclusão do cliente")
def confirmar_exclusao_cliente(cliente_id: int, nome: str, qtd_os: int):
    st.warning(f"Excluir definitivamente o cliente **{nome}**?")
    if qtd_os:
        st.error(f"Atenção: as **{qtd_os} OS** deste cliente também serão excluídas (ON DELETE CASCADE).")
    c1, c2 = st.columns(2)
    if c1.button("Sim, excluir", type="primary", width="stretch"):
        ok = executar(
            lambda: get_supabase().table("clientes").delete().eq("id", cliente_id).execute(),
            f"🗑️ Cliente {nome} excluído.",
        )
        if ok:
            st.rerun()
    if c2.button("Cancelar", width="stretch"):
        st.rerun()


# ---------------------------------------------------------------------------
# Cabeçalho e carga de dados
# ---------------------------------------------------------------------------
st.title("🛠️ TechFix Informática — Painel do Gerente")

if msg := st.session_state.pop("flash", None):
    st.success(msg)

try:
    df_os = carregar_ordens()
    df_cli = carregar_clientes()
except Exception as erro:  # noqa: BLE001
    st.error(f"❌ Não foi possível carregar os dados. {mensagem_amigavel(erro)}")
    st.stop()


# ---------------------------------------------------------------------------
# Barra lateral: filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🔎 Filtros")
    f_nome = st.text_input("Nome do cliente", placeholder="Parte do nome")
    f_email = st.text_input("E-mail", placeholder="Parte do e-mail")
    f_status = st.multiselect("Status", STATUS, default=STATUS)
    st.divider()
    if st.button("🔄 Recarregar dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Dados fictícios para fins acadêmicos (LGPD).")

filtrado = df_os[df_os["Status"].isin(f_status)]
if f_nome:
    filtrado = filtrado[filtrado["Cliente"].str.contains(f_nome, case=False, na=False, regex=False)]
if f_email:
    filtrado = filtrado[filtrado["E-mail"].str.contains(f_email, case=False, na=False, regex=False)]


aba_consultar, aba_cadastrar, aba_editar, aba_indicadores = st.tabs(
    ["📋 Consultar", "➕ Cadastrar", "✏️ Editar/Excluir", "📊 Indicadores"]
)

# ---------------------------------------------------------------------------
# Aba 1 — Consultar
# ---------------------------------------------------------------------------
with aba_consultar:
    st.subheader(f"Ordens de serviço ({len(filtrado)} de {len(df_os)})")
    st.dataframe(
        filtrado.drop(columns=["cliente_id"]),
        hide_index=True,
        width="stretch",
        column_config={
            "OS": st.column_config.NumberColumn(format="%d", width="small"),
            "Abertura": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Atualização": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
        },
    )
    csv = filtrado.drop(columns=["cliente_id"]).to_csv(index=False, sep=";").encode("utf-8-sig")
    st.download_button(
        "⬇️ Exportar CSV (dados filtrados)",
        data=csv,
        file_name=f"techfix_os_{datetime.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
        disabled=filtrado.empty,
    )

# ---------------------------------------------------------------------------
# Aba 2 — Cadastrar
# ---------------------------------------------------------------------------
with aba_cadastrar:
    st.subheader("Nova ordem de serviço")
    tipo = st.radio("Cliente", ["Cliente existente", "Novo cliente"], horizontal=True)

    cli_sel = None
    with st.form("form_nova_os", clear_on_submit=True):
        if tipo == "Cliente existente":
            if df_cli.empty:
                st.info("Nenhum cliente cadastrado ainda. Escolha 'Novo cliente'.")
            else:
                nomes = df_cli.set_index("id")
                cli_sel = st.selectbox(
                    "Selecione o cliente",
                    nomes.index.tolist(),
                    format_func=lambda i: f"{nomes.loc[i, 'nome']} — {nomes.loc[i, 'email']} (nº {i})",
                )
        else:
            c1, c2 = st.columns(2)
            n_nome = c1.text_input("Nome do Cliente", placeholder="Ex.: Ana Teste da Silva")
            n_email = c2.text_input("E-mail", placeholder="Ex.: ana.teste@example.com")
            n_end = c1.text_input("Endereço", placeholder="Ex.: Rua das Flores, 100")
            n_cel = c2.text_input("Celular/WhatsApp", placeholder="Somente números. Ex.: 11900000001")

        modelo = st.text_input("Modelo do Computador", placeholder="Ex.: Notebook Lenovo IdeaPad 3")
        problema = st.text_area("Problema Apresentado", placeholder="Descreva o defeito relatado")
        status_ini = st.selectbox("Status inicial", STATUS, index=0)
        enviado = st.form_submit_button("Cadastrar OS", type="primary")

    if enviado:
        modelo, problema = modelo.strip(), problema.strip()
        erros = [] if (modelo and problema) else ["Preencha o modelo e o problema."]
        novo_cli = None
        if tipo == "Novo cliente":
            novo_cli = {
                "nome": n_nome.strip(),
                "endereco": n_end.strip(),
                "email": n_email.strip().lower(),
                "celular_whatsapp": n_cel.strip(),
            }
            erros += validar_cliente(*novo_cli.values())
        elif cli_sel is None:
            erros.append("Selecione um cliente.")

        if erros:
            for e in erros:
                st.warning(e)
        else:
            def inserir():
                sb = get_supabase()
                cid = cli_sel
                if novo_cli:
                    existe = sb.table("clientes").select("id").eq("email", novo_cli["email"]).execute()
                    cid = existe.data[0]["id"] if existe.data else (
                        sb.table("clientes").insert(novo_cli).execute().data[0]["id"]
                    )
                nova = sb.table("ordens_servico").insert(
                    {"cliente_id": cid, "modelo_computador": modelo,
                     "problema_relatado": problema, "status": status_ini}
                ).execute()
                st.session_state["nova_os"] = nova.data[0]["id"]

            if executar(inserir, "✅ OS cadastrada."):
                st.session_state["flash"] = f"✅ OS nº {st.session_state.pop('nova_os')} cadastrada com sucesso."
                st.rerun()

# ---------------------------------------------------------------------------
# Aba 3 — Editar/Excluir
# ---------------------------------------------------------------------------
with aba_editar:
    col_os, col_cli = st.columns(2, gap="large")

    # ---- Ordem de serviço ----
    with col_os:
        st.subheader("Ordem de serviço")
        if df_os.empty:
            st.info("Nenhuma OS cadastrada.")
        else:
            os_idx = df_os.set_index("OS")
            os_id = st.selectbox(
                "Selecione a OS",
                os_idx.index.tolist(),
                format_func=lambda i: (
                    f"OS {i} — {os_idx.loc[i, 'Cliente']} — "
                    f"{os_idx.loc[i, 'Equipamento']} [{os_idx.loc[i, 'Status']}]"
                ),
            )
            linha = os_idx.loc[os_id]
            with st.form("form_edit_os"):
                # a key inclui o id para os campos recarregarem ao trocar de OS
                e_status = st.selectbox("Status", STATUS, index=STATUS.index(linha["Status"]), key=f"os_st_{os_id}")
                e_modelo = st.text_input("Modelo do Computador", value=linha["Equipamento"], key=f"os_mod_{os_id}")
                e_prob = st.text_area("Problema Apresentado", value=linha["Problema"], key=f"os_prob_{os_id}")
                salvar_os = st.form_submit_button("💾 Salvar OS", type="primary")
            if salvar_os:
                if not e_modelo.strip() or not e_prob.strip():
                    st.warning("Modelo e problema não podem ficar vazios.")
                elif executar(
                    lambda: get_supabase().table("ordens_servico").update(
                        {"status": e_status, "modelo_computador": e_modelo.strip(),
                         "problema_relatado": e_prob.strip()}
                    ).eq("id", os_id).execute(),
                    f"✅ OS nº {os_id} atualizada ({e_status}).",
                ):
                    st.rerun()
            if st.button("🗑️ Excluir esta OS", key="del_os"):
                confirmar_exclusao_os(int(os_id), f"{linha['Cliente']} — {linha['Equipamento']}")

    # ---- Cliente ----
    with col_cli:
        st.subheader("Cliente")
        if df_cli.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            cli_idx = df_cli.set_index("id")
            cli_id = st.selectbox(
                "Selecione o cliente",
                cli_idx.index.tolist(),
                format_func=lambda i: f"{cli_idx.loc[i, 'nome']} — {cli_idx.loc[i, 'email']}",
            )
            c = cli_idx.loc[cli_id]
            with st.form("form_edit_cli"):
                e_nome = st.text_input("Nome", value=c["nome"], key=f"cli_nome_{cli_id}")
                e_end = st.text_input("Endereço", value=c["endereco"], key=f"cli_end_{cli_id}")
                e_email = st.text_input("E-mail", value=c["email"], key=f"cli_email_{cli_id}")
                e_cel = st.text_input("Celular/WhatsApp", value=c["celular_whatsapp"], key=f"cli_cel_{cli_id}")
                salvar_cli = st.form_submit_button("💾 Salvar cliente", type="primary")
            if salvar_cli:
                dados = {
                    "nome": e_nome.strip(),
                    "endereco": e_end.strip(),
                    "email": e_email.strip().lower(),
                    "celular_whatsapp": e_cel.strip(),
                }
                erros = validar_cliente(*dados.values())
                if erros:
                    for e in erros:
                        st.warning(e)
                elif executar(
                    lambda: get_supabase().table("clientes").update(dados).eq("id", int(cli_id)).execute(),
                    f"✅ Cliente {dados['nome']} atualizado.",
                ):
                    st.rerun()
            qtd = int((df_os["cliente_id"] == cli_id).sum())
            st.caption(f"Este cliente possui {qtd} OS.")
            if st.button("🗑️ Excluir este cliente", key="del_cli"):
                confirmar_exclusao_cliente(int(cli_id), c["nome"], qtd)

# ---------------------------------------------------------------------------
# Aba 4 — Indicadores
# ---------------------------------------------------------------------------
with aba_indicadores:
    st.subheader("Indicadores (considerando os filtros da barra lateral)")
    contagem = filtrado["Status"].value_counts().reindex(STATUS, fill_value=0)

    cols = st.columns(len(STATUS) + 1)
    cols[0].metric("Total de OS", len(filtrado))
    for col, (status, qtd) in zip(cols[1:], contagem.items()):
        col.metric(status, int(qtd))

    em_andamento = int(contagem[["Aberto", "Em análise", "Aguardando peça"]].sum())
    m1, m2 = st.columns(2)
    m1.metric("Em andamento (na loja)", em_andamento)
    m2.metric("Clientes cadastrados", len(df_cli))

    st.markdown("**OS por status**")
    st.bar_chart(contagem.rename_axis("Status").rename("Quantidade"), horizontal=True)

    if not filtrado.empty:
        st.markdown("**OS abertas por dia**")
        por_dia = filtrado.groupby(filtrado["Abertura"].dt.date).size().rename("OS abertas")
        st.bar_chart(por_dia)
