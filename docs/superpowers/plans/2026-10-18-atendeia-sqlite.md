# AtendeIA SQLite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guardar a lista de encaminhamentos num arquivo SQLite para ela sobreviver ao reinício.

**Architecture:** `Fila` passa a usar `sqlite3`, da biblioteca padrão. Sem caminho, cada objeto tem o seu SQLite em memória. Com caminho, o arquivo é a lista compartilhada. O atendimento só repassa o caminho. A API de produção abre `data/atendeia.sqlite`. Postgres, login e WhatsApp ficam fora.

**Tech Stack:** Python 3.11+, sqlite3, FastAPI, pytest, httpx (TestClient). Nenhuma dependência nova.

## Global Constraints

- O tema de chamado continua `chamado`. Não usar `status_chamado`.
- O classificador, `data/vertice_ti.json`, o fluxo e os cinco campos de `POST /v1/perguntas` não mudam. O POST não devolve `id`.
- `GET /health` continua `200` `{ "status": "ok" }` sem ler a base de conhecimento.
- Pergunta inválida continua `422` `{ "erro": "pergunta_invalida" }`.
- `DELETE` de id ausente continua `404` `{ "erro": "encaminhamento_inexistente" }` e não lê a base de conhecimento.
- A tabela é `encaminhamentos` com `id INTEGER PRIMARY KEY AUTOINCREMENT`, `pergunta TEXT NOT NULL`, `fluxo TEXT NOT NULL`, `resumo TEXT`.
- `id` começa em 1 e não é reutilizado, nem depois de apagar e nem depois de reabrir o arquivo.
- `resumo` nulo vai como `NULL` e volta como `None`. A lista sai em ordem de `id`.
- Sem caminho, duas filas não se veem. Com o mesmo caminho, veem as mesmas linhas.
- O arquivo `data/atendeia.sqlite` não entra no Git.
- Sem Postgres, login, WhatsApp ou modelo de linguagem.
- Commit só quando o usuário pedir nesta sessão.

---

### Task 1: Fila em SQLite

**Files:**
- Modify: `app/fila.py`
- Modify: `tests/test_fila.py`

**Interfaces:**
- Consumes: `sqlite3`
- Produces: `Fila(banco: Path | None = None)` com `registrar`, `listar` e `remover` como hoje. `remover` continua levantando `KeyError`

O SQLite em memória fica na conexão criada na subida. O TestClient chama a fila em outra thread, então essa conexão usa `check_same_thread=False`. O arquivo abre uma conexão nova a cada chamada e não precisa dessa opção.

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_fila.py`:

```python
def test_arquivo_sobrevive_e_nao_reusa_id(tmp_path) -> None:
    caminho = tmp_path / "fila.sqlite"
    primeira = Fila(caminho)
    primeira.registrar("quero uma proposta", "venda", "resumo")
    primeira.remover(1)
    segunda = Fila(caminho)
    segunda.registrar("quero falar sobre o clima", "desconhecido", None)
    assert segunda.listar() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": None,
        }
    ]


