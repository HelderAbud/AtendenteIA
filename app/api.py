from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
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


def criar_app(atendimento: Atendimento) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(RequestValidationError)
    async def pergunta_invalida(request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"erro": "pergunta_invalida"})

    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        return PAGINA.read_text(encoding="utf-8")

    @app.get("/atendente", response_class=HTMLResponse)
    def atendente() -> str:
        return ATENDENTE.read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/perguntas")
    def perguntas(corpo: PerguntaIn) -> dict:
        return atendimento.responder(corpo.pergunta)

    @app.get("/v1/encaminhamentos")
    def encaminhamentos() -> list:
        return atendimento.encaminhamentos()

    return app


def criar_app_de_arquivo(caminho: Path) -> FastAPI:
    base = BaseConhecimento(caminho)
    return criar_app(Atendimento(classificar, base))


app = criar_app_de_arquivo(
    Path(__file__).resolve().parents[1] / "data" / "vertice_ti.json"
)
