from app.fila import Fila
from app.fluxo import decidir_fluxo, montar_resumo


class Atendimento:
    def __init__(self, classificar_fn, base) -> None:
        self._classificar = classificar_fn
        self._base = base
        self._fila = Fila()

    def responder(self, pergunta: str) -> dict:
        tema = self._classificar(pergunta)
        item = self._base.obter(tema)
        fluxo = decidir_fluxo(tema, pergunta)
        resumo = montar_resumo(pergunta, fluxo)
        if item["encaminhar_humano"]:
            self._fila.registrar(pergunta, fluxo, resumo)
        return {
            "tema": tema,
            "resposta": item["resposta"],
            "encaminhar_humano": item["encaminhar_humano"],
            "fluxo": fluxo,
            "resumo": resumo,
        }

    def encaminhamentos(self) -> list[dict]:
        return self._fila.listar()

    def concluir(self, item_id: int) -> None:
        self._fila.remover(item_id)
