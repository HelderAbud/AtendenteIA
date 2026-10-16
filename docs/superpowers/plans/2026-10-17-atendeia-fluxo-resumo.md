# AtendeIA fluxo e resumo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acrescentar fluxo, resumo e uma página em `GET /` sem mudar o classificador de tema nem o arquivo da Vértice TI.

**Architecture:** Um módulo novo decide o fluxo depois do tema. O atendimento copia a flag da base e monta o resumo. A API devolve os cinco campos e serve a página. Saúde, validação 422 e a recusa de subir sem a base ficam como estão.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx (TestClient).

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador de tema e `data/vertice_ti.json` não mudam.
- `GET /health` continua `200` `{ "status": "ok" }` sem ler a base.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }`.
- Arquivo ausente ou inválido continua impedindo a subida.
- Tema `prazo`, `sla`, `renovacao`, `boleto` ou `chamado` define `fluxo` `suporte` e `resumo` nulo, mesmo com sinal de venda na frase.
- Tema `desconhecido` com trecho `contratar`, `proposta`, `orcamento`, `licenca` ou `fechar` define `fluxo` `venda`.
- Os outros textos definem `fluxo` `desconhecido`.
- `resumo` nulo no suporte. Nos outros fluxos: `Pergunta: {pergunta original}. Motivo: {motivo}.`
- Motivo de venda: `venda sem resposta na base`. Motivo desconhecido: `assunto fora da base`.
- `encaminhar_humano` continua copiado da base.
- Sem WhatsApp, fila, login ou modelo de linguagem.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Fluxo e resumo

**Files:**
- Create: `app/fluxo.py`
- Test: `tests/test_fluxo.py`

**Interfaces:**
- Consumes: `normalizar(texto: str) -> str` de `app.classificador`
- Produces: `decidir_fluxo(tema: str, pergunta: str) -> str` e `montar_resumo(pergunta: str, fluxo: str) -> str | None`

- [ ] **Step 1: Write the failing test**

`tests/test_fluxo.py`

```python
from app.fluxo import decidir_fluxo, montar_resumo


def test_tema_de_suporte_vence_sinal_de_venda() -> None:
    assert decidir_fluxo("prazo", "quero uma proposta e o prazo") == "suporte"
    assert montar_resumo("quero uma proposta e o prazo", "suporte") is None


def test_venda_quando_o_tema_e_desconhecido() -> None:
    assert decidir_fluxo("desconhecido", "quero uma proposta") == "venda"
    assert (
        montar_resumo("quero uma proposta", "venda")
        == "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
    )


def test_orcamento_com_acento_e_venda() -> None:
    assert decidir_fluxo("desconhecido", "quero um orçamento") == "venda"


