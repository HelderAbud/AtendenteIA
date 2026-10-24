import pytest

from app.classificador import classificar


@pytest.mark.parametrize(
    ("pergunta", "tema"),
    [
        ("quando vence meu contrato?", "prazo"),
        ("VIGÊNCIA do suporte", "prazo"),
        ("qual é o sla?", "sla"),
        ("como faco a renovacao?", "renovacao"),
        ("preciso da segunda via do boleto", "boleto"),
        ("qual o status do chamado?", "chamado"),
        ("quero falar sobre o clima", "desconhecido"),
        ("vence o boleto", "desconhecido"),
        ("apagar o arquivo", "desconhecido"),
        ("terminal do servidor", "desconhecido"),
        ("preciso determinar o assunto", "desconhecido"),
        ("qual o vencimento?", "prazo"),
    ],
)
def test_exemplos_fechados(pergunta: str, tema: str) -> None:
    assert classificar(pergunta) == tema
