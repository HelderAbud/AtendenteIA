# AtendeIA Spreadsheet Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma planilha `.xlsx` devolve as mesmas seis respostas da base JSON. O processo continua lendo `data/vertice_ti.json`.

**Architecture:** `BasePlanilha` em `app/base.py` lê a primeira aba com `openpyxl`, separa os seis temas pelas colunas `tema` e `resposta` e reusa `_validar`. `Atendimento` recebe esse objeto sem mudança de classe. Nenhuma rota muda.

**Tech Stack:** Python 3.14, openpyxl, pytest. Dependência nova: `openpyxl>=3.1`.

## Global Constraints

- Temas: `prazo`, `sla`, `renovacao`, `boleto`, `chamado`, `desconhecido`.
- Cabeçalho da primeira aba, em minúsculas e sem espaços nas pontas: `tema`, `resposta`. Sem terceira coluna.
- `encaminhar_humano` não vem da planilha. É verdadeiro só em `desconhecido`.
- Linha com as duas células vazias é ignorada. Fórmula não é calculada: vale o texto guardado na célula.
- Arquivo ausente: `FileNotFoundError`. Arquivo que não é planilha: `zipfile.BadZipFile`. Cabeçalho errado, coluna a mais, tema ausente, tema fora da lista, tema repetido ou resposta em branco: `ValueError` na carga.
- Não ligar `BasePlanilha` em `_app_de_producao`. Não criar variável de ambiente.
- Não alterar páginas, README, classificador nem `data/vertice_ti.json`.
- Nenhuma planilha entra no Git. O teste grava o arquivo.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Ler os seis temas de uma planilha

**Files:**
- Modify: `requirements.txt`
- Modify: `app/base.py`
- Create: `tests/test_base_planilha.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-27-atendeia-planilha.md`

**Interfaces:**
- Consumes: `openpyxl.load_workbook`, `_validar`
- Produces: `BasePlanilha(caminho).obter(tema)` com `resposta` e `encaminhar_humano`

- [x] **Step 1: Write the failing test**

Criar `tests/test_base_planilha.py`:

```python
from pathlib import Path

from openpyxl import Workbook

from app.atendimento import Atendimento
from app.base import BasePlanilha
from app.classificador import classificar

LINHAS = [
    ("prazo", "O contrato vale 12 meses."),
    ("sla", "A primeira resposta sai em 4 horas."),
    ("renovacao", "A renovação é automática."),
    ("boleto", "O boleto sai dia 10."),
    ("chamado", "O chamado segue o protocolo."),
    ("desconhecido", "Um atendente continua a conversa."),
]


def _gravar_planilha(caminho: Path, linhas: list[tuple[str, str]]) -> None:
    livro = Workbook()
    aba = livro.active
    aba.append(["tema", "resposta"])
    for tema, resposta in linhas:
        aba.append([tema, resposta])
    livro.save(caminho)


def test_planilha_devolve_os_seis_temas(tmp_path: Path) -> None:
    caminho = tmp_path / "base.xlsx"
    _gravar_planilha(caminho, [("", ""), *LINHAS])
    base = BasePlanilha(caminho)
    assert base.obter("prazo") == {
        "resposta": "O contrato vale 12 meses.",
        "encaminhar_humano": False,
    }
    assert base.obter("desconhecido")["encaminhar_humano"] is True
    resposta = Atendimento(classificar, base).responder("quando vence meu contrato?")
    assert resposta["tema"] == "prazo"
    assert resposta["resposta"] == "O contrato vale 12 meses."
    assert resposta["encaminhar_humano"] is False
    assert resposta["fluxo"] == "suporte"
    assert resposta["resumo"] is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_base_planilha.py::test_planilha_devolve_os_seis_temas -v`

Expected: FAIL with `ImportError`, because `BasePlanilha` ainda não existe. Se faltar `openpyxl`, instalar com `.\.venv\Scripts\python.exe -m pip install "openpyxl>=3.1"` e acrescentar a linha em `requirements.txt` antes de repetir.

- [x] **Step 3: Write minimal implementation**

Em `requirements.txt`, acrescentar:

```text
openpyxl>=3.1
```

Em `app/base.py`, acrescentar `BasePlanilha`. Arquivo ausente é `FileNotFoundError`. Abrir com `load_workbook` sem `data_only`, para não calcular fórmula. Ler só a primeira aba. A primeira linha tem de ser `tema` e `resposta`, já sem espaços e em minúsculas. Uma terceira coluna preenchida no cabeçalho ou numa linha de dados é `ValueError`. Linha com as duas células vazias é ignorada. Tema fora da lista, tema repetido ou resposta em branco é `ValueError`. Montar o dicionário dos seis temas com `encaminhar_humano` verdadeiro só em `desconhecido` e passar em `_validar`. Não capturar `zipfile.BadZipFile`.

Não alterar `BaseConhecimento`, `BasePdf`, `Atendimento` nem `_app_de_producao`.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add requirements.txt app/base.py tests/test_base_planilha.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-27-atendeia-planilha.md
git commit -m "feat: read the knowledge base from a spreadsheet"
```

---

### Task 2: Recusar planilha ilegível ou incompleta

**Files:**
- Modify: `tests/test_base_planilha.py`
- Modify: `app/base.py`

**Interfaces:**
- Consumes: `BasePlanilha`
- Produces: falha na carga, antes de `obter`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_base_planilha.py`:

```python
import zipfile

import pytest


def test_planilha_ausente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BasePlanilha(tmp_path / "ausente.xlsx")


def test_arquivo_que_nao_e_planilha(tmp_path: Path) -> None:
    caminho = tmp_path / "falso.xlsx"
    caminho.write_bytes(b"nao-planilha")
    with pytest.raises(zipfile.BadZipFile):
        BasePlanilha(caminho)


def test_planilha_com_coluna_a_mais(tmp_path: Path) -> None:
    caminho = tmp_path / "larga.xlsx"
    livro = Workbook()
    aba = livro.active
    aba.append(["tema", "resposta", "extra"])
    for tema, resposta in LINHAS:
        aba.append([tema, resposta, ""])
    livro.save(caminho)
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_sem_um_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "incompleta.xlsx"
    _gravar_planilha(caminho, [linha for linha in LINHAS if linha[0] != "boleto"])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_repete_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "repetida.xlsx"
    _gravar_planilha(caminho, [*LINHAS, ("prazo", "Outro prazo.")])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)


def test_planilha_com_resposta_em_branco(tmp_path: Path) -> None:
    caminho = tmp_path / "branco.xlsx"
    _gravar_planilha(caminho, [("prazo", "   "), *LINHAS[1:]])
    with pytest.raises(ValueError):
        BasePlanilha(caminho)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_base_planilha.py::test_planilha_ausente tests/test_base_planilha.py::test_arquivo_que_nao_e_planilha tests/test_base_planilha.py::test_planilha_com_coluna_a_mais -v`

Expected: FAIL. Ausência pode já passar se a Task 1 conferiu o arquivo. Arquivo ilegível ou coluna a mais ainda não pode ser aceito como base válida.

- [ ] **Step 3: Write minimal implementation**

Completar só o que a Task 1 ainda deixar passar. Não capturar `BadZipFile` para transformar em outro erro. Não alterar rotas nem o README.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/base.py tests/test_base_planilha.py
git commit -m "feat: reject an unreadable knowledge spreadsheet"
```
