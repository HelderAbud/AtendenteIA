# AtendeIA WhatsApp Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Meta confirma a URL e a primeira mensagem de texto entra no mesmo atendimento, na mesma lista e no envio que já existe.

**Architecture:** `GET` e `POST` em `/v1/whatsapp/webhook`. O `GET` devolve o challenge só com o token certo. O `POST` procura a primeira mensagem de texto e chama `Atendimento.responder`. O `from` segue para a função `enviar` já existente. O telefone não entra na lista. `POST /v1/whatsapp` permanece.

**Tech Stack:** Python 3.14, FastAPI, pytest, TestClient. Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- `POST /v1/whatsapp` e `POST /v1/perguntas` continuam com os cinco campos e sem `id`.
- A lista continua só com `id`, `pergunta`, `fluxo` e `resumo`. O telefone não é gravado.
- Texto inválido na rota antiga continua `422` `{ "erro": "pergunta_invalida" }`.
- Falha de envio na rota antiga continua `502` `{ "erro": "envio_falhou" }`. No webhook, a falha de envio continua `200` com corpo vazio, e o encaminhamento já gravado permanece.
- O webhook não pede sessão. Não criar modelo de mensagem pronta, modelo de linguagem nem conferência de `X-Hub-Signature-256`.
- O texto enviado é o campo `resposta`. Só a primeira mensagem de texto do aviso é respondida.
- `ATENDEIA_WHATSAPP_VERIFY_TOKEN` vazio conta como ausente. Não commitar `.env`.
- Não alterar as páginas nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Confirmar o challenge da Meta

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-21-atendeia-whatsapp-webhook.md`

**Interfaces:**
- Consumes: `criar_app` e `criar_app_de_arquivo`
- Produces: `criar_app(..., verificar_token: str | None = None)` e o mesmo argumento em `criar_app_de_arquivo`. `GET /v1/whatsapp/webhook`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_webhook_devolve_o_challenge tests/test_api.py::test_webhook_recusa_challenge_errado -v`

Expected: FAIL with `404` because the route does not exist.

- [ ] **Step 3: Write minimal implementation**

Em `criar_app` e `criar_app_de_arquivo`, acrescentar `verificar_token: str | None = None` e repassar esse argumento. String vazia na chamada continua ausente para quem passar `""`: tratar com `verificar_token or None` antes da comparação, para o processo da tarefa 3.

```python
from fastapi import Query

@app.get("/v1/whatsapp/webhook")
def whatsapp_verificacao(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    token = verificar_token or None
    if (
        token
        and hub_mode == "subscribe"
        and hub_verify_token == token
        and hub_challenge.strip()
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    return JSONResponse(status_code=403, content={"erro": "verificacao_recusada"})
```

Não ler a base. Não chamar `enviar`. Não alterar `POST /v1/whatsapp`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The two new tests passed. If a Postgres test is skipped, subir o banco no Ubuntu com `docker compose up -d` na porta 5437 e rodar de novo. Não usar a porta 5432.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-21-atendeia-whatsapp-webhook.md
git commit -m "feat: verify the whatsapp webhook challenge"
```

---

### Task 2: Responder a primeira mensagem de texto

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `Atendimento.responder` e `enviar(destino, texto)` da tarefa do envio
- Produces: `POST /v1/whatsapp/webhook` e `_texto_do_webhook(aviso) -> tuple[str, str] | None`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
    assert status.status_code == 200
    assert branco.status_code == 200
    assert invalido.status_code == 200
    assert vazio.status_code == 200
    assert status.content == branco.content == invalido.content == vazio.content == b""
    assert enviados == []


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_webhook_envia_a_resposta_da_primeira_mensagem -v`

Expected: FAIL with `404` or `422`, because the `POST` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Não usar modelo Pydantic neste `POST`. O handler global transforma erro de validação em `422` `pergunta_invalida`, e a Meta receberia esse erro.

