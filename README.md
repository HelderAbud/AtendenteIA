# AtendeIA

API de perguntas de contrato da empresa fictícia Vértice TI. Não há cliente real, banco nem modelo de linguagem.

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

```powershell
.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

GET http://127.0.0.1:8000/ abre a página da pergunta.

GET http://127.0.0.1:8000/v1/encaminhamentos devolve a lista em memória das perguntas com encaminhar humano verdadeiro. Ela começa vazia e some ao reiniciar o processo.

GET http://127.0.0.1:8000/atendente abre a página do atendente.

`DELETE http://127.0.0.1:8000/v1/encaminhamentos/{id}` tira esse item da lista. Id ausente devolve 404.

A lista fica em `data/atendeia.sqlite` e continua depois de reiniciar o processo. Esse arquivo não entra no Git.

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
