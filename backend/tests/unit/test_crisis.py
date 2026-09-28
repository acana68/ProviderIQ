import pytest

from app.ai.crisis import mentions_self_harm


@pytest.mark.parametrize(
    "query",
    [
        "I want to kill myself",
        "i've been feeling suicidal, need a psychiatrist in Boston",
        "Suicide prevention counselor near Chicago",
        "thinking about ending my life",
        "I don’t want to live anymore",
        "dont want to wake up",
        "sometimes I wish I was dead",
        "therapist for self-harm",
        "my teen is self harming",
        "I keep cutting myself",
        "I want to hurt myself",
        "KILL MYSELF",
        "everyone would be better off dead without me",
        "I just wanna die",
    ],
)
def test_flags_self_harm_and_suicide_risk(query: str) -> None:
    assert mentions_self_harm(query)


@pytest.mark.parametrize(
    "query",
    [
        "highly rated cardiologist near New York for heart failure",
        "psychiatrist for depression in Boston",
        "I'm dying to find a good dermatologist",
        "killer migraine, need a neurologist",
        "cutting-edge cancer treatment",
        "hurt my knee skiing, orthopedist in Denver",
        "chest pain",
        "",
    ],
)
def test_ordinary_queries_are_not_flagged(query: str) -> None:
    assert not mentions_self_harm(query)
