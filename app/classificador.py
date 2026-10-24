import re
import unicodedata

SINAIS: dict[str, tuple[str, ...]] = {
    "prazo": ("prazo", "vence", "vencer", "vigencia", "termina", "vencimento"),
    "sla": ("sla", "disponibilidade", "primeira resposta", "tempo de resposta"),
    "renovacao": ("renova", "renovacao", "renovar"),
    "boleto": ("boleto", "segunda via", "pagar", "pagamento"),
    "chamado": ("chamado", "ticket", "status", "andamento"),
}

_SUFIXOS = frozenset(
    {
        "",
        "r",
        "er",
        "ar",
        "ir",
        "mento",
        "imento",
        "cao",
        "coes",
        "s",
        "es",
        "ndo",
        "da",
        "do",
        "dos",
        "das",
    }
)


def normalizar(texto: str) -> str:
    texto = texto.lower()
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(
        caractere for caractere in sem_acento if unicodedata.category(caractere) != "Mn"
    )
    return " ".join(sem_acento.split())


def _palavras(texto: str) -> list[str]:
    return re.findall(r"[a-z]+", normalizar(texto))


def tem_sinal(sinal: str, texto: str) -> bool:
    tokens = _palavras(texto)
    partes = sinal.split()
    if len(partes) > 1:
        tamanho = len(partes)
        return any(
            tokens[indice : indice + tamanho] == partes
            for indice in range(len(tokens) - tamanho + 1)
        )
    raiz = partes[0]
    return any(
        token.startswith(raiz) and token[len(raiz) :] in _SUFIXOS for token in tokens
    )


def classificar(texto: str) -> str:
    pontuacao = {
        tema: sum(1 for sinal in sinais if tem_sinal(sinal, texto))
        for tema, sinais in SINAIS.items()
    }
    maior = max(pontuacao.values())
    if maior == 0:
        return "desconhecido"
    vencedores = [tema for tema, pontos in pontuacao.items() if pontos == maior]
    if len(vencedores) != 1:
        return "desconhecido"
    return vencedores[0]
