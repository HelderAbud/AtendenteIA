class Fila:
    def __init__(self) -> None:
        self._itens: list[dict] = []
        self._proximo_id = 1

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        self._itens.append(
            {
                "id": self._proximo_id,
                "pergunta": pergunta,
                "fluxo": fluxo,
                "resumo": resumo,
            }
        )
        self._proximo_id += 1

    def listar(self) -> list[dict]:
        return list(self._itens)

    def remover(self, item_id: int) -> None:
        for indice, item in enumerate(self._itens):
            if item["id"] == item_id:
                del self._itens[indice]
                return
        raise KeyError(item_id)
