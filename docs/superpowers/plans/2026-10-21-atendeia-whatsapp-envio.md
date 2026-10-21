# AtendeIA WhatsApp Send Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enviar a mesma resposta do atendimento para o número que escreveu no WhatsApp.

**Architecture:** `POST /v1/whatsapp` continua chamando o atendimento. Se receber `de` e uma função de envio, manda a `resposta` para esse destino. O telefone não entra na lista. Sem token, não há chamada para fora.

**Tech Stack:** Python 3.14, FastAPI, httpx, pytest, TestClient. Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- Os cinco campos de `POST /v1/perguntas` e de `POST /v1/whatsapp` não mudam. Nenhum dos dois devolve `id`.
- A lista continua só com `id`, `pergunta`, `fluxo` e `resumo`. O telefone não é gravado.
- Texto inválido continua `422` `{ "erro": "pergunta_invalida" }`, fora da lista e sem envio.
- Sem `de`, ou sem função de envio, a rota só devolve o JSON.
- Falha no envio responde `502` `{ "erro": "envio_falhou" }`. O item que a base já pediu para a lista permanece.
- A rota não pede sessão. Não criar webhook de verificação nem modelo de mensagem pronta.
- O texto enviado é o campo `resposta`. A URL é `https://graph.facebook.com/v26.0/{phone_id}/messages`.
- Token e identificador do número ficam no ambiente. Vazio conta como ausente. Não commitar `.env`.
- Não alterar as páginas nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Enviar a resposta quando há destino

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `Atendimento.responder`
- Produces: `criar_app(..., enviar=None)` e `criar_app_de_arquivo(..., enviar=None)`. `enviar(destino, texto)` recebe o `de` e a `resposta`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

Não alterar os testes que postam só `texto`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_whatsapp_envia_a_resposta_para_quem_escreveu -v`

Expected: FAIL because `criar_app_de_arquivo` does not accept `enviar`.

- [ ] **Step 3: Write minimal implementation**

Acrescentar `enviar=None` no fim de `criar_app` e de `criar_app_de_arquivo`. Repassar até `criar_app`.

Em `TextoIn`, `de` é `str | None = None`.

Depois de `responder`, se `enviar` existir e `de` tiver texto além de espaços, chamar `enviar(de.strip(), resposta["resposta"])`. Se essa chamada levantar exceção, responder `502` `{ "erro": "envio_falhou" }`. O JSON de sucesso continua sendo o dicionário do atendimento.

Não gravar `de` na fila. Não proteger a rota com sessão.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_whatsapp_envia_a_resposta_para_quem_escreveu tests/test_api.py::test_whatsapp_sem_destino_nao_envia tests/test_api.py::test_whatsapp_invalido_nao_envia tests/test_api.py::test_falha_no_envio_responde_502_e_guarda_o_encaminhamento tests/test_api.py::test_whatsapp_devolve_a_mesma_resposta_da_pergunta -q`

Expected: those tests pass. The old WhatsApp test still posts only `texto`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py
git commit -m "feat: send the answer back to the whatsapp sender"
```

---

### Task 2: O processo lê o token

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `httpx`, `ATENDEIA_WHATSAPP_TOKEN`, `ATENDEIA_WHATSAPP_PHONE_ID`
- Produces: `_app_de_producao` monta o envio quando as duas variáveis vêm preenchidas

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_envia_pela_cloud_api -v`

Expected: FAIL because no outbound call is made, so `chamadas[0]` does not exist.

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`, importar `httpx`. Criar a função que faz `httpx.post` para `https://graph.facebook.com/v26.0/{phone_id}/messages`, com `Authorization: Bearer {token}`, `timeout=10` e o JSON acima. `raise_for_status()` fica dentro dessa função.

`_app_de_producao` lê as duas variáveis. String vazia vira ausência. Com as duas, repassa `enviar` junto de `senha`, `session_secret` e da URL do Postgres, quando ela existir. Sem uma delas, `enviar` fica ausente.

Em `.env.example`, acrescentar linhas vazias:

```text
ATENDEIA_WHATSAPP_TOKEN=
ATENDEIA_WHATSAPP_PHONE_ID=
```

No README, trocar a frase que diz que a rota não envia mensagem para fora por:

Com `de`, `ATENDEIA_WHATSAPP_TOKEN` e `ATENDEIA_WHATSAPP_PHONE_ID`, a mesma `resposta` segue para esse número. Sem um desses valores, a rota só devolve o JSON.

Não colocar token de exemplo. Não alterar o exemplo JSON de três campos. Não alterar as páginas.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu com `docker compose up -d` na porta 5437 e rodar de novo. Não usar a porta 5432.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .env.example README.md
git commit -m "feat: send whatsapp replies through the cloud api"
```
