import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import criar_app, criar_app_de_arquivo
from app.atendimento import Atendimento
from app.classificador import classificar

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "data" / "vertice_ti.json"

TEXTOS = {
    "prazo": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
    "sla": "A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.",
    "renovacao": "A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.",
    "boleto": "O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.",
    "chamado": "O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.",
    "desconhecido": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
}


class BaseQueFalha:
    def obter(self, tema: str) -> dict:
        raise AssertionError("health nao le a base")


def test_health_nao_le_a_base() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("pergunta", "tema"),
    [
        ("quando vence meu contrato?", "prazo"),
        ("VIGÊNCIA do suporte", "prazo"),
        ("qual é o sla?", "sla"),
        ("como faco a renovacao?", "renovacao"),
        ("preciso da segunda via do boleto", "boleto"),
        ("qual o status do chamado?", "chamado"),
        ("quero falar sobre o clima", "desconhecido"),
        ("vence o boleto", "desconhecido"),
    ],
)
def test_perguntas_da_spec(pergunta: str, tema: str) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json={"pergunta": pergunta})
    if tema == "desconhecido":
        fluxo = "desconhecido"
        resumo = f"Pergunta: {pergunta}. Motivo: assunto fora da base."
    else:
        fluxo = "suporte"
        resumo = None
    assert resposta.status_code == 200
    assert resposta.json() == {
        "tema": tema,
        "resposta": TEXTOS[tema],
        "encaminhar_humano": tema == "desconhecido",
        "fluxo": fluxo,
        "resumo": resumo,
    }


@pytest.mark.parametrize(
    "corpo",
    [{}, {"pergunta": None}, {"pergunta": 10}, {"pergunta": ""}, {"pergunta": "   "}],
)
def test_pergunta_invalida(corpo: dict) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json=corpo)
    assert resposta.status_code == 422
    assert resposta.json() == {"erro": "pergunta_invalida"}


def test_arquivo_ausente_impede_a_subida(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        criar_app_de_arquivo(tmp_path / "ausente.json")


def test_base_invalida_impede_a_subida(tmp_path: Path) -> None:
    caminho = tmp_path / "base.json"
    caminho.write_text(json.dumps({"prazo": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        criar_app_de_arquivo(caminho)


def test_proposta_vira_venda() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    assert resposta.status_code == 200
    assert resposta.json() == {
        "tema": "desconhecido",
        "resposta": TEXTOS["desconhecido"],
        "encaminhar_humano": True,
        "fluxo": "venda",
        "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
    }


def test_raiz_serve_a_pagina() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    texto = resposta.text
    assert 'id="pergunta"' in texto
    assert 'id="resposta"' in texto
    assert 'id="resumo"' in texto
    assert "/v1/perguntas" in texto


def test_lista_nao_le_a_base_e_comeca_vazia() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/v1/encaminhamentos")
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_so_a_flag_verdadeira_entra_na_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    client.post("/v1/perguntas", json={"pergunta": "quando vence meu contrato?"})
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    client.post("/v1/perguntas", json={"pergunta": "quero falar sobre o clima"})
    resposta = client.get("/v1/encaminhamentos")
    assert resposta.status_code == 200
    assert resposta.json() == [
        {
            "id": 1,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base.",
        },
    ]


def test_pergunta_invalida_nao_entra_na_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    invalida = client.post("/v1/perguntas", json={"pergunta": "   "})
    lista = client.get("/v1/encaminhamentos")
    assert invalida.status_code == 422
    assert lista.json() == []


def test_duas_apps_nao_compartilham_a_lista() -> None:
    um = TestClient(criar_app_de_arquivo(ARQUIVO))
    outro = TestClient(criar_app_de_arquivo(ARQUIVO))
    um.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    assert outro.get("/v1/encaminhamentos").json() == []


def test_atendente_serve_a_pagina() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/atendente")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    texto = resposta.text
    assert 'id="lista"' in texto
    assert "/v1/encaminhamentos" in texto
    assert "Nenhum encaminhamento." in texto
    assert "Concluir" in texto
    assert "DELETE" in texto


def test_delete_remove_o_item_e_nao_reusa_o_id() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    client.post("/v1/perguntas", json={"pergunta": "quero falar sobre o clima"})
    removido = client.delete("/v1/encaminhamentos/1")
    assert removido.status_code == 204
    assert removido.content == b""
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    assert client.get("/v1/encaminhamentos").json() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base.",
        },
        {
            "id": 3,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
    ]


def test_delete_de_id_ausente_nao_le_a_base() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.delete("/v1/encaminhamentos/1")
    assert resposta.status_code == 404
    assert resposta.json() == {"erro": "encaminhamento_inexistente"}


def test_dois_apps_no_mesmo_banco_compartilham_a_lista(tmp_path) -> None:
    banco = tmp_path / "fila.sqlite"
    um = TestClient(criar_app_de_arquivo(ARQUIVO, banco))
    outro = TestClient(criar_app_de_arquivo(ARQUIVO, banco))
    um.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    outro.delete("/v1/encaminhamentos/1")
    um.post("/v1/perguntas", json={"pergunta": "quero falar sobre o clima"})
    assert outro.get("/v1/encaminhamentos").json() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base.",
        }
    ]