def test_sem_sinal_fica_desconhecido() -> None:
    assert decidir_fluxo("desconhecido", "quero falar sobre o clima") == "desconhecido"
    assert (
        montar_resumo("quero falar sobre o clima", "desconhecido")
        == "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fluxo.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.fluxo'`

- [ ] **Step 3: Write minimal implementation**

`app/fluxo.py`

```python
from app.classificador import normalizar

SINAIS_VENDA = ("contratar", "proposta", "orcamento", "licenca", "fechar")
TEMAS_SUPORTE = ("prazo", "sla", "renovacao", "boleto", "chamado")


def decidir_fluxo(tema: str, pergunta: str) -> str:
    if tema in TEMAS_SUPORTE:
        return "suporte"
    normalizado = normalizar(pergunta)
    if any(sinal in normalizado for sinal in SINAIS_VENDA):
        return "venda"
    return "desconhecido"


def montar_resumo(pergunta: str, fluxo: str) -> str | None:
    if fluxo == "suporte":
        return None
    motivo = (
        "venda sem resposta na base"
        if fluxo == "venda"
        else "assunto fora da base"
    )
    return f"Pergunta: {pergunta}. Motivo: {motivo}."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fluxo.py tests/test_classificador.py -q`

Expected: the new fluxo tests pass and the 8 classifier tests still pass.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/fluxo.py tests/test_fluxo.py
git commit -m "feat: decide sale or support flow after the topic"
```

---

### Task 2: Resposta com cinco campos

**Files:**
- Modify: `app/atendimento.py`
- Modify: `tests/test_atendimento.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `decidir_fluxo` e `montar_resumo`
- Produces: `Atendimento.responder` devolve `tema`, `resposta`, `encaminhar_humano`, `fluxo` e `resumo`

- [ ] **Step 1: Write the failing test**

Substituir o corpo de `tests/test_atendimento.py` por:

```python
from app.atendimento import Atendimento
from app.classificador import classificar


class BaseFalsa:
    def obter(self, tema: str) -> dict:
        return {"resposta": f"texto-{tema}", "encaminhar_humano": False}


class BaseSempreHumano:
    def obter(self, tema: str) -> dict:
        return {"resposta": "da base", "encaminhar_humano": True}


def test_devolve_o_texto_da_base_trocada() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    assert atendimento.responder("quando vence meu contrato?") == {
        "tema": "prazo",
        "resposta": "texto-prazo",
        "encaminhar_humano": False,
        "fluxo": "suporte",
        "resumo": None,
    }


def test_copia_encaminhar_da_base() -> None:
    atendimento = Atendimento(lambda texto: "prazo", BaseSempreHumano())
    assert atendimento.responder("qualquer coisa") == {
        "tema": "prazo",
        "resposta": "da base",
        "encaminhar_humano": True,
        "fluxo": "suporte",
        "resumo": None,
    }


def test_venda_usa_a_resposta_da_base_e_o_resumo() -> None:
    atendimento = Atendimento(classificar, BaseFalsa())
    assert atendimento.responder("quero uma proposta") == {
        "tema": "desconhecido",
        "resposta": "texto-desconhecido",
        "encaminhar_humano": False,
        "fluxo": "venda",
        "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
    }
```

O terceiro teste usa a base falsa, cuja flag de desconhecido é `False`. Isso prova que a flag continua vindo da base, enquanto o resumo vem do fluxo.

Em `tests/test_api.py`, substituir o miolo de `test_perguntas_da_spec` por:

```python
def test_perguntas_da_spec(pergunta: str, tema: str) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json={"pergunta": pergunta})
    if tema == "desconhecido":
        fluxo = "desconhecido"
        resumo = f"Pergunta: {pergunta}. Motivo: assunto fora da base."
    else:
        fluxo = "suporte"
        resumo = None
    assert resposta.status_code == 200
    assert resposta.json() == {
        "tema": tema,
        "resposta": TEXTOS[tema],
        "encaminhar_humano": tema == "desconhecido",
        "fluxo": fluxo,
        "resumo": resumo,
    }
```

Acrescentar:

```python
def test_proposta_vira_venda() -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    assert resposta.status_code == 200
    assert resposta.json() == {
        "tema": "desconhecido",
        "resposta": TEXTOS["desconhecido"],
        "encaminhar_humano": True,
        "fluxo": "venda",
        "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
    }
```

Não alterar `test_health_nao_le_a_base`, `test_pergunta_invalida`, `test_arquivo_ausente_impede_a_subida` nem `test_base_invalida_impede_a_subida`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py::test_devolve_o_texto_da_base_trocada -v`

Expected: FAIL because the response has no `fluxo`.

- [ ] **Step 3: Write minimal implementation**

`app/atendimento.py`

```python
from app.fluxo import decidir_fluxo, montar_resumo


class Atendimento:
    def __init__(self, classificar_fn, base) -> None:
        self._classificar = classificar_fn
        self._base = base

    def responder(self, pergunta: str) -> dict:
        tema = self._classificar(pergunta)
        item = self._base.obter(tema)
        fluxo = decidir_fluxo(tema, pergunta)
        return {
            "tema": tema,
            "resposta": item["resposta"],
            "encaminhar_humano": item["encaminhar_humano"],
            "fluxo": fluxo,
            "resumo": montar_resumo(pergunta, fluxo),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the suite passes, including health, 422 and the startup refusals.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/atendimento.py tests/test_atendimento.py tests/test_api.py
git commit -m "feat: return flow and handoff summary with each answer"
```

---

### Task 3: Página na raiz

**Files:**
- Create: `web/index.html`
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `POST /v1/perguntas`
- Produces: `GET /` com HTML `200` contendo `id="pergunta"`, `id="resposta"`, `id="resumo"` e o texto `/v1/perguntas`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_raiz_serve_a_pagina() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]
    texto = resposta.text
    assert 'id="pergunta"' in texto
    assert 'id="resposta"' in texto
    assert 'id="resumo"' in texto
    assert "/v1/perguntas" in texto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_raiz_serve_a_pagina -v`

Expected: FAIL with status `404`.

- [ ] **Step 3: Write minimal implementation**

`web/index.html`

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>AtendeIA</title>
</head>
<body>
  <form id="form">
    <label for="pergunta">Pergunta</label>
    <input id="pergunta" name="pergunta" type="text">
    <button type="submit">Enviar</button>
  </form>
  <p id="resposta"></p>
  <p id="resumo"></p>
  <script>
    const form = document.getElementById("form");
    const campo = document.getElementById("pergunta");
    const resposta = document.getElementById("resposta");
    const resumo = document.getElementById("resumo");
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const pedido = await fetch("/v1/perguntas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta: campo.value })
      });
      const corpo = await pedido.json();
      resposta.textContent = corpo.resposta || "";
      resumo.textContent = corpo.resumo || "";
    });
  </script>
</body>
</html>
```

Em `criar_app`, acrescentar o import `HTMLResponse` e a rota:

```python
from fastapi.responses import HTMLResponse, JSONResponse

PAGINA = Path(__file__).resolve().parents[1] / "web" / "index.html"


def criar_app(atendimento: Atendimento) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def pergunta_invalida(request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"erro": "pergunta_invalida"})

    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        return PAGINA.read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/perguntas")
    def perguntas(corpo: PerguntaIn) -> dict:
        return atendimento.responder(corpo.pergunta)

    return app
```

No README, na seção de subir localmente, acrescentar que `GET /` abre a página da pergunta.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. `GET /health` ainda não lê a base.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add web/index.html app/api.py tests/test_api.py README.md
git commit -m "feat: serve the question page at the site root"
```
