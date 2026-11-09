# AtendeIA Ollama Reescrever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Com o nome do modelo no ambiente, o processo pede ao Ollama local para reescrever só o texto da base. Sem o nome, a resposta continua a da base.

**Architecture:** `_criar_reescrever_ollama` faz um `POST` no Ollama e devolve o texto. `Atendimento` já trata exceção, vazio e outro tipo. `_app_de_producao` só passa a função quando `ATENDEIA_OLLAMA_MODELO` tem nome. O teste troca o `httpx.post` e não liga o Ollama.

**Tech Stack:** Python 3.14, FastAPI, pytest, httpx. Nenhuma dependência nova.

## Global Constraints

- A URL é `http://127.0.0.1:11434/api/generate`. O corpo tem `model`, `prompt` e `stream` falso. O prazo é `timeout=10`.
- O `prompt` é `Reescreva o texto abaixo em português, com outras palavras. Não acrescente fato, data, número, nome nem assunto que não esteja no texto. Devolva só o texto reescrito.` mais uma linha em branco e o texto da base.
- O retorno é o campo `response` inteiro quando é uma `str` com conteúdo depois de `strip`. Rede, status de erro, campo ausente, outro tipo ou texto em branco levanta exceção.
- `ATENDEIA_OLLAMA_MODELO` vazia ou ausente não cria a função e não avisa na subida.
- Tema, fluxo, resumo, encaminhamento e a lista permanecem nas regras atuais. A falha continua `200` com o texto da base e o aviso `falha ao reescrever a resposta`.
- Não criar rota, página, chave, API paga, segundo modelo nem dependência.
- Não alterar o classificador, `data/vertice_ti.json` nem as páginas.
- A suíte não liga o Ollama.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Pedir a reescrita ao Ollama

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-11-06-atendeia-ollama-reescrever.md`

**Interfaces:**
- Consumes: `httpx.post`
- Produces: `_criar_reescrever_ollama(modelo) -> Callable[[str], str]`

- [x] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_ollama_reescreve_o_texto_da_base(monkeypatch) -> None:
    chamadas = []

    def post(url, json, timeout):
        chamadas.append((url, json, timeout))

        class Resposta:
            def raise_for_status(self):
                return None

            def json(self):
                return {"response": " texto reescrito "}

        return Resposta()

    monkeypatch.setattr("app.api.httpx.post", post)
    reescrever = _criar_reescrever_ollama("modelo-teste")
    assert reescrever("texto da base") == " texto reescrito "
    assert chamadas == [
        (
            "http://127.0.0.1:11434/api/generate",
            {
                "model": "modelo-teste",
                "prompt": (
                    "Reescreva o texto abaixo em português, com outras palavras. "
                    "Não acrescente fato, data, número, nome nem assunto que não "
                    "esteja no texto. Devolva só o texto reescrito.\n\n"
                    "texto da base"
                ),
                "stream": False,
            },
            10,
        )
    ]


def test_ollama_sem_texto_util_levanta_erro(monkeypatch) -> None:
    def post(url, json, timeout):
        class Resposta:
            def raise_for_status(self):
                return None

            def json(self):
                return {"response": "   "}

        return Resposta()

    monkeypatch.setattr("app.api.httpx.post", post)
    reescrever = _criar_reescrever_ollama("modelo-teste")
    with pytest.raises(ValueError, match="resposta vazia do modelo"):
        reescrever("texto da base")
```

Importar `_criar_reescrever_ollama` junto dos outros nomes de `app.api`. `pytest` já está importado neste arquivo.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_ollama_reescreve_o_texto_da_base -v`

Expected: FAIL with `ImportError`, because `_criar_reescrever_ollama` ainda não existe.

- [x] **Step 3: Write minimal implementation**

Em `app/api.py`, acrescentar a função. Não alterar `_app_de_producao`, `criar_app_de_arquivo` nem o README.

```python
def _criar_reescrever_ollama(modelo: str):
    def reescrever(texto: str) -> str:
        prompt = (
            "Reescreva o texto abaixo em português, com outras palavras. "
            "Não acrescente fato, data, número, nome nem assunto que não "
            "esteja no texto. Devolva só o texto reescrito.\n\n"
            f"{texto}"
        )
        resposta = httpx.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": modelo, "prompt": prompt, "stream": False},
            timeout=10,
        )
        resposta.raise_for_status()
        conteudo = resposta.json().get("response")
        if not isinstance(conteudo, str) or not conteudo.strip():
            raise ValueError("resposta vazia do modelo")
        return conteudo

    return reescrever
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [x] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-11-06-atendeia-ollama-reescrever.md
git commit -m "feat: ask ollama to rewrite the base answer"
```

---

### Task 2: Ler o nome do modelo no ambiente

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `_criar_reescrever_ollama`, `Atendimento(..., reescrever=None)`
- Produces: `_app_de_producao` lê `ATENDEIA_OLLAMA_MODELO`

- [x] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_app_de_producao_reescreve_pelo_ollama(monkeypatch) -> None:
    def post(url, json, timeout):
        class Resposta:
            def raise_for_status(self):
                return None

            def json(self):
                return {"response": "texto reescrito"}

        return Resposta()

    monkeypatch.setattr("app.api.httpx.post", post)
    monkeypatch.setenv("ATENDEIA_OLLAMA_MODELO", "modelo-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    monkeypatch.delenv("ATENDEIA_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("ATENDEIA_WHATSAPP_PHONE_ID", raising=False)
    client = TestClient(_app_de_producao())
    resposta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tema"] == "prazo"
    assert corpo["resposta"] == "texto reescrito"
    assert corpo["fluxo"] == "suporte"


def test_app_de_producao_sem_modelo_mantem_o_texto_da_base(monkeypatch) -> None:
    chamadas = []

    def post(url, json, timeout):
        chamadas.append(url)
        raise RuntimeError("ollama")

    monkeypatch.setattr("app.api.httpx.post", post)
    monkeypatch.setenv("ATENDEIA_OLLAMA_MODELO", "")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    resposta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == (
        "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura."
    )
    assert chamadas == []


def test_app_de_producao_mantem_a_base_quando_o_ollama_falha(monkeypatch, caplog) -> None:
    def post(url, json, timeout):
        raise RuntimeError("ollama")

    monkeypatch.setattr("app.api.httpx.post", post)
    monkeypatch.setenv("ATENDEIA_OLLAMA_MODELO", "modelo-teste")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    with caplog.at_level("WARNING", logger="atendeia"):
        resposta = client.post(
            "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
        )
    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == (
        "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura."
    )
    assert "falha ao reescrever a resposta" in caplog.text
```

No README, trocar o rodapé para:

`PDF e planilha.`

Em `.env.example`, acrescentar a linha `ATENDEIA_OLLAMA_MODELO=`.

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_reescreve_pelo_ollama -v`

Expected: FAIL because `resposta` ainda é o texto da base, não `texto reescrito`.

- [x] **Step 3: Write minimal implementation**

`criar_app_de_arquivo` ganha `reescrever=None` e chama `Atendimento(classificar, base, banco, postgres_url, reescrever=reescrever)`.

Em `_app_de_producao`, ler `os.environ.get("ATENDEIA_OLLAMA_MODELO") or None`. Com nome, criar a função. Sem nome, passar `None`. Entregar `reescrever=reescrever` nas duas chamadas de `criar_app_de_arquivo`. Não acrescentar aviso de subida para essa variável.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [x] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py README.md .env.example
git commit -m "feat: read the ollama model name from the environment"
```
