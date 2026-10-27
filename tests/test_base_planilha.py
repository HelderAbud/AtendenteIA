from pathlib import Path

from openpyxl import Workbook

from app.atendimento import Atendimento
from app.base import BasePlanilha
from app.classificador import classificar

LINHAS = [
    ("prazo", "O contrato vale 12 meses."),
    ("sla", "A primeira resposta sai em 4 horas."),
    ("renovacao", "A renovação é automática."),
    ("boleto", "O boleto sai dia 10."),
    ("chamado", "O chamado segue o protocolo."),
    ("desconhecido", "Um atendente continua a conversa."),
]


def _gravar_planilha(caminho: Path, linhas: list[tuple[str, str]]) -> None:
    livro = Workbook()
    aba = livro.active
    aba.append(["tema", "resposta"])
    for tema, resposta in linhas:
        aba.append([tema, resposta])
    livro.save(caminho)


def test_planilha_devolve_os_seis_temas(tmp_path: Path) -> None:
    caminho = tmp_path / "base.xlsx"
    _gravar_planilha(caminho, [("", ""), *LINHAS])
    base = BasePlanilha(caminho)
    assert base.obter("prazo") == {
        "resposta": "O contrato vale 12 meses.",
        "encaminhar_humano": False,
    }
    assert base.obter("desconhecido")["encaminhar_humano"] is True
    resposta = Atendimento(classificar, base).responder("quando vence meu contrato?")
    assert resposta["tema"] == "prazo"
    assert resposta["resposta"] == "O contrato vale 12 meses."
    assert resposta["encaminhar_humano"] is False
    assert resposta["fluxo"] == "suporte"
    assert resposta["resumo"] is None
