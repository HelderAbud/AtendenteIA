import json
from pathlib import Path

from pypdf import PdfReader

TEMAS_NEGOCIO = ("prazo", "sla", "renovacao", "boleto", "chamado")
TEMA_DESCONHECIDO = "desconhecido"
TEMAS = TEMAS_NEGOCIO + (TEMA_DESCONHECIDO,)


class BaseConhecimento:
    def __init__(self, caminho: Path) -> None:
        if not caminho.is_file():
            raise FileNotFoundError(caminho)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self._itens = _validar(dados)

    def obter(self, tema: str) -> dict:
        return self._itens[tema]


def _validar(dados: object) -> dict[str, dict]:
    if not isinstance(dados, dict):
        raise ValueError("base invalida")
    itens: dict[str, dict] = {}
    for tema in TEMAS:
        if tema not in dados or not isinstance(dados[tema], dict):
            raise ValueError(f"tema ausente: {tema}")
        resposta = dados[tema].get("resposta")
        encaminhar = dados[tema].get("encaminhar_humano")
        if not isinstance(resposta, str) or not resposta.strip():
            raise ValueError(f"resposta ausente: {tema}")
        if not isinstance(encaminhar, bool):
            raise ValueError(f"encaminhar ausente: {tema}")
        if encaminhar is not (tema == TEMA_DESCONHECIDO):
            raise ValueError(f"encaminhar inesperado: {tema}")
        itens[tema] = {
            "resposta": resposta,
            "encaminhar_humano": encaminhar,
        }
    return itens


class BasePdf:
    def __init__(self, caminho: Path) -> None:
        if not caminho.is_file():
            raise FileNotFoundError(caminho)
        self._itens = _validar(_itens_do_pdf(caminho))

    def obter(self, tema: str) -> dict:
        return self._itens[tema]


def _itens_do_pdf(caminho: Path) -> dict[str, dict]:
    leitor = PdfReader(caminho)
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    blocos: dict[str, list[str]] = {}
    atual: str | None = None
    for linha in texto.splitlines():
        nome = linha.strip().lower()
        if nome in TEMAS:
            if nome in blocos:
                raise ValueError(f"tema repetido: {nome}")
            blocos[nome] = []
            atual = nome
            continue
        if atual is not None and linha.strip():
            blocos[atual].append(linha.strip())
    itens: dict[str, dict] = {}
    for tema in TEMAS:
        if tema not in blocos:
            raise ValueError(f"tema ausente: {tema}")
        resposta = " ".join(blocos[tema]).strip()
        if not resposta:
            raise ValueError(f"resposta ausente: {tema}")
        itens[tema] = {
            "resposta": resposta,
            "encaminhar_humano": tema == TEMA_DESCONHECIDO,
        }
    return itens
