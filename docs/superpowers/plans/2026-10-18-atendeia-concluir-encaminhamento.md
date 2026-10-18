# AtendeIA concluir encaminhamento Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar um `id` a cada encaminhamento e removê-lo com `DELETE /v1/encaminhamentos/{id}`, também pelo botão da página do atendente.

**Architecture:** A fila numera e remove. O atendimento só repassa. A API traduz id ausente em 404. A página chama o DELETE e tira o bloco da tela. Não há banco nem WhatsApp neste plano.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx (TestClient).

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador, `data/vertice_ti.json`, o fluxo e os cinco campos de `POST /v1/perguntas` não mudam. O POST não devolve `id`.
- `GET /health` continua `200` `{ "status": "ok" }` sem ler a base.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }` e não entra na lista.
- `id` começa em 1, soma 1 a cada registro e não é reutilizado no mesmo processo.
- Item da lista: `id`, `pergunta`, `fluxo`, `resumo`.
- `DELETE /v1/encaminhamentos/{id}` devolve `204` sem corpo quando remove. Id inteiro ausente devolve `404` `{ "erro": "encaminhamento_inexistente" }`.
- A lista continua em memória e some ao reiniciar.
- Sem banco, login, WhatsApp ou modelo de linguagem.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Id e remoção na fila

**Files:**
- Modify: `app/fila.py`
- Modify: `tests/test_fila.py`
- Modify: `tests/test_atendimento.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: nada
- Produces: `Fila.registrar(pergunta: str, fluxo: str, resumo: str | None) -> None`, `Fila.listar() -> list[dict]` com `id`, e `Fila.remover(item_id: int) -> None` que levanta `KeyError` se o id não existe

- [ ] **Step 1: Write the failing test**

Substituir `tests/test_fila.py` por:

```python
import pytest

from app.fila import Fila


def test_lista_comeca_vazia() -> None:
    assert Fila().listar() == []


def test_registra_na_ordem_com_id_e_resumo_nulo() -> None:
    fila = Fila()
    fila.registrar("quero uma proposta", "venda", "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.")
    fila.registrar("qualquer coisa", "suporte", None)
    assert fila.listar() == [
        {
            "id": 1,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {"id": 2, "pergunta": "qualquer coisa", "fluxo": "suporte", "resumo": None},
    ]


def test_remover_nao_reusa_o_id() -> None:
    fila = Fila()
    fila.registrar("primeira", "venda", "resumo")
    fila.registrar("segunda", "desconhecido", "resumo 2")
    fila.remover(1)
    fila.registrar("terceira", "venda", "resumo 3")
    assert fila.listar() == [
        {"id": 2, "pergunta": "segunda", "fluxo": "desconhecido", "resumo": "resumo 2"},
        {"id": 3, "pergunta": "terceira", "fluxo": "venda", "resumo": "resumo 3"},
    ]


def test_id_ausente_levanta_key_error() -> None:
    fila = Fila()
    with pytest.raises(KeyError):
        fila.remover(1)
```

Em `tests/test_atendimento.py`, a lista de `test_flag_verdadeira_entra_na_ordem` ganha `"id": 1` no primeiro item e `"id": 2` no segundo. Em `tests/test_api.py`, a lista de `test_so_a_flag_verdadeira_entra_na_lista` ganha os mesmos ids. Não criar `concluir` nesta tarefa.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fila.py::test_registra_na_ordem_com_id_e_resumo_nulo -v`

Expected: FAIL because the item has no `id`.

- [ ] **Step 3: Write minimal implementation**

`app/fila.py`

```python
class Fila:
    def __init__(self) -> None:
        self._itens: list[dict] = []
        self._proximo_id = 1

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        self._itens.append(
            {
                "id": self._proximo_id,
                "pergunta": pergunta,
                "fluxo": fluxo,
                "resumo": resumo,
            }
        )
        self._proximo_id += 1

    def listar(self) -> list[dict]:
        return list(self._itens)

    def remover(self, item_id: int) -> None:
        for indice, item in enumerate(self._itens):
            if item["id"] == item_id:
                del self._itens[indice]
                return
        raise KeyError(item_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. The listed items now include `id`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/fila.py tests/test_fila.py tests/test_atendimento.py tests/test_api.py
git commit -m "feat: number handoffs and remove one by id"
```

---

### Task 2: Atendimento repassa o id

**Files:**
- Modify: `app/atendimento.py`
- Modify: `tests/test_atendimento.py`

**Interfaces:**
- Consumes: `Fila.registrar`, `Fila.listar` e `Fila.remover`
- Produces: `Atendimento.encaminhamentos() -> list[dict]` com `id`, e `Atendimento.concluir(item_id: int) -> None` que deixa o `KeyError` subir

O construtor continua `Atendimento(classificar_fn, base)`. `responder` continua devolvendo só os cinco campos.

- [ ] **Step 1: Write the failing test**

Em `tests/test_atendimento.py`, acrescentar:

```python
def test_concluir_remove_so_o_id() -> None:
    atendimento = Atendimento(classificar, BaseSempreHumano())
    atendimento.responder("quando vence meu contrato?")
    atendimento.responder("quero uma proposta")
    atendimento.concluir(1)
    assert atendimento.encaminhamentos() == [
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        }
    ]
