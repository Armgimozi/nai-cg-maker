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
