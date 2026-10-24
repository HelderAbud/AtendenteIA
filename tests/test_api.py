import hashlib
import hmac
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


def test_pergunta_longa_nao_entra_na_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    longa = "a" * 501
    resposta = client.post("/v1/perguntas", json={"pergunta": longa})
    whatsapp = client.post("/v1/whatsapp", json={"texto": longa})
    assert resposta.status_code == 422
    assert resposta.json() == {"erro": "pergunta_invalida"}
    assert whatsapp.status_code == 422
    assert whatsapp.json() == {"erro": "pergunta_invalida"}
    assert client.get("/v1/encaminhamentos").json() == []


def test_delete_com_id_texto_nao_diz_pergunta_invalida() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.delete("/v1/encaminhamentos/abc")
    assert resposta.status_code == 422
    assert resposta.json() == {"erro": "requisicao_invalida"}


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


def test_login_bloqueia_depois_de_cinco_erros() -> None:
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        senha="senha-teste",
        session_secret="segredo-teste",
    )
    client = TestClient(app, follow_redirects=False)
    for _ in range(5):
        recusada = client.post("/login", data={"senha": "outra"})
        assert recusada.status_code == 401
    bloqueada = client.post("/login", data={"senha": "senha-teste"})
    assert bloqueada.status_code == 429
    assert "Muitas tentativas." in bloqueada.text
    assert client.get("/atendente").status_code == 303


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
    assert whatsapp.json() == pergunta.json()
    assert enviados == []
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


def test_rota_publica_nao_envia_mesmo_se_o_envio_falha() -> None:
    def quebra(destino, texto):
        raise RuntimeError("meta")

    app = criar_app_de_arquivo(ARQUIVO, enviar=quebra)
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp",
        json={"texto": "quero uma proposta", "de": "5511999999999"},
    )
    assert resposta.status_code == 200
    assert resposta.json()["fluxo"] == "venda"
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
    aberto = client.post(
        "/v1/whatsapp",
        json={"texto": texto, "de": "5511999999999"},
    )
    assert aberto.json() == pergunta.json()
    assert chamadas == []
    whatsapp = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": texto},
                }
            ]
        ),
    )
    assert whatsapp.status_code == 200
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


def _aviso(mensagens: list[dict]) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": mensagens}}]}]}


def test_webhook_envia_a_resposta_da_primeira_mensagem() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    aviso = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511000000000",
                    "type": "image",
                    "image": {"id": "1"},
                },
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": texto},
                },
                {
                    "from": "5511222222222",
                    "type": "text",
                    "text": {"body": "quero uma proposta"},
                },
            ]
        ),
    )
    assert aviso.status_code == 200
    assert aviso.content == b""
    assert enviados == [("5511999999999", pergunta.json()["resposta"])]
    assert client.get("/v1/encaminhamentos").json() == []


def test_webhook_guarda_o_encaminhamento_sem_telefone() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": "quero uma proposta"},
                }
            ]
        ),
    )
    assert resposta.status_code == 200
    assert enviados == [("5511999999999", TEXTOS["desconhecido"])]
    item = client.get("/v1/encaminhamentos").json()[0]
    assert item["pergunta"] == "quero uma proposta"
    assert item["fluxo"] == "venda"
    assert item["resumo"] == (
        "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
    )
    assert "5511999999999" not in str(client.get("/v1/encaminhamentos").json())


def test_webhook_sem_texto_nao_chama_o_atendimento() -> None:
    enviados = []
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    status = client.post(
        "/v1/whatsapp/webhook",
        json={"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]},
    )
    branco = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [{"from": "5511999999999", "type": "text", "text": {"body": "   "}}]
        ),
    )
    invalido = client.post("/v1/whatsapp/webhook", content=b"nao-json")
    vazio = client.post("/v1/whatsapp/webhook", content=b"")
    longo = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": "a" * 501},
                }
            ]
        ),
    )
    assert status.status_code == 200
    assert branco.status_code == 200
    assert invalido.status_code == 200
    assert vazio.status_code == 200
    assert longo.status_code == 200
    assert (
        status.content
        == branco.content
        == invalido.content
        == vazio.content
        == longo.content
        == b""
    )
    assert enviados == []


