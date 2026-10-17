from app.fluxo import decidir_fluxo, montar_resumo


class Atendimento:
    def __init__(self, classificar_fn, base) -> None:
        self._classificar = classificar_fn
        self._base = base

    def responder(self, pergunta: str) -> dict:
        tema = self._classificar(pergunta)
        item = self._base.obter(tema)
        fluxo = decidir_fluxo(tema, pergunta)
        return {
            "tema": tema,
            "resposta": item["resposta"],
            "encaminhar_humano": item["encaminhar_humano"],
            "fluxo": fluxo,
            "resumo": montar_resumo(pergunta, fluxo),
        }
