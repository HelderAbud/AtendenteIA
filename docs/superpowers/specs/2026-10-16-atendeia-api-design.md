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

- WhatsApp, Instagram e Telegram. O recorte 2 acrescenta uma única página em `GET /`.
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

Resposta `200` do recorte 1, antes do fluxo:

```json
{
  "tema": "prazo",
  "resposta": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
  "encaminhar_humano": false
}
```

A partir do recorte 2 a resposta vigente tem cinco campos. O contrato está na seção Recorte 2.

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

## Recorte 2

O recorte 1 permanece. O classificador de tema não muda. `data/vertice_ti.json` não ganha campo. `GET /health`, o `422` e a recusa de subir sem a base continuam iguais. O nome do tema de chamado continua `chamado`.

A resposta de `POST /v1/perguntas` passa a ter sempre cinco campos: `tema`, `resposta`, `encaminhar_humano`, `fluxo` e `resumo`.

Suporte, quando a base responde:

```json
{
  "tema": "prazo",
  "resposta": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
  "encaminhar_humano": false,
  "fluxo": "suporte",
  "resumo": null
}
```

Venda, pedido de contrato novo sem tema na base:

```json
{
  "tema": "desconhecido",
  "resposta": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
  "encaminhar_humano": true,
  "fluxo": "venda",
  "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
}
```

Fora da base e sem sinal de venda:

```json
{
  "tema": "desconhecido",
  "resposta": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
  "encaminhar_humano": true,
  "fluxo": "desconhecido",
  "resumo": "Pergunta: quero falar sobre o clima. Motivo: assunto fora da base."
}
```

Regras, nesta ordem:

1. O tema sai do classificador atual. O fluxo é decidido depois.
2. Tema `prazo`, `sla`, `renovacao`, `boleto` ou `chamado` define `fluxo` `suporte` e `resumo` nulo. Vale mesmo que a frase contenha um sinal de venda.
3. Tema `desconhecido` com um sinal de venda define `fluxo` `venda`. Os sinais, já normalizados como no classificador, são `contratar`, `proposta`, `orcamento`, `licenca` e `fechar`. Cada um conta se aparecer como trecho.
4. Qualquer outro texto define `fluxo` `desconhecido`.
5. `resumo` é nulo quando o fluxo é `suporte`. Nos outros fluxos o texto é `Pergunta: {pergunta original}. Motivo: {motivo}.` O motivo de venda é `venda sem resposta na base`. O motivo desconhecido é `assunto fora da base`. A pergunta no resumo é o texto recebido, sem normalizar.
6. `encaminhar_humano` continua copiado da base. Na base real, venda e desconhecido usam o tema `desconhecido`, cuja flag é verdadeira.

`GET /` entrega uma página com um campo, a resposta e o resumo quando ele não for nulo. A página chama `POST /v1/perguntas`. Neste recorte não há fila. Login e WhatsApp continuam fora.

Os testes que comparam o JSON inteiro passam a esperar `fluxo` e `resumo`. Há teste novo para `quero uma proposta` e para `GET /`.

## Recorte 3

Os recortes 1 e 2 permanecem. Classificador, `data/vertice_ti.json`, fluxo, resumo, `GET /`, `GET /health` e o `422` não mudam de regra. Não há banco, login, WhatsApp nem modelo de linguagem.

`POST /v1/perguntas` continua devolvendo os cinco campos. Quando `encaminhar_humano` é verdadeiro, a mesma chamada guarda um item na lista em memória do processo. Flag falsa não entra, mesmo que a frase tenha sinal de venda. A flag continua copiada da base: o teste com base falsa pode ter fluxo `venda` e lista vazia.

`GET /v1/encaminhamentos` devolve a lista, na ordem de chegada. Lista vazia é `[]`. Cada item tem só três campos:

```json
[
  {
    "pergunta": "quero uma proposta",
    "fluxo": "venda",
    "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
  }
]
```

`resumo` no item pode ser nulo quando a base força a flag verdadeira num tema de suporte. A pergunta guardada é o texto recebido, sem normalizar. Pergunta inválida não entra na lista. `GET /health` não lê a base nem a lista. Dois processos não compartilham a lista: ao reiniciar, ela volta a `[]`. A página em `GET /` não muda.

## Recorte 4

Os recortes 1, 2 e 3 permanecem. A lista, os cinco campos, o classificador, `data/vertice_ti.json`, `GET /`, `GET /health` e o `422` não mudam de regra. Não há banco, login, WhatsApp nem modelo de linguagem. Nenhum item ganha campo novo.

`GET /atendente` entrega uma página que lê `GET /v1/encaminhamentos` e mostra os itens na ordem recebida. Cada item aparece com a pergunta, o fluxo e o resumo. Resumo nulo aparece vazio. Lista vazia mostra o texto `Nenhum encaminhamento.` A página não grava nada e não lê a base. `GET /` continua sendo a página da pergunta.
