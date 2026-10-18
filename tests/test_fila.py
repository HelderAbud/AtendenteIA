import pytest

from app.fila import Fila


def test_lista_comeca_vazia() -> None:
    assert Fila().listar() == []


def test_registra_na_ordem_com_id_e_resumo_nulo() -> None:
    fila = Fila()
    fila.registrar("quero uma proposta", "venda", "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.")
    fila.registrar("qualquer coisa", "suporte", None)
    assert fila.listar() == [
        {
            "id": 1,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {"id": 2, "pergunta": "qualquer coisa", "fluxo": "suporte", "resumo": None},
    ]


def test_remover_nao_reusa_o_id() -> None:
    fila = Fila()
    fila.registrar("primeira", "venda", "resumo")
    fila.registrar("segunda", "desconhecido", "resumo 2")
    fila.remover(1)
    fila.registrar("terceira", "venda", "resumo 3")
    assert fila.listar() == [
        {"id": 2, "pergunta": "segunda", "fluxo": "desconhecido", "resumo": "resumo 2"},
        {"id": 3, "pergunta": "terceira", "fluxo": "venda", "resumo": "resumo 3"},
    ]


def test_id_ausente_levanta_key_error() -> None:
    fila = Fila()
    with pytest.raises(KeyError):
        fila.remover(1)


def test_arquivo_sobrevive_e_nao_reusa_id(tmp_path) -> None:
    caminho = tmp_path / "fila.sqlite"
    primeira = Fila(caminho)
    primeira.registrar("quero uma proposta", "venda", "resumo")
    primeira.remover(1)
    segunda = Fila(caminho)
    segunda.registrar("quero falar sobre o clima", "desconhecido", None)
    assert segunda.listar() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": None,
        }
    ]


def test_mesmo_arquivo_e_visto_por_duas_filas(tmp_path) -> None:
    caminho = tmp_path / "fila.sqlite"
    Fila(caminho).registrar("quero uma proposta", "venda", "resumo")
    assert Fila(caminho).listar() == [
        {"id": 1, "pergunta": "quero uma proposta", "fluxo": "venda", "resumo": "resumo"}
    ]
