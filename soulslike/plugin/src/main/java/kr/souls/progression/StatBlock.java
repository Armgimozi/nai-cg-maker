package kr.souls.progression;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 능력치 여섯 (5.2): 체력 vig, 정신 mnd, 기력 end, 근력 str, 민첩 dex, 지능 int. 창·표의 차례도 이것이다 (HUD 막대 셋의 차례 뒤에 공격 셋).
 * 레벨 = 합 − 59 (여섯이 모두 10 이면 레벨 1). 값은 1..99. 바꿀 수 없는 값이다 (with 가 새 값을 만든다).
 */
public record StatBlock(int vig, int mnd, int end, int str, int dex, int intel) {
    /** 코드 이름의 차례 (프로필 JSON 의 열쇠, lang 의 stat.&lt;id&gt;.*) */
    public static final List<String> IDS = List.of("vig", "mnd", "end", "str", "dex", "int");
    /** 레벨 = 합 − LEVEL_OFFSET */
    public static final int LEVEL_OFFSET = 59;
    public static final int MIN = 1, MAX = 99;
    /** 출신을 고르기 전 (능력치 창은 모두 10 으로 보인다, 5.10) */
    public static final StatBlock BASE = new StatBlock(10, 10, 10, 10, 10, 10);

    public StatBlock {
        vig = clamp(vig);
        mnd = clamp(mnd);
        end = clamp(end);
        str = clamp(str);
        dex = clamp(dex);
        intel = clamp(intel);
    }

    private static int clamp(int v) {
        return Math.max(MIN, Math.min(MAX, v));
    }

    public int sum() {
        return vig + mnd + end + str + dex + intel;
    }

    public int level() {
        return sum() - LEVEL_OFFSET;
    }

    /** id 의 값 (모르는 id 는 −1). */
    public int get(String id) {
        return switch (id.toLowerCase(Locale.ROOT)) {
            case "vig" -> vig;
            case "mnd" -> mnd;
            case "end" -> end;
            case "str" -> str;
            case "dex" -> dex;
            case "int" -> intel;
            default -> -1;
        };
    }

    /** id 의 값을 바꾼 새 값. 모르는 id 면 그대로. */
    public StatBlock with(String id, int v) {
        return switch (id.toLowerCase(Locale.ROOT)) {
            case "vig" -> new StatBlock(v, mnd, end, str, dex, intel);
            case "mnd" -> new StatBlock(vig, v, end, str, dex, intel);
            case "end" -> new StatBlock(vig, mnd, v, str, dex, intel);
            case "str" -> new StatBlock(vig, mnd, end, v, dex, intel);
            case "dex" -> new StatBlock(vig, mnd, end, str, v, intel);
            case "int" -> new StatBlock(vig, mnd, end, str, dex, v);
            default -> this;
        };
    }

    public StatBlock plus(String id, int n) {
        return with(id, get(id) + n);
    }

    public static StatBlock of(Map<String, Integer> m) {
        return new StatBlock(m.getOrDefault("vig", 10), m.getOrDefault("mnd", 10), m.getOrDefault("end", 10),
                m.getOrDefault("str", 10), m.getOrDefault("dex", 10), m.getOrDefault("int", 10));
    }

    public static boolean known(String id) {
        return id != null && IDS.contains(id.toLowerCase(Locale.ROOT));
    }

    /** 시험 줄 꼴: vig:15,mnd:9,end:11,str:13,dex:11,int:9 */
    public String line() {
        return "vig:" + vig + ",mnd:" + mnd + ",end:" + end + ",str:" + str + ",dex:" + dex + ",int:" + intel;
    }
}
