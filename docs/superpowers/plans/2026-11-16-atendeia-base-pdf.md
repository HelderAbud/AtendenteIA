# AtendeIA Base PDF no Processo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Com um caminho no ambiente, o processo abre a base em PDF. Sem o caminho, continua em `data/vertice_ti.json`.

**Architecture:** `BasePdf` já existe. `criar_app_de_arquivo` ganha `pdf=False` e, quando verdadeiro, usa esse leitor. `_app_de_producao` só liga a flag quando `ATENDEIA_BASE_PDF` tem caminho. O teste grava um PDF temporário.

**Tech Stack:** Python 3.14, FastAPI, pytest, pypdf. Nenhuma dependência nova.

## Global Constraints

- `pdf=False` continua em `BaseConhecimento`. `pdf=True` abre o caminho com `BasePdf`.
- Arquivo ausente é `FileNotFoundError`. Arquivo que não é PDF é `pypdf.errors.PdfReadError`. Base inválida é `ValueError` na carga.
- `ATENDEIA_BASE_PDF` vazia ou ausente não avisa e mantém `data/vertice_ti.json`.
- Com caminho, os dois retornos de `_app_de_producao` usam esse arquivo e `pdf=True`.
- Não alterar o classificador, o Ollama, as rotas, as páginas nem `BasePdf`.
- Não há OCR, planilha no processo nem PDF no Git.
- O rodapé do README passa a `Planilha.` só na tarefa 2.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Abrir a base por um caminho de PDF

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-11-16-atendeia-base-pdf.md`

**Interfaces:**
- Consumes: `BasePdf`
- Produces: `criar_app_de_arquivo(..., pdf=False)`

- [x] **Step 1: Write the failing test**

Em `tests/test_api.py`, importar `PdfReadError` de `pypdf.errors` e `LINHAS, _gravar_pdf` de `tests.test_base_pdf`. Acrescentar:

```python
def test_app_de_arquivo_le_pdf(tmp_path: Path) -> None:
    caminho = tmp_path / "base.pdf"
    _gravar_pdf(caminho, LINHAS)
    client = TestClient(criar_app_de_arquivo(caminho, pdf=True))
    resposta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tema"] == "prazo"
    assert corpo["resposta"] == "O contrato vale 12 meses."
    assert corpo["fluxo"] == "suporte"
    assert corpo["encaminhar_humano"] is False


def test_pdf_ausente_ou_ilegivel_impede_a_subida(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        criar_app_de_arquivo(tmp_path / "ausente.pdf", pdf=True)
    falso = tmp_path / "falso.pdf"
    falso.write_bytes(b"nao e pdf")
    with pytest.raises(PdfReadError):
        criar_app_de_arquivo(falso, pdf=True)
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_arquivo_le_pdf -v`

Expected: FAIL with `TypeError`, because `criar_app_de_arquivo` ainda não aceita `pdf`.

- [x] **Step 3: Write minimal implementation**

Em `app/api.py`, importar `BasePdf` junto de `BaseConhecimento`. `criar_app_de_arquivo` ganha `pdf: bool = False` no fim da assinatura. A base fica:

```python
base = BasePdf(caminho) if pdf else BaseConhecimento(caminho)
```

Não alterar `_app_de_producao`, o README nem `.env.example`.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [x] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/api.py tests/test_api.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-11-16-atendeia-base-pdf.md
git commit -m "feat: open the knowledge base from a pdf path"
```

---

### Task 2: Ler o caminho do PDF no ambiente

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `criar_app_de_arquivo(..., pdf=False)`
- Produces: `_app_de_producao` lê `ATENDEIA_BASE_PDF`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_app_de_producao_le_o_pdf_do_ambiente(monkeypatch, tmp_path: Path) -> None:
    caminho = tmp_path / "base.pdf"
    _gravar_pdf(caminho, LINHAS)
    monkeypatch.setenv("ATENDEIA_BASE_PDF", str(caminho))
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    monkeypatch.delenv("ATENDEIA_OLLAMA_MODELO", raising=False)
    client = TestClient(_app_de_producao())
    resposta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == "O contrato vale 12 meses."
    assert resposta.json()["tema"] == "prazo"


def test_app_de_producao_sem_pdf_mantem_o_json(monkeypatch) -> None:
    monkeypatch.setenv("ATENDEIA_BASE_PDF", "")
    monkeypatch.delenv("ATENDEIA_DATABASE_URL", raising=False)
    client = TestClient(_app_de_producao())
    resposta = client.post(
        "/v1/perguntas", json={"pergunta": "quando vence meu contrato?"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["resposta"] == TEXTOS["prazo"]
```

No README, trocar o rodapé para:

`Planilha.`

Em `.env.example`, acrescentar a linha `ATENDEIA_BASE_PDF=`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_app_de_producao_le_o_pdf_do_ambiente -v`

Expected: FAIL because `resposta` ainda é o texto do JSON, não `O contrato vale 12 meses.`

- [ ] **Step 3: Write minimal implementation**

Em `_app_de_producao`, ler `os.environ.get("ATENDEIA_BASE_PDF") or None`. Com caminho, `caminho` é esse `Path` e `pdf` é verdadeiro. Sem caminho, `caminho` continua `data/vertice_ti.json` e `pdf` é falso. Não avisar na subida. Passar `pdf=pdf` nas duas chamadas de `criar_app_de_arquivo`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py README.md .env.example
git commit -m "feat: read the knowledge pdf path from the environment"
```
