from app.classificador import tem_sinal

SINAIS_VENDA = ("contratar", "proposta", "orcamento", "licenca", "fechar")
TEMAS_SUPORTE = ("prazo", "sla", "renovacao", "boleto", "chamado")


def decidir_fluxo(tema: str, pergunta: str) -> str:
    if tema in TEMAS_SUPORTE:
        return "suporte"
    if any(tem_sinal(sinal, pergunta) for sinal in SINAIS_VENDA):
        return "venda"
    return "desconhecido"


def montar_resumo(pergunta: str, fluxo: str) -> str | None:
    if fluxo == "suporte":
        return None
    motivo = (
        "venda sem resposta na base"
        if fluxo == "venda"
        else "assunto fora da base"
    )
    return f"Pergunta: {pergunta}. Motivo: {motivo}."
