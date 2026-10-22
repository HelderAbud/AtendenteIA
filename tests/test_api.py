import json
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import _app_de_producao, criar_app, criar_app_de_arquivo
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


def test_dois_apps_no_mesmo_postgres_compartilham_a_lista() -> None:
    url = "postgresql://atendeia:atendeia@127.0.0.1:5437/atendeia"
    try:
        with psycopg.connect(url) as conexao:
            conexao.execute("TRUNCATE encaminhamentos RESTART IDENTITY")
            conexao.commit()
    except psycopg.OperationalError:
        pytest.skip("Postgres em 127.0.0.1:5437 indisponível")
    except psycopg.errors.UndefinedTable:
        pass
    um = TestClient(criar_app_de_arquivo(ARQUIVO, postgres_url=url))
    outro = TestClient(criar_app_de_arquivo(ARQUIVO, postgres_url=url))
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


def test_senha_certa_abre_sessao_e_senha_errada_nao() -> None:
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        senha="senha-teste",
        session_secret="segredo-teste",
    )
    client = TestClient(app, follow_redirects=False)
    formulario = client.get("/login")
    assert formulario.status_code == 200
    assert 'name="senha"' in formulario.text
    assert "Entrar" in formulario.text
    errada = client.post("/login", data={"senha": "outra"})
    assert errada.status_code == 401
    assert "Senha recusada." in errada.text
    assert client.get("/atendente").status_code == 303
    certa = client.post("/login", data={"senha": "senha-teste"})
    assert certa.status_code == 303
    assert certa.headers["location"] == "/atendente"
    assert client.get("/atendente").status_code == 200


def test_lista_e_delete_sem_sessao_nao_mexem_na_fila() -> None:
    app = criar_app_de_arquivo(
        ARQUIVO,
        senha="senha-teste",
        session_secret="segredo-teste",
    )
    client = TestClient(app, follow_redirects=False)
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    lista = client.get("/v1/encaminhamentos")
    apagar = client.delete("/v1/encaminhamentos/1")
    assert lista.status_code == 401
    assert lista.json() == {"erro": "sessao_ausente"}
    assert apagar.status_code == 401
    assert apagar.json() == {"erro": "sessao_ausente"}
    client.post("/login", data={"senha": "senha-teste"})
    assert client.get("/v1/encaminhamentos").json()[0]["id"] == 1
    assert client.delete("/v1/encaminhamentos/1").status_code == 204
    assert client.get("/v1/encaminhamentos").json() == []


def test_app_de_producao_liga_o_portao_com_as_duas_variaveis(monkeypatch) -> None:
    monkeypatch.setenv("ATENDEIA_SENHA", "senha-teste")
    monkeypatch.setenv("ATENDEIA_SESSION_SECRET", "segredo-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    app = _app_de_producao()
    client = TestClient(app, follow_redirects=False)
    assert client.get("/atendente").status_code == 303
    assert client.get("/atendente").headers["location"] == "/login"


def test_whatsapp_devolve_a_mesma_resposta_da_pergunta() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    whatsapp = client.post("/v1/whatsapp", json={"texto": texto})
    assert whatsapp.status_code == 200
    assert whatsapp.json() == pergunta.json()


@pytest.mark.parametrize(
    "corpo",
    [{}, {"texto": None}, {"texto": 10}, {"texto": ""}, {"texto": "   "}],
)
def test_whatsapp_invalido_nao_entra_na_lista(corpo: dict) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/whatsapp", json=corpo)
    lista = client.get("/v1/encaminhamentos")
    assert resposta.status_code == 422
    assert resposta.json() == {"erro": "pergunta_invalida"}
    assert lista.json() == []


def test_whatsapp_entra_na_mesma_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    client.post("/v1/whatsapp", json={"texto": "quero falar sobre o clima"})
    assert client.get("/v1/encaminhamentos").json() == [
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


def test_whatsapp_envia_a_resposta_para_quem_escreveu() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    whatsapp = client.post(
        "/v1/whatsapp",
        json={"texto": texto, "de": "5511999999999"},
    )
    assert whatsapp.status_code == 200
    assert whatsapp.json() == pergunta.json()
    assert enviados == [("5511999999999", pergunta.json()["resposta"])]
    assert "5511999999999" not in str(client.get("/v1/encaminhamentos").json())


def test_whatsapp_sem_destino_nao_envia() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    whatsapp = client.post("/v1/whatsapp", json={"texto": texto})
    assert whatsapp.json() == pergunta.json()
    assert enviados == []


def test_whatsapp_invalido_nao_envia() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp",
        json={"texto": "   ", "de": "5511999999999"},
    )
    assert resposta.status_code == 422
    assert enviados == []
    assert client.get("/v1/encaminhamentos").json() == []


def test_falha_no_envio_responde_502_e_guarda_o_encaminhamento() -> None:
    def quebra(destino, texto):
        raise RuntimeError("meta")

    app = criar_app_de_arquivo(ARQUIVO, enviar=quebra)
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp",
        json={"texto": "quero uma proposta", "de": "5511999999999"},
    )
    assert resposta.status_code == 502
    assert resposta.json() == {"erro": "envio_falhou"}
    assert client.get("/v1/encaminhamentos").json()[0]["pergunta"] == "quero uma proposta"


def test_app_de_producao_envia_pela_cloud_api(monkeypatch) -> None:
    chamadas = []

    def post(url, headers, json, timeout):
        chamadas.append((url, headers, json, timeout))

        class Resposta:
            def raise_for_status(self):
                return None

        return Resposta()

    monkeypatch.setattr("app.api.httpx.post", post)
    monkeypatch.setenv("ATENDEIA_WHATSAPP_TOKEN", "token-teste")
    monkeypatch.setenv("ATENDEIA_WHATSAPP_PHONE_ID", "1099")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    whatsapp = client.post(
        "/v1/whatsapp",
        json={"texto": texto, "de": "5511999999999"},
    )
    assert whatsapp.json() == pergunta.json()
    assert chamadas[0][0] == "https://graph.facebook.com/v26.0/1099/messages"
    assert chamadas[0][1]["Authorization"] == "Bearer token-teste"
    assert chamadas[0][2] == {
        "messaging_product": "whatsapp",
        "to": "5511999999999",
        "type": "text",
        "text": {"body": pergunta.json()["resposta"]},
    }


def test_webhook_devolve_o_challenge() -> None:
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        verificar_token="verificar-teste",
    )
    client = TestClient(app)
    resposta = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "123456",
        },
    )
    assert resposta.status_code == 200
    assert resposta.text == "123456"
    assert "text/plain" in resposta.headers["content-type"]


def test_webhook_recusa_challenge_errado() -> None:
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        verificar_token="verificar-teste",
    )
    client = TestClient(app)
    recusada = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "outro",
            "hub.challenge": "123456",
        },
    )
    assert recusada.status_code == 403
    assert recusada.json() == {"erro": "verificacao_recusada"}
    sem_token = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "outro",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "123456",
        },
    )
    assert sem_token.status_code == 403
    vazio = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "   ",
        },
    )
    assert vazio.status_code == 403
    ausente = TestClient(
        criar_app(Atendimento(classificar, BaseQueFalha()))
    ).get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "123456",
        },
    )
    assert ausente.status_code == 403
