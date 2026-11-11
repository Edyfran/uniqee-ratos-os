"""O confere_env diz preenchida ou vazia e nunca imprime o valor.

    tools/video-use/.venv/bin/python tools/video-use/helpers/test_confere_env.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import confere_env

SEGREDO = "sk-SEGREDO-123456"


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        env = Path(d) / ".env.local"
        env.write_text(f"# nota\nELEVENLABS_API_KEY={SEGREDO}\nVOZ_ID=\nexport X=\"{SEGREDO}\"\n", encoding="utf-8")
        assert confere_env.estado(env) == {"ELEVENLABS_API_KEY": True, "VOZ_ID": False, "X": True}

        # o programa inteiro, de ponta a ponta, num kit simulado (helpers/ ao lado de .env.local)
        raiz = Path(d) / "kit"
        helpers = raiz / "tools" / "video-use" / "helpers"
        helpers.mkdir(parents=True)
        (helpers / "confere_env.py").write_text(Path(confere_env.__file__).read_text(encoding="utf-8"), encoding="utf-8")
        (raiz / ".env.local").write_text(env.read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run([sys.executable, str(helpers / "confere_env.py")], capture_output=True, text=True, encoding="utf-8")
        assert SEGREDO not in r.stdout + r.stderr, "imprimiu o valor da chave"
        assert "ELEVENLABS_API_KEY: preenchida" in r.stdout and "VOZ_ID: vazia" in r.stdout
        assert r.returncode == 1                    # há vazia
    print("ok test_confere_env")


if __name__ == "__main__":
    main()
