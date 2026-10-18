# AtendeIA página do atendente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Servir em `GET /atendente` uma página que mostra a lista já existente de encaminhamentos.

**Architecture:** A rota lê um HTML estático, no mesmo estilo de `GET /`. O navegador chama `GET /v1/encaminhamentos` e escreve pergunta, fluxo e resumo. A fila, o atendimento e o JSON da resposta não mudam.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx (TestClient).

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador, `data/vertice_ti.json`, a fila e os cinco campos da resposta não mudam.
- `GET /health` continua `200` `{ "status": "ok" }` sem ler a base.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }`.
- `GET /` continua a página da pergunta.
- `GET /atendente` não lê a base e não grava item.
- A página mostra os itens na ordem da lista. Resumo nulo fica vazio. Lista vazia mostra `Nenhum encaminhamento.`
- Sem banco, login, WhatsApp ou modelo de linguagem.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Página do atendente

**Files:**
- Create: `web/atendente.html`
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `GET /v1/encaminhamentos`, que devolve uma lista de `{pergunta, fluxo, resumo}`
- Produces: `GET /atendente` com HTML `200` contendo `id="lista"`, o texto `/v1/encaminhamentos` e o texto `Nenhum encaminhamento.`

- [ ] **Step 1: Write the failing test**

Acrescentar no fim de `tests/test_api.py`:

```python
def test_atendente_serve_a_pagina() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/atendente")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    texto = resposta.text
    assert 'id="lista"' in texto
    assert "/v1/encaminhamentos" in texto
    assert "Nenhum encaminhamento." in texto
```

Não alterar os testes que já existem. Não criar `web/atendente.html` e não editar `app/api.py` ainda.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_atendente_serve_a_pagina -v`

Expected: FAIL with status `404`.

- [ ] **Step 3: Write minimal implementation**

`web/atendente.html`

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>AtendeIA</title>
</head>
<body>
  <h1>Encaminhamentos</h1>
  <div id="lista">Nenhum encaminhamento.</div>
  <script>
    const lista = document.getElementById("lista");
    fetch("/v1/encaminhamentos")
      .then((pedido) => pedido.json())
      .then((itens) => {
        if (!itens.length) {
          lista.textContent = "Nenhum encaminhamento.";
          return;
        }
        lista.textContent = "";
        for (const item of itens) {
          const bloco = document.createElement("article");
          const pergunta = document.createElement("p");
          const fluxo = document.createElement("p");
          const resumo = document.createElement("p");
          pergunta.textContent = item.pergunta;
          fluxo.textContent = item.fluxo;
          resumo.textContent = item.resumo || "";
          bloco.append(pergunta, fluxo, resumo);
          lista.append(bloco);
        }
      });
  </script>
</body>
</html>
```

Em `app/api.py`, ao lado de `PAGINA`, acrescentar:

```python
ATENDENTE = Path(__file__).resolve().parents[1] / "web" / "atendente.html"
```

Dentro de `criar_app`, depois da rota `GET /`, acrescentar:

```python
    @app.get("/atendente", response_class=HTMLResponse)
    def atendente() -> str:
        return ATENDENTE.read_text(encoding="utf-8")
```

Não mudar `GET /health`, `POST /v1/perguntas`, `GET /v1/encaminhamentos`, `criar_app_de_arquivo` nem o `app` do módulo.

No README, na seção `## Subir localmente`, logo depois da frase de `GET /v1/encaminhamentos`, acrescentar:

`GET http://127.0.0.1:8000/atendente` abre a página do atendente.

Não alterar o exemplo JSON de três campos. Não alterar `web/index.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. `GET /health` ainda não lê a base. `GET /atendente` com `BaseQueFalha` não chama `obter`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add web/atendente.html app/api.py tests/test_api.py README.md
git commit -m "feat: show the handoff list on an attendant page"
```
