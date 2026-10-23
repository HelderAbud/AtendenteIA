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

## Recorte 5

Os recortes 1 a 4 permanecem, com uma mudança na lista: cada item ganha `id`. Não há banco, login, WhatsApp nem modelo de linguagem. A lista continua em memória e some ao reiniciar. O banco e o WhatsApp ficam para os recortes seguintes, nessa ordem.

O `id` é um inteiro que começa em 1. Cada registro novo soma 1. Um `id` removido não volta a ser usado no mesmo processo. `GET /v1/encaminhamentos` passa a devolver quatro campos, nesta ordem de chaves no teste: `id`, `pergunta`, `fluxo`, `resumo`.

```json
[
  {
    "id": 1,
    "pergunta": "quero uma proposta",
    "fluxo": "venda",
    "resumo": "Pergunta: quero uma proposta. Motivo: venda sem resposta na base."
  }
]
```

`DELETE /v1/encaminhamentos/{id}` remove só esse item e devolve `204` sem corpo. `id` inteiro que não está na lista devolve `404` `{ "erro": "encaminhamento_inexistente" }`. A rota não lê a base. `POST /v1/perguntas` continua com os cinco campos e não devolve o `id`.

A página `GET /atendente` mostra um botão `Concluir` em cada item. O botão chama o `DELETE` daquele `id` e tira o item da tela. Se não sobrar item, a página volta a mostrar `Nenhum encaminhamento.`

## Recorte 6

Os recortes 1 a 5 permanecem na resposta HTTP. A lista deixa de morar só na memória e passa para um arquivo SQLite. Não há Postgres, login, WhatsApp nem modelo de linguagem neste recorte.

Depois deste recorte, a ordem é esta: Postgres, com a mesma tabela saindo do arquivo; login, em que a página do atendente e o `DELETE` passam a exigir sessão; WhatsApp, usando a mesma resposta e a mesma lista.

A tabela `encaminhamentos` tem `id` inteiro gerado pelo SQLite com `AUTOINCREMENT`, `pergunta`, `fluxo` e `resumo`. O `id` começa em 1 e não volta a ser usado, nem depois de apagar a linha e nem depois de reiniciar. `resumo` nulo fica `NULL` no arquivo e volta `None` na lista. A ordem da lista é a ordem do `id`.

O arquivo de operação é `data/atendeia.sqlite`. Ele não entra no Git. Sem caminho, a fila usa um SQLite só daquele objeto, e dois objetos não se veem. Com o mesmo caminho, dois objetos e dois processos veem as mesmas linhas. Fechar o objeto e abrir outro no mesmo arquivo devolve as linhas gravadas.

`GET /v1/encaminhamentos`, `DELETE /v1/encaminhamentos/{id}`, o `204`, o `404`, os cinco campos do `POST` e as duas páginas não mudam de contrato. `GET /health` continua sem ler a base de conhecimento. O `DELETE` de id ausente continua sem ler essa base.

## Recorte 7

Os recortes 1 a 6 permanecem na resposta HTTP. A lista de operação sai de `data/atendeia.sqlite` e passa para o Postgres, na mesma tabela `encaminhamentos`: `id`, `pergunta`, `fluxo` e `resumo`. Login, WhatsApp e modelo de linguagem continuam fora.

O `id` é `BIGINT GENERATED BY DEFAULT AS IDENTITY`. Começa em 1 e não volta a ser usado, nem depois de apagar a linha e nem depois de abrir outra conexão. `resumo` nulo fica `NULL` e volta `None`. A ordem da lista é a ordem do `id`.

A fila SQLite permanece para os testes que não recebem URL: sem caminho, cada objeto tem a lista só na memória; com caminho de arquivo, o SQLite continua valendo. A URL do Postgres é outro argumento. Se ela vier preenchida, a lista é o Postgres e o caminho de arquivo é ignorado. Duas filas, dois atendimentos ou dois apps na mesma URL veem as mesmas linhas. Fechar o objeto e abrir outro na mesma URL devolve as linhas gravadas.

A variável é `ATENDEIA_DATABASE_URL`. O valor local é `postgresql://atendeia:atendeia@127.0.0.1:5437/atendeia`. A senha fica no `.env`, que não entra no Git. O exemplo versionado é `.env.example`. O Postgres sobe no Ubuntu, com Docker, pela porta do host **5437**. O serviço PostgreSQL 18 do Windows, na porta 5432, não é o banco deste projeto. A API continua na porta 8000.

