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
