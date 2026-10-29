from pathlib import Path
import zipfile

import pytest
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


def test_planilha_ausente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BasePlanilha(tmp_path / "ausente.xlsx")


def test_arquivo_que_nao_e_planilha(tmp_path: Path) -> None:
    caminho = tmp_path / "falso.xlsx"
    caminho.write_bytes(b"nao-planilha")
    with pytest.raises(zipfile.BadZipFile):
        BasePlanilha(caminho)


def test_planilha_com_coluna_a_mais(tmp_path: Path) -> None:
    caminho = tmp_path / "larga.xlsx"
    livro = Workbook()
    aba = livro.active
    aba.append(["tema", "resposta", "extra"])
    for tema, resposta in LINHAS:
        aba.append([tema, resposta, ""])
    livro.save(caminho)
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_sem_um_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "incompleta.xlsx"
    _gravar_planilha(caminho, [linha for linha in LINHAS if linha[0] != "boleto"])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_repete_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "repetida.xlsx"
    _gravar_planilha(caminho, [*LINHAS, ("prazo", "Outro prazo.")])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_com_resposta_em_branco(tmp_path: Path) -> None:
    caminho = tmp_path / "branco.xlsx"
    _gravar_planilha(caminho, [("prazo", "   "), *LINHAS[1:]])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)
