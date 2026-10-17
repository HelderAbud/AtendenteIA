# AtendeIA encaminhamentos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guardar em memória as perguntas cuja flag `encaminhar_humano` é verdadeira e devolvê-las em `GET /v1/encaminhamentos`.

**Architecture:** Uma fila pura guarda pergunta, fluxo e resumo. O atendimento registra o item depois de montar a resposta, só quando a flag copiada da base é verdadeira. A API expõe a lista do mesmo atendimento. A página, o classificador e o JSON da Vértice TI não mudam.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx (TestClient).

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador de tema e `data/vertice_ti.json` não mudam.
- `GET /health` continua `200` `{ "status": "ok" }` sem ler a base.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }` e não entra na lista.
- Arquivo ausente ou inválido continua impedindo a subida.
- A resposta de `POST /v1/perguntas` continua com os cinco campos do recorte 2.
- A lista só recebe item quando `encaminhar_humano` é verdadeiro. Flag falsa não entra.
- Cada item tem só `pergunta`, `fluxo` e `resumo`. A pergunta é o texto recebido.
- A ordem é a ordem de chegada. Lista vazia é `[]`.
- A lista vive no processo. Reiniciar zera. Dois apps não compartilham a lista.
- `GET /` não muda.
- Sem banco, login, WhatsApp ou modelo de linguagem.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Fila em memória

**Files:**
- Create: `app/fila.py`
- Test: `tests/test_fila.py`

**Interfaces:**
- Consumes: nada
- Produces: `Fila.registrar(pergunta: str, fluxo: str, resumo: str | None) -> None` e `Fila.listar() -> list[dict]`

- [ ] **Step 1: Write the failing test**

`tests/test_fila.py`

```python
from app.fila import Fila


def test_lista_comeca_vazia() -> None:
    assert Fila().listar() == []


def test_registra_na_ordem_e_guarda_resumo_nulo() -> None:
    fila = Fila()
    fila.registrar("quero uma proposta", "venda", "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.")
    fila.registrar("qualquer coisa", "suporte", None)
    assert fila.listar() == [
        {
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {"pergunta": "qualquer coisa", "fluxo": "suporte", "resumo": None},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fila.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.fila'`.

- [ ] **Step 3: Write minimal implementation**

`app/fila.py`

```python
class Fila:
    def __init__(self) -> None:
        self._itens: list[dict] = []

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        self._itens.append(
            {"pergunta": pergunta, "fluxo": fluxo, "resumo": resumo}
        )

    def listar(self) -> list[dict]:
        return list(self._itens)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fila.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/fila.py tests/test_fila.py
git commit -m "feat: keep an in-memory handoff queue"
```

---

### Task 2: Atendimento registra a flag verdadeira

**Files:**
- Modify: `app/atendimento.py`
- Modify: `tests/test_atendimento.py`

**Interfaces:**
- Consumes: `Fila.registrar` e `Fila.listar` da tarefa 1; `decidir_fluxo` e `montar_resumo` de `app.fluxo`
- Produces: `Atendimento.responder(pergunta: str) -> dict` com os cinco campos atuais e `Atendimento.encaminhamentos() -> list[dict]`

O construtor continua `Atendimento(classificar_fn, base)`. A fila nasce dentro do atendimento.

- [ ] **Step 1: Write the failing test**

Acrescentar no fim de `tests/test_atendimento.py`:

```python
def test_flag_falsa_nao_entra_na_fila() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    atendimento.responder("quero uma proposta")
    assert atendimento.encaminhamentos() == []


def test_flag_verdadeira_entra_na_ordem() -> None:
    atendimento = Atendimento(classificar, BaseSempreHumano())
    atendimento.responder("quando vence meu contrato?")
    atendimento.responder("quero uma proposta")
    assert atendimento.encaminhamentos() == [
        {
            "pergunta": "quando vence meu contrato?",
            "fluxo": "suporte",
            "resumo": None,
        },
        {
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
    ]
```

Não alterar os três testes que já existem. O segundo deles continua provando que a flag vem da base. O teste novo com `BaseFalsa` prova que fluxo `venda` com flag falsa não entra na lista.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py::test_flag_falsa_nao_entra_na_fila -v`

Expected: FAIL because `Atendimento` has no `encaminhamentos`.

- [ ] **Step 3: Write minimal implementation**

`app/atendimento.py`

```python
from app.fila import Fila
from app.fluxo import decidir_fluxo, montar_resumo


class Atendimento:
    def __init__(self, classificar_fn, base) -> None:
        self._classificar = classificar_fn
        self._base = base
        self._fila = Fila()

    def responder(self, pergunta: str) -> dict:
        tema = self._classificar(pergunta)
        item = self._base.obter(tema)
        fluxo = decidir_fluxo(tema, pergunta)
        resumo = montar_resumo(pergunta, fluxo)
        if item["encaminhar_humano"]:
            self._fila.registrar(pergunta, fluxo, resumo)
        return {
            "tema": tema,
            "resposta": item["resposta"],
            "encaminhar_humano": item["encaminhar_humano"],
            "fluxo": fluxo,
            "resumo": resumo,
        }

    def encaminhamentos(self) -> list[dict]:
        return self._fila.listar()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py tests/test_fila.py -q`

Expected: the atendimento and fila tests pass.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/atendimento.py tests/test_atendimento.py
git commit -m "feat: record answers that ask for a human"
```

---

### Task 3: GET da lista

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Atendimento.encaminhamentos() -> list[dict]` e `Atendimento.responder(pergunta: str) -> dict`
- Produces: `GET /v1/encaminhamentos` com a lista do atendimento criado em `criar_app`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
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
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        },
        {
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
```

Não alterar `test_health_nao_le_a_base`, `test_perguntas_da_spec`, `test_proposta_vira_venda`, `test_raiz_serve_a_pagina` nem os testes de subida.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_lista_nao_le_a_base_e_comeca_vazia -v`

Expected: FAIL with status `404`.

- [ ] **Step 3: Write minimal implementation**

Em `criar_app`, depois de `POST /v1/perguntas`, acrescentar:

```python
    @app.get("/v1/encaminhamentos")
    def encaminhamentos() -> list:
        return atendimento.encaminhamentos()
```

No README, na seção `## Subir localmente`, depois da frase de `GET /`, acrescentar:

`GET http://127.0.0.1:8000/v1/encaminhamentos` devolve a lista em memória das perguntas com encaminhar humano verdadeiro. Ela começa vazia e some ao reiniciar o processo.

Não alterar o exemplo JSON de três campos. Não alterar `web/index.html`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. `GET /health` ainda não lê a base. A lista vazia do teste com `BaseQueFalha` não chama `obter`.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py README.md
git commit -m "feat: list human handoffs from the running process"
```
