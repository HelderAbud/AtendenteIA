# AtendeIA WhatsApp Signature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Com o segredo do aplicativo, o aviso da Meta só entra no atendimento quando a assinatura do corpo cru confere.

**Architecture:** `POST /v1/whatsapp/webhook` lê os bytes do corpo. Se `app_secret` estiver preenchido, confere `X-Hub-Signature-256` com HMAC-SHA256 antes do JSON e antes do atendimento. Sem o segredo, o `POST` permanece como no recorte 11. O `GET` do challenge não usa essa assinatura.

**Tech Stack:** Python 3.14, FastAPI, hmac e hashlib da biblioteca padrão, pytest, TestClient. Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- `POST /v1/whatsapp` e `POST /v1/perguntas` continuam com os cinco campos e sem `id`. A falha de envio da rota antiga continua `502` `{ "erro": "envio_falhou" }`.
- A lista continua só com `id`, `pergunta`, `fluxo` e `resumo`. O telefone não é gravado.
- Sem `app_secret`, o `POST /v1/whatsapp/webhook` continua aceitando aviso sem assinatura e devolvendo `200` vazio.
- Com `app_secret`, assinatura ausente ou errada responde `403` `{ "erro": "assinatura_recusada" }`, não chama o atendimento e não envia.
- A conferência usa os bytes crus do corpo, não um JSON regravado. A comparação é `hmac.compare_digest`.
- O `GET /v1/whatsapp/webhook` não exige essa assinatura. A rota não pede sessão.
- Não criar modelo de mensagem pronta nem modelo de linguagem.
- `ATENDEIA_WHATSAPP_APP_SECRET` vazio conta como ausente. Não commitar `.env`.
- Não alterar as páginas nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Recusar aviso com assinatura errada

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-22-atendeia-whatsapp-assinatura.md`

**Interfaces:**
- Consumes: `POST /v1/whatsapp/webhook` e `_texto_do_webhook`
- Produces: `criar_app(..., app_secret: str | None = None)` e o mesmo argumento em `criar_app_de_arquivo`. `_assinatura_confere(segredo: str, corpo: bytes, cabecalho: str) -> bool`

- [ ] **Step 1: Write the failing test**

Em `tests/test_api.py`, importar `hashlib` e `hmac`. Acrescentar:

```python
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
```

`cabecalho=""` significa que o teste não envia o cabeçalho. O helper só acrescenta `x-hub-signature-256` quando `cabecalho` é uma string não vazia.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_webhook_recusa_assinatura_errada -v`

Expected: FAIL with `TypeError`, because `criar_app` ainda não aceita `app_secret`.

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`, importar `hashlib`, `hmac` e `json`. Acrescentar `app_secret: str | None = None` em `criar_app` e em `criar_app_de_arquivo`, e repassar o argumento. Não alterar `_app_de_producao` nesta tarefa.

```python
def _assinatura_confere(segredo: str, corpo: bytes, cabecalho: str) -> bool:
    if not cabecalho.startswith("sha256="):
        return False
    digest = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", cabecalho)
```

No `POST`, ler o corpo uma vez. Não chamar `request.json()` depois disso.

```python
@app.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request) -> Response:
    corpo = await request.body()
    segredo = app_secret or None
    if segredo is not None:
        cabecalho = request.headers.get("x-hub-signature-256", "")
        if not _assinatura_confere(segredo, corpo, cabecalho):
            return JSONResponse(
                status_code=403, content={"erro": "assinatura_recusada"}
            )
    try:
        aviso = json.loads(corpo)
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

O restante do fluxo do recorte 11 permanece. Sem `app_secret`, a conferência não acontece.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes, including the tests that postam sem assinatura. If a Postgres test is skipped, subir o banco no Ubuntu com `docker compose up -d` na porta 5437 e rodar de novo. Não usar a porta 5432.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-22-atendeia-whatsapp-assinatura.md
git commit -m "feat: reject a whatsapp webhook with a bad signature"
```

---

### Task 2: Ler o segredo do aplicativo no ambiente

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `app_secret` de `criar_app_de_arquivo`
- Produces: `_app_de_producao` lê `ATENDEIA_WHATSAPP_APP_SECRET`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

Não exportar `ATENDEIA_DATABASE_URL` no shell do pytest. Não chamar a Graph API real.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_exige_a_assinatura -v`

Expected: FAIL with `200` no primeiro `POST`, because `_app_de_producao` ainda não lê `ATENDEIA_WHATSAPP_APP_SECRET` e o aviso sem assinatura entra.

- [ ] **Step 3: Write minimal implementation**

`_app_de_producao` lê `ATENDEIA_WHATSAPP_APP_SECRET`. String vazia vira ausência. Repassar `app_secret` nos dois ramos de `criar_app_de_arquivo`, junto de `senha`, `session_secret`, `enviar`, `verificar_token` e da URL do Postgres, quando ela existir.

Em `.env.example`, acrescentar:

```text
ATENDEIA_WHATSAPP_APP_SECRET=
```

No README, depois do parágrafo de `GET /v1/whatsapp/webhook`, acrescentar:

Com `ATENDEIA_WHATSAPP_APP_SECRET`, o `POST /v1/whatsapp/webhook` só segue quando `X-Hub-Signature-256` é `sha256=` mais o HMAC-SHA256 do corpo cru. Assinatura ausente ou errada responde `403` com `{ "erro": "assinatura_recusada" }` e não chama o atendimento. Sem o segredo, o `POST` continua como está.

Não colocar segredo de exemplo. Não alterar o exemplo JSON de três campos. Não alterar as páginas. Não alterar a seção final que ainda lista o WhatsApp como fora do recorte.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The new test passed and did not call the real Graph API. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .env.example README.md
git commit -m "feat: read the whatsapp app secret from the environment"
```
