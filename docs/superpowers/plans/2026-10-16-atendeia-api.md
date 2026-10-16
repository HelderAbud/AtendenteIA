# AtendeIA API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a API que classifica uma pergunta de contrato da Vértice TI e devolve o texto da base fixa, com testes sem rede.

**Architecture:** A API HTTP depende só do atendimento. O atendimento chama o classificador e a base. O classificador escolhe o tema por sinais. A base lê `data/vertice_ti.json`. Nos testes, a base é substituída sem subir servidor.

**Tech Stack:** Python 3.11+, FastAPI, pytest, httpx (TestClient).

## Global Constraints

- Python 3.11+; FastAPI e pytest; sem banco.
- Empresa fictícia Vértice TI; sem cliente real e sem dado pessoal.
- O tema de chamado chama-se `chamado`.
- Tema desconhecido responde HTTP 200 e `encaminhar_humano: true`.
- Pergunta inválida responde HTTP 422 e `{ "erro": "pergunta_invalida" }`.
- `GET /health` responde HTTP 200 e `{ "status": "ok" }` sem ler a base.
- Cada sinal soma 1 ponto se aparecer como trecho do texto já normalizado e conta uma vez; empate ou zero vira `desconhecido`.
- Números e frases prontas (12 meses, 4 horas, 99,5%, renovação automática) ficam só no texto da resposta.
- A base é `data/vertice_ti.json`; arquivo ausente, chave faltando, texto vazio ou booleano errado impede a API de iniciar.
- Fora deste recorte: WhatsApp, Instagram, Telegram, site, painel, login, modelo de linguagem, RAG, PDF, PIX, boleto real, planilha, e-mail, CRM, agentes de venda e suporte, análise jurídica.
- Rodar `pytest` na raiz do projeto. Nenhuma chamada de rede.
- Commit só quando o usuário pedir nesta sessão. Os comandos abaixo ficam prontos para esse momento.

---

### Task 1: Classificador

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/classificador.py`
- Test: `tests/test_classificador.py`

**Interfaces:**
- Consumes: nada
- Produces: `classificar(texto: str) -> str` com um destes valores: `prazo`, `sla`, `renovacao`, `boleto`, `chamado`, `desconhecido`

- [ ] **Step 1: Write the failing test**

`.gitignore`

```text
.venv/
__pycache__/
.pytest_cache/
*.pyc
```

`requirements.txt`

```text
fastapi>=0.115
uvicorn>=0.32
pytest>=8.3
httpx>=0.27
```

`pytest.ini`

```ini
[pytest]
pythonpath = .
```

`app/__init__.py` fica vazio.

`tests/test_classificador.py`

```python
import pytest

from app.classificador import classificar


@pytest.mark.parametrize(
    ("pergunta", "tema"),
    [
        ("quando vence meu contrato?", "prazo"),
        ("VIGÊNCIA do suporte", "prazo"),
        ("qual é o sla?", "sla"),
        ("como faco a renovacao?", "renovacao"),
        ("preciso da segunda via do boleto", "boleto"),
        ("qual o status do chamado?", "chamado"),
        ("quero falar sobre o clima", "desconhecido"),
        ("vence o boleto", "desconhecido"),
    ],
)
def test_exemplos_fechados(pergunta: str, tema: str) -> None:
    assert classificar(pergunta) == tema
```

- [ ] **Step 2: Run test to verify it fails**

Run from the project root: `pytest tests/test_classificador.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.classificador'`

- [ ] **Step 3: Write minimal implementation**

`app/classificador.py`

```python
import unicodedata

SINAIS: dict[str, tuple[str, ...]] = {
    "prazo": ("prazo", "vence", "vencer", "vigencia", "termina", "vencimento"),
    "sla": ("sla", "disponibilidade", "primeira resposta", "tempo de resposta"),
    "renovacao": ("renova", "renovacao", "renovar"),
    "boleto": ("boleto", "segunda via", "pagar", "pagamento"),
    "chamado": ("chamado", "ticket", "status", "andamento"),
}


def normalizar(texto: str) -> str:
    texto = texto.lower()
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(
        caractere for caractere in sem_acento if unicodedata.category(caractere) != "Mn"
    )
    return " ".join(sem_acento.split())


def classificar(texto: str) -> str:
    normalizado = normalizar(texto)
    pontuacao = {
        tema: sum(1 for sinal in sinais if sinal in normalizado)
        for tema, sinais in SINAIS.items()
    }
    maior = max(pontuacao.values())
    if maior == 0:
        return "desconhecido"
    vencedores = [tema for tema, pontos in pontuacao.items() if pontos == maior]
    if len(vencedores) != 1:
        return "desconhecido"
    return vencedores[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classificador.py -v`

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git init -b Main
git add .gitignore requirements.txt pytest.ini app/__init__.py app/classificador.py tests/test_classificador.py
git commit -m "feat: classify contract questions by keyword signals"
```

---

### Task 2: Base da Vértice TI

**Files:**
- Create: `data/vertice_ti.json`
- Create: `app/base.py`
- Test: `tests/test_base.py`

**Interfaces:**
- Consumes: nada do classificador
- Produces: `BaseConhecimento(caminho: Path)` e `obter(tema: str) -> dict` com as chaves `resposta: str` e `encaminhar_humano: bool`. Arquivo ausente levanta `FileNotFoundError`. Conteúdo inválido levanta `ValueError`.

- [ ] **Step 1: Write the failing test**

`tests/test_base.py`

```python
import json
from pathlib import Path

