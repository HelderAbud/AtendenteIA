import asyncio
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.requests import Request
from pydantic import BaseModel, field_validator

from app.atendimento import Atendimento
from app.base import BaseConhecimento
from app.classificador import classificar

logger = logging.getLogger("atendeia")
LIMITE_TEXTO = 500
LIMITE_FALHAS = 5


class PerguntaIn(BaseModel):
    pergunta: str

    @field_validator("pergunta")
    @classmethod
    def nao_vazia(cls, valor: str) -> str:
        if not valor.strip() or len(valor) > LIMITE_TEXTO:
            raise ValueError("pergunta_invalida")
        return valor


class TextoIn(BaseModel):
    texto: str
    de: str | None = None

    @field_validator("texto")
    @classmethod
    def nao_vazia(cls, valor: str) -> str:
        if not valor.strip() or len(valor) > LIMITE_TEXTO:
            raise ValueError("pergunta_invalida")
        return valor


PAGINA = Path(__file__).resolve().parents[1] / "web" / "index.html"
ATENDENTE = Path(__file__).resolve().parents[1] / "web" / "atendente.html"


def _html_login(mostrar_erro: bool = False) -> str:
    erro = "<p>Senha recusada.</p>\n" if mostrar_erro else ""
    return (
        f"{erro}<form method=\"post\" action=\"/login\">"
        '<input name="senha" type="password">'
        "<button type=\"submit\">Entrar</button>"
        "</form>"
    )


def _texto_do_webhook(aviso: object) -> tuple[str, str] | None:
    if not isinstance(aviso, dict):
        return None
    for entrada in aviso.get("entry") or []:
        if not isinstance(entrada, dict):
            continue
        for mudanca in entrada.get("changes") or []:
            if not isinstance(mudanca, dict):
                continue
            valor = mudanca.get("value")
            if not isinstance(valor, dict):
                continue
            for mensagem in valor.get("messages") or []:
                if not isinstance(mensagem, dict) or mensagem.get("type") != "text":
                    continue
                texto = mensagem.get("text")
                corpo = texto.get("body") if isinstance(texto, dict) else None
                if not isinstance(corpo, str) or not corpo.strip():
                    continue
                origem = mensagem.get("from")
                destino = origem.strip() if isinstance(origem, str) else ""
                return corpo, destino
    return None


def _assinatura_confere(segredo: str, corpo: bytes, cabecalho: str) -> bool:
    if not cabecalho.startswith("sha256="):
        return False
    digest = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", cabecalho)


