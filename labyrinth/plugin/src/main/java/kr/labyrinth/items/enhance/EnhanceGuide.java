package kr.labyrinth.items.enhance;

import java.util.ArrayList;
import java.util.List;

/**
 * 강화 화면의 강화석 안내 글 (순수 — 단위 테스트 대상). 0.3.5 결정 5: 장비에는 층 글자를 붙이지 않는다. 강화석은 장비의 숨은 단계로
 * 정해지므로 '초반·중반·후반 장비'로만 말하고, 층은 강화석을 얻는 곳(재료)에만 적는다.
 */
final class EnhanceGuide {

    private static final String[] PHASES_3 = {"초반", "중반", "후반"};
    private static final String[] PHASES_2 = {"초반", "후반"};

    private EnhanceGuide() {}

    /**
     * '강화석: 초반 장비 하급 · 중반 상급 · 후반 최상급' — 돌 이름(낮은 단계부터)에서 ' 강화석'을 뺀 말. 돌이 2~3개가 아니면
     * '강화석은 장비마다 정해져 있습니다'.
     */
    static String stoneGuide(List<String> stoneNames) {
        int n = stoneNames == null ? 0 : stoneNames.size();
        String[] phases = n == 3 ? PHASES_3 : n == 2 ? PHASES_2 : null;
        if (phases == null) return "강화석은 장비마다 정해져 있습니다 (아래 비용 줄)";
        List<String> parts = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            String name = String.valueOf(stoneNames.get(i)).replace(" 강화석", "").replace("강화석", "").trim();
            parts.add((i == 0 ? phases[i] + " 장비 " : phases[i] + " ") + (name.isEmpty() ? stoneNames.get(i) : name));
        }
        return "강화석: " + String.join(" · ", parts);
    }

    /** 강화석을 얻는 곳: '지하 1~3층 몬스터·상자·보스 · 상인' (재료라 층을 적는다). 설정에 없는 돌이면 '미궁에서 얻습니다'. */
    static String stoneSource(List<EnhanceRules.Stone> stones, String stone, boolean shop) {
        if (stones == null || stone == null) return "미궁에서 얻습니다";
        for (EnhanceRules.Stone s : stones) {
            if (!s.item().equals(stone)) continue;
            int prev = 0;
            for (EnhanceRules.Stone o : stones) if (o.maxFloor() < s.maxFloor()) prev = Math.max(prev, o.maxFloor());
            int from = prev + 1, to = Math.max(from, s.maxFloor());
            return "지하 " + (from == to ? from + "층" : from + "~" + to + "층") + " 몬스터·상자·보스" + (shop ? " · 상인" : "");
        }
        return "미궁에서 얻습니다";
    }
}
