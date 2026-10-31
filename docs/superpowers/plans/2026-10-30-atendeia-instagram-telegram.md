# AtendeIA Instagram e Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instagram e Telegram devolvem a mesma resposta de uma pergunta e, quando a base pede humano, entram na mesma lista. Nenhuma das duas rotas envia mensagem.

**Architecture:** Duas rotas finas em `app/api.py` chamam `atendimento.responder`. O corpo aceita só `texto`, com as mesmas regras de `TextoIn`. Não há cliente novo nem variável de ambiente.

**Tech Stack:** Python 3.14, FastAPI, pytest. Nenhuma dependência nova.

## Global Constraints

- O corpo é `{ "texto": "..." }`. A resposta tem os cinco campos, sem `id`.
- Texto ausente, em branco, de outro tipo ou com mais de 500 caracteres é `422` `{ "erro": "pergunta_invalida" }` e não entra na lista.
- Campo extra é ignorado e não é guardado. A rota não chama `enviar`.
- A lista é a mesma de `POST /v1/perguntas`. O `id` segue a ordem de chegada.
- As rotas não pedem sessão.
- Não criar webhook, envio, página nem variável de ambiente.
- Não alterar o classificador, `data/vertice_ti.json`, as páginas nem o exemplo JSON de três campos.
- O rodapé do README permanece.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Responder um texto do Instagram

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-30-atendeia-instagram-telegram.md`

**Interfaces:**
- Consumes: `atendimento.responder`
- Produces: `POST /v1/instagram`

- [x] **Step 1: Write the failing test**

Em `tests/test_api.py`, acrescentar:

```python
def test_instagram_responde_como_a_pergunta_e_nao_envia() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    texto = "quero uma proposta"
    pergunta = client.post("/v1/perguntas", json={"pergunta": texto})
    instagram = client.post(
        "/v1/instagram",
        json={"texto": texto, "de": "usuario-instagram"},
    )
    assert instagram.status_code == 200
    assert instagram.json() == pergunta.json()
    assert enviados == []
    lista = client.get("/v1/encaminhamentos").json()
    assert [item["pergunta"] for item in lista] == [texto, texto]
    assert [item["id"] for item in lista] == [1, 2]
    assert "usuario-instagram" not in str(lista)


def test_instagram_invalido_nao_entra_na_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    vazio = client.post("/v1/instagram", json={"texto": "   "})
    longo = client.post("/v1/instagram", json={"texto": "a" * 501})
    assert vazio.status_code == 422
    assert vazio.json() == {"erro": "pergunta_invalida"}
    assert longo.status_code == 422
    assert longo.json() == {"erro": "pergunta_invalida"}
    assert client.get("/v1/encaminhamentos").json() == []
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_instagram_responde_como_a_pergunta_e_nao_envia -v`

Expected: FAIL with `404`, because `POST /v1/instagram` ainda não existe.

- [x] **Step 3: Write minimal implementation**

Em `app/api.py`, acrescentar `POST /v1/instagram`. O corpo usa a mesma validação de `texto` que `TextoIn`: ausente, em branco ou com mais de 500 caracteres continua `422` `pergunta_invalida`. A rota devolve `atendimento.responder(corpo.texto)` e não chama `enviar`.

No README, depois do parágrafo de `POST /v1/whatsapp`, acrescentar:

`POST /v1/instagram` recebe `{ "texto": "..." }` e devolve a mesma resposta de `POST /v1/perguntas`. O encaminhamento entra na mesma lista. Esta rota não envia mensagem.

Não alterar o WhatsApp, o rodapé nem o exemplo JSON de três campos.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [x] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py README.md docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-30-atendeia-instagram-telegram.md
git commit -m "feat: answer instagram texts on the same handoff list"
```

---

### Task 2: Responder um texto do Telegram

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `atendimento.responder`
- Produces: `POST /v1/telegram`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_telegram_entra_na_mesma_lista_e_nao_envia() -> None:
    enviados = []
    app = criar_app_de_arquivo(
        ARQUIVO,
        enviar=lambda destino, texto: enviados.append((destino, texto)),
    )
    client = TestClient(app)
    client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    client.post("/v1/instagram", json={"texto": "quero falar sobre o clima"})
    telegram = client.post(
        "/v1/telegram",
        json={"texto": "quero uma proposta", "de": "usuario-telegram"},
    )
    assert telegram.status_code == 200
    assert telegram.json()["fluxo"] == "venda"
    assert enviados == []
    lista = client.get("/v1/encaminhamentos").json()
    assert [item["id"] for item in lista] == [1, 2, 3]
    assert [item["pergunta"] for item in lista] == [
        "quero uma proposta",
        "quero falar sobre o clima",
        "quero uma proposta",
    ]
    assert "usuario-telegram" not in str(lista)


def test_telegram_invalido_nao_entra_na_lista() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    ausente = client.post("/v1/telegram", json={})
    assert ausente.status_code == 422
    assert ausente.json() == {"erro": "pergunta_invalida"}
    assert client.get("/v1/encaminhamentos").json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_telegram_entra_na_mesma_lista_e_nao_envia -v`

Expected: FAIL with `404`, because `POST /v1/telegram` ainda não existe.

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`, acrescentar `POST /v1/telegram` com as mesmas regras da rota do Instagram. Não chama `enviar`.

No README, no parágrafo do Instagram, incluir o Telegram na mesma frase: as duas rotas recebem `{ "texto": "..." }`, devolvem a mesma resposta e não enviam mensagem.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py README.md
git commit -m "feat: answer telegram texts on the same handoff list"
```
