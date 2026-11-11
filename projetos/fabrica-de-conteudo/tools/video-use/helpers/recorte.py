"""Recorte da pessoa em vídeo: a máscara do take do celular, quadro a quadro, pronta pro alfa.

    python recorte.py take.mp4 --ini 10 --fim 15 --saida mascara.mov

Três modelos, cada um no que faz bem (medido em 06/11/2026 em 30 quadros de um celular com cadeira gamer, Majora e escudo na
parede, e 10 de um avatar de fundo limpo, contra o BiRefNet-portrait como referência):

  * o MODNet (25 MB, Apache-2.0, `modnet.onnx` baixado na primeira vez) roda a 10 quadros por segundo e diz ONDE há gente
    (rápido, mas confunde o fundo escuro com a pessoa e serrilha o cabelo);
  * o BiRefNet general-lite do rembg (224 MB, MIT) dá o contorno de verdade (o alfa macio, o cabelo): roda só num RECORTE
    em volta da pessoa (a caixa do MODNet com `MARGEM`) a cada `CHAVE`-ésimo quadro (2,5 qps), sem o pós-processo do rembg
    (que binariza e serrilha). O que o MODNet não vê como gente (a até `PERTO` px) cai: o microfone, o escudo.

A limpeza (`_limpa`) fica com a pessoa e o que encosta nela, tapa furo pequeno (o vão entre os dedos fica aberto), põe alfa 1 no
miolo e deixa macia só a faixa da borda, sem o halo da cor do fundo. Os quadros do meio (`_entre`) misturam os dois quadros-chave
vizinhos e o MODNet do próprio quadro (a mão que se mexeu fica sólida; o fantasma o `_limpa` corta); `_suaviza` tira o tremor da borda. O Vision da Apple e o
guided filter foram medidos e perdem: o Vision pega o Majora e fura a camisa; o filtro guiado engorda a borda do cabelo.

O terceiro é o SAM 2.1-tiny (`_sam`, ONNX em onnxruntime com a memória de vídeo, Apache-2.0 nos pesos e no código; 181 MB), que dá o
LIMITE: quem pode ser pessoa. O prompt do 1º quadro sai sozinho do rosto (YuNet do OpenCV, MIT, 230 KB): a caixa em volta da pessoa,
pontos de dentro (rosto, peito, ombros) e três pontos de fora acima da cabeça. Dali o SAM SEGUE a pessoa pela memória (os quadros do
BiRefNet e os do meio, a 5 qps; entre dois o limite é a união dos vizinhos): é a memória que deixa o Majora colado no cabelo de fora, porque o
SAM de um quadro só (medido: 59 MB, sem memória) o leva junto toda vez que ele encosta no cabelo. Se o SAM perde a pessoa, o rosto o
prende de novo. O alfa do BiRefNet só vale dentro do limite dilatado em
`LIMITE` px: o SAM tira o que o MODNet e o BiRefNet confundem com a pessoa quando é da cor do cabelo (o Majora e a ponta da cadeira
colados na cabeça), e o BiRefNet continua tirando o que o SAM pega demais (a mesa preta). O ViTMatte-S foi medido pra refazer a
borda e ficou de fora: os pesos são Apache-2.0, mas foram treinados no Composition-1k da Adobe, de uso só em pesquisa; no lugar, o
próprio BiRefNet-lite (MIT) refaz a borda, agora em 1080 de largura: o quadro e a máscara têm a resolução do quadro final (antes a
máscara saía em 540 e era esticada de 2 a 3 vezes). Sem o SAM (sem rede na 1ª vez) o recorte sai como antes, sem o limite.

O alfa entre os quadros do matte é interpolado pelo ffmpeg (`framerate`). O resultado fica em cache pelo conteúdo do bruto +
trecho + taxa + modelo: refazer o plano não recorta de novo. Sem o BiRefNet (sem rede na primeira vez) o recorte sai só com o
MODNet, e se este também faltar, com o u2netp do rembg; a trava de qualidade (`confere`) pega o resultado ruim e diz o motivo
em português comum (`pergunta` é a linha que o agente lê pra perguntar ao aluno).

O meta traz o que o layout precisa: `topo` (cabelo) e `hw` (largura da cabeça) em pixels do take, `cx` (centro da cabeça),
`ms_quadro` (o tempo do matte) e `qualidade` (a medida da máscara, `mede_qualidade`). Toda chamada de ffmpeg passa pelo `ff`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

import cena
import ff

TAXA = 10
MODELO = "modnet+birefnet-general-lite+sam2.1-tiny"      # o fino, o grande e o limite; o nome entra na chave do cache
FINO, GRANDE, LIMITADOR = "modnet", "birefnet-general-lite", "sam2.1-hiera-tiny"
LIMIAR = 0.0          # logit do SAM acima do qual é pessoa (0 = o ponto de 50%). Com 1 o SAM do 1º quadro, o do prompt, perdia o cabelo e os óculos
LIMITE = 8            # px (em 1080 de largura) que o alfa pode passar da silhueta do SAM (14 deixava passar a ponta do Majora colada no cabelo)
CHAVE = 4             # o modelo grande roda a cada 4º quadro do matte (2,5 qps): o tempo do recorte é quase todo dele
SAM_CADA = 2          # o SAM segue a pessoa a cada 2º quadro (5 qps); o do meio usa a união dos dois vizinhos. A cada 4º (2,5 qps) deixou a ponta do Majora passar nos quadros do meio, quando a cabeça se mexe
MARGEM = 60           # px (em 540 de largura; `ESC` vezes isso em `LADO`) em volta da pessoa no recorte que o grande enxerga
PERTO = 8             # px que o alfa do grande pode passar do que o fino vê como gente
FURO = 250            # px: furo menor que isto dentro da pessoa é tapado (o vão entre os dedos é maior e fica)
NUCLEO = 2            # px que o alfa de dentro da pessoa é 1: só a faixa da borda é macia
PISO, TETO = 0.12, 0.85   # abaixo é fundo, acima é pessoa: tira o halo da cor do fundo
MODNET_URL = "https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx"
MODNET_SHA256 = "07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9"
VERSAO = 5            # muda quando o formato do meta muda: o cache velho não vale
LADO = 1080           # a máscara tem a largura do quadro final (o MODNet roda em 512, o BiRefNet em 1024, sobre o quadro de 1080)
ESC = LADO // 540     # os px de cima (MARGEM, PERTO, FURO, NUCLEO...) foram medidos em 540: valem ESC vezes isso em LADO
K_QUEIXO = 1.35       # altura cabelo→queixo / largura da cabeça. shortcut: calibrado em UMA pessoa (o dono);
                      # trocar por pontos de rosto (Vision/mediapipe) quando o kit levar um.


def _chave(video: Path, ini: float, fim: float, taxa: int, modelo: str) -> str:
    st = video.stat()
    pedido = [cena._resumo(str(video.resolve()), st.st_size, st.st_mtime_ns), ini, fim, taxa, modelo, VERSAO, CHAVE, MARGEM, PERTO, FURO, NUCLEO, PISO, TETO, LADO, SAM_CADA, LIMITE, LIMIAR]
    return hashlib.blake2b(json.dumps(pedido).encode(), digest_size=12).hexdigest()


def medida_da_cabeca(m: np.ndarray) -> dict | None:
    """Cabelo, queixo e centro da cabeça numa máscara 0-255 (linhas x colunas), em fração da altura.

    O cabelo é a primeira linha com pessoa de verdade (não um fio solto); a largura da cabeça é a
    maior largura nos 20% de altura abaixo dele; o queixo (`queixo()`) é cabelo + K_QUEIXO x largura."""
    h, w = m.shape
    larg = (m > 128).sum(axis=1)
    linhas = np.nonzero(larg >= 0.06 * w)[0]
    if not len(linhas):
        return None
    topo = int(linhas[0])
    jan = slice(topo, min(h, topo + int(0.20 * h)))
    hw = float(larg[jan].max())
    cols = np.nonzero((m[jan] > 128).any(axis=0))[0]
    return {"topo": topo / h, "cx": float(cols.mean()) / w, "hw": hw / w}


# A trava de qualidade. Cada limite vem da medida de 06/11/2026 no IMG_3886 (celular, cadeira gamer, Majora e escudo na parede)
# e num avatar de fundo limpo (docs no `recorte-modelos.md` do kit): o u2netp passava de todos no celular, o modelo novo passa em todos.
LIMITES = {
    "ponta": 0.16,        # mediana, nos quadros, das linhas do cabelo até a cabeça ter metade da largura (em largura de cabeça): cabelo
                          # limpo 0,07 a 0,16 (o coque do dono dá 0,14); cadeira ou objeto preso em cima do cabelo, 0,19 a 0,25.
                          # Mede pouco: pega o u2netp e não o recorte bom, mas deixa passar o defeito pequeno
    "ponta_quadros": 8,   # com menos quadros que isto a `ponta` não vale: um trecho de meio segundo é uma pose só
    "buracos": 1.5,       # % da pessoa que é furo dentro da silhueta (mediana dos quadros)
    "salto": 0.08,        # p90 de |área(t) - área(t-1)| / área, a 10 qps: a máscara que pisca (gente se mexendo fica abaixo de 0,10)
    "cortada": 0.5,       # fração dos quadros com a pessoa colada no topo: cabeça cortada, o layout não tem onde pôr o cabelo
    "excesso_quadros": 0.40,   # fração dos quadros-chave em que o recorte SEM o limite do SAM leva mais de `EXCESSO_ZONA` % da área do
                          # rosto, fora do SAM, na zona da cabeça (`_excesso`): objeto da cor do cabelo colado na cabeça. O SAM o tira
                          # do recorte (IMG_3886, com o Majora: 25% dos quadros-chave passam de 3% e o recorte sai limpo, 0 de 60 quadros
                          # com objeto, então passa); acima de 40% o fundo ali é difícil demais e o SAM pode ter seguido a coisa errada
    "excesso_min": 3,     # com menos quadros-chave que isto (1 s de trecho) a medida não vale
}


def _maior(b: np.ndarray) -> np.ndarray:
    from scipy import ndimage
    lab, n = ndimage.label(b)
    return b if n < 2 else lab == 1 + int(np.argmax(ndimage.sum(b, lab, range(1, n + 1))))


def mede_qualidade(mascaras: list[np.ndarray]) -> dict:
    """Mede a máscara de um trecho (lista de máscaras 0-255, em ordem, a `TAXA` qps) sem referência nenhuma:
    `ponta` (algo preso em cima do cabelo: a cadeira, o objeto na parede), `buracos` (% da pessoa
    que é furo), `salto` (a máscara que pisca) e `cortada` (cabeça cortada). `onde` diz em que quadro cada defeito pesa
    mais (índice no trecho). Cabe a `confere` dizer se passa."""
    from scipy import ndimage
    pontas, buracos, areas, cortada, sem, onde = [], [], [], 0, 0, {}
    ids = []
    for i, m in enumerate(mascaras):
        b = _maior(m > 128)
        h, w = b.shape
        larg = b.sum(axis=1)
        linhas = np.nonzero(larg >= 0.04 * w)[0]
        if not len(linhas) or not b.any():
            sem += 1
            onde.setdefault("sem_pessoa", i)
            continue
        areas.append(float(b.sum()))
        ids.append(i)
        buracos.append(100 * float((ndimage.binary_fill_holes(b) & ~b).sum()) / b.sum())
        topo = int(linhas[0])
        if larg[:2].max() >= 0.06 * w:
            cortada += 1
            onde.setdefault("cortada", i)
        hw = float(larg[topo:topo + int(0.20 * h)].max())
        pontas.append(float(np.nonzero(larg[topo:] >= 0.5 * hw)[0][0]) / hw)
    n = max(1, len(mascaras))
    a = np.array(areas)
    saltos = np.abs(np.diff(a)) / a[:-1] if len(a) > 2 else np.zeros(0)
    if pontas:
        onde["ponta"] = ids[int(np.argmax(pontas))]
        onde["buracos"] = ids[int(np.argmax(buracos))]
    if len(saltos):
        onde["salto"] = ids[1 + int(np.argmax(saltos))]
    return {"quadros": len(mascaras), "sem_pessoa": sem / n,
            "ponta": float(np.median(pontas)) if pontas else 0.0,
            "buracos": float(np.median(buracos)) if buracos else 0.0,
            "salto": float(np.percentile(saltos, 90)) if len(saltos) else 0.0,
            "cortada": cortada / n, "onde": onde}


def _quando(q: dict, defeito: str) -> str:
    """O segundo do bruto onde o defeito pesa mais, em `m:ss` (vazio se a medida não diz: cache de antes do `onde`)."""
    i = (q.get("onde") or {}).get(defeito)
    if defeito == "excesso" and q.get("excesso"):
        i = q["excesso"]["quadros"][int(np.argmax(q["excesso"]["pct"]))]
    if i is None:
        return ""
    t = float(q.get("ini", 0.0)) + i / max(1, q.get("taxa", TAXA))
    return f" (aos {int(t // 60)}:{int(t % 60):02d})"


def confere(meta: dict) -> tuple[bool, str]:
    """O recorte presta pro layout `dividida`? `(ok, motivo)`: o motivo vem em português comum, na voz de quem fala com o
    aluno (o fundo é quase sempre a causa), com o segundo do bruto onde pesa mais. Vai no aviso do storyboard e na pergunta
    do agente (`pergunta`). Meta sem `qualidade` (cache de antes da trava) vale como ok: a trava não inventa defeito."""
    q = (meta or {}).get("qualidade")
    if not q:
        return True, ""
    if q["sem_pessoa"] > 0.2:
        return False, "pouca luz no seu rosto: o recorte não achou você" + _quando(q, "sem_pessoa")
    if q["quadros"] >= LIMITES["ponta_quadros"] and q["ponta"] >= LIMITES["ponta"]:
        return False, "tem algo colado na sua cabeça, como cadeira ou objeto na parede" + _quando(q, "ponta")
    ex = q.get("excesso")
    if ex and len(ex["pct"]) >= LIMITES["excesso_min"] and np.mean(np.array(ex["pct"]) > EXCESSO_ZONA) >= LIMITES["excesso_quadros"]:
        return False, "tem algo colado na sua cabeça, como cadeira ou objeto na parede" + _quando(q, "excesso")
    if q["buracos"] > LIMITES["buracos"]:
        return False, "o fundo tem a cor do seu cabelo ou da sua roupa" + _quando(q, "buracos")
    if q["salto"] > LIMITES["salto"]:
        return False, "o fundo muda de cor perto de você e o contorno pisca" + _quando(q, "salto")
    if q["cortada"] >= LIMITES["cortada"]:
        return False, "a sua cabeça encosta no topo do quadro" + _quando(q, "cortada")
    return True, ""


def pergunta(motivo: str) -> str:
    """A linha que o passo da tela dividida imprime quando a trava reprova: o agente lê, pergunta ao aluno e, sem resposta,
    o vídeo segue com a pessoa no cartão (o layout já caiu pra ele). A 3ª opção que a pesquisa de 06/11 propôs ("grave 3 s do fundo vazio,
    sem você") fica fora: pede o BackgroundMattingV2 (PyTorch, pesos sem licença própria) e câmera parada, e o celular na mão desfaz isso."""
    import re
    causa = re.sub(r" \(aos (\d+:\d\d)\)$", r", \1", motivo)
    return (f"recorte: fundo poluído ({causa}) — pergunte ao aluno: 1) seguir com a pessoa no cartão (tela dividida com o seu "
            "fundo), 2) regravar com fundo liso (parede lisa a 1 m atrás, luz de frente, nada colado na cabeça). Sem resposta: cartão.")


_FINO: dict = {}
_MEMO: dict = {}

# Os modelos que o recorte baixa na 1ª vez (nome no cache -> url, sha256). O SAM 2.1-tiny em vídeo é o export ONNX do `square-zero-labs`
# (Apache-2.0, dos pesos da Meta, também Apache-2.0; fp32, 181 MB; o autor o validou contra o PyTorch: IoU 0,997, e aqui deu 0,977 contra
# o SAM do transformers nos 60 quadros do IMG_3886). O de um quadro só do onnx-community (int8, 59 MB) foi medido e perde: sem memória,
# leva o Majora colado no cabelo. As urls fixam a revisão: o arquivo não muda debaixo do aluno.
_HF = "https://huggingface.co/square-zero-labs/sam2.1-tiny-video-onnx/resolve/3b2984dd865f6e9d2cc6aed0be6a5a5c2eb352ce/"
_ZOO = "https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a/models/face_detection_yunet/"
MODELOS = {
    "modnet.onnx": (MODNET_URL, MODNET_SHA256),
    "yunet.onnx": (_ZOO + "face_detection_yunet_2023mar.onnx", "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "sam2.1-tiny/constants.json": (_HF + "constants.json", "172edc70e892aab0aef6caedf97b8e4091fbf6c5d26dac5fd9ea69d093d927d3"),
    "sam2.1-tiny/vision_encoder.onnx": (_HF + "onnx/vision_encoder.onnx", "aa7a8542942f042e235a993a1ab0ccf5f049918500577802a7f10ec1b39bb873"),
    "sam2.1-tiny/mask_decoder.onnx": (_HF + "onnx/mask_decoder.onnx", "0461896de3db00936fe1643506f129d71cb6d5d2ae15754811756b7ea1b070c6"),
    "sam2.1-tiny/memory_encoder.onnx": (_HF + "onnx/memory_encoder.onnx", "580d246c109de88838f600ba7c1c0d03d1fe267f7641b06f8c88c5f0dc5834cd"),
    "sam2.1-tiny/memory_attention.onnx": (_HF + "onnx/memory_attention.onnx", "791e648ce8f5ef91ad00ba06e83066ff261ae5a645f0b042b4f46a89fd054baf"),
    "sam2.1-tiny/pointer_tpos.onnx": (_HF + "onnx/pointer_tpos.onnx", "7e71df1d75dba09bc18dd4ae745c2a2cceebdd14d84eadea2fe65d0205f101fc"),
}
SAM_ARQUIVOS = [n for n in MODELOS if n.startswith("sam2.1-tiny/")] + ["yunet.onnx"]
SAM_MB = 181          # o que o aluno baixa pro limite (SAM + detector de rosto), uma vez só


def _modelo(nome: str) -> Path:
    """O caminho do modelo no cache (`cena.CACHE/../modelos`), baixado e conferido pelo hash se faltar. A mensagem da 1ª vez diz o
    tamanho: o aluno não fica olhando um recorte parado sem saber por quê."""
    import shutil
    import urllib.request
    url, sha = MODELOS[nome]
    arq = cena.CACHE.parent / "modelos" / nome
    if _MEMO.get(arq) == sha and arq.exists():
        return arq
    if not arq.exists() or hashlib.sha256(arq.read_bytes()).hexdigest() != sha:
        arq.parent.mkdir(parents=True, exist_ok=True)
        if nome in SAM_ARQUIVOS and not _MEMO.get("avisou"):
            _MEMO["avisou"] = True
            print(f"recorte: baixando os modelos do recorte (SAM 2.1-tiny e detector de rosto), ~{SAM_MB} MB, uma vez só", file=sys.stderr)
        tmp = arq.with_name(arq.name + ".tmp")
        req = urllib.request.Request(url, headers={"User-Agent": "fabrica-de-conteudo"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if hashlib.sha256(tmp.read_bytes()).hexdigest() != sha:
            tmp.unlink()
            raise RuntimeError(f"o {nome} baixado não bate com o hash esperado")
        tmp.replace(arq)
    _MEMO[arq] = sha
    return arq


def _modnet():
    """O MODNet em onnxruntime (CPU): quadro RGB -> alfa 0-255 do tamanho do quadro. Baixa o modelo na primeira vez
    (`cena.CACHE/../modelos`), com conferência do hash."""
    if "f" in _FINO:
        return _FINO["f"]
    import onnxruntime as ort
    se = ort.InferenceSession(str(_modelo("modnet.onnx")), providers=["CPUExecutionProvider"])
    nome = se.get_inputs()[0].name

    def f(img: Image.Image) -> np.ndarray:
        w, h = img.size
        W, H = 512, int(round(h * 512 / w / 32)) * 32
        x = (np.asarray(img.convert("RGB").resize((W, H), Image.BILINEAR), np.float32) - 127.5) / 127.5
        o = se.run(None, {nome: x.transpose(2, 0, 1)[None]})[0][0, 0]
        return np.array(Image.fromarray((np.clip(o, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR))
    _FINO["f"] = f
    return f


def _dil(b: np.ndarray, n: int) -> np.ndarray:
    """Dilatação de `n` px em cruz (o mesmo que `binary_dilation(iterations=n)`), 30x mais rápida em 1080x1920."""
    import cv2
    return cv2.dilate(b.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)), iterations=n).astype(bool)


def _ero(b: np.ndarray, n: int) -> np.ndarray:
    import cv2
    return cv2.erode(b.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)), iterations=n).astype(bool)


def _rosto(img: np.ndarray) -> tuple[float, float, float, float] | None:
    """O rosto maior (x, y, largura, altura em px do quadro) pelo YuNet do OpenCV (MIT, 230 KB, CPU, qualquer sistema). O modelo entra
    por buffer: o OpenCV no Windows não abre caminho com acento (a pasta do usuário)."""
    import cv2
    if "yunet" not in _MEMO:
        _MEMO["yunet"] = _modelo("yunet.onnx").read_bytes()
    k = 540 / img.shape[1]                      # o detector não precisa de mais, e o quadro de 1080 custa 4x
    pq = cv2.resize(img, (540, int(round(img.shape[0] * k))), interpolation=cv2.INTER_AREA)
    if "det" not in _MEMO:
        try:
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)     # o aviso do alvo do dnn, a cada detector
        except AttributeError:
            pass
        _MEMO["det"] = cv2.FaceDetectorYN.create("onnx", np.frombuffer(_MEMO["yunet"], np.uint8), np.empty(0, np.uint8), (pq.shape[1], pq.shape[0]), 0.6)
    det = _MEMO["det"]
    det.setInputSize((pq.shape[1], pq.shape[0]))
    _, f = det.detect(cv2.cvtColor(pq, cv2.COLOR_RGB2BGR))
    if f is None or not len(f):
        return None
    x, y, w, h = f[int(np.argmax(f[:, -1]))][:4] / k
    return float(x), float(y), float(w), float(h)


def _pontos_do_corpo(fino: np.ndarray, rosto: tuple[float, float, float, float], n: int = 4) -> list:
    """Pontos de dentro do corpo tirados do MODNet, pelos mais afastados dos do rosto e do peito e entre si (amostragem do ponto mais
    longe): chegam ao braço levantado e à mão ao lado do rosto, que a caixa e os 4 pontos do rosto não pedem (sem eles o SAM do 1º
    quadro deixa a mão de fora, e a memória repete o erro). Acima da testa não há ponto: é onde mora o objeto que o recorte confunde
    com o cabelo."""
    x, y, fw, fh = rosto
    cx = x + fw / 2
    m = _ero(fino > 230, 12)
    m[: int(max(0, y + 0.6 * fh))] = False
    ys, xs = np.nonzero(m[::8, ::8])
    if not len(ys):
        return []
    cand = np.stack([xs * 8.0, ys * 8.0], axis=1)
    feitos = [[cx, y + fh * 0.6], [cx, y + fh * 2.4]]
    novos = []
    for _ in range(n):
        d = np.min([np.hypot(cand[:, 0] - a, cand[:, 1] - b) for a, b in feitos], axis=0)
        k = int(np.argmax(d))
        if d[k] < 0.8 * fw:
            break
        feitos.append(list(cand[k]))
        novos.append([float(cand[k][0]), float(cand[k][1])])
    return novos


def _prompt(rosto: tuple[float, float, float, float], w: int, h: int, extra: list | None = None) -> tuple[list, list, list]:
    """O prompt do SAM sem clique do aluno, tirado do rosto: a caixa da pessoa (do meio da testa pra baixo, 2,4 larguras de rosto
    pra cada lado), pontos de dentro (rosto, peito, os dois ombros) e três de fora acima da cabeça, onde o objeto colado no cabelo
    aparece. Ponto de fora que cairia fora do quadro (cabeça perto do topo) não entra."""
    x, y, fw, fh = rosto
    cx = x + fw / 2
    caixa = [max(0, cx - fw * 2.4), max(0, y - fh * 0.7), min(w, cx + fw * 2.4), h]
    pts = [[cx, y + fh * 0.6], [cx, y + fh * 2.4], [cx - fw * 1.3, y + fh * 3.0], [cx + fw * 1.3, y + fh * 3.0]]
    pts += [list(p) for p in (extra or [])]
    lab = [1] * len(pts)
    for dx, dy in ((-1.6, 1.3), (1.6, 1.3), (0, 1.9)):
        px, py = cx + dx * fw, y - dy * fh
        if py >= 2:
            pts.append([min(w - 2, max(2, px)), py])
            lab.append(0)
    return caixa, pts, lab


def _so_a_pessoa(b: np.ndarray, sementes: list) -> np.ndarray:
    """A mancha da pessoa na máscara do SAM: abre (tira os fiapos e as pintas que o SAM põe no escudo e na espada da parede, que a
    dilatação do limite ligaria ao cabelo) e fica só com as manchas que têm um ponto de dentro (o rosto, o braço, a mão)."""
    import cv2
    ab = _dil(_ero(b, 3), 3)
    _, lab = cv2.connectedComponents(ab.astype(np.uint8), connectivity=4)
    ks = {int(lab[min(b.shape[0] - 1, int(p[1])), min(b.shape[1] - 1, int(p[0]))]) for p in sementes} - {0}
    return np.isin(lab, list(ks)) if ks else ab


class _Trilha:
    """O SAM 2.1-tiny em vídeo, ONNX (export `square-zero-labs`, validado por eles contra o PyTorch: IoU 0,997): o 1º quadro leva o
    prompt do rosto e dali cada quadro passa pela atenção sobre a memória (o quadro do prompt, os 6 últimos, 16 ponteiros do objeto).
    Chamar `trilha(img, rosto)` em ordem; `rosto` só vale no 1º quadro e quando o SAM perde a pessoa (pontuação do objeto <= 0: aí o
    rosto a prende de novo e a memória recomeça)."""

    def __init__(self, sess: dict, const: dict):
        self.s, self.c = sess, const
        self.media = np.array(const["image_mean"], np.float32)
        self.desvio = np.array(const["image_std"], np.float32)
        self.tpe = np.array(const["memory_temporal_positional_encoding"], np.float32).reshape(7, 1, 64)
        self.reinicia()

    def reinicia(self):
        self.cond = None            # (tokens, pos, ponteiro, indice do quadro)
        self.recentes: list = []    # (tokens, pos, ponteiro, indice) dos quadros seguidos, o mais novo por último
        self.i = -1

    def _feats(self, img: np.ndarray):
        import cv2
        x = (cv2.resize(img, (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255 - self.media) / self.desvio
        return self.s["enc"].run(None, {"pixel_values": x.transpose(2, 0, 1)[None]})

    def _decodifica(self, f, cond_feats, pts, lab):
        return self.s["dec"].run(None, {"feats0": f[0], "feats1": f[1], "feats2_cond": cond_feats,
                                        "input_points": np.array([[pts]], np.float32), "input_labels": np.array([[lab]], np.int32)})

    def _memoria(self, f, alto, escore, binariza):
        t, p = self.s["menc"].run(None, {"feats2": f[2], "high_res_mask": alto, "object_score_logits": escore.reshape(1, 1),
                                         "binarize": np.array(binariza, np.float32)})
        return t, p

    def _cond_feats(self, f, total: int):
        """A atenção do quadro sobre a memória: o do prompt (linha 6 do PE temporal), os 6 últimos (linha = distância - 1; falta de quadro
        repete o mais novo) e 16 ponteiros do objeto em 4 pedaços de 64 (a posição vem da distância normalizada)."""
        blocos = [(self.cond[0], self.cond[1] + self.tpe[6])]
        viz = self.recentes[-6:]
        dist = [self.i - r[3] for r in viz]
        while len(viz) < 6:
            viz = viz + [viz[-1] if viz else self.cond]
            dist = dist + [dist[-1] if dist else 1]
        ordem = sorted(zip(dist, viz), key=lambda t: -t[0])
        for d, r in ordem:
            blocos.append((r[0], r[1] + self.tpe[max(0, min(5, d - 1))]))
        pont = [(self.i - self.cond[3], self.cond[2])] + [(self.i - r[3], r[2]) for r in reversed(self.recentes[-15:])]
        while len(pont) < 16:
            pont.append(pont[-1])
        diffs = np.array([d for d, _ in pont], np.float32) / max(1.0, min(total, 16) - 1.0)
        ppos = self.s["ptr"].run(None, {"normalized_diffs": diffs})[0]                  # (16, 64)
        ptoks = np.concatenate([p.reshape(4, 64) for _, p in pont]).reshape(64, 1, 64)
        ppe = np.repeat(ppos, 4, axis=0).reshape(64, 1, 64)
        mem = np.concatenate([b[0] for b in blocos] + [ptoks]).astype(np.float32)
        mpe = np.concatenate([b[1] for b in blocos] + [ppe]).astype(np.float32)
        feat = f[2].reshape(256, 4096).T.reshape(4096, 1, 256)
        pos = f[4].reshape(256, 4096).T.reshape(4096, 1, 256)
        return self.s["att"].run(None, {"current_vision_features": np.ascontiguousarray(feat), "current_vision_position_embeddings": np.ascontiguousarray(pos),
                                        "memory": mem, "memory_pos": mpe})[0]

    def __call__(self, img: np.ndarray, rosto, total: int = 16, extra: list | None = None) -> np.ndarray:
        import cv2
        h, w = img.shape[:2]
        self.i += 1
        f = self._feats(img)
        perdeu = False
        if self.cond is not None:
            o = self._decodifica(f, self._cond_feats(f, total), [[0.0, 0.0]], [-1])
            perdeu = float(o[3].reshape(-1)[0]) <= 0
        if self.cond is None or perdeu:
            self.cond, self.recentes = None, []
            caixa, pts, lab = _prompt(rosto, w, h, extra)
            sx, sy = 1024 / w, 1024 / h
            P = [[caixa[0] * sx, caixa[1] * sy], [caixa[2] * sx, caixa[3] * sy]] + [[a * sx, b * sy] for a, b in pts]
            o = self._decodifica(f, f[3], P, [2, 3] + lab)
            binariza = 1.0
        else:
            binariza = 0.0
        low, alto, _, escore, ptr = o
        self.low = low.reshape(256, 256)     # o logit cru (a medida do limiar usa)
        t, p = self._memoria(f, alto, escore.reshape(-1), binariza)
        reg = (t, p, ptr.reshape(256), self.i)
        if binariza:
            self.cond = reg
        else:
            self.recentes.append(reg)
        return _so_a_pessoa(cv2.resize(low.reshape(256, 256), (w, h), interpolation=cv2.INTER_LINEAR) > LIMIAR, [pts_semente(rosto)] + list(extra or []))


def pts_semente(rosto) -> list:
    """O ponto do rosto (dentro da pessoa) que escolhe a mancha da pessoa na máscara."""
    x, y, fw, fh = rosto
    return [x + fw / 2, y + fh * 0.6]


def _sam():
    """Uma trilha nova do SAM 2.1-tiny (vídeo, ONNX): (quadro RGB, rosto) em ordem -> silhueta da pessoa (bool, tamanho do quadro). Os
    modelos (181 MB) baixam na 1ª vez; as sessões do onnxruntime ficam em memória, a memória do vídeo é de cada trilha."""
    if "s" in _FINO:                         # o teste troca o SAM por um falso
        return _FINO["s"]
    import onnxruntime as ort
    if "ort" not in _FINO:
        a = {n.split("/")[1]: _modelo(n) for n in SAM_ARQUIVOS if n.startswith("sam2.1-tiny/")}
        mk = lambda n: ort.InferenceSession(str(a[n]), providers=["CPUExecutionProvider"])
        _FINO["ort"] = ({"enc": mk("vision_encoder.onnx"), "dec": mk("mask_decoder.onnx"), "menc": mk("memory_encoder.onnx"),
                         "att": mk("memory_attention.onnx"), "ptr": mk("pointer_tpos.onnx")}, json.loads(a["constants.json"].read_text(encoding="utf-8")))
    return _Trilha(*_FINO["ort"])


def _caixa(alfa: np.ndarray, margem: int = MARGEM) -> tuple[int, int, int, int] | None:
    """A caixa em volta da pessoa (maior mancha do fino) com `margem`: o que o grande enxerga."""
    ys, xs = np.nonzero(cena._maior_componente(alfa) > 128)
    if not len(ys):
        return None
    h, w = alfa.shape
    return (max(0, int(xs.min()) - margem), max(0, int(ys.min()) - margem),
            min(w, int(xs.max()) + 1 + margem), min(h, int(ys.max()) + 1 + margem))


def _alfa_grande(img: Image.Image, caixa: tuple[int, int, int, int]) -> np.ndarray:
    """O BiRefNet general-lite só no recorte da pessoa (0-1, tamanho do quadro). Sem o pós-processo do rembg, que
    binariza e serrilha a borda: o alfa macio do modelo é o que dá o cabelo."""
    from rembg import remove
    x0, y0, x1, y1 = caixa
    m = np.array(remove(img.crop(caixa).convert("RGB"), session=cena._sessao(GRANDE), only_mask=True,
                        post_process_mask=False), np.float32) / 255
    out = np.zeros((img.height, img.width), np.float32)
    out[y0:y1, x0:x1] = m
    return out


def _liga(b: np.ndarray, esc: int = 1) -> np.ndarray:
    """A maior mancha e as que encostam nela (a mão solta do corpo continua pessoa), sem fiapo nem mancha solta."""
    from scipy import ndimage
    lab, n = ndimage.label(b)
    if n < 2:
        return b
    tam = ndimage.sum(b, lab, range(1, n + 1))
    k = 1 + int(np.argmax(tam))
    perto = _dil(lab == k, 4 * esc)
    ok = lab == k
    for i in range(1, n + 1):
        if i != k and tam[i - 1] > 0.005 * tam[k - 1] and (perto & (lab == i)).any():
            ok |= lab == i
    return ok


def _limpa(g: np.ndarray, fino: np.ndarray, esc: int = 1) -> np.ndarray:
    """O alfa do grande (0-1) limpo: só o que o fino também vê como gente (tira o que o grande confunde: o microfone, o
    escudo), só a pessoa e o que encosta nela, furo pequeno tapado (o vão entre os dedos fica), miolo sólido e só a
    faixa da borda macia (com o halo do fundo tirado: abaixo de `PISO` é fundo, acima de `TETO` é pessoa).
    `esc` é quantas vezes a largura de 540 em que os px de cima foram medidos (`ESC` no quadro de `LADO`)."""
    from scipy import ndimage
    g = g * _dil(fino > 0.3, PERTO * esc)
    forma = _liga(g > 0.5, esc)
    cheio = ndimage.binary_fill_holes(forma)
    lab, n = ndimage.label(cheio & ~forma)
    if n:
        area = ndimage.sum(cheio & ~forma, lab, range(1, n + 1))
        forma = forma | np.isin(lab, 1 + np.nonzero(area <= FURO * esc * esc)[0])
    miolo = _ero(forma, NUCLEO * esc)
    faixa = _dil(forma, 2 * esc)
    a = np.clip((g - PISO) / (TETO - PISO), 0, 1)
    return np.where(miolo, 1.0, np.where(faixa, a, 0.0)).astype(np.float32)


def _entre(ka: np.ndarray, kb: np.ndarray, t: float, fino: np.ndarray) -> np.ndarray:
    """O alfa grande de um quadro SEM quadro-chave: a mistura dos dois vizinhos (`t` vai de 0 a 1 de `ka` a `kb`), com o MODNet
    do próprio quadro por cima onde ele tem certeza (>0,5) e a mistura toca (>0,2): é o que mantém a mão que se mexeu sólida
    em vez de metade do alfa. Fora da zona dos vizinhos o MODNet não entra (é onde ele erra: o fundo escuro). Medido na
    sequência: IoU contra o BiRefNet de todos os quadros 0,982 (0,977 só a mistura); o fantasma que sobra o `_limpa` corta."""
    mistura = (1 - t) * ka + t * kb
    return np.maximum(mistura, fino * (fino > 0.5) * (mistura > 0.2))


def _suaviza(alfas: list[np.ndarray], como_uint8: bool = False) -> list[np.ndarray]:
    """A borda não treme: média curta no tempo (1-2-1), e onde o vizinho difere muito (movimento de verdade) fica o próprio.
    Aceita alfa 0-1 ou uint8 (160 quadros de 1080x1920 em float não cabem na memória do notebook do aluno); `como_uint8` devolve uint8."""
    def f(x):
        return x.astype(np.float32) / 255 if x.dtype == np.uint8 else x
    out = []
    for i in range(len(alfas)):
        a, p, q = f(alfas[i]), f(alfas[max(0, i - 1)]), f(alfas[min(len(alfas) - 1, i + 1)])
        wp, wq = 0.25 * (np.abs(p - a) < 0.4), 0.25 * (np.abs(q - a) < 0.4)
        r = (1 - wp - wq) * a + wp * p + wq * q
        out.append((r * 255 + 0.5).astype(np.uint8) if como_uint8 else r)
    return out


class Mascaras(list):
    """As máscaras do trecho (0-255, uma por quadro) e, em `extra`, o que o matte mediu e a máscara sozinha não diz (`excesso`)."""
    extra: dict


EXCESSO_ZONA = 3.0    # % da área do rosto que o recorte sem o SAM leva a mais, na zona da cabeça, pra o quadro contar como excesso


def _excesso(g: np.ndarray, fino: np.ndarray, lim: np.ndarray, rosto: tuple[float, float, float, float]) -> float:
    """O que o recorte SEM o limite do SAM leva a mais na zona da cabeça (da testa pra cima e a largura da cabeça), em % da área do
    rosto: é o objeto da cor do cabelo colado na cabeça (o Majora, a ponta da cadeira), que a `ponta` não vê. O SAM o tira,
    mas o excesso diz que o fundo ali é difícil: o SAM pode ter seguido a coisa errada."""
    x, y, fw, fh = rosto
    cx = x + fw / 2
    h, w = g.shape
    z = (slice(int(max(0, y - 0.8 * fh)), int(min(h, y + 0.1 * fh))), slice(int(max(0, cx - 1.1 * fw)), int(min(w, cx + 1.1 * fw))))
    sem = (g[z] * _dil(fino[z] > 0.3, PERTO * ESC)) > 0.5
    return 100.0 * float((sem & ~lim[z]).sum()) / max(1.0, fw * fh)


def _limites(quadros: list[Path], chaves: list[int], finos: list | None = None):
    """O limite (bool, tamanho do quadro) de cada quadro pelo SAM, e o rosto de cada quadro-chave. O SAM roda a cada `SAM_CADA`-ésimo
    quadro e nos quadros-chave; o do meio é a união dos vizinhos (a mão que se mexeu entre dois quadros fica dentro). O rosto que o
    YuNet não achou vem do quadro mais perto onde achou. `None` se o SAM não rodou (sem rede na 1ª vez, ou rosto em nenhum quadro)."""
    n = len(quadros)
    rodar = sorted({*range(0, n, SAM_CADA), n - 1, *chaves})
    abre = lambda i: np.asarray(Image.open(quadros[i]).convert("RGB"))
    rostos = {i: _rosto(abre(i)) for i in rodar}
    achados = [i for i in rodar if rostos[i]]
    if not achados:
        print("recorte: rosto não achado; sem o limite do SAM", file=sys.stderr)
        return None, {}
    for i in rodar:
        if not rostos[i]:
            rostos[i] = rostos[min(achados, key=lambda j: abs(j - i))]
    sam = _sam()
    lims = {}
    for i in rodar:
        m = sam(abre(i), rostos[i], len(rodar), _pontos_do_corpo(finos[i], rostos[i]) if finos else None)
        if finos and m.sum() < 0.6 * (finos[i] > 128).sum():     # o SAM pegou menos da metade do que o MODNet vê: não vale como limite
            m = np.ones_like(m)
        lims[i] = m if m.all() else _dil(m, LIMITE)
    for i in range(n):
        if i not in lims:
            lims[i] = lims[max(j for j in rodar if j < i)] | lims[min(j for j in rodar if j > i)]
    return lims, rostos


def _matte_do_trecho(quadros: list[Path]) -> list[np.ndarray]:
    """As máscaras (0-255) dos quadros: o MODNet em todos (diz onde há gente), o BiRefNet general-lite, no recorte da pessoa, a
    cada `CHAVE`-ésimo quadro (é ele que dá o contorno e o cabelo) e o SAM 2.1-tiny a cada `SAM_CADA`-ésimo (diz quem PODE ser
    pessoa: o alfa só vale dentro do limite dele); os quadros do meio misturam os dois vizinhos e o fino do próprio quadro. Cai
    pro que houver: sem o SAM, o recorte sem limite; sem o grande, o fino limpo; sem o fino, o u2netp. Tudo em `LADO` de largura."""
    abre = lambda i: Image.open(quadros[i]).convert("RGB")
    n = len(quadros)
    try:
        fino = _modnet()
    except Exception as e:      # sem rede e sem o modelo: o u2netp do rembg (a trava de qualidade avalia o que sair)
        print(f"recorte: sem MODNet ({e}); u2netp", file=sys.stderr)
        return [cena._alfa(abre(i), "u2netp", lado=512) for i in range(n)]
    finos = [fino(abre(i)) for i in range(n)]
    ks = sorted({*range(0, n, CHAVE), n - 1})
    try:
        lims, rostos = _limites(quadros, ks, finos)
    except Exception as e:      # sem o SAM: o recorte de antes
        print(f"recorte: sem SAM ({e}); sem o limite", file=sys.stderr)
        lims, rostos = None, {}
    extra: dict = {"sam": lims is not None}
    f1 = lambda i: finos[i].astype(np.float32) / 255
    try:
        chaves, exc = {}, {}
        for k in ks:
            cx = _caixa(finos[k], MARGEM * ESC)
            g = _alfa_grande(abre(k), cx) if cx else np.zeros(finos[k].shape, np.float32)
            if lims is not None:
                exc[k] = _excesso(g, f1(k), lims[k], rostos[k])
                g = g * lims[k]
            chaves[k] = g.astype(np.float16)
    except Exception as e:      # sem o grande: só o fino
        print(f"recorte: sem BiRefNet ({e}); MODNet sozinho", file=sys.stderr)
        out = [cena._maior_componente((_limpa(f1(i), f1(i), ESC) * (lims[i] if lims is not None else 1) * 255).astype(np.uint8)) for i in range(n)]
        r = Mascaras(out)
        r.extra = extra
        return r
    if exc:
        extra["excesso"] = {"quadros": sorted(exc), "pct": [round(exc[k], 2) for k in sorted(exc)]}
    limpos = []
    for i in range(n):
        if i in chaves:
            g = chaves[i].astype(np.float32)
        else:
            ant = max(k for k in ks if k <= i)
            pos = min(k for k in ks if k >= i)
            g = _entre(chaves[ant].astype(np.float32), chaves[pos].astype(np.float32), (i - ant) / (pos - ant), f1(i))
            if lims is not None:
                g = g * lims[i]
        limpos.append((_limpa(g, f1(i), ESC) * 255 + 0.5).astype(np.uint8))
    r = Mascaras(_suaviza(limpos, como_uint8=True))
    r.extra = extra
    return r


def recorta_pessoa(video: Path, ini: float, fim: float, saida: Path, taxa: int = TAXA,
                   usa_cache: bool = True, modelo: str = MODELO) -> dict:
    """Recorta a pessoa de `video` entre `ini` e `fim` (segundos do bruto).

    Grava em `saida` a MÁSCARA (gray, ffv1, `taxa` qps, `LADO` de largura: a do quadro final): pequena perto de um vídeo
    com alfa. Quem monta junta com o take por `grafo_alfa`, que interpola a máscara até o fps do take.
    Devolve o meta (o mesmo do .json do cache): `mascara`, `topo`, `hw`, `cx` em pixels do quadro 1080x1920,
    `largura`, `altura` (1080, 1920), `fps`, `quadros`, `ms_quadro` (0 se veio do cache) e `cache`."""
    video, saida = Path(video), Path(saida)
    cache = cena.CACHE / "pessoa"
    chave = _chave(video, ini, fim, taxa, modelo)
    c_mov, c_json = cache / f"{chave}.mov", cache / f"{chave}.json"
    if usa_cache and c_mov.exists() and c_json.exists():
        meta = json.loads(c_json.read_text(encoding="utf-8"))
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_bytes(c_mov.read_bytes())
        return {**meta, "mascara": str(saida), "ms_quadro": 0.0, "cache": True}

    sonda = ff.probe(video)
    L, A, fps = sonda.largura, sonda.altura, sonda.fps
    dur = fim - ini
    lh = int(round(LADO * A / L / 2)) * 2
    meds, t_matte, mascaras = [], 0.0, []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "q").mkdir()
        (td / "m").mkdir()
        ff.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ini}", "-t", f"{dur}", "-i", video,
                "-vf", f"fps={taxa},scale={LADO}:{lh}", td / "q" / "%05d.png"], quiet=True)
        quadros = sorted((td / "q").glob("*.png"))
        if not quadros:
            raise RuntimeError(f"nenhum quadro em {video} entre {ini} e {fim}")
        t0 = time.perf_counter()
        mascaras = _matte_do_trecho(quadros)
        t_matte = time.perf_counter() - t0
        for i, a in enumerate(mascaras, 1):
            Image.fromarray(a).save(td / "m" / f"{i:05d}.png")
            if (md := medida_da_cabeca(a)):
                meds.append(md)
        if not meds:
            raise RuntimeError("o matte não achou pessoa no trecho")
        mov = td / "mascara.mov"
        ff.run(["ffmpeg", "-y", "-v", "error", "-framerate", f"{taxa}", "-i", td / "m" / "%05d.png",
                "-c:v", "ffv1", "-pix_fmt", "gray", mov], quiet=True)
        med = {k: float(np.median([x[k] for x in meds])) for k in meds[0]}
        # em pixels do quadro 1080x1920, qualquer que seja o tamanho do bruto (540x960, 4K...): o enquadramento é um só
        meta = {"topo": med["topo"] * 1920, "hw": med["hw"] * 1080, "cx": med["cx"] * 1080, "largura": 1080,
                "altura": 1920, "quadros": len(quadros), "taxa_matte": taxa, "fps": fps,
                "ms_quadro": 1000 * t_matte / len(quadros), "cache": False, "modelo": modelo,
                "qualidade": {**mede_qualidade(mascaras), **getattr(mascaras, "extra", {}), "ini": ini, "taxa": taxa}}
        cache.mkdir(parents=True, exist_ok=True)
        tmp = c_mov.with_suffix(".tmp.mov")
        tmp.write_bytes(mov.read_bytes())
        tmp.replace(c_mov)
        c_json.write_text(json.dumps(meta), encoding="utf-8")
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_bytes(mov.read_bytes())
    return {**meta, "mascara": str(saida)}


