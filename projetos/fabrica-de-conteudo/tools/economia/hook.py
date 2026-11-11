"""PreToolUse: pergunta ao leitura.avalia e, se ele negar, nega com a versão barata.

As regras moram no leitura.py. Aqui só: estado da sessão, registro e o JSON do hook.
Roda no Mac, no Windows e no Linux. O registro vai pro lugar de log de cada sistema
(ECONOMIA_REGISTRO aponta outro arquivo; o teste usa, pra não sujar o da máquina).
"""
import json, os, re, sys, time
from pathlib import Path

from leitura import TMP, avalia

ESTADO = TMP / "economia-hook"


def pasta_de_log(sistema=None, env=None, home=None):
    """Mac: ~/Library/Logs. Windows: %LOCALAPPDATA%\\economia. Linux: $XDG_STATE_HOME/economia (padrão ~/.local/state)."""
    sistema, env, home = sistema or sys.platform, os.environ if env is None else env, Path(home or Path.home())
    if sistema == "darwin":
        return home / "Library" / "Logs"
    if sistema.startswith("win"):
        return Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local") / "economia"
    return Path(env.get("XDG_STATE_HOME") or home / ".local" / "state") / "economia"


REGISTRO = Path(os.environ.get("ECONOMIA_REGISTRO") or pasta_de_log() / "economia.jsonl")


def main():
    e = json.loads(sys.stdin.buffer.read().decode("utf-8"))  # utf-8 explícito: o Windows lê o cano em cp1252
    sessao = e.get("session_id", "sem-sessao")
    ESTADO.mkdir(parents=True, exist_ok=True)
    arq = ESTADO / f"{re.sub(r'[^\w-]', '_', sessao)}.json"
    estado = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    d = avalia(e.get("tool_name"), e.get("tool_input") or {}, e.get("cwd", "."), estado)
    arq.write_text(json.dumps(estado), encoding="utf-8")
    if not d or not d.motivo:
        return
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "sessao": sessao, "tipo": d.tipo, "alvo": d.alvo,
                            "bruto": d.bruto, "devolvido": d.devolvido}, ensure_ascii=False) + "\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": d.motivo}}))


if __name__ == "__main__":
    main()
