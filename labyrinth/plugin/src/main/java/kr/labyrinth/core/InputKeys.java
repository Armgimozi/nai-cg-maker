package kr.labyrinth.core;

import java.util.Locale;

/**
 * 키 안내 문구 (MiniMessage). 웅크리기·손 바꾸기·버리기 키는 사람마다 바꿔 둘 수 있으니(예: 웅크리기 = Ctrl)
 * 글자로 박지 않고 {@code <key:...>} 키 바인드 컴포넌트로 보낸다 → 각자 클라이언트가 자기 키 이름(예: "왼쪽 Ctrl")으로 그린다.
 * 서버 쪽 판정은 {@code Player#isSneaking()} 이라 어떤 키에 묶여 있든 똑같이 동작한다.
 */
public final class InputKeys {

    public static final String SNEAK = "<key:key.sneak>";
    public static final String SWAP = "<key:key.swapOffhand>";
    public static final String DROP = "<key:key.drop>";

    /** 직업 스킬 4개 키 한 줄 안내. */
    public static final String CLASS_KEYS = SWAP + " · " + SNEAK + "+" + SWAP + " · " + DROP + " · " + SNEAK + "+" + DROP;

    private InputKeys() {}

    /** 입력 이름 (직업 SWAP/SNEAK_SWAP/DROP/SNEAK_DROP, 무기 LEFT/RIGHT/SNEAK_LEFT/SNEAK_RIGHT). */
    public static String label(String input) {
        return switch (input == null ? "" : input.toUpperCase(Locale.ROOT)) {
            case "SWAP" -> SWAP;
            case "SNEAK_SWAP" -> SNEAK + "+" + SWAP;
            case "DROP" -> DROP;
            case "SNEAK_DROP" -> SNEAK + "+" + DROP;
            case "LEFT" -> "좌클릭";
            case "RIGHT" -> "우클릭";
            case "SNEAK_LEFT" -> SNEAK + "+좌클릭";
            case "SNEAK_RIGHT" -> SNEAK + "+우클릭";
            default -> input == null ? "?" : input;
        };
    }

    /** 액션바용 [키] 표기. */
    public static String bracket(String input) { return "[" + label(input) + "]"; }
}
