# AtendeIA WhatsApp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Responder um texto de WhatsApp com a mesma resposta da pergunta e gravar o encaminhamento na mesma lista.

**Architecture:** `POST /v1/whatsapp` valida o texto como a pergunta e chama o atendimento que já existe. A fila não muda. Não há envio para a API da Meta.

**Tech Stack:** Python 3.14, FastAPI, pytest, TestClient. Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador, `data/vertice_ti.json`, o fluxo e os cinco campos de `POST /v1/perguntas` não mudam. Nenhum POST devolve `id`.
- `POST /v1/whatsapp` não pede sessão. Com o portão ligado, a lista e o `DELETE` continuam pedindo.
- Texto vazio, só com espaços, ausente ou de outro tipo responde `422` `{ "erro": "pergunta_invalida" }` e não entra na lista.
- A lista continua com `id`, `pergunta`, `fluxo` e `resumo`. O texto do WhatsApp entra no campo `pergunta`.
- Não guardar telefone. Não chamar a API da Meta. Não criar webhook de verificação.
- `GET /health` continua `{ "status": "ok" }` e não lê a base.
- Não alterar as páginas nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: O texto usa a mesma resposta e a mesma lista

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Atendimento.responder`
- Produces: `POST /v1/whatsapp` com corpo `{ "texto": "..." }` e a mesma resposta de `POST /v1/perguntas`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

Não alterar os testes de `POST /v1/perguntas`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_whatsapp_devolve_a_mesma_resposta_da_pergunta -v`

Expected: FAIL because `POST /v1/whatsapp` does not exist (404).

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`, acrescentar um modelo com o campo `texto: str` e o mesmo validador de `PerguntaIn`: vazio ou só espaços levantam `ValueError`. O handler que já existe transforma isso em `422` `{ "erro": "pergunta_invalida" }`.

`POST /v1/whatsapp` chama `atendimento.responder(corpo.texto)` e devolve o dicionário. Não pede sessão. Não lê telefone.

No README, depois do parágrafo de `ATENDEIA_SENHA`, acrescentar:

`POST /v1/whatsapp` recebe `{ "texto": "..." }` e devolve a mesma resposta de `POST /v1/perguntas`. O encaminhamento entra na mesma lista. Esta rota não envia mensagem para fora.

Não alterar o exemplo JSON de três campos. Não alterar as páginas.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The three new tests passed. If a Postgres test is skipped, subir o banco no Ubuntu com `docker compose up -d` na porta 5437 e rodar de novo. Não usar a porta 5432.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py README.md
git commit -m "feat: answer whatsapp texts on the same handoff list"
```
