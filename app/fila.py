class Fila:
    def __init__(self) -> None:
        self._itens: list[dict] = []

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        self._itens.append(
            {"pergunta": pergunta, "fluxo": fluxo, "resumo": resumo}
        )

    def listar(self) -> list[dict]:
        return list(self._itens)