Sem a variável, o `app` do módulo não abre `data/atendeia.sqlite`: a lista fica só naquele processo e some ao reiniciar. Com a variável, a API cria a tabela na subida, se ela ainda não existir, e a lista continua depois de reiniciar. Se o Postgres estiver parado, a API não sobe.

`GET /health` continua `{ "status": "ok" }` e não consulta o banco. O `POST` continua com os cinco campos e sem `id`. O `DELETE` ausente continua `404` sem ler a base de conhecimento. O exemplo JSON de três campos no README permanece como está. A frase do README que ainda aponta a lista para o arquivo SQLite é atualizada neste recorte.

## Recorte 8

Os recortes 1 a 7 permanecem na resposta do cliente. WhatsApp e modelo de linguagem continuam fora. Não há cadastro, segundo usuário, papel nem tabela de login. A senha é de um único atendente e não entra no Git.

O portão liga só quando a fábrica recebe os dois valores, `senha` e `session_secret`. No processo, eles vêm de `ATENDEIA_SENHA` e `ATENDEIA_SESSION_SECRET`. Vazio conta como ausente. Se faltar um dos dois, `GET /`, `POST /v1/perguntas`, `GET /atendente`, a lista e o `DELETE` continuam como no recorte 7. Os testes que não passam senha permanecem verdes.

Com os dois valores:

- `GET /login` devolve o formulário. O campo é `senha` e o botão é `Entrar`.
- `POST /login` com a senha certa grava a sessão e responde `303` para `/atendente`. A sessão só marca que o atendente entrou. A senha não fica no cookie.
- Senha errada responde `401`, mostra `Senha recusada.` e não cria sessão.
- `GET /atendente` sem sessão responde `303` para `/login`. Com sessão, devolve a página que já existe.
- `GET /v1/encaminhamentos` e `DELETE /v1/encaminhamentos/{id}` sem sessão respondem `401` `{ "erro": "sessao_ausente" }` e não leem a base de conhecimento. O `GET` entra no portão porque a página do atendente lê essa lista.
- Com sessão, o `DELETE` continua `204` sem corpo, e o id ausente continua `404` `{ "erro": "encaminhamento_inexistente" }` sem ler a base.

`GET /`, `POST /v1/perguntas` e `GET /health` não pedem sessão. O `POST` continua com os cinco campos e sem `id`. A página `web/atendente.html` não muda: o navegador manda o cookie na mesma origem. O exemplo JSON de três campos no README permanece.

## Recorte 9

Os recortes 1 a 8 permanecem. O WhatsApp usa o mesmo atendimento, a mesma resposta e a mesma lista. Não há segunda fila, segundo classificador nem modelo de linguagem. Este recorte não envia mensagem para a API da Meta, não guarda telefone e não cria webhook de verificação.

`POST /v1/whatsapp` recebe `{ "texto": "..." }`. O corpo da resposta é o mesmo que `POST /v1/perguntas` devolveria para esse texto: `tema`, `resposta`, `encaminhar_humano`, `fluxo` e `resumo`. O `id` não volta nessa resposta.

Texto vazio, só com espaços, ausente ou de outro tipo responde `422` `{ "erro": "pergunta_invalida" }` e não entra na lista.

Quando a base pede humano, o texto entra na mesma lista, com o próximo `id`. Uma pergunta na rota antiga e um texto no WhatsApp compartilham a fila e a ordem de chegada. A `pergunta` gravada é o texto recebido.

A rota não pede sessão. Com o portão ligado, a lista e o `DELETE` continuam pedindo. `GET /health` continua sem ler a base. As páginas não mudam. O exemplo JSON de três campos no README permanece.

## Recorte 10

Os recortes 1 a 9 permanecem. O `POST /v1/whatsapp` passa a poder devolver a mesma `resposta` para quem escreveu. Não há webhook de verificação, modelo de mensagem pronta nem modelo de linguagem. O telefone não entra na lista.

O corpo ganha `de`, opcional. Sem `de`, ou com `de` vazio, a rota continua só devolvendo os cinco campos. Com `de` preenchido e com a função de envio configurada, a API envia o texto da `resposta` para esse destino e ainda devolve os cinco campos, sem `id`.

Texto inválido continua `422` `{ "erro": "pergunta_invalida" }`, não entra na lista e não dispara envio.

Se o envio falha, a resposta HTTP é `502` `{ "erro": "envio_falhou" }`. O encaminhamento que a base já tiver pedido permanece na lista.

