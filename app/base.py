import json
from pathlib import Path

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