def test_falha_no_envio_do_webhook_fica_no_log(caplog) -> None:
    def quebra(destino, texto):
        raise RuntimeError("meta")

    app = criar_app_de_arquivo(ARQUIVO, enviar=quebra)
    client = TestClient(app)
    with caplog.at_level("WARNING", logger="atendeia"):
        resposta = client.post(
            "/v1/whatsapp/webhook",
            json=_aviso(
                [
                    {
                        "from": "5511999999999",
                        "type": "text",
                        "text": {"body": "quero uma proposta"},
                    }
                ]
            ),
        )
    assert resposta.status_code == 200
    assert resposta.content == b""
    assert "falha ao enviar a resposta do webhook" in caplog.text
    assert client.get("/v1/encaminhamentos").json()[0]["pergunta"] == "quero uma proposta"


def test_subida_avisa_quando_faltam_segredos(monkeypatch, caplog) -> None:
    monkeypatch.delenv("ATENDEIA_SENHA", raising=False)
    monkeypatch.delenv("ATENDEIA_SESSION_SECRET", raising=False)
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    monkeypatch.delenv("ATENDEIA_WHATSAPP_APP_SECRET", raising=False)
    monkeypatch.setenv("ATENDEIA_WHATSAPP_TOKEN", "token")
    monkeypatch.setenv("ATENDEIA_WHATSAPP_PHONE_ID", "1099")
    with caplog.at_level("WARNING", logger="atendeia"):
        _app_de_producao()
    assert "painel e fila abertos" in caplog.text
    assert "webhook sem assinatura" in caplog.text


def test_webhook_sem_remetente_guarda_e_nao_envia() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso([{"type": "text", "text": {"body": "quero uma proposta"}}]),
    )
    assert resposta.status_code == 200
    assert enviados == []
    assert client.get("/v1/encaminhamentos").json()[0]["pergunta"] == "quero uma proposta"


def test_webhook_com_falha_no_envio_responde_200_e_guarda() -> None:
    def falhar(destino: str, texto: str) -> None:
        raise RuntimeError("meta indisponivel")

    app = criar_app_de_arquivo(ARQUIVO, enviar=falhar)
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": "quero uma proposta"},
                }
            ]
        ),
    )
    assert resposta.status_code == 200
    assert resposta.content == b""
    assert client.get("/v1/encaminhamentos").json()[0]["pergunta"] == "quero uma proposta"


def test_webhook_nao_pede_sessao() -> None:
    app = criar_app_de_arquivo(
        ARQUIVO,
        senha="segredo",
        session_secret="assinatura",
    )
    client = TestClient(app)
    resposta = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": "quero uma proposta"},
                }
            ]
        ),
    )
    assert resposta.status_code == 200
    assert client.get("/v1/encaminhamentos").status_code == 401


def test_app_de_producao_confirma_o_webhook(monkeypatch) -> None:
    monkeypatch.setenv("ATENDEIA_WHATSAPP_VERIFY_TOKEN", "verificar-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    monkeypatch.delenv("ATENDEIA_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("ATENDEIA_WHATSAPP_PHONE_ID", raising=False)
    client = TestClient(_app_de_producao())
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


def _app_de_producao_sem_verificacao(monkeypatch):
    monkeypatch.setenv("ATENDEIA_WHATSAPP_VERIFY_TOKEN", "")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    return _app_de_producao()


def test_app_de_producao_recebe_o_webhook_e_envia(monkeypatch) -> None:
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
    monkeypatch.setenv("ATENDEIA_WHATSAPP_VERIFY_TOKEN", "verificar-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    aviso = client.post(
        "/v1/whatsapp/webhook",
        json=_aviso(
            [
                {
                    "from": "5511999999999",
                    "type": "text",
                    "text": {"body": texto},
                }
            ]
        ),
    )
    assert aviso.status_code == 200
    assert chamadas[0][0] == "https://graph.facebook.com/v26.0/1099/messages"
    assert chamadas[0][1]["Authorization"] == "Bearer token-teste"
    assert chamadas[0][2]["to"] == "5511999999999"
    assert chamadas[0][2]["text"]["body"] == pergunta.json()["resposta"]
    vazio = TestClient(_app_de_producao_sem_verificacao(monkeypatch)).get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "123456",
        },
    )
    assert vazio.status_code == 403


def _post_assinado(client: TestClient, segredo: str, aviso: object, cabecalho: str | None = None):
    corpo = json.dumps(aviso).encode()
    headers = {"content-type": "application/json"}
    if cabecalho is None:
        digest = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
        headers["x-hub-signature-256"] = f"sha256={digest}"
    elif cabecalho:
        headers["x-hub-signature-256"] = cabecalho
    return client.post("/v1/whatsapp/webhook", content=corpo, headers=headers)


