"""
OCR 모듈: 휴대폰 카메라 프레임 한 장 -> 카드별 영어 텍스트

사용법:
    from ocr_module import extract
    for card in extract(jpeg_bytes):   # 또는 OpenCV 이미지(numpy 배열)
        print(card["title"], card["text"])

반환 형식 (벡터화 담당에게 넘기는 데이터):
    {"title": str, "text": str, "confidence": float, "timestamp": str}

같은 카드(제목)가 더 높은 신뢰도로 다시 읽히면 다시 반환한다.
DB 쪽에서는 title 기준으로 덮어쓰기(upsert) 하면 된다.
"""
from datetime import datetime

import cv2
import numpy as np
from rapidfuzz import fuzz
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

# ----- 조정용 값 (실제 촬영 사진 보면서 바꾸기) -----
BLUR_THRESHOLD = 60       # 이보다 선명도가 낮으면 흔들린 프레임으로 보고 버림
MIN_CARD_AREA = 0.05      # 화면 대비 카드 최소 면적 비율
CARD_RATIO = 16 / 9       # 카드 세로/가로 비율 (테스트 페이지 카드는 9:16)
RATIO_MIN = 1.4           # 이보다 납작하면 카드가 아님
CUT_TOLERANCE = 0.08      # 정상 폭보다 8% 이상 좁으면 잘린 카드로 봄
EDGE_MARGIN = 3           # 사진 끝에서 이만큼 안쪽이어야 "완전히 보이는 카드"
MIN_SCORE = 0.5           # 이보다 낮은 신뢰도의 줄은 버림
UPSCALE = 1               # 카드 이미지 확대 배율 (실제 사진에서 글씨가 작으면 1.5~2로)
DUP_SIMILARITY = 85       # 제목 유사도가 이 이상이면 같은 카드로 봄

# 글자 인식은 영어 전용 모델 (PP-OCRv5 en). 기본값인 중국어 모델은 영어 띄어쓰기를 자주 빼먹는다
engine = RapidOCR(params={
    "Rec.lang_type": LangRec.EN,
    "Rec.ocr_version": OCRVersion.PPOCRV5,
    "Rec.model_type": ModelType.MOBILE,
    # 속도: 카드 글자는 뒤집히지 않으므로 방향 판별을 끄고,
    # 검출 이미지는 키우지 않고 긴 변 736px 이하로만 줄인다 (기본값은 짧은 변을 736px까지 키움)
    "Global.use_cls": False,
    "Det.limit_type": "max",
    "Det.limit_side_len": 736,
    "Global.log_level": "error",
})
seen = {}  # 제목(소문자) -> 마지막으로 반환한 결과


def to_image(frame):
    """JPEG/PNG 바이트 또는 numpy 배열을 OpenCV 이미지로 변환"""
    if isinstance(frame, np.ndarray):
        return frame
    return cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)


def is_sharp(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() >= BLUR_THRESHOLD


def classify_boxes(img):
    """프레임 속 흰 사각형마다 (x, y, w, h, 판정) 반환. 판정이 "ok"면 완전한 카드

    카드는 두 가지 방식으로 잘린다.
      1) 사진 끝에 걸림 (폰이 카드 일부만 찍음)
      2) 컨베이어 영역 끝에 걸림 (페이지가 overflow:hidden으로 자름)
         → 사진 안쪽에 있어서 1)로는 못 잡음. 폭이 정상보다 좁은 걸로 잡는다.
    """
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = [cv2.boundingRect(c) for c in cnts]
    boxes = [b for b in boxes if b[2] * b[3] >= W * H * MIN_CARD_AREA]
    # 정상 카드 폭 = 높이로 계산한 폭과 실제로 가장 넓은 카드 폭 중 큰 값
    # (카드 여러 장이 붙어 한 덩어리가 된 건 기준에서 뺀다)
    max_w = max((b[2] for b in boxes if b[3] / b[2] >= RATIO_MIN), default=0)

    out = []
    for x, y, w, h in sorted(boxes, key=lambda b: b[0]):
        full_w = max(h / CARD_RATIO, max_w)
        if h / w < RATIO_MIN:
            verdict = "카드 아님(납작함)"
        elif x <= EDGE_MARGIN or y <= EDGE_MARGIN \
                or x + w >= W - EDGE_MARGIN or y + h >= H - EDGE_MARGIN:
            verdict = "잘림(사진 끝)"
        elif w < full_w * (1 - CUT_TOLERANCE):
            verdict = f"잘림(폭 {w / full_w:.0%})"
        else:
            verdict = "ok"
        out.append((x, y, w, h, verdict))
    return out


def find_cards(img):
    """프레임에서 완전히 보이는 카드들만 왼쪽부터 순서대로 잘라서 반환"""
    return [img[y:y + h, x:x + w] for x, y, w, h, v in classify_boxes(img) if v == "ok"]


def join_lines(lines):
    """줄들을 한 문장으로 합치기. 줄 끝 하이픈(hyphen-ated)은 붙여서 이어줌"""
    out = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if out.endswith("-") and line[:1].islower():
            out = out[:-1] + line
        else:
            out = f"{out} {line}" if out else line
    return out


def read_card(card):
    """카드 한 장 -> (제목, 본문, 평균 신뢰도). 못 읽으면 None"""
    if UPSCALE != 1:
        card = cv2.resize(card, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    result = engine(card)
    if result.txts is None or len(result.txts) == 0:
        return None

    # (윗변 y, 왼쪽 x, 텍스트, 신뢰도)
    lines = [(box[0][1], box[0][0], txt, float(score))
             for box, txt, score in zip(result.boxes, result.txts, result.scores)
             if float(score) >= MIN_SCORE]
    lines.sort(key=lambda l: (round(l[0] / 10), l[1]))  # 위→아래, 같은 줄이면 왼→오
    lines = [l for l in lines if not l[2].strip().isdigit()]  # 카드 번호(001 등) 제거
    if len(lines) < 2:
        return None

    # 제목은 대문자로 표시됨 → 맨 위에서부터 이어지는 대문자 줄들을 제목으로 봄
    n_title = 0
    while n_title < len(lines) and any(ch.isalpha() for ch in lines[n_title][2]) \
            and lines[n_title][2].upper() == lines[n_title][2]:
        n_title += 1
    n_title = max(n_title, 1)

    title = join_lines(l[2] for l in lines[:n_title])
    text = join_lines(l[2] for l in lines[n_title:])
    if not text:
        return None
    conf = sum(l[3] for l in lines) / len(lines)
    return title, text, conf


def extract(frame):
    """프레임 한 장 -> 새로 저장할(또는 더 잘 읽힌) 카드 목록"""
    img = to_image(frame)
    if img is None or not is_sharp(img):
        return []

    out = []
    for card in find_cards(img):
        r = read_card(card)
        if not r:
            continue
        title, text, conf = r
        key = title.lower()
        dup = next((k for k in seen if fuzz.ratio(k, key) >= DUP_SIMILARITY), None)
        if dup and seen[dup]["confidence"] >= conf:
            continue  # 이미 더 잘 읽은 버전이 있음

        item = {
            "title": title,
            "text": text,
            "confidence": round(conf, 3),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        seen[dup or key] = item
        out.append(item)
    return out


def reset():
    """중복 기록 초기화 (새 세션 시작할 때)"""
    seen.clear()
