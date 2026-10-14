package kr.labyrinth.content;

/**
 * glyphs.yml — UI 폰트 글리프. ch = 사설 영역 문자(1 코드포인트). advance = 클라이언트 글자 폭(px, 생성기가 PNG 로
 * 검증한 값; 없으면 -1). HUD·메뉴 조합에서 폭을 하드코딩하지 말고 이 값을 쓸 것.
 */
public record GlyphDef(String id, String ch, String file, int ascent, int height, int advance) {

    public GlyphDef(String id, String ch, String file, int ascent, int height) {
        this(id, ch, file, ascent, height, -1);
    }
}
