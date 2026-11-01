"""Cadastro de pacientes - versão Streamlit (deploy no Streamlit Community Cloud).

Executar localmente:  streamlit run app.py
"""

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

CSV_PATH = Path(__file__).parent / "pacientes.csv"
COLUNAS = ["data_hora", "nome", "idade", "convenio", "prioridade", "observacoes"]
CONVENIOS = ["Particular", "Unimed", "Bradesco Saúde", "SulAmérica", "Amil", "Hapvida", "Outro"]
ULTIMOS = 10

st.set_page_config(page_title="Cadastro de Pacientes", page_icon="🩺", layout="centered")


def carregar_csv() -> pd.DataFrame:
    if not CSV_PATH.exists():
        return pd.DataFrame(columns=COLUNAS)
    return pd.read_csv(CSV_PATH, encoding="utf-8-sig")


def gravar_linha(linha: dict) -> None:
    novo_arquivo = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo_arquivo:
            writer.writeheader()
        writer.writerow(linha)


# Estado da sessão: lista de cadastros e última mensagem de retorno
if "pacientes" not in st.session_state:
    st.session_state.pacientes = carregar_csv().to_dict("records")
if "mensagem" not in st.session_state:
    st.session_state.mensagem = None

st.title("🩺 Cadastro de Pacientes")
st.caption("Consultório médico — preencha os dados abaixo.")

with st.form("cadastro", clear_on_submit=True):
    nome = st.text_input("Nome do paciente", placeholder="Ex.: Maria da Silva")
    idade = st.number_input("Idade", min_value=0, max_value=130, value=None, step=1)
    convenio = st.selectbox("Convênio", CONVENIOS, index=None, placeholder="Selecione...")
    prioridade = st.slider("Prioridade do atendimento (1 = baixa, 5 = urgente)", 1, 5, 3)
    observacoes = st.text_area("Motivo da consulta / observações")
    enviado = st.form_submit_button("Cadastrar", type="primary", width="stretch")

if enviado:
    nome = nome.strip()
    if not nome:
        st.session_state.mensagem = ("warning", "Informe o nome do paciente.")
    elif idade is None:
        st.session_state.mensagem = ("warning", "Informe a idade.")
    elif convenio is None:
        st.session_state.mensagem = ("warning", "Selecione o convênio.")
    else:
        linha = {
            "data_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "nome": nome,
            "idade": int(idade),
            "convenio": convenio,
            "prioridade": int(prioridade),
            "observacoes": observacoes.strip(),
        }
        gravar_linha(linha)
        st.session_state.pacientes.append(linha)
        st.session_state.mensagem = ("success", f"Paciente **{nome}** cadastrado com sucesso!")

if st.session_state.mensagem:
    tipo, texto = st.session_state.mensagem
    getattr(st, tipo)(texto)

df = pd.DataFrame(st.session_state.pacientes, columns=COLUNAS)

st.subheader(f"Últimos {ULTIMOS} cadastros")
st.dataframe(df.tail(ULTIMOS).iloc[::-1], hide_index=True, width="stretch")

st.download_button(
    "⬇️ Baixar pacientes.csv",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="pacientes.csv",
    mime="text/csv",
    width="stretch",
    disabled=df.empty,
)
st.info(
    "O armazenamento no Streamlit Cloud é efêmero: o arquivo do servidor é apagado "
    "quando o app reinicia. Baixe o CSV para guardar os dados."
)
