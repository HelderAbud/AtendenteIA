# AtendeIA README Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O rodapé do README deixa de tratar WhatsApp e painel como ausentes.

**Architecture:** Uma frase em `README.md`. Nenhuma rota, página ou teste muda. O exemplo JSON de três campos permanece.

**Tech Stack:** Markdown. Nenhum comando de teste é a prova desta tarefa.

## Global Constraints

- Trocar só a frase sob `## Fora deste recorte`.
- A frase nova é: `Modelo de linguagem, PDF, planilha e modelo de mensagem pronta.`
- O título da seção permanece.
- O exemplo JSON de três campos permanece, com `tema`, `resposta` e `encaminhar_humano`.
- Não alterar `app/`, `tests/`, `web/`, `.env.example` nem os parágrafos de WhatsApp, login e Postgres.
- Commit só quando o usuário pedir nesta sessão. O desenho entra nesse commit.

---

### Task 1: Atualizar o que fica de fora

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-10-16-atendeia-api-design.md`
- Modify: `docs/superpowers/plans/2026-10-23-atendeia-readme-fora.md`

- [ ] **Step 1: Confirm the current footer**

A seção termina assim:

```markdown
## Fora deste recorte

WhatsApp, painel, modelo de linguagem, PDF e planilha.
```

- [ ] **Step 2: Replace that sentence only**

```markdown
## Fora deste recorte

Modelo de linguagem, PDF, planilha e modelo de mensagem pronta.
```

- [ ] **Step 3: Check the file**

Confirmar que o título `## Fora deste recorte` continua, que a frase nova está no lugar da antiga, e que o exemplo JSON ainda tem só `tema`, `resposta` e `encaminhar_humano`. Não rodar a suíte: nenhum comportamento mudou.

- [ ] **Step 4: Commit**

Só executar se o usuário pedir commit nesta sessão.

```powershell
git add README.md docs/superpowers/specs/2026-10-16-atendeia-api-design.md docs/superpowers/plans/2026-10-23-atendeia-readme-fora.md
git commit -m "docs: list what stays out of the readme"
```
