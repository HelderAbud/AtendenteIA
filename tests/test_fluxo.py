from app.fluxo import decidir_fluxo, montar_resumo


def test_tema_de_suporte_vence_sinal_de_venda() -> None:
    assert decidir_fluxo("prazo", "quero uma proposta e o prazo") == "suporte"
    assert montar_resumo("quero uma proposta e o prazo", "suporte") is None


def test_venda_quando_o_tema_e_desconhecido() -> None:
    assert decidir_fluxo("desconhecido", "quero uma proposta") == "venda"
    assert (
        montar_resumo("quero uma proposta", "venda")
        == "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
    )


def test_orcamento_com_acento_e_venda() -> None:
    assert decidir_fluxo("desconhecido", "quero um orçamento") == "venda"


def test_sem_sinal_fica_desconhecido() -> None:
    assert decidir_fluxo("desconhecido", "quero falar sobre o clima") == "desconhecido"
    assert (
        montar_resumo("quero falar sobre o clima", "desconhecido")
        == "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base."
    )
