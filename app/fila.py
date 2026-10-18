import sqlite3
from pathlib import Path


class Fila:
    def __init__(self, banco: Path | None = None) -> None:
        self._banco = banco
        self._memoria = None
        if banco is None:
            self._memoria = sqlite3.connect(":memory:", check_same_thread=False)
            self._criar(self._memoria)
        else:
            banco.parent.mkdir(parents=True, exist_ok=True)
            with self._conectar() as conexao:
                self._criar(conexao)

    def _conectar(self) -> sqlite3.Connection:
        if self._memoria is not None:
            return self._memoria
        return sqlite3.connect(self._banco)

    def _fechar(self, conexao: sqlite3.Connection) -> None:
        if self._memoria is None:
            conexao.close()

    def _criar(self, conexao: sqlite3.Connection) -> None:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS encaminhamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pergunta TEXT NOT NULL,
                fluxo TEXT NOT NULL,
                resumo TEXT
            )
            """
        )
        conexao.commit()

    def registrar(self, pergunta: str, fluxo: str, resumo: str | None) -> None:
        conexao = self._conectar()
        try:
            conexao.execute(
                "INSERT INTO encaminhamentos (pergunta, fluxo, resumo) VALUES (?, ?, ?)",
                (pergunta, fluxo, resumo),
            )
            conexao.commit()
        finally:
            self._fechar(conexao)

    def listar(self) -> list[dict]:
        conexao = self._conectar()
        try:
            linhas = conexao.execute(
                "SELECT id, pergunta, fluxo, resumo FROM encaminhamentos ORDER BY id"
            ).fetchall()
        finally:
            self._fechar(conexao)
        return [
            {"id": linha[0], "pergunta": linha[1], "fluxo": linha[2], "resumo": linha[3]}
            for linha in linhas
        ]

    def remover(self, item_id: int) -> None:
        conexao = self._conectar()
        try:
            cursor = conexao.execute(
                "DELETE FROM encaminhamentos WHERE id = ?", (item_id,)
            )
            conexao.commit()
            if cursor.rowcount == 0:
                raise KeyError(item_id)
        finally:
            self._fechar(conexao)
