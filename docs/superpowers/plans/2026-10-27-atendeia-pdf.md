# AtendeIA PDF Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um PDF com texto selecionável devolve as mesmas seis respostas da base JSON. O processo continua lendo `data/vertice_ti.json`.

**Architecture:** `BasePdf` em `app/base.py` extrai o texto com `pypdf`, separa os seis temas por linha e reusa `_validar`. `Atendimento` recebe esse objeto sem mudança de classe. Nenhuma rota muda.

**Tech Stack:** Python 3.14, pypdf, pytest. Dependência nova: `pypdf>=5.1`.

## Global Constraints

- Temas: `prazo`, `sla`, `renovacao`, `boleto`, `chamado`, `desconhecido`.
- `encaminhar_humano` não vem do PDF. É verdadeiro só em `desconhecido`.
- A resposta é o texto do bloco, com as linhas unidas por um espaço.
- Arquivo ausente: `FileNotFoundError`. Arquivo ilegível: `pypdf.errors.PdfReadError`. Tema ausente, tema repetido, resposta em branco ou PDF sem texto: `ValueError` na carga.
- Não ligar `BasePdf` em `_app_de_producao`. Não criar variável de ambiente.
- Não alterar páginas, README, classificador nem `data/vertice_ti.json`.
- Nenhum PDF entra no Git. O teste grava o arquivo.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Ler os seis temas de um PDF

**Files:**
- Modify: `requirements.txt`
- Modify: `app/base.py`
- Create: `tests/test_base_pdf.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-27-atendeia-pdf.md`

**Interfaces:**
- Consumes: `pypdf.PdfReader`, `_validar`
- Produces: `BasePdf(caminho).obter(tema)` com `resposta` e `encaminhar_humano`

- [x] **Step 1: Write the failing test**

Criar `tests/test_base_pdf.py`:

```python
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.atendimento import Atendimento
from app.base import BasePdf
from app.classificador import classificar

LINHAS = [
    "prazo",
    "O contrato vale 12 meses.",
    "sla",
    "A primeira resposta sai em 4 horas.",
    "renovacao",
    "A renovação é automática.",
    "boleto",
    "O boleto sai dia 10.",
    "chamado",
    "O chamado segue o protocolo.",
    "desconhecido",
    "Um atendente continua a conversa.",
]


def _literal(texto: str) -> str:
    saida = []
    for caractere in texto.encode("latin-1"):
        if caractere in (ord("\\"), ord("("), ord(")")):
            saida.append("\\" + chr(caractere))
        elif caractere < 32 or caractere > 126:
            saida.append(f"\\{caractere:03o}")
        else:
            saida.append(chr(caractere))
    return "".join(saida)


def _gravar_pdf(caminho: Path, linhas: list[str]) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    fonte = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    comandos = ["BT", "/F1 12 Tf", "72 740 Td", "16 TL"]
    for indice, linha in enumerate(linhas):
        if indice:
            comandos.append("T*")
        comandos.append("(" + _literal(linha) + ") Tj")
    comandos.append("ET")
    fluxo = DecodedStreamObject()
    fluxo.set_data("\n".join(comandos).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(fluxo)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): fonte})}
    )
    writer.write(caminho)


def test_pdf_devolve_os_seis_temas(tmp_path: Path) -> None:
    caminho = tmp_path / "base.pdf"
    _gravar_pdf(caminho, LINHAS)
    base = BasePdf(caminho)
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

Run: `.venv\Scripts\python.exe -m pytest tests/test_base_pdf.py::test_pdf_devolve_os_seis_temas -v`

Expected: FAIL with `ImportError`, because `BasePdf` ainda não existe. Se faltar `pypdf`, instalar com `.\.venv\Scripts\python.exe -m pip install "pypdf>=5.1"` e acrescentar a linha em `requirements.txt` antes de repetir.

- [x] **Step 3: Write minimal implementation**

Em `requirements.txt`, acrescentar:

```text
pypdf>=5.1
```

Em `app/base.py`, acrescentar `BasePdf`. Extrair o texto de cada página com `extract_text`, na ordem, unindo as páginas por `\n`. Uma linha em minúsculas e sem espaços nas pontas, se for um tema, abre o bloco. Tema repetido é `ValueError`. As outras linhas não vazias entram na resposta do bloco aberto, unidas por um espaço. Tema ausente ou resposta em branco é `ValueError`. Montar o dicionário dos seis temas com `encaminhar_humano` verdadeiro só em `desconhecido` e passar em `_validar`. Arquivo ausente continua `FileNotFoundError`.

Não alterar `BaseConhecimento`, `Atendimento` nem `_app_de_producao`.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If `extract_text` colar o título na resposta, ajustar só o gravador do teste até cada tema ficar sozinho na linha. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add requirements.txt app/base.py tests/test_base_pdf.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-27-atendeia-pdf.md
git commit -m "feat: read the knowledge base from a pdf"
```

---

### Task 2: Recusar PDF ilegível ou incompleto

**Files:**
- Modify: `tests/test_base_pdf.py`
- Modify: `app/base.py`

**Interfaces:**
- Consumes: `BasePdf`
- Produces: falha na carga, antes de `obter`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_base_pdf.py`:

```python
import pytest
from pypdf.errors import PdfReadError


def test_pdf_ausente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BasePdf(tmp_path / "ausente.pdf")


def test_arquivo_que_nao_e_pdf(tmp_path: Path) -> None:
    caminho = tmp_path / "falso.pdf"
    caminho.write_bytes(b"nao-pdf")
    with pytest.raises(PdfReadError):
        BasePdf(caminho)


def test_pdf_sem_texto(tmp_path: Path) -> None:
    caminho = tmp_path / "vazio.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(caminho)
    with pytest.raises(ValueError):
        BasePdf(caminho)


def test_pdf_sem_um_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "incompleto.pdf"
    _gravar_pdf(caminho, [linha for linha in LINHAS if linha != "boleto"])
    with pytest.raises(ValueError):
        BasePdf(caminho)


def test_pdf_repete_tema(tmp_path: Path) -> None:
    caminho = tmp_path / "repetido.pdf"
    _gravar_pdf(caminho, LINHAS + ["prazo", "Outro prazo."])
    with pytest.raises(ValueError):
        BasePdf(caminho)


def test_pdf_com_resposta_em_branco(tmp_path: Path) -> None:
    caminho = tmp_path / "branco.pdf"
    linhas = [linha for linha in LINHAS if linha != "O contrato vale 12 meses."]
    _gravar_pdf(caminho, linhas)
    with pytest.raises(ValueError):
        BasePdf(caminho)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_base_pdf.py::test_pdf_ausente tests/test_base_pdf.py::test_arquivo_que_nao_e_pdf tests/test_base_pdf.py::test_pdf_sem_texto -v`

Expected: FAIL. Ausência pode já passar se a Task 1 conferiu o arquivo. PDF ilegível ou sem texto ainda não pode ser aceito como base válida.

- [ ] **Step 3: Write minimal implementation**

Completar só o que a Task 1 ainda deixar passar. Não capturar `PdfReadError` para transformar em outro erro. Não alterar rotas nem o README.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/base.py tests/test_base_pdf.py
git commit -m "feat: reject an unreadable knowledge pdf"
```