def test_mesmo_arquivo_e_visto_por_duas_filas(tmp_path) -> None:
    caminho = tmp_path / "fila.sqlite"
    Fila(caminho).registrar("quero uma proposta", "venda", "resumo")
    assert Fila(caminho).listar() == [
        {"id": 1, "pergunta": "quero uma proposta", "fluxo": "venda", "resumo": "resumo"}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fila.py::test_arquivo_sobrevive_e_nao_reusa_id -v`

Expected: FAIL because `Fila()` does not accept a path.

- [ ] **Step 3: Write minimal implementation**

`app/fila.py`

```python
import sqlite3
from pathlib import Path


class Fila:
    def __init__(self, banco: Path | None = None) -> None:
        self._banco = banco
        self._memoria = None
        if banco is None:
            self._memoria = sqlite3.connect(":memory:", check_same_thread=False)
            self._criar(self._memoria)
        else:
            banco.parent.mkdir(parents=True, exist_ok=True)
            with self._conectar() as conexao:
                self._criar(conexao)

    def _conectar(self) -> sqlite3.Connection:
        if self._memoria is not None:
            return self._memoria
        return sqlite3.connect(self._banco)

    def _fechar(self, conexao: sqlite3.Connection) -> None:
        if self._memoria is None:
            conexao.close()

    def _criar(self, conexao: sqlite3.Connection) -> None:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS encaminhamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta TEXT NOT NULL,
                fluxo TEXT NOT NULL,
                resumo TEXT
            )
            """
        )
        conexao.commit()

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        conexao = self._conectar()
        try:
            conexao.execute(
                "INSERT INTO encaminhamentos (pergunta, fluxo, resumo) VALUES (?, ?, ?)",
                (pergunta, fluxo, resumo),
            )
            conexao.commit()
        finally:
            self._fechar(conexao)

    def listar(self) -> list[dict]:
        conexao = self._conectar()
        try:
            linhas = conexao.execute(
                "SELECT id, pergunta, fluxo, resumo FROM encaminhamentos ORDER BY id"
            ).fetchall()
        finally:
            self._fechar(conexao)
        return [
            {"id": linha[0], "pergunta": linha[1], "fluxo": linha[2], "resumo": linha[3]}
            for linha in linhas
        ]

    def remover(self, item_id: int) -> None:
        conexao = self._conectar()
        try:
            cursor = conexao.execute(
                "DELETE FROM encaminhamentos WHERE id = ?", (item_id,)
            )
            conexao.commit()
            if cursor.rowcount == 0:
                raise KeyError(item_id)
        finally:
            self._fechar(conexao)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest tests/test_fila.py tests/test_atendimento.py tests/test_api.py -q`

Expected: those tests pass. `Fila()` sem caminho continua isolada.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/fila.py tests/test_fila.py
git commit -m "feat: store handoffs in sqlite"
```

---

### Task 2: Atendimento recebe o caminho

**Files:**
- Modify: `app/atendimento.py`
- Modify: `tests/test_atendimento.py`

**Interfaces:**
- Consumes: `Fila(banco: Path | None = None)`
- Produces: `Atendimento(classificar_fn, base, banco: Path | None = None)`. Sem o terceiro argumento, o comportamento dos testes atuais permanece

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_atendimento.py`:

```python
def test_mesmo_banco_sobrevive_entre_atendimentos(tmp_path) -> None:
    banco = tmp_path / "fila.sqlite"
    primeiro = Atendimento(classificar, BaseSempreHumano(), banco)
    primeiro.responder("quando vence meu contrato?")
    primeiro.concluir(1)
    segundo = Atendimento(classificar, BaseSempreHumano(), banco)
    segundo.responder("quero uma proposta")
    assert segundo.encaminhamentos() == [
        {
            "id": 2,
            "pergunta": "quero uma proposta",
            "fluxo": "venda",
            "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base.",
        }
    ]
```

Não alterar os testes que constroem `Atendimento` com dois argumentos.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py::test_mesmo_banco_sobrevive_entre_atendimentos -v`

Expected: FAIL because `Atendimento` does not accept a third argument.

- [ ] **Step 3: Write minimal implementation**

Em `app/atendimento.py`, mudar o construtor para:

```python
    def __init__(self, classificar_fn, base, banco=None) -> None:
        self._classificar = classificar_fn
        self._base = base
        self._fila = Fila(banco)
```

`responder`, `encaminhamentos` e `concluir` ficam como estão.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/atendimento.py tests/test_atendimento.py
git commit -m "feat: let the answer service open a sqlite file"
```

---

### Task 3: A API abre o arquivo

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api.py`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Atendimento(classificar_fn, base, banco)`
- Produces: `criar_app_de_arquivo(caminho: Path, banco: Path | None = None)`. O `app` do módulo usa `data/atendeia.sqlite`

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_api.py`:

```python
def test_dois_apps_no_mesmo_banco_compartilham_a_lista(tmp_path) -> None:
    banco = tmp_path / "fila.sqlite"
    um = TestClient(criar_app_de_arquivo(ARQUIVO, banco))
    outro = TestClient(criar_app_de_arquivo(ARQUIVO, banco))
    um.post("/v1/perguntas", json={"pergunta": "quero uma proposta"})
    outro.delete("/v1/encaminhamentos/1")
    um.post("/v1/perguntas", json={"pergunta": "quero falar sobre o clima"})
    assert outro.get("/v1/encaminhamentos").json() == [
        {
            "id": 2,
            "pergunta": "quero falar sobre o clima",
            "fluxo": "desconhecido",
            "resumo": "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base.",
        }
    ]
```

Não alterar `test_duas_apps_nao_compartilham_a_lista`. Ele continua chamando `criar_app_de_arquivo` sem banco.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api.py::test_dois_apps_no_mesmo_banco_compartilham_a_lista -v`

Expected: FAIL because `criar_app_de_arquivo` does not accept the second argument.

- [ ] **Step 3: Write minimal implementation**

Em `app/api.py`:

```python
def criar_app_de_arquivo(caminho: Path, banco: Path | None = None) -> FastAPI:
    base = BaseConhecimento(caminho)
    return criar_app(Atendimento(classificar, base, banco))


app = criar_app_de_arquivo(
    Path(__file__).resolve().parents[1] / "data" / "vertice_ti.json",
    Path(__file__).resolve().parents[1] / "data" / "atendeia.sqlite",
)
```

Em `.gitignore`, acrescentar a linha `data/*.sqlite`.

No README, depois da frase do `DELETE`, acrescentar:

A lista fica em `data/atendeia.sqlite` e continua depois de reiniciar o processo. Esse arquivo não entra no Git.

Não alterar o exemplo JSON de três campos. Não alterar as páginas.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. `test_duas_apps_nao_compartilham_a_lista` continua verde porque não recebe arquivo.

- [ ] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add app/api.py tests/test_api.py .gitignore README.md
git commit -m "feat: keep the handoff list in a sqlite file"
```
