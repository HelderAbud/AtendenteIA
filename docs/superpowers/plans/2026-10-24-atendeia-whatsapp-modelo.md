# AtendeIA WhatsApp Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Com o nome do modelo preenchido, a mesma resposta segue como parâmetro desse modelo. Sem o nome, o envio continua em texto livre.

**Architecture:** `_criar_enviar_whatsapp` ganha `modelo`. A URL, o token e o destino não mudam. O processo lê `ATENDEIA_WHATSAPP_TEMPLATE` e repassa o nome. As duas rotas que já enviam usam essa função.

**Tech Stack:** Python 3.14, httpx, pytest. Nenhuma dependência nova. Graph API `v26.0`. Idioma do modelo: `pt_BR`.

## Global Constraints

- O texto enviado é a `resposta`, não o resumo.
- Sem modelo, o JSON continua `type` `text` e `text.body`.
- Com modelo, o JSON é `type` `template`, idioma `pt_BR`, um parâmetro `text` com a `resposta`.
- String vazia conta como modelo ausente.
- A URL continua `https://graph.facebook.com/v26.0/{phone_id}/messages`, com `Authorization: Bearer` e `timeout` 10.
- Falha de envio na rota antiga continua `502`. No webhook, continua `200` vazio.
- O telefone não entra na lista. Não há modelo de linguagem.
- Não alterar as páginas nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Enviar pelo modelo quando o nome existe

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-24-atendeia-whatsapp-modelo.md`

**Interfaces:**
- Consumes: `httpx.post`
- Produces: `_criar_enviar_whatsapp(token, phone_id, modelo=None)`. `modelo` vazio não muda o texto livre

- [x] **Step 1: Write the failing test**

Em `tests/test_api.py`, importar `_criar_enviar_whatsapp`. Acrescentar:

```python
def _post_falso(chamadas):
    def post(url, headers, json, timeout):
        chamadas.append((url, headers, json, timeout))

        class Resposta:
            def raise_for_status(self):
                return None

        return Resposta()

    return post


def test_envio_com_modelo_manda_a_resposta_no_parametro(monkeypatch) -> None:
    chamadas = []
    monkeypatch.setattr("app.api.httpx.post", _post_falso(chamadas))
    enviar = _criar_enviar_whatsapp("token-teste", "1099", modelo="aviso_contrato")
    enviar("5511999999999", "O contrato vale 12 meses.")
    assert chamadas[0][0] == "https://graph.facebook.com/v26.0/1099/messages"
    assert chamadas[0][1]["Authorization"] == "Bearer token-teste"
    assert chamadas[0][3] == 10
    assert chamadas[0][2] == {
        "messaging_product": "whatsapp",
        "to": "5511999999999",
        "type": "template",
        "template": {
            "name": "aviso_contrato",
            "language": {"code": "pt_BR"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": "O contrato vale 12 meses."}
                    ],
                }
            ],
        },
    }


def test_envio_sem_modelo_continua_texto_livre(monkeypatch) -> None:
    chamadas = []
    monkeypatch.setattr("app.api.httpx.post", _post_falso(chamadas))
    livre = _criar_enviar_whatsapp("token-teste", "1099")
    livre("5511999999999", "texto livre")
    vazio = _criar_enviar_whatsapp("token-teste", "1099", modelo="")
    vazio("5511999999999", "texto livre")
    assert chamadas[0][2]["type"] == "text"
    assert chamadas[0][2]["text"] == {"body": "texto livre"}
    assert chamadas[1][2]["type"] == "text"
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_envio_com_modelo_manda_a_resposta_no_parametro -v`

Expected: FAIL with `TypeError`, because `_criar_enviar_whatsapp` ainda não aceita `modelo`.

- [x] **Step 3: Write minimal implementation**

```python
def _criar_enviar_whatsapp(token: str, phone_id: str, modelo: str | None = None):
    def enviar(destino: str, texto: str) -> None:
        nome = modelo or None
        if nome:
            corpo = {
                "messaging_product": "whatsapp",
                "to": destino,
                "type": "template",
                "template": {
                    "name": nome,
                    "language": {"code": "pt_BR"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": texto}],
                        }
                    ],
                },
            }
        else:
            corpo = {
                "messaging_product": "whatsapp",
                "to": destino,
                "type": "text",
                "text": {"body": texto},
            }
        resposta = httpx.post(
            f"https://graph.facebook.com/v26.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json=corpo,
            timeout=10,
        )
        resposta.raise_for_status()

    return enviar
