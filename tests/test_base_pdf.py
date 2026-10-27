from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.atendimento import Atendimento
from app.base import BasePdf
from app.classificador import classificar

LINHAS = [
    "prazo",
    "O contrato vale 12 meses.",
    "sla",
    "A primeira resposta sai em 4 horas.",
    "renovacao",
    "A renovação é automática.",
    "boleto",
    "O boleto sai dia 10.",
    "chamado",
    "O chamado segue o protocolo.",
    "desconhecido",
    "Um atendente continua a conversa.",
]


def _literal(texto: str) -> str:
    saida = []
    for caractere in texto.encode("latin-1"):
        if caractere in (ord("\\"), ord("("), ord(")")):
            saida.append("\\" + chr(caractere))
        elif caractere < 32 or caractere > 126:
            saida.append(f"\\{caractere:03o}")
        else:
            saida.append(chr(caractere))
    return "".join(saida)


def _gravar_pdf(caminho: Path, linhas: list[str]) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    fonte = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    comandos = ["BT", "/F1 12 Tf", "72 740 Td", "16 TL"]
    for indice, linha in enumerate(linhas):
        if indice:
            comandos.append("T*")
        comandos.append("(" + _literal(linha) + ") Tj")
    comandos.append("ET")
    fluxo = DecodedStreamObject()
    fluxo.set_data("\n".join(comandos).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(fluxo)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): fonte})}
    )
    writer.write(caminho)


def test_pdf_devolve_os_seis_temas(tmp_path: Path) -> None:
    caminho = tmp_path / "base.pdf"
    _gravar_pdf(caminho, LINHAS)
    base = BasePdf(caminho)
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
