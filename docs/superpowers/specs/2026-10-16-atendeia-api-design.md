# AtendeIA — API de perguntas de contrato

Recorte 1. Empresa fictícia: Vértice TI. Sem cliente real e sem dado pessoal.

## Problem

Uma empresa de contrato de tecnologia perde tempo repetindo prazo, SLA, renovação, boleto e status de chamado. Este recorte entrega uma API que responde essas cinco perguntas a partir de uma base fixa, com testes que não dependem de internet.

## Scope

- API HTTP em Python (FastAPI).
- Quatro peças: API, atendimento, classificador e base.
- Base em arquivo versionado `data/vertice_ti.json`.
- Classificador determinístico por sinais.
- Testes de classificador, atendimento e API.

## Out of scope

- WhatsApp, Instagram, Telegram e site.
- Painel do atendente, login e cadastro de cliente.
- Modelo de linguagem, RAG e PDF.
- PIX, boleto real, planilha, e-mail e CRM.
- Agentes separados de venda e de suporte.
- Análise jurídica do texto do contrato.

Esses itens ficam para recortes seguintes, atrás da mesma ideia de API.

## Decisions

- Produto: AtendeIA. Pasta: `AtendenteIA`.
- Stack deste recorte: Python 3.11+, FastAPI, pytest. Sem banco.
- A API depende só do atendimento. O atendimento depende do classificador e da base. Nos testes, a base é trocada sem subir servidor.
- Tema desconhecido é regra de negócio: HTTP 200 e `encaminhar_humano: true`.
- Pergunta inválida é validação: HTTP 422 e corpo `{ "erro": "pergunta_invalida" }`.
- O nome do tema de chamado é `chamado`.
- Números e frases prontas (12 meses, 4 horas, 99,5%, renovação automática) ficam só no texto da resposta. Não entram como sinal.

## Architecture

| Peça | Função | Depende de |
|---|---|---|
| API | Recebe HTTP e devolve JSON | Atendimento |
| Atendimento | Classifica, busca a resposta e monta o JSON | Classificador e base |
| Classificador | Escolhe um tema a partir do texto | Nada |
| Base | Lê o arquivo da Vértice TI | Arquivo JSON |

Arquivos:

```text
app/api.py
app/atendimento.py
app/classificador.py
app/base.py
data/vertice_ti.json
tests/test_classificador.py
tests/test_atendimento.py
tests/test_api.py
```

## API

`GET /health` → `200` `{ "status": "ok" }`. Não lê a base.

`POST /v1/perguntas`

Pedido:

```json
{ "pergunta": "quando vence meu contrato?" }
```

Resposta `200`:

```json
{
  "tema": "prazo",
  "resposta": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
  "encaminhar_humano": false
}
```

`pergunta` ausente, nula, de outro tipo, vazia ou só com espaços → `422` `{ "erro": "pergunta_invalida" }`.

## Classifier

1. Minúsculas.
2. Remover acentos.
3. Juntar espaços repetidos.
4. Cada sinal soma 1 ponto se aparecer como trecho do texto já normalizado. Cada sinal conta uma vez.
5. Vence o tema com pontuação única e maior. Empate ou zero → `desconhecido`.

| Tema | Sinais |
|---|---|
| `prazo` | prazo, vence, vencer, vigencia, termina, vencimento |
| `sla` | sla, disponibilidade, primeira resposta, tempo de resposta |
| `renovacao` | renova, renovacao, renovar |
| `boleto` | boleto, segunda via, pagar, pagamento |
| `chamado` | chamado, ticket, status, andamento |

Exemplos fechados:

| Pergunta | Tema |
|---|---|
| quando vence meu contrato? | `prazo` |
| VIGÊNCIA do suporte | `prazo` |
| qual é o sla? | `sla` |
| como faco a renovacao? | `renovacao` |
| preciso da segunda via do boleto | `boleto` |
| qual o status do chamado? | `chamado` |
| quero falar sobre o clima | `desconhecido` |
| vence o boleto | `desconhecido` |

`vence o boleto` empata `prazo` e `boleto` com 1 ponto cada.

## Knowledge base

`data/vertice_ti.json` tem as chaves `prazo`, `sla`, `renovacao`, `boleto`, `chamado` e `desconhecido`. Cada chave tem `resposta` (texto não vazio) e `encaminhar_humano` (booleano). Nos cinco temas de negócio o booleano é `false`. Em `desconhecido` é `true`.

Textos:

- `prazo`: O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.
- `sla`: A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.
- `renovacao`: A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.
- `boleto`: O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.
- `chamado`: O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.
- `desconhecido`: Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.

Se o arquivo não existir na subida, ou faltar chave, texto ou booleano, a API não inicia.

## Acceptance criteria

- Cada pergunta da tabela de exemplos devolve o tema indicado.
- Nos cinco temas de negócio, `encaminhar_humano` é `false` e a resposta é o texto da base.
- Tema desconhecido devolve `200`, o texto de `desconhecido` e `encaminhar_humano: true`.
- Pergunta inválida devolve `422` e `{ "erro": "pergunta_invalida" }`.
- `GET /health` devolve `200` e `{ "status": "ok" }` sem consultar a base.
- Atendimento com base substituída devolve o texto dessa base.
- Arquivo da base ausente impede a subida da API.

## Risks

- Sinais por trecho podem pontuar uma palavra dentro de outra. A lista deste recorte foi escolhida para as oito perguntas fechadas; sinal novo precisa de teste novo.
- A base é institucional e igual para toda pergunta. Não consulta contrato de um cliente específico.
- Trocar o texto da Vértice TI exige atualizar o teste que fixa esse texto.

## Verification

Na pasta do projeto, com o ambiente Python desta máquina:

```text
pytest
```

Os testes cobrem classificador, atendimento com base trocada e a API (perguntas, validação e saúde). Não há chamada de rede.
