import json
from pathlib import Path

import pytest

from app.base import BaseConhecimento

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO = RAIZ / "data" / "vertice_ti.json"

TEXTOS = {
    "prazo": "O contrato de suporte da Vértice TI vale 12 meses a partir da assinatura.",
    "sla": "A primeira resposta ocorre em até 4 horas úteis. A disponibilidade acordada é de 99,5% ao mês.",
    "renovacao": "A renovação é automática. A Vértice TI avisa por e-mail 30 dias antes do vencimento.",
    "boleto": "O boleto sai por e-mail todo dia 10. A segunda via fica com o financeiro da Vértice TI.",
    "chamado": "O status do chamado segue o protocolo aberto com a Vértice TI. Os estados são aberto, em andamento e concluído.",
    "desconhecido": "Não encontrei esse assunto na base da Vértice TI. Um atendente continua a conversa.",
}


def test_arquivo_real_devolve_os_textos() -> None:
    base = BaseConhecimento(ARQUIVO)
    for tema, texto in TEXTOS.items():
        item = base.obter(tema)
        assert item["resposta"] == texto
        assert item["encaminhar_humano"] is (tema == "desconhecido")


def test_arquivo_ausente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        BaseConhecimento(tmp_path / "ausente.json")


def _gravar(tmp_path: Path, dados: dict) -> Path:
    caminho = tmp_path / "base.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def _base_valida() -> dict:
    return {
        tema: {
            "resposta": texto,
            "encaminhar_humano": tema == "desconhecido",
        }
        for tema, texto in TEXTOS.items()
    }


def test_chave_ausente(tmp_path: Path) -> None:
    dados = _base_valida()
    del dados["boleto"]
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_resposta_vazia(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["prazo"]["resposta"] = "   "
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_booleano_ausente(tmp_path: Path) -> None:
    dados = _base_valida()
    del dados["sla"]["encaminhar_humano"]
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_encaminhar_errado_no_tema_de_negocio(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["prazo"]["encaminhar_humano"] = True
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))


def test_encaminhar_errado_no_desconhecido(tmp_path: Path) -> None:
    dados = _base_valida()
    dados["desconhecido"]["encaminhar_humano"] = False
    with pytest.raises(ValueError):
        BaseConhecimento(_gravar(tmp_path, dados))
