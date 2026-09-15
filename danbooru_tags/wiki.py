"""위키 저장소 — 사람도 AI 도 읽는 마크다운 문서함.

문서 1개 = ``wiki/<slug>.md`` 파일 하나. 맨 위에 짧은 front matter 를 두고
그 아래가 본문(마크다운)이다. 파일이 그대로 사람이 읽는 형태라 git 에 커밋해
버전 관리하기 좋고, 서버 없이도 Claude Code 같은 AI 에이전트가 폴더를 열어
바로 읽을 수 있다.

    ---
    title: 세라 (주인공)
    tags: 캐릭터, 설정
    updated: 2026-09-15T12:00:00+00:00
    ---
    은발에 붉은 눈. 항상 검은 리본을 …

서버(server.py)는 이 저장소를 두 가지로 노출한다.
  * 앱 UI 용 JSON API  (/api/wiki …)
  * AI/스크립트 용 평문 (/wiki/<slug>.md, /llms.txt, /llms-full.txt)
또 스튜디오의 '장면 태그 찾기'·'재구성' 요청에 문서를 골라 붙이면 Claude 가
그 내용을 맥락으로 읽는다(server.py 의 wiki_pages 처리).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# slug: 한글·영문·숫자·'-'·'_' 만(경로 탈출/특수문자 차단). 파일명 = slug + ".md"
_SLUG_RE = re.compile(r"^[\w\-]{1,80}$", re.UNICODE)
_FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
MAX_CONTENT = 200_000  # 문서 1개 본문 상한(바이트가 아닌 글자 수)


class WikiError(ValueError):
    """잘못된 slug/입력 등 사용자 오류(HTTP 400 으로 응답)."""


@dataclass
class Page:
    slug: str
    title: str
    content: str = ""
    tags: list[str] = field(default_factory=list)
    updated: str = ""

    def to_dict(self, with_content: bool = True) -> dict:
        d = {"slug": self.slug, "title": self.title, "tags": list(self.tags),
             "updated": self.updated, "summary": summarize(self.content)}
        if with_content:
            d["content"] = self.content
        return d

    def to_markdown(self) -> str:
        """front matter + 본문. 파일 저장/평문 응답 공용."""
        fm = [f"title: {self.title}"]
        if self.tags:
            fm.append("tags: " + ", ".join(self.tags))
        if self.updated:
            fm.append(f"updated: {self.updated}")
        return "---\n" + "\n".join(fm) + "\n---\n" + self.content.rstrip("\n") + "\n"


def normalize_slug(s: str) -> str:
    """제목/입력 → slug. 공백은 '-', 허용되지 않는 문자는 제거. 유니코드(한글) 유지."""
    s = unicodedata.normalize("NFC", str(s or "")).strip().lower()
    s = re.sub(r"[\s/\\]+", "-", s)
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    return s[:80]


def validate_slug(slug: str) -> str:
    slug = unicodedata.normalize("NFC", str(slug or "")).strip()
    if not _SLUG_RE.match(slug) or slug in (".", "..") or slug.startswith("."):
        raise WikiError("문서 이름(slug)은 한글·영문·숫자·'-'·'_' 만 쓸 수 있습니다 (1~80자).")
    return slug


def summarize(content: str, limit: int = 140) -> str:
    """본문 첫 문단을 마크다운 기호를 대충 벗겨 한 줄 요약으로."""
    for para in re.split(r"\n\s*\n", content.strip()):
        # 제목 줄은 요약에서 뺀다(제목은 따로 있으므로)
        text = re.sub(r"^\s{0,3}#{1,6}\s.*$", "", para, flags=re.M)
        text = re.sub(r"^\s{0,3}([-*+]\s+|\d+\.\s+|>\s*)", "", text, flags=re.M)
        text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"[`*_~]+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"
    return ""


def parse_markdown(raw: str, slug: str) -> Page:
    """파일 내용 → Page. front matter 가 없으면 첫 '# 제목' 또는 slug 를 제목으로."""
    meta: dict[str, str] = {}
    body = raw
    m = _FM_RE.match(raw)
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            if sep:
                meta[k.strip().lower()] = v.strip()
    title = meta.get("title", "")
    if not title:
        h = re.search(r"^#\s+(.+?)\s*$", body, re.M)
        title = h.group(1).strip() if h else slug
    tags = [t.strip() for t in re.split(r"[,\n]", meta.get("tags", "")) if t.strip()]
    return Page(slug=slug, title=title, content=body.strip("\n"), tags=tags,
                updated=meta.get("updated", ""))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WikiStore:
    """``wiki/`` 폴더의 .md 파일을 읽고 쓰는 얇은 저장소.

    매 요청마다 디스크를 읽으므로(문서 수백 개 규모까진 충분히 빠름) 파일을
    에디터/AI 가 직접 고쳐도 서버 재시작 없이 즉시 반영된다. gunicorn 워커가
    여럿이어도 같은 디스크를 보므로 서로 어긋나지 않는다."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # ── 조회 ──
    def _path(self, slug: str) -> Path:
        return self.root / f"{validate_slug(slug)}.md"

    def exists(self, slug: str) -> bool:
        try:
            return self._path(slug).is_file()
        except WikiError:
            return False

    def get(self, slug: str) -> Page | None:
        p = self._path(slug)
        if not p.is_file():
            return None
        return parse_markdown(p.read_text(encoding="utf-8"), p.stem)

    def list(self) -> list[Page]:
        if not self.root.is_dir():
            return []
        pages = []
        for p in self.root.glob("*.md"):
            if p.name.startswith(".") or not _SLUG_RE.match(p.stem):
                continue
            try:
                pages.append(parse_markdown(p.read_text(encoding="utf-8"), p.stem))
            except (OSError, UnicodeDecodeError):
                continue
        # 최근 수정 순(updated 없으면 파일 mtime), 같으면 제목순
        def key(pg: Page):
            return (pg.updated or datetime.fromtimestamp(
                (self.root / f"{pg.slug}.md").stat().st_mtime, tz=timezone.utc
            ).isoformat(), pg.title)
        pages.sort(key=key, reverse=True)
        return pages

    def search(self, query: str, limit: int = 30) -> list[dict]:
        """단순 키워드 검색. 공백으로 나눈 모든 단어가 (제목/태그/본문 어딘가에)
        들어 있는 문서를, 제목·태그 일치에 가중치를 줘 정렬한다. 문서 수가 많지
        않은 개인 위키를 전제로 한 것이라 색인 없이 매번 훑는다."""
        words = [w.lower() for w in query.split() if w.strip()]
        if not words:
            return []
        hits = []
        for pg in self.list():
            title, body = pg.title.lower(), pg.content.lower()
            tags = " ".join(pg.tags).lower()
            score = 0
            ok = True
            for w in words:
                in_title, in_tags, in_body = w in title, w in tags, w in body
                if not (in_title or in_tags or in_body):
                    ok = False
                    break
                score += (10 if in_title else 0) + (5 if in_tags else 0) + min(body.count(w), 5)
            if ok:
                hits.append((score, pg))
        hits.sort(key=lambda x: (-x[0], x[1].title))
        out = []
        for score, pg in hits[:limit]:
            d = pg.to_dict(with_content=False)
            d["score"] = score
            d["snippet"] = _snippet(pg.content, words)
            out.append(d)
        return out

    # ── 변경 ──
    def put(self, slug: str, title: str, content: str, tags: list[str] | None = None,
            updated: str | None = None) -> Page:
        slug = validate_slug(slug)
        title = (title or "").strip() or slug
        content = (content or "").replace("\r\n", "\n")
        if len(content) > MAX_CONTENT:
            raise WikiError(f"본문이 너무 깁니다(최대 {MAX_CONTENT:,}자).")
        clean_tags = []
        for t in tags or []:
            t = str(t).strip()
            if t and t not in clean_tags:
                clean_tags.append(t)
        page = Page(slug=slug, title=title, content=content.strip("\n"),
                    tags=clean_tags, updated=updated or _now())
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self._path(slug).with_suffix(".md.tmp")
        tmp.write_text(page.to_markdown(), encoding="utf-8")
        tmp.replace(self._path(slug))  # 원자적 교체: 쓰다 죽어도 반쪽 파일이 남지 않음
        return page

    def delete(self, slug: str) -> bool:
        p = self._path(slug)
        if not p.is_file():
            return False
        p.unlink()
        return True

    def rename(self, old: str, new: str) -> Page:
        page = self.get(old)
        if page is None:
            raise WikiError("원본 문서가 없습니다.")
        new = validate_slug(new)
        if new != page.slug and self.exists(new):
            raise WikiError("같은 이름의 문서가 이미 있습니다.")
        moved = self.put(new, page.title, page.content, page.tags, updated=page.updated)
        if new != page.slug:
            self.delete(page.slug)
        return moved

    # ── 내보내기/가져오기 (배포 환경은 디스크가 초기화될 수 있어 백업용) ──
    def export_all(self) -> dict:
        return {"format": "nai-cg-maker-wiki/1", "exported": _now(),
                "pages": [p.to_dict() for p in self.list()]}

    def import_all(self, data: dict, overwrite: bool = False) -> dict:
        pages = data.get("pages") if isinstance(data, dict) else None
        if not isinstance(pages, list):
            raise WikiError("가져올 데이터 형식이 아닙니다 (pages 배열이 필요).")
        added = skipped = 0
        for item in pages:
            if not isinstance(item, dict):
                continue
            slug = item.get("slug") or normalize_slug(item.get("title", ""))
            try:
                slug = validate_slug(slug)
            except WikiError:
                skipped += 1
                continue
            if not overwrite and self.exists(slug):
                skipped += 1
                continue
            self.put(slug, item.get("title") or slug, item.get("content") or "",
                     item.get("tags") or [], updated=item.get("updated") or None)
            added += 1
        return {"imported": added, "skipped": skipped}

    # ── AI/LLM 용 평문 ──
    def llms_index(self, base_url: str = "") -> str:
        """llms.txt 관례(https://llmstxt.org): 사이트/문서를 LLM 이 훑기 좋은 목차."""
        base = base_url.rstrip("/")
        lines = ["# NAI CG Maker 위키", "",
                 "> 사용자가 정리한 캐릭터·작품·프롬프트 설정 위키. 아래 각 문서는 "
                 "마크다운 원문(.md)으로 바로 읽을 수 있고, `/llms-full.txt` 는 전체를 한 파일로 준다.", "",
                 "## 읽는 법 (AI 에이전트용)", "",
                 f"- 목록(JSON): `GET {base}/api/wiki`",
                 f"- 문서 1개(JSON): `GET {base}/api/wiki/<slug>`  ·  원문: `GET {base}/wiki/<slug>.md`",
                 f"- 검색: `GET {base}/api/wiki/search?q=<키워드>`",
                 f"- 전체 원문: `GET {base}/llms-full.txt`",
                 f"- 쓰기(허용 시): `PUT {base}/api/wiki/<slug>` JSON {{title, content, tags}}", "",
                 "## 문서", ""]
        for pg in self.list():
            desc = summarize(pg.content, 100)
            tag = f" [{', '.join(pg.tags)}]" if pg.tags else ""
            lines.append(f"- [{pg.title}]({base}/wiki/{pg.slug}.md){tag}"
                         + (f": {desc}" if desc else ""))
        if not self.list():
            lines.append("- (아직 문서가 없습니다)")
        return "\n".join(lines) + "\n"

    def llms_full(self) -> str:
        parts = ["# NAI CG Maker 위키 — 전체 문서\n"]
        for pg in self.list():
            head = f"\n\n---\n\n# {pg.title}\n\nslug: {pg.slug}"
            if pg.tags:
                head += f"\ntags: {', '.join(pg.tags)}"
            if pg.updated:
                head += f"\nupdated: {pg.updated}"
            parts.append(head + "\n\n" + pg.content)
        return "".join(parts) + "\n"

    def context_for_ai(self, slugs: list[str], max_chars: int = 12_000) -> str:
        """스튜디오 요청에 붙일 위키 맥락. 선택한 문서를 순서대로 이어 붙이되
        총량을 제한하고, 잘린 문서는 표시한다."""
        out: list[str] = []
        used = 0
        for s in slugs:
            try:
                pg = self.get(s)
            except WikiError:
                pg = None
            if pg is None:
                continue
            block = f"## {pg.title}" + (f" ({', '.join(pg.tags)})" if pg.tags else "") + f"\n{pg.content}"
            room = max_chars - used
            if room <= 0:
                break
            if len(block) > room:
                block = block[:room].rstrip() + "\n…(길어서 잘림)"
            out.append(block)
            used += len(block) + 2
        return "\n\n".join(out)


def _snippet(content: str, words: list[str], width: int = 120) -> str:
    low = content.lower()
    pos = min((low.find(w) for w in words if low.find(w) >= 0), default=-1)
    if pos < 0:
        return summarize(content, width)
    start = max(0, pos - width // 3)
    s = re.sub(r"\s+", " ", content[start:start + width]).strip()
    return ("…" if start > 0 else "") + s + ("…" if start + width < len(content) else "")


def dumps(obj) -> str:  # 테스트/디버그 편의
    return json.dumps(obj, ensure_ascii=False, indent=2)
