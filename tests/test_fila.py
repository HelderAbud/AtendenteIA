from app.fila import Fila


def test_lista_comeca_vazia() -> None:
    assert Fila().listar() == []


def test_registra_na_ordem_e_guarda_resumo_nulo() -> None:
    fila = Fila()
    fila.registrar("quero uma proposta", "venda", "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.")
    fila.registrar("qualquer coisa", "suporte", None)
    assert fila.listar() == [
        {
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {"pergunta": "qualquer coisa", "fluxo": "suporte", "resumo": None},
    ]
