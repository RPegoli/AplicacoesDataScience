"""Cadastro de pacientes - versão Gradio (execução local).

Executar:  python app.py   ->  http://127.0.0.1:7860
"""

import csv
from datetime import datetime
from pathlib import Path

import gradio as gr
import pandas as pd

CSV_PATH = Path(__file__).parent / "pacientes.csv"
COLUNAS = ["data_hora", "nome", "idade", "convenio", "prioridade", "observacoes"]
CONVENIOS = ["Particular", "Unimed", "Bradesco Saúde", "SulAmérica", "Amil", "Hapvida", "Outro"]
ULTIMOS = 10


def carregar_ultimos() -> pd.DataFrame:
    if not CSV_PATH.exists():
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    return df.tail(ULTIMOS).iloc[::-1].reset_index(drop=True)


def cadastrar(nome, idade, convenio, prioridade, observacoes):
    nome = (nome or "").strip()
    if not nome:
        return "⚠️ Informe o nome do paciente.", carregar_ultimos()
    if idade is None or not 0 <= idade <= 130:
        return "⚠️ Informe uma idade válida (0 a 130).", carregar_ultimos()
    if not convenio:
        return "⚠️ Selecione o convênio.", carregar_ultimos()

    novo_arquivo = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if novo_arquivo:
            writer.writerow(COLUNAS)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            nome,
            int(idade),
            convenio,
            int(prioridade),
            (observacoes or "").strip(),
        ])

    return f"✅ Paciente **{nome}** cadastrado com sucesso!", carregar_ultimos()


with gr.Blocks(title="Cadastro de Pacientes") as demo:
    gr.Markdown("# 🩺 Cadastro de Pacientes\nConsultório médico — preencha os dados abaixo.")

    # Coluna única: todos os componentes empilhados, ideal para celular
    with gr.Column():
        nome = gr.Textbox(label="Nome do paciente", placeholder="Ex.: Maria da Silva")
        idade = gr.Number(label="Idade", value=None, precision=0, minimum=0, maximum=130)
        convenio = gr.Dropdown(label="Convênio", choices=CONVENIOS, value=None)
        prioridade = gr.Slider(label="Prioridade do atendimento (1 = baixa, 5 = urgente)",
                               minimum=1, maximum=5, step=1, value=3)
        observacoes = gr.Textbox(label="Motivo da consulta / observações", lines=4)
        botao = gr.Button("Cadastrar", variant="primary")
        mensagem = gr.Markdown()
        gr.Markdown(f"### Últimos {ULTIMOS} cadastros")
        tabela = gr.Dataframe(value=carregar_ultimos, headers=COLUNAS, interactive=False, wrap=True)

    botao.click(
        cadastrar,
        inputs=[nome, idade, convenio, prioridade, observacoes],
        outputs=[mensagem, tabela],
    )

if __name__ == "__main__":
    demo.launch()
