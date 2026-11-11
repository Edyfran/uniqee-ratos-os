"""Runner único: pytest coleta os mesmos `test_*` que cada arquivo roda no seu `main()`.

Os testes pedem a pasta temporária por nomes diferentes (`tmp`, `_`, `d`); todos são o
`tmp_path` do pytest. `video` e `mudo` são os clipes que o `main()` do test_ff monta.
"""
import pytest

collect_ignore = [
    "test_receitas.py",   # recebe `page`/`p` de uma sessão Playwright aberta no main(); não é do kit
]


# Arquivos cujos asserts moram só dentro do main(), sem nenhum `test_*`: o pytest roda o main() como um teste.
# (test_transcript roda no import: o assert que falha vira erro de coleta, não passa calado)
SO_MAIN = {"test_confere_env", "test_referencia", "test_checks", "test_notas_lorcana", "test_notas_lorcana_medidas", "test_ouvido",
           "test_casos_vermelhos", "test_publicacao"}


def pytest_pycollect_makeitem(collector, name, obj):
    if name == "main" and collector.module.__name__ in SO_MAIN and callable(obj):
        def roda():
            assert not obj(), "main() devolveu código de erro"   # None ou 0 é sucesso
        return pytest.Function.from_parent(collector, name="main", callobj=roda)


@pytest.fixture(autouse=True, scope="session")
def _cache_isolado(tmp_path_factory):
    # quem renderiza gravaria o tempo medido e pegaria as vagas do cache de quem roda (a conferência do aluno)
    import os
    os.environ["FABRICA_CACHE"] = str(tmp_path_factory.mktemp("cache"))


@pytest.fixture
def tmp(tmp_path, request):
    if request.module.__name__ == "test_emenda":   # o main() dele já entrega a, b e sub criadas
        for n in ("a", "b", "sub"):
            (tmp_path / n).mkdir()
    return tmp_path


@pytest.fixture
def _(tmp_path):
    return tmp_path


@pytest.fixture
def d(tmp_path):
    return tmp_path


@pytest.fixture
def video(tmp_path):
    import test_ff
    return test_ff._fixture(tmp_path, com_audio=True)


@pytest.fixture
def mudo(tmp_path):
    import test_ff
    return test_ff._fixture(tmp_path, com_audio=False)
