import unicodedata

SINAIS: dict[str, tuple[str, ...]] = {
    "prazo": ("prazo", "vence", "vencer", "vigencia", "termina", "vencimento"),
    "sla": ("sla", "disponibilidade", "primeira resposta", "tempo de resposta"),
    "renovacao": ("renova", "renovacao", "renovar"),
    "boleto": ("boleto", "segunda via", "pagar", "pagamento"),
    "chamado": ("chamado", "ticket", "status", "andamento"),
}


def normalizar(texto: str) -> str:
    texto = texto.lower()
    sem_acento = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(
        caractere for caractere in sem_acento if unicodedata.category(caractere) != "Mn"
    )
    return " ".join(sem_acento.split())


def classificar(texto: str) -> str:
    normalizado = normalizar(texto)
    pontuacao = {
        tema: sum(1 for sinal in sinais if sinal in normalizado)
        for tema, sinais in SINAIS.items()
    }
    maior = max(pontuacao.values())
    if maior == 0:
        return "desconhecido"
    vencedores = [tema for tema, pontos in pontuacao.items() if pontos == maior]
    if len(vencedores) != 1:
        return "desconhecido"
    return vencedores[0]
