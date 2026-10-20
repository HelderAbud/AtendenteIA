# AtendeIA Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exigir sessão na página do atendente, na lista e no DELETE quando a senha e o segredo da sessão estão configurados.

**Architecture:** A fábrica recebe `senha` e `session_secret`. Os dois ligados ativam o portão e o cookie assinado do Starlette. Sem um deles, as rotas atuais ficam abertas. Não há tabela de usuário. WhatsApp fica fora.

**Tech Stack:** Python 3.14, FastAPI, Starlette SessionMiddleware, pytest, TestClient. Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador, `data/vertice_ti.json`, o fluxo e os cinco campos de `POST /v1/perguntas` não mudam. O POST não devolve `id`.
- `GET /`, `POST /v1/perguntas` e `GET /health` não pedem sessão. `GET /health` continua `{ "status": "ok" }` e não consulta o Postgres nem a base.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }`.
- Sem senha ou sem segredo, a lista, o `DELETE` e `GET /atendente` continuam como hoje. Não alterar os testes que não passam senha.
- Com os dois valores, lista e `DELETE` sem sessão devolvem `401` `{ "erro": "sessao_ausente" }` e não leem a base. `GET /atendente` sem sessão devolve `303` para `/login`.
- Com sessão, `DELETE` de id ausente continua `404` `{ "erro": "encaminhamento_inexistente" }` e não lê a base.
- A senha não entra no cookie, no Git nem numa tabela. Um atendente só. Sem cadastro e sem logout neste recorte.
- Não alterar `web/atendente.html` nem o exemplo JSON de três campos.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Entrar com a senha

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `starlette.middleware.sessions.SessionMiddleware`
- Produces: `criar_app(atendimento, senha=None, session_secret=None)` e `criar_app_de_arquivo(caminho, banco=None, postgres_url=None, senha=None, session_secret=None)`. O portão liga só quando `senha` e `session_secret` vêm preenchidos. `GET /login` e `POST /login` existem nesse caso

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

`BaseQueFalha` já existe neste arquivo. Não alterar os testes atuais.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_senha_certa_abre_sessao_e_senha_errada_nao -v`

Expected: FAIL because `criar_app` does not accept `senha`.

- [ ] **Step 3: Write minimal implementation**

Em `criar_app` e `criar_app_de_arquivo`, acrescentar `senha=None` e `session_secret=None` no fim. Repassar os dois até `criar_app`.

Quando os dois vierem preenchidos, registrar o `SessionMiddleware` com `secret_key=session_secret` e publicar:

- `GET /login`: HTML com `<form method="post" action="/login">`, `<input name="senha" type="password">` e um botão `Entrar`.
- `POST /login`: ler o campo `senha` do formulário. Se for igual à senha configurada, gravar `request.session["atendente"] = True` e responder `RedirectResponse("/atendente", status_code=303)`. Caso contrário, responder `401` com o mesmo formulário e o texto `Senha recusada.`.

`GET /atendente`, quando o portão está ligado e a sessão não tem `atendente`, responde `RedirectResponse("/login", status_code=303)`. Com sessão, continua devolvendo `web/atendente.html`. Sem portão, `GET /atendente` continua como está.

Ainda não proteger a lista nem o `DELETE` nesta tarefa.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_senha_certa_abre_sessao_e_senha_errada_nao tests/test_api.py::test_atendente_serve_a_pagina -q`

Expected: both pass. The attendant page test stays open because it does not pass a password.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py
git commit -m "feat: open an attendant session from a password"
```

---

### Task 2: Lista e DELETE exigem a sessão

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: a sessão `atendente` da tarefa 1
- Produces: com o portão ligado, `GET /v1/encaminhamentos` e `DELETE /v1/encaminhamentos/{id}` sem sessão devolvem `401` `{ "erro": "sessao_ausente" }`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

Não alterar `test_delete_remove_o_item_e_nao_reusa_o_id` nem `test_delete_de_id_ausente_nao_le_a_base`. Eles continuam sem senha.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_lista_e_delete_sem_sessao_nao_mexem_na_fila -v`

Expected: FAIL because the list still returns 200 without a session.

- [ ] **Step 3: Write minimal implementation**

Com o portão ligado, `GET /v1/encaminhamentos` e `DELETE` sem `request.session.get("atendente")` devolvem `401` `{ "erro": "sessao_ausente" }` antes de chamar a fila e antes de ler a base. Com a sessão, o comportamento atual permanece. Sem portão, as duas rotas permanecem abertas.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py -q`

Expected: the file passes, including the tests that delete without a password.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py
git commit -m "feat: require a session to list and finish handoffs"
```

---

### Task 3: O processo lê as variáveis

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: `ATENDEIA_SENHA` e `ATENDEIA_SESSION_SECRET`
- Produces: `_app_de_producao` liga o portão quando as duas variáveis vêm preenchidas. String vazia deixa o portão desligado

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_app_de_producao_liga_o_portao_com_as_duas_variaveis(monkeypatch) -> None:
    monkeypatch.setenv("ATENDEIA_SENHA", "senha-teste")
    monkeypatch.setenv("ATENDEIA_SESSION_SECRET", "segredo-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    app = _app_de_producao()
    client = TestClient(app, follow_redirects=False)
    assert client.get("/atendente").status_code == 303
    assert client.get("/atendente").headers["location"] == "/login"
```

Importar `_app_de_producao` de `app.api`. Não exportar `ATENDEIA_DATABASE_URL` neste teste.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_liga_o_portao_com_as_duas_variaveis -v`

Expected: FAIL because `_app_de_producao` does not read the password variables, so `/atendente` stays 200.

- [ ] **Step 3: Write minimal implementation**

Em `_app_de_producao`, ler as duas variáveis. String vazia vira ausência. Repassar `senha` e `session_secret` para `criar_app_de_arquivo` junto da URL do Postgres, quando ela existir.

Em `.env.example`, acrescentar linhas vazias:

```text
ATENDEIA_SENHA=
ATENDEIA_SESSION_SECRET=
```

No README, depois do parágrafo de `ATENDEIA_DATABASE_URL`, acrescentar:

Com `ATENDEIA_SENHA` e `ATENDEIA_SESSION_SECRET`, a página do atendente, a lista e o `DELETE` pedem entrada em `/login`. Sem uma das duas, essas rotas continuam abertas.

Não colocar senha de exemplo. Não alterar o exemplo JSON de três campos. Não alterar `web/atendente.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .env.example README.md
git commit -m "feat: read the attendant password from the environment"
```
