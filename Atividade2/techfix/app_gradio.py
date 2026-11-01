"""
TechFix Informática — Atendimento (Gradio)

Formulário de balcão/celular para abrir ordens de serviço.
- Reaproveita o cliente se o e-mail já estiver cadastrado; senão cria um novo.
- Abre a OS com status 'Aberto' e informa o número gerado.

Credenciais: SUPABASE_URL e SUPABASE_KEY no arquivo .env (veja .env.example).
Executar:  python app_gradio.py
"""

import os
import re

import gradio as gr
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

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CELULAR_RE = re.compile(r"^[0-9]{10,13}$")

_client: Client | None = None


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_supabase() -> Client:
    """Cria (uma única vez) o cliente Supabase a partir das variáveis de ambiente."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError(
                "Credenciais não configuradas. Crie o arquivo .env com "
                "SUPABASE_URL e SUPABASE_KEY (veja .env.example)."
            )
        _client = create_client(url, key)
    return _client


def obter_ou_criar_cliente(sb: Client, nome, endereco, email, celular) -> tuple[int, bool]:
    """Retorna (id_do_cliente, reaproveitado?)."""
    achado = sb.table("clientes").select("id").eq("email", email).limit(1).execute()
    if achado.data:
        return achado.data[0]["id"], True

    novo = (
        sb.table("clientes")
        .insert({"nome": nome, "endereco": endereco, "email": email, "celular_whatsapp": celular})
        .execute()
    )
    return novo.data[0]["id"], False


def mensagem_amigavel(erro: Exception) -> str:
    """Traduz erros técnicos do banco/rede em mensagens para o atendente."""
    texto = str(erro)
    if "Credenciais" in texto:
        return texto
    if "23505" in texto or "duplicate key" in texto:
        return "Este e-mail já está cadastrado. Tente novamente."
    if "23514" in texto or "check constraint" in texto:
        return "Algum campo não passou na validação do banco (e-mail, celular ou campo vazio)."
    if "42501" in texto or "row-level security" in texto:
        return "Sem permissão no banco. Verifique as políticas RLS do schema.sql."
    if "getaddrinfo" in texto or "Connect" in texto or "timed out" in texto:
        return "Não foi possível conectar ao Supabase. Verifique a internet e a SUPABASE_URL."
    return f"Erro inesperado ao gravar: {texto}"


# ---------------------------------------------------------------------------
# Regras da tela
# ---------------------------------------------------------------------------
def validar(nome, endereco, email, celular, modelo, problema) -> list[str]:
    erros = []
    obrigatorios = {
        "Nome do Cliente": nome,
        "Endereço": endereco,
        "E-mail": email,
        "Celular/WhatsApp": celular,
        "Modelo do Computador": modelo,
        "Problema Apresentado": problema,
    }
    vazios = [rotulo for rotulo, valor in obrigatorios.items() if not valor]
    if vazios:
        erros.append("Preencha: " + ", ".join(vazios) + ".")
    if email and not EMAIL_RE.match(email):
        erros.append("E-mail em formato inválido (ex.: nome@exemplo.com).")
    if celular and not celular.isdigit():
        erros.append("Celular deve conter apenas números (sem espaços, traços ou parênteses).")
    elif celular and not CELULAR_RE.match(celular):
        erros.append("Celular deve ter de 10 a 13 dígitos (DDD + número).")
    return erros


def cadastrar(nome, endereco, email, celular, modelo, problema):
    nome = (nome or "").strip()
    endereco = (endereco or "").strip()
    email = (email or "").strip().lower()
    celular = (celular or "").strip()
    modelo = (modelo or "").strip()
    problema = (problema or "").strip()

    erros = validar(nome, endereco, email, celular, modelo, problema)
    if erros:
        return "### ⚠️ Corrija os campos\n" + "\n".join(f"- {e}" for e in erros)

    try:
        sb = get_supabase()
        cliente_id, reaproveitado = obter_ou_criar_cliente(sb, nome, endereco, email, celular)
        os_criada = (
            sb.table("ordens_servico")
            .insert(
                {
                    "cliente_id": cliente_id,
                    "modelo_computador": modelo,
                    "problema_relatado": problema,
                    "status": "Aberto",
                }
            )
            .execute()
        )
        numero_os = os_criada.data[0]["id"]
    except Exception as erro:  # noqa: BLE001 — qualquer falha vira mensagem amigável
        return f"### ❌ Não foi possível cadastrar\n{mensagem_amigavel(erro)}"

    origem = (
        f"Cliente já cadastrado (nº {cliente_id}) — dados reaproveitados."
        if reaproveitado
        else f"Novo cliente cadastrado (nº {cliente_id})."
    )
    return (
        f"### ✅ OS nº {numero_os} aberta com sucesso\n"
        f"- {origem}\n"
        f"- Equipamento: **{modelo}**\n"
        f"- Status: **Aberto**\n\n"
        f"Informe ao cliente o número **{numero_os}** para acompanhamento."
    )


def limpar():
    return "", "", "", "", "", "", ""


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
CSS = """
.gradio-container { max-width: 860px !important; margin: 0 auto; }
#resultado { min-height: 3rem; }
"""

with gr.Blocks(title="TechFix — Abertura de OS") as demo:
    gr.Markdown(
        "# 🛠️ TechFix Informática\n"
        "### Abertura de Ordem de Serviço\n"
        "Preencha os dados do cliente e do equipamento e toque em **Cadastrar**. "
        "Se o e-mail já existir, o cadastro do cliente é reaproveitado. "
        "Todos os campos são obrigatórios. *Use apenas dados fictícios em testes.*"
    )

    with gr.Group():
        gr.Markdown("**👤 Cliente**")
        with gr.Row():
            with gr.Column(min_width=280):
                nome = gr.Textbox(label="Nome do Cliente", placeholder="Ex.: Ana Teste da Silva")
            with gr.Column(min_width=280):
                email = gr.Textbox(label="E-mail", placeholder="Ex.: ana.teste@example.com", type="email")
        with gr.Row():
            with gr.Column(min_width=280):
                endereco = gr.Textbox(label="Endereço", placeholder="Ex.: Rua das Flores, 100 - Centro")
            with gr.Column(min_width=280):
                celular = gr.Textbox(
                    label="Celular/WhatsApp",
                    placeholder="Somente números com DDD. Ex.: 11900000001",
                    max_length=13,
                )

    with gr.Group():
        gr.Markdown("**💻 Equipamento**")
        modelo = gr.Textbox(label="Modelo do Computador", placeholder="Ex.: Notebook Dell Inspiron 15")
        problema = gr.Textbox(
            label="Problema Apresentado",
            placeholder="Descreva o defeito relatado pelo cliente. Ex.: não liga, tela azul ao iniciar...",
            lines=4,
        )

    with gr.Row():
        btn_cadastrar = gr.Button("Cadastrar", variant="primary", min_width=140)
        btn_limpar = gr.Button("Limpar", variant="secondary", min_width=140)

    resultado = gr.Markdown(elem_id="resultado")

    campos = [nome, endereco, email, celular, modelo, problema]
    btn_cadastrar.click(cadastrar, inputs=campos, outputs=resultado)
    btn_limpar.click(limpar, outputs=campos + [resultado])


if __name__ == "__main__":
    # share=True gera um link público temporário (*.gradio.live) para testar no celular.
    # Para rodar só localmente: defina GRADIO_SHARE=false no .env.
    compartilhar = os.getenv("GRADIO_SHARE", "true").lower() != "false"
    demo.launch(share=compartilhar, css=CSS, theme=gr.themes.Soft())
