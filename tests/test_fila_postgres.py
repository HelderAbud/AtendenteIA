import pytest

from app.fila_postgres import FilaPostgres

import psycopg

URL = "postgresql://atendeia:atendeia@127.0.0.1:5437/atendeia"


@pytest.fixture(autouse=True)
def tabela_limpa() -> None:
    try:
        with psycopg.connect(URL) as conexao:
            conexao.execute(
                "TRUNCATE encaminhamentos RESTART IDENTITY"
            )
            conexao.commit()
    except psycopg.errors.UndefinedTable:
        return
    except psycopg.OperationalError:
        pytest.skip("Postgres em 127.0.0.1:5437 indisponível")


def test_url_sobrevive_e_nao_reusa_id() -> None:
    primeira = FilaPostgres(URL)
    primeira.registrar("quero uma proposta", "venda", "resumo")
    primeira.remover(1)
    segunda = FilaPostgres(URL)
    segunda.registrar("quero falar sobre o clima", "desconhecido", None)
    assert segunda.listar() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": None,
        }
    ]


def test_mesma_url_e_vista_por_duas_filas() -> None:
    FilaPostgres(URL).registrar("quero uma proposta", "venda", "resumo")
    assert FilaPostgres(URL).listar() == [
        {"id": 1, "pergunta": "quero uma proposta", "fluxo": "venda", "resumo": "resumo"}
    ]
