"""위키 저장소 — 사람도 AI 도 읽는 마크다운 문서함.

문서 1개 = ``wiki/<slug>.md`` 파일 하나. slug 는 ``아이템/녹슨-검`` 처럼 '/' 로
하위 폴더를 가질 수 있다(폴더 = 분류). 맨 위에 YAML 식 front matter 를 두고
그 아래가 본문(마크다운)이다. 파일이 그대로 사람이 읽는 형태라 git 에 커밋해
버전 관리하기 좋고, 서버 없이도 Claude Code 같은 AI 에이전트가 폴더를 열어
바로 읽을 수 있다.

    ---
    title: 녹슨 검
    tags: 무기, 초반
    updated: 2026-09-15T12:00:00+00:00
    id: item_001
    공격력: 12
    가격: 50
    ---
    폐광 2층에서 나오는 …

title / tags / updated 는 서버가 관리하고, 그 밖의 줄(id, 공격력 …)은
**사용자 속성**으로 한 글자도 바꾸지 않고 그대로 보존·저장한다. 게임 데이터처럼
수치를 속성으로 적어 두면 AI 가 나중에 긁어 가공하기 좋다.

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

# slug 의 한 조각: 한글·영문·숫자·'-'·'_' 만(경로 탈출/특수문자 차단).
# 조각을 '/' 로 이어 하위 폴더를 표현한다. 파일 경로 = slug + ".md"
_SEG_RE = re.compile(r"^[\w\-]{1,80}$", re.UNICODE)
_FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_MANAGED = ("title", "tags", "updated")   # 서버가 관리하는 front matter 키
MAX_CONTENT = 200_000  # 문서 1개 본문 상한(바이트가 아닌 글자 수)
MAX_DEPTH = 6          # 폴더 깊이 상한


class WikiError(ValueError):
    """잘못된 slug/입력 등 사용자 오류(HTTP 400 으로 응답)."""


@dataclass
class Page:
    slug: str
    title: str
    content: str = ""
    tags: list[str] = field(default_factory=list)
    updated: str = ""
    props_raw: str = ""     # title/tags/updated 를 뺀 front matter 원문(줄바꿈 구분) — 그대로 보존

    @property
    def folder(self) -> str:
        return self.slug.rpartition("/")[0]

    @property
    def props(self) -> dict[str, str]:
        """props_raw 중 `키: 값` 한 줄짜리를 dict 로(표시·검색용). 원문은 props_raw 가 기준."""
        return parse_props(self.props_raw)

    def to_dict(self, with_content: bool = True) -> dict:
        d = {"slug": self.slug, "title": self.title, "folder": self.folder, "tags": list(self.tags),
             "updated": self.updated, "summary": summarize(self.content),
             "props": self.props, "props_raw": self.props_raw}
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
        if self.props_raw.strip():
            fm.append(self.props_raw.strip("\n"))
        return "---\n" + "\n".join(fm) + "\n---\n" + self.content.rstrip("\n") + "\n"


def parse_props(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (raw or "").splitlines():
        m = re.match(r"^([^\s:#][^:]*?)\s*:\s*(.*?)\s*$", line)
        if m and m.group(2) != "":
            out[m.group(1)] = m.group(2).strip("'\"")
    return out


def normalize_slug(s: str) -> str:
    """제목/입력 → slug. 공백은 '-', 허용되지 않는 문자는 제거, '/' 는 폴더 구분으로 유지."""
    s = unicodedata.normalize("NFC", str(s or "")).strip().lower().replace("\\", "/")
    segs = []
    for seg in s.split("/"):
        seg = re.sub(r"\s+", "-", seg.strip())
        seg = re.sub(r"[^\w\-]", "", seg, flags=re.UNICODE)
        seg = re.sub(r"-{2,}", "-", seg).strip("-_")[:80]
        if seg:
            segs.append(seg)
    return "/".join(segs[:MAX_DEPTH + 1])


def validate_slug(slug: str) -> str:
    slug = unicodedata.normalize("NFC", str(slug or "")).strip().strip("/")
    segs = slug.split("/")
    ok = (0 < len(segs) <= MAX_DEPTH + 1
          and all(_SEG_RE.match(x) and x not in (".", "..") and not x.startswith(".") for x in segs))
    if not ok:
        raise WikiError("문서 이름(slug)은 한글·영문·숫자·'-'·'_' 만 쓸 수 있고(조각당 1~80자), "
                        "'/' 로 폴더를 나눕니다. 예) 아이템/녹슨-검")
    return "/".join(segs)


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
    """파일 내용 → Page. front matter 가 없으면 첫 '# 제목' 또는 slug 마지막 조각을 제목으로.

    title/tags/updated 외의 front matter 줄은 순서·내용 그대로 props_raw 에 남긴다
    (여러 줄 값, 목록(`- x`), 주석 포함 — 해석하지 않으므로 잃어버리지 않는다)."""
    meta: dict[str, str] = {}
    extra: list[str] = []
    body = raw
    m = _FM_RE.match(raw)
    if m:
        body = raw[m.end():]
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(":")
            key = k.strip().lower()
            if sep and key in _MANAGED and not line[:1].isspace():
                meta[key] = v.strip()
            else:
                extra.append(line.rstrip())
    title = meta.get("title", "")
    if not title:
        h = re.search(r"^#\s+(.+?)\s*$", body, re.M)
        title = h.group(1).strip() if h else slug.rpartition("/")[2]
    tags = [t.strip() for t in re.split(r"[,\n]", meta.get("tags", "")) if t.strip()]
    return Page(slug=slug, title=title, content=body.strip("\n"), tags=tags,
                updated=meta.get("updated", ""), props_raw="\n".join(extra).strip("\n"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_props(props) -> str:
    """요청의 props(문자열 또는 {키: 값}) → 저장할 front matter 원문."""
    if props is None:
        return ""
    if isinstance(props, dict):
        lines = [f"{str(k).strip()}: {v}" for k, v in props.items() if str(k).strip()]
    else:
        lines = str(props).replace("\r\n", "\n").split("\n")
    out = []
    for line in lines:
        line = line.rstrip()
        k = line.partition(":")[0].strip().lower()
        if k in _MANAGED and not line[:1].isspace():
            continue                      # 관리 키는 본 필드로만 (중복 방지)
        if line.strip() == "---":
            continue                      # front matter 경계를 깨뜨리지 않도록
        out.append(line)
    return "\n".join(out).strip("\n")


class WikiStore:
    """``wiki/`` 폴더(와 하위 폴더)의 .md 파일을 읽고 쓰는 얇은 저장소.

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
        return parse_markdown(p.read_text(encoding="utf-8"), validate_slug(slug))

    def list(self) -> list[Page]:
        if not self.root.is_dir():
            return []
        pages = []
        for p in sorted(self.root.rglob("*.md")):
            rel = p.relative_to(self.root).with_suffix("")
            slug = "/".join(rel.parts)
            try:
                validate_slug(slug)
            except WikiError:
                continue                  # 규칙에 안 맞는 파일/숨김 폴더는 무시
            try:
                pages.append(parse_markdown(p.read_text(encoding="utf-8"), slug))
            except (OSError, UnicodeDecodeError):
                continue
        # 최근 수정 순(updated 없으면 파일 mtime), 같으면 제목순
        def key(pg: Page):
            return (pg.updated or datetime.fromtimestamp(
                (self.root / f"{pg.slug}.md").stat().st_mtime, tz=timezone.utc
            ).isoformat(), pg.title)
        pages.sort(key=key, reverse=True)
        return pages

    def folders(self) -> list[str]:
        seen: set[str] = set()
        for pg in self.list():
            parts = pg.slug.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                seen.add("/".join(parts[:i]))
        return sorted(seen)

    def search(self, query: str, limit: int = 30) -> list[dict]:
        """단순 키워드 검색. 공백으로 나눈 모든 단어가 (제목/태그/속성/본문 어딘가에)
        들어 있는 문서를, 제목·태그 일치에 가중치를 줘 정렬한다. 문서 수가 많지
        않은 개인 위키를 전제로 한 것이라 색인 없이 매번 훑는다."""
        words = [w.lower() for w in query.split() if w.strip()]
        if not words:
            return []
        hits = []
        for pg in self.list():
            title, body = pg.title.lower(), pg.content.lower()
            tags = " ".join(pg.tags).lower()
            props = (pg.props_raw + " " + pg.slug).lower()
            score = 0
            ok = True
            for w in words:
                in_title, in_tags, in_props, in_body = w in title, w in tags, w in props, w in body
                if not (in_title or in_tags or in_props or in_body):
                    ok = False
                    break
                score += (10 if in_title else 0) + (5 if in_tags else 0) + (3 if in_props else 0) + min(body.count(w), 5)
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
            updated: str | None = None, props=None) -> Page:
        slug = validate_slug(slug)
        title = (title or "").strip() or slug.rpartition("/")[2]
        content = (content or "").replace("\r\n", "\n")
        if len(content) > MAX_CONTENT:
            raise WikiError(f"본문이 너무 깁니다(최대 {MAX_CONTENT:,}자).")
        clean_tags = []
        for t in tags or []:
            t = str(t).strip()
            if t and t not in clean_tags:
                clean_tags.append(t)
        page = Page(slug=slug, title=title, content=content.strip("\n"),
                    tags=clean_tags, updated=updated or _now(), props_raw=_clean_props(props))
        path = self._path(slug)
        if path.parent != self.root and path.parent.with_suffix(".md").is_file():
            raise WikiError("같은 이름의 문서가 있어 폴더로 만들 수 없습니다.")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(page.to_markdown(), encoding="utf-8")
        tmp.replace(path)  # 원자적 교체: 쓰다 죽어도 반쪽 파일이 남지 않음
        return page

    def delete(self, slug: str) -> bool:
        p = self._path(slug)
        if not p.is_file():
            return False
        p.unlink()
        # 비게 된 폴더는 정리(위키 루트는 남김)
        d = p.parent
        while d != self.root and d.is_dir() and not any(d.iterdir()):
            d.rmdir()
            d = d.parent
        return True

    def rename(self, old: str, new: str) -> Page:
        page = self.get(old)
        if page is None:
            raise WikiError("원본 문서가 없습니다.")
        new = validate_slug(new)
        if new != page.slug and self.exists(new):
            raise WikiError("같은 이름의 문서가 이미 있습니다.")
        moved = self.put(new, page.title, page.content, page.tags, updated=page.updated,
                         props=page.props_raw)
        if new != page.slug:
            self.delete(page.slug)
        return moved

    # ── 내보내기/가져오기 (배포 환경은 디스크가 초기화될 수 있어 백업용) ──
    def export_all(self) -> dict:
        return {"format": "nai-cg-maker-wiki/2", "exported": _now(),
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
                     item.get("tags") or [], updated=item.get("updated") or None,
                     props=item.get("props_raw") if "props_raw" in item else item.get("props"))
            added += 1
        return {"imported": added, "skipped": skipped}

    # ── AI/LLM 용 평문 ──
    def llms_index(self, base_url: str = "") -> str:
        """llms.txt 관례(https://llmstxt.org): 사이트/문서를 LLM 이 훑기 좋은 목차."""
        base = base_url.rstrip("/")
        lines = ["# NAI CG Maker 위키", "",
                 "> 사용자가 정리한 캐릭터·작품·프롬프트·게임 데이터 위키. 아래 각 문서는 "
                 "마크다운 원문(.md)으로 바로 읽을 수 있고, `/llms-full.txt` 는 전체를 한 파일로 준다. "
                 "각 문서 맨 위 front matter(`---` 사이)에 속성(수치 등)이 있다.", "",
                 "## 읽는 법 (AI 에이전트용)", "",
                 f"- 목록(JSON): `GET {base}/api/wiki`",
                 f"- 문서 1개(JSON): `GET {base}/api/wiki/<slug>`  ·  원문: `GET {base}/wiki/<slug>.md`",
                 f"- 검색: `GET {base}/api/wiki/search?q=<키워드>`",
                 f"- 전체 원문: `GET {base}/llms-full.txt`",
                 f"- 쓰기(허용 시): `PUT {base}/api/wiki/<slug>` JSON {{title, content, tags, props}}",
                 "- slug 의 '/' 는 폴더(분류)다. 예) 아이템/녹슨-검", "",
                 "## 문서", ""]
        pages = self.list()
        for pg in sorted(pages, key=lambda p: (p.folder, p.title)):
            desc = summarize(pg.content, 100)
            tag = f" [{', '.join(pg.tags)}]" if pg.tags else ""
            lines.append(f"- [{pg.title}]({base}/wiki/{pg.slug}.md){tag}"
                         + (f": {desc}" if desc else ""))
        if not pages:
            lines.append("- (아직 문서가 없습니다)")
        return "\n".join(lines) + "\n"

    def llms_full(self) -> str:
        parts = ["# NAI CG Maker 위키 — 전체 문서\n"]
        for pg in sorted(self.list(), key=lambda p: (p.folder, p.title)):
            head = f"\n\n---\n\n# {pg.title}\n\nslug: {pg.slug}"
            if pg.tags:
                head += f"\ntags: {', '.join(pg.tags)}"
            if pg.updated:
                head += f"\nupdated: {pg.updated}"
            if pg.props_raw:
                head += "\n" + pg.props_raw
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
            block = f"## {pg.title}" + (f" ({', '.join(pg.tags)})" if pg.tags else "")
            if pg.props_raw:
                block += "\n" + pg.props_raw
            block += f"\n{pg.content}"
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