No processo, o envio existe quando `ATENDEIA_WHATSAPP_TOKEN` e `ATENDEIA_WHATSAPP_PHONE_ID` vêm preenchidos. Vazio conta como ausente. Faltando um dos dois, não há chamada para fora. A chamada é `POST https://graph.facebook.com/v26.0/{phone_id}/messages`, com o token no cabeçalho `Authorization` e o corpo de texto da Cloud API. O texto enviado é a `resposta`, não o resumo.

A rota continua sem sessão. As páginas e o exemplo JSON de três campos não mudam.

## Recorte 11

Os recortes 1 a 10 permanecem. A Meta passa a chamar a API. O texto entra no mesmo atendimento e na mesma lista. A `resposta` volta pelo envio que já existe. Não há modelo de mensagem pronta nem modelo de linguagem. O telefone não entra na lista. A assinatura `X-Hub-Signature-256` e o segredo do aplicativo ficam fora: sem esses valores, quem alcançar a URL consegue postar um aviso no formato da Meta.

`POST /v1/whatsapp` não muda. O aviso da Meta usa outro caminho, `GET` e `POST` em `/v1/whatsapp/webhook`. As duas rotas não pedem sessão.

`GET /v1/whatsapp/webhook` confirma a URL. A confirmação só sai quando `verificar_token` vem preenchido, `hub.mode` é `subscribe`, `hub.verify_token` é igual a esse valor e `hub.challenge` tem texto. A resposta é `200`, o corpo é o challenge em texto puro e o atendimento não é chamado. Qualquer outro caso responde `403` `{ "erro": "verificacao_recusada" }`, sem ler a base. No processo, o valor vem de `ATENDEIA_WHATSAPP_VERIFY_TOKEN`. Vazio conta como ausente.

`POST /v1/whatsapp/webhook` lê a primeira mensagem com `type` igual a `text` e com `text.body` preenchido, na ordem do JSON. O corpo segue para o mesmo atendimento. O campo `from`, se vier preenchido, é o destino do envio. A `resposta` enviada é a do atendimento, não o resumo. A rota devolve `200` com corpo vazio, também quando o envio falha. O encaminhamento que a base já tiver pedido permanece. A rota antiga continua respondendo `502` `{ "erro": "envio_falhou" }` na falha de envio.

Aviso sem essa mensagem de texto, texto só com espaços, JSON inválido ou corpo vazio devolve `200` vazio, não chama o atendimento e não envia. Uma segunda mensagem de texto no mesmo aviso não é respondida. `GET /health` continua sem ler a base. As páginas e o exemplo JSON de três campos não mudam.

## Recorte 12

Os recortes 1 a 11 permanecem. O `POST /v1/whatsapp/webhook` passa a poder exigir a assinatura da Meta. Não há modelo de mensagem pronta nem modelo de linguagem. O telefone não entra na lista.

O argumento é `app_secret`. No processo, ele vem de `ATENDEIA_WHATSAPP_APP_SECRET`. Vazio conta como ausente. Sem o segredo, o `POST` continua como no recorte 11, inclusive sem o cabeçalho.

Com o segredo preenchido, a conferência acontece no corpo cru, antes de ler o JSON e antes do atendimento. O cabeçalho é `X-Hub-Signature-256`. O valor tem de ser `sha256=` seguido do HMAC-SHA256 desse corpo, em hexadecimal, calculado com o segredo. A comparação não vaza o segredo por diferença de tempo. Assinatura ausente, prefixo errado ou digest errado responde `403` `{ "erro": "assinatura_recusada" }`, não chama o atendimento e não envia.

Com a assinatura certa, vale o recorte 11: a primeira mensagem de texto entra no mesmo atendimento, a `resposta` segue pelo envio que já existe, o telefone não entra na lista e a rota devolve `200` vazio. Corpo vazio ou JSON inválido com assinatura certa continua `200` vazio, sem atendimento. O `GET` do challenge não usa essa assinatura. `POST /v1/whatsapp` não muda e a falha de envio dessa rota continua `502`.

A rota continua sem sessão. As páginas e o exemplo JSON de três campos não mudam.

## Recorte 13

Os recortes 1 a 12 permanecem. Nenhuma rota, página ou teste muda. O exemplo JSON de três campos no README permanece.

A seção `Fora deste recorte` deixa de citar WhatsApp e painel. A frase passa a ser: modelo de linguagem, PDF, planilha e modelo de mensagem pronta. O título da seção permanece.