```

Não alterar `_app_de_producao` nesta tarefa.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The existing production test still sees `type` `text`. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-24-atendeia-whatsapp-modelo.md
git commit -m "feat: send whatsapp replies with a message template"
```

---

### Task 2: Ler o nome do modelo no ambiente

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `_criar_enviar_whatsapp(..., modelo=None)`
- Produces: `_app_de_producao` lê `ATENDEIA_WHATSAPP_TEMPLATE`

- [x] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_app_de_producao_envia_pelo_modelo(monkeypatch) -> None:
    chamadas = []
    monkeypatch.setattr("app.api.httpx.post", _post_falso(chamadas))
    monkeypatch.setenv("ATENDEIA_WHATSAPP_TOKEN", "token-teste")
    monkeypatch.setenv("ATENDEIA_WHATSAPP_PHONE_ID", "1099")
    monkeypatch.setenv("ATENDEIA_WHATSAPP_TEMPLATE", "aviso_contrato")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    texto = "quando vence meu contrato?"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    whatsapp = client.post(
        "/v1/whatsapp",
        json={"texto": texto, "de": "5511999999999"},
    )
    assert whatsapp.json() == pergunta.json()
    assert chamadas[0][2]["type"] == "template"
    assert chamadas[0][2]["template"]["name"] == "aviso_contrato"
    assert chamadas[0][2]["template"]["language"] == {"code": "pt_BR"}
    assert chamadas[0][2]["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": pergunta.json()["resposta"]}
    ]
    assert "5511999999999" not in str(client.get("/v1/encaminhamentos").json())
    monkeypatch.setenv("ATENDEIA_WHATSAPP_TEMPLATE", "")
    aberto = TestClient(_app_de_producao())
    aberto.post("/v1/whatsapp", json={"texto": texto, "de": "5511888888888"})
    assert chamadas[1][2]["type"] == "text"
    assert chamadas[1][2]["text"]["body"] == pergunta.json()["resposta"]
```

Não exportar `ATENDEIA_DATABASE_URL`. Não chamar a Graph API real. A prova usa o webhook, porque `POST /v1/whatsapp` não envia.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_envia_pelo_modelo -v`

Expected: FAIL because `chamadas[0][2]["type"]` ainda é `text`.

- [x] **Step 3: Write minimal implementation**

`_app_de_producao` lê `ATENDEIA_WHATSAPP_TEMPLATE`. String vazia vira ausência. Passar `modelo` para `_criar_enviar_whatsapp` só quando o token e o identificador do número também existem.

Em `.env.example`, acrescentar:

```text
ATENDEIA_WHATSAPP_TEMPLATE=
```

No README, depois do parágrafo de `ATENDEIA_WHATSAPP_APP_SECRET`, acrescentar:

Com `ATENDEIA_WHATSAPP_TEMPLATE`, a mesma `resposta` segue como parâmetro desse modelo, em `pt_BR`. Sem essa variável, o envio continua em texto livre.

Na seção `Fora deste recorte`, trocar a frase por:

```text
Modelo de linguagem, PDF e planilha.
```

Não colocar nome de modelo de exemplo. Não alterar o exemplo JSON de três campos. Não alterar as páginas.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The new test passed and did not call the real Graph API. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .env.example README.md
git commit -m "feat: read the whatsapp template name from the environment"
```
