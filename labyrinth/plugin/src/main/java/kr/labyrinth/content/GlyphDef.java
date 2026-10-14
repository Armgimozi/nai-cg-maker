package kr.labyrinth.content;

/** glyphs.yml — UI 폰트 글리프. ch = 사설 영역 문자(1 코드포인트). */
public record GlyphDef(String id, String ch, String file, int ascent, int height) {}