def grafo_alfa(take_i: int, mascara_i: int, meta: dict, saida: str = "p") -> str:
    """Filtro que faz do take (entrada `take_i`) a pessoa com alfa (rótulo `saida`): a máscara sobe pro
    tamanho do take e o `framerate` mistura os quadros vizinhos até o fps do take (a interpolação)."""
    L, A = meta["largura"], meta["altura"]
    return (f"[{mascara_i}:v]format=gray,erosion,scale={L}:{A}:flags=bicubic,"
            f"framerate=fps={meta['fps']}:interp_start=0:interp_end=255:scene=100[_m];"
            f"[{take_i}:v]scale={L}:{A},format=yuv444p[_v];[_v][_m]alphamerge[{saida}]")


# O enquadramento da ref do dono (De3s_A.js, S.dividida claro): cabelo y 1064, queixo y 1686 em 1080x1920.
ALVO_TOPO, ALVO_QUEIXO = 1064, 1686


def queixo(meta: dict) -> float:
    return meta["topo"] + K_QUEIXO * meta["hw"]


def enquadra(meta: dict) -> dict:
    """Escala e posição da pessoa no quadro 1080x1920 pra o cabelo cair em 1064 e o queixo em 1686.

    A escala sai da altura da cabeça (queixo - topo); o centro vai pra x 540. A escala é limitada
    (0,8 a 1,6): cabeça que pede mais que isso é enquadramento ruim, e a fábrica avisa em vez de esticar."""
    s = (ALVO_QUEIXO - ALVO_TOPO) / max(1.0, queixo(meta) - meta["topo"])
    aviso = "" if 0.8 <= s <= 1.6 else f"cabeça pede escala {s:.2f}: enquadramento do bruto fora do que a tela dividida aguenta"
    s = min(1.6, max(0.8, s))
    return {"escala": s, "x": 540 - meta["cx"] * s, "y": ALVO_TOPO - meta["topo"] * s, "aviso": aviso}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("video", type=Path)
    p.add_argument("--ini", type=float, default=0.0)
    p.add_argument("--fim", type=float, required=True)
    p.add_argument("--saida", type=Path, required=True)
    p.add_argument("--taxa", type=int, default=TAXA)
    a = p.parse_args()
    meta = recorta_pessoa(a.video, a.ini, a.fim, a.saida, a.taxa)
    print(json.dumps({**meta, **enquadra(meta)}, indent=1))


if __name__ == "__main__":
    main()