```

Não alterar `test_flag_verdadeira_entra_na_ordem`. A tarefa 1 já colocou os ids nessa asserção.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py::test_concluir_remove_so_o_id -v`

Expected: FAIL because `Atendimento` has no `concluir`.

- [ ] **Step 3: Write minimal implementation**

Em `app/atendimento.py`, acrescentar:

```python
    def concluir(self, item_id: int) -> None:
        self._fila.remover(item_id)
```

`encaminhamentos` continua devolvendo `self._fila.listar()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/atendimento.py tests/test_atendimento.py
git commit -m "feat: conclude one handoff by id"
```

---

### Task 3: DELETE e botão Concluir

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `web/atendente.html`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Atendimento.concluir(item_id: int) -> None`, que deixa `KeyError` subir
- Produces: `DELETE /v1/encaminhamentos/{item_id}` com `204` ou `404` `{ "erro": "encaminhamento_inexistente" }`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
```

Em `test_atendente_serve_a_pagina`, acrescentar:

```python
    assert "Concluir" in texto
    assert "DELETE" in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_delete_de_id_ausente_nao_le_a_base -v`

Expected: FAIL with status `404` whose body is not `encaminhamento_inexistente`, or status `405`.

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`, importar `Response` de `fastapi`. Dentro de `criar_app`, depois de `GET /v1/encaminhamentos`:

```python
    @app.delete("/v1/encaminhamentos/{item_id}")
    def concluir_encaminhamento(item_id: int) -> Response:
        try:
            atendimento.concluir(item_id)
        except KeyError:
            return JSONResponse(
                status_code=404, content={"erro": "encaminhamento_inexistente"}
            )
        return Response(status_code=204)
```

Substituir o laço de `web/atendente.html` para criar o botão e o listener:

```javascript
        for (const item of itens) {
          const bloco = document.createElement("article");
          const pergunta = document.createElement("p");
          const fluxo = document.createElement("p");
          const resumo = document.createElement("p");
          const botao = document.createElement("button");
          pergunta.textContent = item.pergunta;
          fluxo.textContent = item.fluxo;
          resumo.textContent = item.resumo || "";
          botao.textContent = "Concluir";
          botao.addEventListener("click", async () => {
            const pedido = await fetch("/v1/encaminhamentos/" + item.id, { method: "DELETE" });
            if (pedido.status !== 204) {
              return;
            }
            bloco.remove();
            if (!lista.querySelector("article")) {
              lista.textContent = "Nenhum encaminhamento.";
            }
          });
          bloco.append(pergunta, fluxo, resumo, botao);
          lista.append(bloco);
        }
```

No README, depois da frase de `GET /atendente`, acrescentar:

`DELETE http://127.0.0.1:8000/v1/encaminhamentos/{id}` tira esse item da lista. Id ausente devolve 404.

Não alterar o exemplo JSON de três campos. Não alterar `web/index.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. O DELETE com `BaseQueFalha` não chama `obter`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py web/atendente.html README.md
git commit -m "feat: remove one handoff from the attendant page"
```