import pytest

from app.base import BaseConhecimento

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "data" / "vertice_ti.json"

TEXTOS = {
    "prazo": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
    "sla": "A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.",
    "renovacao": "A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.",
    "boleto": "O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.",
    "chamado": "O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.",
    "desconhecido": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
}


def test_arquivo_real_devolve_os_textos() -> None:
    base = BaseConhecimento(ARQUIVO)
    for tema, texto in TEXTOS.items():
        item = base.obter(tema)
        assert item["resposta"] == texto
        assert item["encaminhar_humano"] is (tema == "desconhecido")


def test_arquivo_ausente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BaseConhecimento(tmp_path / "ausente.json")


def _gravar(tmp_path: Path, dados: dict) -> Path:
    caminho = tmp_path / "base.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def _base_valida() -> dict:
    return {
        tema: {
            "resposta": texto,
            "encaminhar_humano": tema == "desconhecido",
        }
        for tema, texto in TEXTOS.items()
    }


def test_chave_ausente(tmp_path: Path) -> None:
    dados = _base_valida()
    del dados["boleto"]
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_resposta_vazia(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["prazo"]["resposta"] = "   "
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_booleano_ausente(tmp_path: Path) -> None:
    dados = _base_valida()
    del dados["sla"]["encaminhar_humano"]
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_encaminhar_errado_no_tema_de_negocio(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["prazo"]["encaminhar_humano"] = True
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_encaminhar_errado_no_desconhecido(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["desconhecido"]["encaminhar_humano"] = False
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_base.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.base'`

- [ ] **Step 3: Write minimal implementation**

`data/vertice_ti.json`

```json
{
  "prazo": {
    "resposta": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
    "encaminhar_humano": false
  },
  "sla": {
    "resposta": "A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.",
    "encaminhar_humano": false
  },
  "renovacao": {
    "resposta": "A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.",
    "encaminhar_humano": false
  },
  "boleto": {
    "resposta": "O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.",
    "encaminhar_humano": false
  },
  "chamado": {
    "resposta": "O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.",
    "encaminhar_humano": false
  },
  "desconhecido": {
    "resposta": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
    "encaminhar_humano": true
  }
}
```

`app/base.py`

```python
import json
from pathlib import Path

TEMAS_NEGOCIO = ("prazo", "sla", "renovacao", "boleto", "chamado")
TEMA_DESCONHECIDO = "desconhecido"
TEMAS = TEMAS_NEGOCIO + (TEMA_DESCONHECIDO,)


class BaseConhecimento:
    def __init__(self, caminho: Path) -> None:
        if not caminho.is_file():
            raise FileNotFoundError(caminho)
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self._itens = _validar(dados)

    def obter(self, tema: str) -> dict:
        return self._itens[tema]


def _validar(dados: object) -> dict[str, dict]:
    if not isinstance(dados, dict):
        raise ValueError("base invalida")
    itens: dict[str, dict] = {}
    for tema in TEMAS:
        if tema not in dados or not isinstance(dados[tema], dict):
            raise ValueError(f"tema ausente: {tema}")
        resposta = dados[tema].get("resposta")
        encaminhar = dados[tema].get("encaminhar_humano")
        if not isinstance(resposta, str) or not resposta.strip():
            raise ValueError(f"resposta ausente: {tema}")
        if not isinstance(encaminhar, bool):
            raise ValueError(f"encaminhar ausente: {tema}")
        if encaminhar is not (tema == TEMA_DESCONHECIDO):
            raise ValueError(f"encaminhar inesperado: {tema}")
        itens[tema] = {
            "resposta": resposta,
            "encaminhar_humano": encaminhar,
        }
    return itens
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_base.py -v`

Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add data/vertice_ti.json app/base.py tests/test_base.py
git commit -m "feat: load Vertice TI answers from a versioned file"
```

---

### Task 3: Atendimento

**Files:**
- Create: `app/atendimento.py`
- Test: `tests/test_atendimento.py`

**Interfaces:**
- Consumes: `classificar(texto: str) -> str` e qualquer objeto com `obter(tema: str) -> dict` contendo `resposta` e `encaminhar_humano`
- Produces: `Atendimento(classificar_fn, base)` e `responder(pergunta: str) -> dict` com `tema`, `resposta` e `encaminhar_humano` copiados da base

- [ ] **Step 1: Write the failing test**

`tests/test_atendimento.py`

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
    }


def test_copia_encaminhar_da_base() -> None:
    atendimento = Atendimento(lambda texto: "prazo", BaseSempreHumano())
    assert atendimento.responder("qualquer coisa") == {
        "tema": "prazo",
        "resposta": "da base",
        "encaminhar_humano": True,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_atendimento.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.atendimento'`

- [ ] **Step 3: Write minimal implementation**

`app/atendimento.py`

```python
class Atendimento:
    def __init__(self, classificar_fn, base) -> None:
        self._classificar = classificar_fn
        self._base = base

    def responder(self, pergunta: str) -> dict:
        tema = self._classificar(pergunta)
        item = self._base.obter(tema)
        return {
            "tema": tema,
            "resposta": item["resposta"],
            "encaminhar_humano": item["encaminhar_humano"],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_atendimento.py -v`

Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/atendimento.py tests/test_atendimento.py
git commit -m "feat: answer from the classifier and a swappable knowledge base"
```

---

### Task 4: API HTTP

**Files:**
- Create: `app/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Atendimento`, `classificar` e `BaseConhecimento`
- Produces: `criar_app(atendimento) -> FastAPI` e `criar_app_de_arquivo(caminho: Path) -> FastAPI`. A segunda levanta `FileNotFoundError` ou `ValueError` antes de devolver o app quando a base não sobe.

- [ ] **Step 1: Write the failing test**

`tests/test_api.py`

```python
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import criar_app, criar_app_de_arquivo
from app.atendimento import Atendimento
from app.classificador import classificar

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "data" / "vertice_ti.json"

TEXTOS = {
    "prazo": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
    "sla": "A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.",
    "renovacao": "A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.",
    "boleto": "O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.",
    "chamado": "O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.",
    "desconhecido": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
}


class BaseQueFalha:
    def obter(self, tema: str) -> dict:
        raise AssertionError("health nao le a base")


def test_health_nao_le_a_base() -> None:
    client = TestClient(criar_app(Atendimento(classificar, BaseQueFalha())))
    resposta = client.get("/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("pergunta", "tema"),
    [
        ("quando vence meu contrato?", "prazo"),
        ("VIGÊNCIA do suporte", "prazo"),
        ("qual é o sla?", "sla"),
        ("como faco a renovacao?", "renovacao"),
        ("preciso da segunda via do boleto", "boleto"),
        ("qual o status do chamado?", "chamado"),
        ("quero falar sobre o clima", "desconhecido"),
        ("vence o boleto", "desconhecido"),
    ],
)
def test_perguntas_da_spec(pergunta: str, tema: str) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json={"pergunta": pergunta})
    assert resposta.status_code == 200
    assert resposta.json() == {
        "tema": tema,
        "resposta": TEXTOS[tema],
        "encaminhar_humano": tema == "desconhecido",
    }


@pytest.mark.parametrize(
    "corpo",
    [{}, {"pergunta": None}, {"pergunta": 10}, {"pergunta": ""}, {"pergunta": "   "}],
)
def test_pergunta_invalida(corpo: dict) -> None:
    client = TestClient(criar_app_de_arquivo(ARQUIVO))
    resposta = client.post("/v1/perguntas", json=corpo)
    assert resposta.status_code == 422
    assert resposta.json() == {"erro": "pergunta_invalida"}


def test_arquivo_ausente_impede_a_subida(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        criar_app_de_arquivo(tmp_path / "ausente.json")


def test_base_invalida_impede_a_subida(tmp_path: Path) -> None:
    caminho = tmp_path / "base.json"
    caminho.write_text(json.dumps({"prazo": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        criar_app_de_arquivo(caminho)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.api'`

- [ ] **Step 3: Write minimal implementation**

`app/api.py`

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.atendimento import Atendimento
from app.base import BaseConhecimento
from app.classificador import classificar


class PerguntaIn(BaseModel):
    pergunta: str

    @field_validator("pergunta")
    @classmethod
    def nao_vazia(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("pergunta_invalida")
        return valor


def criar_app(atendimento: Atendimento) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def pergunta_invalida(request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"erro": "pergunta_invalida"})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/perguntas")
    def perguntas(corpo: PerguntaIn) -> dict:
        return atendimento.responder(corpo.pergunta)

    return app


def criar_app_de_arquivo(caminho: Path) -> FastAPI:
    base = BaseConhecimento(caminho)
    return criar_app(Atendimento(classificar, base))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -v`

Expected: PASS of the classifier, base, atendimento and API tests. No network.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py
git commit -m "feat: expose contract questions over HTTP"
```
