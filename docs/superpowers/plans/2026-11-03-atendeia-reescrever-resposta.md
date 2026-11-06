# AtendeIA Reescrever Resposta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma função opcional reescreve só o texto que a base já devolveu. Tema, fluxo, resumo, encaminhamento e a lista permanecem.

**Architecture:** `Atendimento.responder` continua classificando, lendo a base, decidindo o fluxo e gravando a lista. Depois disso, se `reescrever` existir, ela recebe o texto da base e o campo `resposta` pode mudar. Sem a função, o texto da base segue intacto. O processo não chama modelo nenhum.

**Tech Stack:** Python 3.14, pytest. Nenhuma dependência nova.

## Global Constraints

- `reescrever` é opcional e recebe só a `str` da base.
- O retorno entra em `resposta` só quando é uma `str` com conteúdo depois de `strip`. O valor usado é o retorno inteiro.
- Retorno em branco, de outro tipo ou exceção mantém o texto da base. A exceção avisa `falha ao reescrever a resposta` no logger `atendeia`.
- Tema, `encaminhar_humano`, `fluxo`, `resumo` e a lista não passam pela função. A lista é gravada mesmo se a reescrita falhar.
- Não criar rota, página, variável de ambiente, cliente HTTP nem dependência.
- Não alterar o classificador, `data/vertice_ti.json`, as páginas, o exemplo JSON de três campos nem o rodapé do README.
- `criar_app_de_arquivo` continua chamando `Atendimento(classificar, base, banco, postgres_url)`.
- Commit só quando o usuário pedir nesta sessão. O desenho entra no primeiro commit do recorte.

---

### Task 1: Reescrever só o texto da base

**Files:**
- Modify: `app/atendimento.py`
- Modify: `tests/test_atendimento.py`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-11-03-atendeia-reescrever-resposta.md`

**Interfaces:**
- Consumes: `classificar`, `base.obter`, `decidir_fluxo`, `montar_resumo`
- Produces: `Atendimento(..., reescrever=None)`

- [x] **Step 1: Write the failing test**

Acrescentar em `tests/test_atendimento.py`:

```python
def test_reescreve_so_o_texto_da_base() -> None:
    atendimento = Atendimento(
        classificar,
        BaseSempreHumano(),
        reescrever=lambda texto: f"novo {texto}",
    )
    assert atendimento.responder("quando vence meu contrato?") == {
        "tema": "prazo",
        "resposta": "novo da base",
        "encaminhar_humano": True,
        "fluxo": "suporte",
        "resumo": None,
    }
    assert atendimento.encaminhamentos() == [
        {
            "id": 1,
            "pergunta": "quando vence meu contrato?",
            "fluxo": "suporte",
            "resumo": None,
        }
    ]


def test_reescrever_que_falha_mantem_o_texto_da_base(caplog) -> None:
    def reescrever(texto: str) -> str:
        raise RuntimeError("modelo")

    atendimento = Atendimento(
        classificar, BaseSempreHumano(), reescrever=reescrever
    )
    with caplog.at_level("WARNING", logger="atendeia"):
        resposta = atendimento.responder("quando vence meu contrato?")
    assert resposta["resposta"] == "da base"
    assert resposta["tema"] == "prazo"
    assert len(atendimento.encaminhamentos()) == 1
    assert "falha ao reescrever a resposta" in caplog.text


def test_reescrever_vazio_ou_de_outro_tipo_mantem_o_texto_da_base() -> None:
    for retorno in ("   ", None, 12):
        atendimento = Atendimento(
            classificar,
            BaseFalsa(),
            reescrever=lambda texto, valor=retorno: valor,
        )
        assert (
            atendimento.responder("quando vence meu contrato?")["resposta"]
            == "texto-prazo"
        )
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_atendimento.py::test_reescreve_so_o_texto_da_base -v`

Expected: FAIL with `TypeError`, because `Atendimento` ainda não aceita `reescrever`.

- [x] **Step 3: Write minimal implementation**

Em `app/atendimento.py`, importar `logging`, criar `logger = logging.getLogger("atendeia")` e acrescentar `reescrever=None` no fim de `__init__`. Guardar em `self._reescrever`.

Em `responder`, gravar a lista como hoje e usar `self._texto(item["resposta"])` no campo `resposta`.

```python
def _texto(self, resposta: str) -> str:
    if self._reescrever is None:
        return resposta
    try:
        nova = self._reescrever(resposta)
    except Exception:
        logger.warning("falha ao reescrever a resposta")
        return resposta
    if isinstance(nova, str) and nova.strip():
        return nova
    return resposta
```

Não alterar `app/api.py`, o README, o classificador nem a base.

- [x] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: the full suite passes. If a Postgres test is skipped, subir o banco no Ubuntu na porta 5437 e rodar de novo.

- [x] **Step 5: Commit**

Só executar se o usuário pedir commit nesta sessão. Incluir o desenho deste recorte.

```powershell
git add app/atendimento.py tests/test_atendimento.py docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-11-03-atendeia-reescrever-resposta.md
git commit -m "feat: rewrite only the base answer text"
```
