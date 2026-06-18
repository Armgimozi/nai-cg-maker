"""Danbooru 태그 사전 로딩 및 조회.

danbooru.csv(tag,category,post_count,"aliases") 를 읽어
  - 정식 태그 존재 여부 검증
  - 별칭 → 정식 태그 해석
  - post 수(인기도) / 카테고리 부여
에 사용한다. LLM 이 제안한 태그를 '실제 존재하는 정식 태그'로 정규화하는 것이 목적.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# CSV 의 카테고리 정수 코드 → 이름
CATEGORY = {0: "general", 1: "artist", 3: "copyright", 4: "character", 5: "meta"}


def normalize(name: str) -> str:
    """LLM/사용자 입력 태그를 danbooru 표기로 정규화: 소문자, 공백→언더스코어."""
    n = name.strip().lower().strip("\"'")
    # 내부 연속 공백을 단일 언더스코어로
    n = "_".join(part for part in n.replace("\t", " ").split(" ") if part)
    return n


@dataclass
class Match:
    tag: str            # 정식 태그명
    category: str       # general/artist/copyright/character/meta
    count: int          # post 수
    matched_as: str | None  # 별칭으로 매칭됐을 때 입력 별칭, 아니면 None


class TagDB:
    def __init__(self, csv_path: str | Path):
        self.path = Path(csv_path)
        self.tags: dict[str, tuple[int, int]] = {}      # name -> (category_code, count)
        self.alias: dict[str, str] = {}                  # alias -> canonical name
        self.rev_alias: dict[str, list[str]] = {}        # canonical name -> [alias, ...]
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(
                f"태그 사전이 없습니다: {self.path}\n"
                "먼저 `python fetch_tags.py` 로 danbooru.csv 를 받아주세요."
            )
        with open(self.path, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if len(row) < 3:
                    continue
                name = row[0].strip()
                if not name:
                    continue
                try:
                    cat = int(row[1])
                except ValueError:
                    cat = 0
                try:
                    count = int(row[2])
                except ValueError:
                    count = 0
                self.tags[name] = (cat, count)
                if len(row) >= 4 and row[3]:
                    for al in row[3].split(","):
                        al = al.strip()
                        # tagcomplete 의 '/xx' 단축키는 별칭이 아니므로 제외
                        if al and not al.startswith("/"):
                            self.alias.setdefault(al, name)
                            self.rev_alias.setdefault(name, []).append(al)

    def aliases_of(self, name: str) -> list[str]:
        """정식 태그명 → 알려진 별칭 목록(없으면 빈 리스트)."""
        return self.rev_alias.get(name, [])

    def __len__(self) -> int:
        return len(self.tags)

    def lookup(self, raw: str) -> Match | None:
        """입력 태그를 정식 태그로 해석. 없으면 None."""
        n = normalize(raw)
        if not n:
            return None
        if n in self.tags:
            cat, count = self.tags[n]
            return Match(n, CATEGORY.get(cat, "general"), count, None)
        canon = self.alias.get(n)
        if canon and canon in self.tags:
            cat, count = self.tags[canon]
            return Match(canon, CATEGORY.get(cat, "general"), count, n)
        return None

    def search(self, query: str, limit: int = 60) -> list[Match]:
        """직접 조회: 입력 글자가 태그명/별칭에 들어간 정식 태그를 인기순으로.

        LLM 없이 CSV 만으로 동작(키·비용 불필요). 정확도순(완전일치→접두→단어
        시작→부분일치) 1차, 같은 등급 안에서는 post 수(인기) 2차 정렬한다.
        """
        q = normalize(query)
        if not q:
            return []
        scored: list[tuple[float, int, str, Match]] = []
        seen: set[str] = set()
        for name, (cat, count) in self.tags.items():
            rank = _match_rank(name, q)
            if rank is None:
                continue
            seen.add(name)
            scored.append((rank, -count, name,
                           Match(name, CATEGORY.get(cat, "general"), count, None)))
        # 별칭으로만 잡히는 태그(정식명에는 q 가 없던 것)도 보강해서 포함
        for al, canon in self.alias.items():
            if canon in seen or canon not in self.tags:
                continue
            rank = _match_rank(al, q)
            if rank is None:
                continue
            seen.add(canon)
            cat, count = self.tags[canon]
            scored.append((rank + 0.5, -count, canon,
                           Match(canon, CATEGORY.get(cat, "general"), count, al)))
        scored.sort(key=lambda t: (t[0], t[1], t[2]))
        return [m for _, _, _, m in scored[:limit]]


def _match_rank(name: str, q: str) -> float | None:
    """name 안에서 q 의 매칭 품질(낮을수록 좋음). 매칭 없으면 None.

    0=완전일치, 1=단어(언더스코어 토큰)의 시작, 2=그 외 부분일치.
    접두사와 '_단어' 시작을 같은 등급으로 묶어, 그 안에서는 인기(post 수)가
    순서를 정하게 한다. 예) 'eyes' → blue_eyes(176만)가 eyes_*(소수)보다 위.
    """
    if name == q:
        return 0.0
    if name.startswith(q) or any(part.startswith(q) for part in name.split("_")):
        return 1.0
    if q in name:
        return 2.0
    return None