def test_webhook_recusa_assinatura_errada() -> None:
    enviados = []
    app = criar_app(
        Atendimento(classificar, BaseQueFalha()),
        verificar_token="verificar-teste",
        app_secret="segredo-teste",
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    aviso = _aviso(
        [{"from": "5511999999999", "type": "text", "text": {"body": "quero uma proposta"}}]
    )
    challenge = client.get(
        "/v1/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verificar-teste",
            "hub.challenge": "123456",
        },
    )
    assert challenge.status_code == 200
    assert challenge.text == "123456"
    ausente = _post_assinado(client, "segredo-teste", aviso, cabecalho="")
    errada = _post_assinado(client, "segredo-teste", aviso, cabecalho="sha256=" + ("0" * 64))
    sem_prefixo = _post_assinado(
        client,
        "segredo-teste",
        aviso,
        cabecalho=hmac.new(
            b"segredo-teste", json.dumps(aviso).encode(), hashlib.sha256
        ).hexdigest(),
    )
    outro_corpo = _post_assinado(
        client,
        "segredo-teste",
        aviso,
        cabecalho="sha256="
        + hmac.new(b"segredo-teste", b'{"a":1}', hashlib.sha256).hexdigest(),
    )
    assert (
        ausente.status_code
        == errada.status_code
        == sem_prefixo.status_code
        == outro_corpo.status_code
        == 403
    )
    assert ausente.json() == {"erro": "assinatura_recusada"}
    assert enviados == []


def test_webhook_com_assinatura_certa_envia_e_nao_grava_telefone() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        app_secret="segredo-teste",
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    aviso = _aviso(
        [{"from": "5511999999999", "type": "text", "text": {"body": "quero uma proposta"}}]
    )
    resposta = _post_assinado(client, "segredo-teste", aviso)
    assert resposta.status_code == 200
    assert resposta.content == b""
    assert enviados == [("5511999999999", TEXTOS["desconhecido"])]
    item = client.get("/v1/encaminhamentos").json()[0]
    assert item["pergunta"] == "quero uma proposta"
    assert "5511999999999" not in str(client.get("/v1/encaminhamentos").json())
    invalido = client.post(
        "/v1/whatsapp/webhook",
        content=b"nao-json",
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256="
            + hmac.new(b"segredo-teste", b"nao-json", hashlib.sha256).hexdigest(),
        },
    )
    assert invalido.status_code == 200
    assert invalido.content == b""
    vazio = client.post(
        "/v1/whatsapp/webhook",
        content=b"",
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256="
            + hmac.new(b"segredo-teste", b"", hashlib.sha256).hexdigest(),
        },
    )
    assert vazio.status_code == 200
    assert vazio.content == b""
    assert len(client.get("/v1/encaminhamentos").json()) == 1


def test_app_de_producao_exige_a_assinatura(monkeypatch) -> None:
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
    monkeypatch.setenv("ATENDEIA_WHATSAPP_APP_SECRET", "segredo-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    aviso = _aviso(
        [
            {
                "from": "5511999999999",
                "type": "text",
                "text": {"body": "quando vence meu contrato?"},
            }
        ]
    )
    cru = json.dumps(aviso).encode()
    recusado = client.post(
        "/v1/whatsapp/webhook",
        content=cru,
        headers={"content-type": "application/json"},
    )
    assert recusado.status_code == 403
    assert recusado.json() == {"erro": "assinatura_recusada"}
    assert chamadas == []
    digest = hmac.new(b"segredo-teste", cru, hashlib.sha256).hexdigest()
    aceite = client.post(
        "/v1/whatsapp/webhook",
        content=cru,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": f"sha256={digest}",
        },
    )
    assert aceite.status_code == 200
    assert chamadas[0][2]["to"] == "5511999999999"
    pergunta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert chamadas[0][2]["text"]["body"] == pergunta.json()["resposta"]
    monkeypatch.setenv("ATENDEIA_WHATSAPP_APP_SECRET", "")
    aberto = TestClient(_app_de_producao())
    sem_assinatura = aberto.post(
        "/v1/whatsapp/webhook",
        content=cru,
        headers={"content-type": "application/json"},
    )
    assert sem_assinatura.status_code == 200
    assert len(chamadas) == 2
