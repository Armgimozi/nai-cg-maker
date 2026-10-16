package kr.labyrinth.content;

import java.util.Locale;

/**
 * 광산 재료의 종류 (items.yml {@code mine_kind}, 0.3.6). 등급은 {@link ItemDef#mineLevel()} (1 구리·석영 … 6 오리하르콘·용혈석).
 * 판매가({@code sell.mine})·도감·강화 '얻는 곳' 글이 이 값으로 갈린다 — id 끝으로 짐작하지 않는다.
 */
public enum MineKind {
    ORE, INGOT, GEM;

    public String id() { return name().toLowerCase(Locale.ROOT); }

    public static MineKind byId(String id) {
        if (id == null || id.isBlank()) return null;
        try { return valueOf(id.trim().toUpperCase(Locale.ROOT)); } catch (IllegalArgumentException e) { return null; }
    }
}
