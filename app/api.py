import os
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.requests import Request
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


def criar_app(
    atendimento: Atendimento,
    senha: str | None = None,
    session_secret: str | None = None,
) -> FastAPI:
    app = FastAPI()
    gate = bool(senha and session_secret)

    @app.exception_handler(RequestValidationError)
    async def pergunta_invalida(request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"erro": "pergunta_invalida"})

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

        @app.get("/login", response_class=HTMLResponse)
        def login_formulario() -> str:
            return _html_login()

        @app.post("/login")
        async def login_enviar(request: Request):
            corpo = await request.body()
            valores = parse_qs(corpo.decode())
            tentativa = valores.get("senha", [""])[0]
            if tentativa == senha:
                request.session["atendente"] = True
                return RedirectResponse("/atendente", status_code=303)
            return HTMLResponse(_html_login(mostrar_erro=True), status_code=401)

    return app


def criar_app_de_arquivo(
    caminho: Path,
    banco: Path | None = None,
    postgres_url: str | None = None,
    senha: str | None = None,
    session_secret: str | None = None,
) -> FastAPI:
    base = BaseConhecimento(caminho)
    return criar_app(
        Atendimento(classificar, base, banco, postgres_url),
        senha=senha,
        session_secret=session_secret,
    )


def _app_de_producao() -> FastAPI:
    caminho = Path(__file__).resolve().parents[1] / "data" / "vertice_ti.json"
    url = os.environ.get("ATENDEIA_DATABASE_URL")
    if url:
        return criar_app_de_arquivo(caminho, postgres_url=url)
    return criar_app_de_arquivo(caminho)


app = _app_de_producao()