def criar_app(
    atendimento: Atendimento,
    senha: str | None = None,
    session_secret: str | None = None,
    enviar=None,
    verificar_token: str | None = None,
    app_secret: str | None = None,
) -> FastAPI:
    app = FastAPI()
    gate = bool(senha and session_secret)

    @app.exception_handler(RequestValidationError)
    async def pergunta_invalida(request, exc: RequestValidationError):
        for erro in exc.errors():
            if "pergunta" in erro.get("loc", ()) or "texto" in erro.get("loc", ()):
                return JSONResponse(
                    status_code=422, content={"erro": "pergunta_invalida"}
                )
        return JSONResponse(status_code=422, content={"erro": "requisicao_invalida"})

    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        return PAGINA.read_text(encoding="utf-8")

    @app.get("/atendente")
    def atendente(request: Request):
        if gate and not request.session.get("atendente"):
            return RedirectResponse("/login", status_code=303)
        return HTMLResponse(ATENDENTE.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/perguntas")
    def perguntas(corpo: PerguntaIn) -> dict:
        return atendimento.responder(corpo.pergunta)

    @app.post("/v1/whatsapp")
    def whatsapp(corpo: TextoIn):
        return atendimento.responder(corpo.texto)

    @app.get("/v1/whatsapp/webhook")
    def whatsapp_verificacao(
        hub_mode: str = Query(default="", alias="hub.mode"),
        hub_verify_token: str = Query(default="", alias="hub.verify_token"),
        hub_challenge: str = Query(default="", alias="hub.challenge"),
    ):
        token = verificar_token or None
        if (
            token
            and hub_mode == "subscribe"
            and hub_verify_token == token
            and hub_challenge.strip()
        ):
            return Response(content=hub_challenge, media_type="text/plain")
        return JSONResponse(status_code=403, content={"erro": "verificacao_recusada"})

    @app.post("/v1/whatsapp/webhook")
    async def whatsapp_webhook(request: Request) -> Response:
        corpo = await request.body()
        segredo = app_secret or None
        if segredo is not None:
            cabecalho = request.headers.get("x-hub-signature-256", "")
            if not _assinatura_confere(segredo, corpo, cabecalho):
                return JSONResponse(
                    status_code=403, content={"erro": "assinatura_recusada"}
                )
        try:
            aviso = json.loads(corpo)
        except Exception:
            return Response(status_code=200)
        achado = _texto_do_webhook(aviso)
        if achado is None:
            return Response(status_code=200)
        texto, destino = achado
        if len(texto) > LIMITE_TEXTO:
            return Response(status_code=200)
        resultado = await asyncio.to_thread(atendimento.responder, texto)
        if enviar is not None and destino:
            try:
                await asyncio.to_thread(enviar, destino, resultado["resposta"])
            except Exception:
                logger.warning("falha ao enviar a resposta do webhook")
                return Response(status_code=200)
        return Response(status_code=200)

    @app.get("/v1/encaminhamentos")
    def encaminhamentos(request: Request):
        if gate and not request.session.get("atendente"):
            return JSONResponse(status_code=401, content={"erro": "sessao_ausente"})
        return atendimento.encaminhamentos()

    @app.delete("/v1/encaminhamentos/{item_id}")
    def concluir_encaminhamento(request: Request, item_id: int) -> Response:
        if gate and not request.session.get("atendente"):
            return JSONResponse(status_code=401, content={"erro": "sessao_ausente"})
        try:
            atendimento.concluir(item_id)
        except KeyError:
            return JSONResponse(
                status_code=404, content={"erro": "encaminhamento_inexistente"}
            )
        return Response(status_code=204)

    if gate:
        from starlette.middleware.sessions import SessionMiddleware

        app.add_middleware(SessionMiddleware, secret_key=session_secret)
        falhas: dict[str, int] = {}

        @app.get("/login", response_class=HTMLResponse)
        def login_formulario() -> str:
            return _html_login()

        @app.post("/login")
        async def login_enviar(request: Request):
            origem = request.client.host if request.client else ""
            if falhas.get(origem, 0) >= LIMITE_FALHAS:
                return HTMLResponse("<p>Muitas tentativas.</p>", status_code=429)
            corpo = await request.body()
            valores = parse_qs(corpo.decode())
            tentativa = valores.get("senha", [""])[0]
            if hmac.compare_digest(tentativa.encode(), senha.encode()):
                falhas[origem] = 0
                request.session["atendente"] = True
                return RedirectResponse("/atendente", status_code=303)
            falhas[origem] = falhas.get(origem, 0) + 1
            return HTMLResponse(_html_login(mostrar_erro=True), status_code=401)

    return app


def _criar_enviar_whatsapp(token: str, phone_id: str, modelo: str | None = None):
    def enviar(destino: str, texto: str) -> None:
        nome = modelo or None
        if nome:
            corpo = {
                "messaging_product": "whatsapp",
                "to": destino,
                "type": "template",
                "template": {
                    "name": nome,
                    "language": {"code": "pt_BR"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [{"type": "text", "text": texto}],
                        }
                    ],
                },
            }
        else:
            corpo = {
                "messaging_product": "whatsapp",
                "to": destino,
                "type": "text",
                "text": {"body": texto},
            }
        resposta = httpx.post(
            f"https://graph.facebook.com/v26.0/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json=corpo,
            timeout=10,
        )
        resposta.raise_for_status()

    return enviar


def criar_app_de_arquivo(
    caminho: Path,
    banco: Path | None = None,
    postgres_url: str | None = None,
    senha: str | None = None,
    session_secret: str | None = None,
    enviar=None,
    verificar_token: str | None = None,
    app_secret: str | None = None,
) -> FastAPI:
    base = BaseConhecimento(caminho)
    return criar_app(
        Atendimento(classificar, base, banco, postgres_url),
        senha=senha,
        session_secret=session_secret,
        enviar=enviar,
        verificar_token=verificar_token,
        app_secret=app_secret,
    )


def _app_de_producao() -> FastAPI:
    caminho = Path(__file__).resolve().parents[1] / "data" / "vertice_ti.json"
    senha = os.environ.get("ATENDEIA_SENHA") or None
    session_secret = os.environ.get("ATENDEIA_SESSION_SECRET") or None
    token = os.environ.get("ATENDEIA_WHATSAPP_TOKEN") or None
    phone_id = os.environ.get("ATENDEIA_WHATSAPP_PHONE_ID") or None
    modelo = os.environ.get("ATENDEIA_WHATSAPP_TEMPLATE") or None
    enviar = (
        _criar_enviar_whatsapp(token, phone_id, modelo=modelo)
        if token and phone_id
        else None
    )
    verificar_token = os.environ.get("ATENDEIA_WHATSAPP_VERIFY_TOKEN") or None
    app_secret = os.environ.get("ATENDEIA_WHATSAPP_APP_SECRET") or None
    if not (senha and session_secret):
        logger.warning(
            "painel e fila abertos: faltam ATENDEIA_SENHA ou ATENDEIA_SESSION_SECRET"
        )
    if token and phone_id and not app_secret:
        logger.warning(
            "webhook sem assinatura: falta ATENDEIA_WHATSAPP_APP_SECRET"
        )
    url = os.environ.get("ATENDEIA_DATABASE_URL")
    if url:
        return criar_app_de_arquivo(
            caminho,
            postgres_url=url,
            senha=senha,
            session_secret=session_secret,
            enviar=enviar,
            verificar_token=verificar_token,
            app_secret=app_secret,
        )
    return criar_app_de_arquivo(
        caminho,
        senha=senha,
        session_secret=session_secret,
        enviar=enviar,
        verificar_token=verificar_token,
        app_secret=app_secret,
    )


app = _app_de_producao()
