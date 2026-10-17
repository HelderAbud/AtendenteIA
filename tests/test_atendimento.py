from app.atendimento import Atendimento
from app.classificador import classificar


class BaseFalsa:
    def obter(self, tema: str) -> dict:
        return {"resposta": f"texto-{tema}", "encaminhar_humano": False}


class BaseSempreHumano:
    def obter(self, tema: str) -> dict:
        return {"resposta": "da base", "encaminhar_humano": True}


def test_devolve_o_texto_da_base_trocada() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    assert atendimento.responder("quando vence meu contrato?") == {
        "tema": "prazo",
        "resposta": "texto-prazo",
        "encaminhar_humano": False,
        "fluxo": "suporte",
        "resumo": None,
    }


def test_copia_encaminhar_da_base() -> None:
    atendimento = Atendimento(lambda texto: "prazo", BaseSempreHumano())
    assert atendimento.responder("qualquer coisa") == {
        "tema": "prazo",
        "resposta": "da base",
        "encaminhar_humano": True,
        "fluxo": "suporte",
        "resumo": None,
    }


def test_venda_usa_a_resposta_da_base_e_o_resumo() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    assert atendimento.responder("quero uma proposta") == {
        "tema": "desconhecido",
        "resposta": "texto-desconhecido",
        "encaminhar_humano": False,
        "fluxo": "venda",
        "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
    }
