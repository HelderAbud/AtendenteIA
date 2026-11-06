import psycopg
import pytest

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


def test_flag_falsa_nao_entra_na_fila() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    atendimento.responder("quero uma proposta")
    assert atendimento.encaminhamentos() == []


def test_flag_verdadeira_entra_na_ordem() -> None:
    atendimento = Atendimento(classificar, BaseSempreHumano())
    atendimento.responder("quando vence meu contrato?")
    atendimento.responder("quero uma proposta")
    assert atendimento.encaminhamentos() == [
        {
            "id": 1,
            "pergunta": "quando vence meu contrato?",
            "fluxo": "suporte",
            "resumo": None,
        },
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
    ]


def test_concluir_remove_so_o_id() -> None:
    atendimento = Atendimento(classificar, BaseSempreHumano())
    atendimento.responder("quando vence meu contrato?")
    atendimento.responder("quero uma proposta")
    atendimento.concluir(1)
    assert atendimento.encaminhamentos() == [
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        }
    ]


def test_mesmo_banco_sobrevive_entre_atendimentos(tmp_path) -> None:
    banco = tmp_path / "fila.sqlite"
    primeiro = Atendimento(classificar, BaseSempreHumano(), banco)
    primeiro.responder("quando vence meu contrato?")
    primeiro.concluir(1)
    segundo = Atendimento(classificar, BaseSempreHumano(), banco)
    segundo.responder("quero uma proposta")
    assert segundo.encaminhamentos() == [
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        }
    ]


def test_mesmo_postgres_sobrevive_entre_atendimentos() -> None:
    url = "postgresql://atendeia:atendeia@127.0.0.1:5437/atendeia"
    try:
        with psycopg.connect(url) as conexao:
            conexao.execute("TRUNCATE encaminhamentos RESTART IDENTITY")
            conexao.commit()
    except psycopg.OperationalError:
        pytest.skip("Postgres em 127.0.0.1:5437 indisponível")
    except psycopg.errors.UndefinedTable:
        pass
    primeiro = Atendimento(classificar, BaseSempreHumano(), postgres_url=url)
    primeiro.responder("quando vence meu contrato?")
    primeiro.concluir(1)
    segundo = Atendimento(classificar, BaseSempreHumano(), postgres_url=url)
    segundo.responder("quero uma proposta")
    assert segundo.encaminhamentos() == [
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        }
    ]


def test_reescreve_so_o_texto_da_base() -> None:
    atendimento = Atendimento(
        classificar,
        BaseSempreHumano(),
        reescrever=lambda texto: f"novo {texto}",
    )
    assert atendimento.responder("quando vence meu contrato?") == {
        "tema": "prazo",
        "resposta": "novo da base",
        "encaminhar_humano": True,
        "fluxo": "suporte",
        "resumo": None,
    }
    assert atendimento.encaminhamentos() == [
        {
            "id": 1,
            "pergunta": "quando vence meu contrato?",
            "fluxo": "suporte",
            "resumo": None,
        }
    ]


def test_reescrever_que_falha_mantem_o_texto_da_base(caplog) -> None:
    def reescrever(texto: str) -> str:
        raise RuntimeError("modelo")

    atendimento = Atendimento(
        classificar, BaseSempreHumano(), reescrever=reescrever
    )
    with caplog.at_level("WARNING", logger="atendeia"):
        resposta = atendimento.responder("quando vence meu contrato?")
    assert resposta["resposta"] == "da base"
    assert resposta["tema"] == "prazo"
    assert len(atendimento.encaminhamentos()) == 1
    assert "falha ao reescrever a resposta" in caplog.text


def test_reescrever_vazio_ou_de_outro_tipo_mantem_o_texto_da_base() -> None:
    for retorno in ("   ", None, 12):
        atendimento = Atendimento(
            classificar,
            BaseFalsa(),
            reescrever=lambda texto, valor=retorno: valor,
        )
        assert (
            atendimento.responder("quando vence meu contrato?")["resposta"]
            == "texto-prazo"
        )