```python
def _texto_do_webhook(aviso: object) -> tuple[str, str] | None:
    if not isinstance(aviso, dict):
        return None
    for entrada in aviso.get("entry") or []:
        if not isinstance(entrada, dict):
            continue
        for mudanca in entrada.get("changes") or []:
            if not isinstance(mudanca, dict):
                continue
            valor = mudanca.get("value")
            if not isinstance(valor, dict):
                continue
            for mensagem in valor.get("messages") or []:
                if not isinstance(mensagem, dict) or mensagem.get("type") != "text":
                    continue
                texto = mensagem.get("text")
                corpo = texto.get("body") if isinstance(texto, dict) else None
                if not isinstance(corpo, str) or not corpo.strip():
                    continue
                origem = mensagem.get("from")
                destino = origem.strip() if isinstance(origem, str) else ""
                return corpo, destino
    return None


@app.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request) -> Response:
    try:
        aviso = await request.json()
    except Exception:
        return Response(status_code=200)
    achado = _texto_do_webhook(aviso)
    if achado is None:
        return Response(status_code=200)
    texto, destino = achado
    resultado = atendimento.responder(texto)
    if enviar is not None and destino:
        try:
            enviar(destino, resultado["resposta"])
        except Exception:
            return Response(status_code=200)
    return Response(status_code=200)
```

A segunda mensagem de texto do mesmo aviso não é lida, porque a função volta na primeira. Sem `from`, a resposta do atendimento ainda acontece e o envio não.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The new webhook tests passed. A rota antiga que falha no envio continua `502`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py
git commit -m "feat: answer the first whatsapp webhook text"
```

---

### Task 3: Ler o token de verificação do ambiente

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `verificar_token` de `criar_app_de_arquivo` e `_texto_do_webhook`
- Produces: `_app_de_producao` lê `ATENDEIA_WHATSAPP_VERIFY_TOKEN`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

O helper fica no próprio teste, não como função nova do módulo, para o token vazio ser outra subida do processo:

```python
def _app_de_producao_sem_verificacao(monkeypatch):
    monkeypatch.setenv("ATENDEIA_WHATSAPP_VERIFY_TOKEN", "")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    return _app_de_producao()
```

Colocar esse helper acima de `test_app_de_producao_recebe_o_webhook_e_envia`. Não exportar `ATENDEIA_DATABASE_URL` no shell do pytest.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_confirma_o_webhook -v`

Expected: FAIL with `403`, because `_app_de_producao` ainda não lê `ATENDEIA_WHATSAPP_VERIFY_TOKEN`.

- [ ] **Step 3: Write minimal implementation**

`_app_de_producao` lê `ATENDEIA_WHATSAPP_VERIFY_TOKEN`. String vazia vira ausência. Repassar `verificar_token` nos dois ramos de `criar_app_de_arquivo`, junto de `senha`, `session_secret`, `enviar` e da URL do Postgres, quando ela existir.

Em `.env.example`, acrescentar:

```text
ATENDEIA_WHATSAPP_VERIFY_TOKEN=
```

No README, depois do parágrafo de `POST /v1/whatsapp`, acrescentar:

`GET /v1/whatsapp/webhook` confirma a Meta quando `hub.mode` é `subscribe` e `hub.verify_token` é igual a `ATENDEIA_WHATSAPP_VERIFY_TOKEN`. A resposta é o `hub.challenge` em texto. `POST` nessa mesma rota lê a primeira mensagem de texto do aviso, usa o mesmo atendimento e devolve `200` vazio. O número segue no envio e não entra na lista. Sem o token de verificação, o `GET` responde `403`.

Não colocar token de exemplo. Não alterar o exemplo JSON de três campos. Não alterar as páginas. Não alterar a seção final que ainda lista o WhatsApp como fora do recorte.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The new tests passed and did not call the real Graph API. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .env.example README.md
git commit -m "feat: read the whatsapp verify token from the environment"
```
