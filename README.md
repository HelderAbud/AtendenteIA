# AtendeIA

API de perguntas de contrato da empresa fictícia Vértice TI. Não há cliente real nem modelo de linguagem.

Quatro peças: a API recebe HTTP, o atendimento liga o classificador à base, o classificador escolhe o tema e a base lê `data/vertice_ti.json`.

Temas: `prazo`, `sla`, `renovacao`, `boleto` e `chamado`. Empate ou nenhum sinal vira `desconhecido`.

## Requisitos

Python 3.11 ou mais novo.

## Instalar e testar

Na raiz do projeto:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -v
```

## Subir localmente

O Postgres sobe no Ubuntu, na raiz do projeto, com `docker compose up -d`. A porta no host é 5437. A variável `ATENDEIA_DATABASE_URL` está em `.env.example`.

```powershell
.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

GET http://127.0.0.1:8000/ abre a página da pergunta.

GET http://127.0.0.1:8000/v1/encaminhamentos devolve a lista das perguntas com encaminhar humano verdadeiro.

GET http://127.0.0.1:8000/atendente abre a página do atendente.

`DELETE http://127.0.0.1:8000/v1/encaminhamentos/{id}` tira esse item da lista. Id ausente devolve 404.

Com `ATENDEIA_DATABASE_URL`, a lista fica no Postgres e continua depois de reiniciar o processo. Sem essa variável, a lista fica só no processo e some ao reiniciar.

Com `ATENDEIA_SENHA` e `ATENDEIA_SESSION_SECRET`, a página do atendente, a lista e o `DELETE` pedem entrada em `/login`. Sem uma das duas, essas rotas continuam abertas.

`POST /v1/whatsapp` recebe `{ "texto": "..." }` e devolve a mesma resposta de `POST /v1/perguntas`. O encaminhamento entra na mesma lista. Esta rota não envia mensagem para fora.

`GET http://127.0.0.1:8000/health`

```json
{ "status": "ok" }
```

`POST http://127.0.0.1:8000/v1/perguntas`

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

Pergunta ausente, nula, de outro tipo ou em branco devolve `422` com `{ "erro": "pergunta_invalida" }`. Tema desconhecido devolve `200` com `encaminhar_humano` verdadeiro.

## Fora deste recorte

WhatsApp, painel, modelo de linguagem, PDF e planilha.
