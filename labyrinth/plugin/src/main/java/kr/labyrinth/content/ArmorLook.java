package kr.labyrinth.content;

import java.util.Locale;
import java.util.Set;
import kr.labyrinth.stats.Stat;

/**
 * 방어구 겉모습 (look_spec §1.1). 판금·가죽·천은 부위마다 숨은 장단점이 있고, 머리·몸·다리·발 네 칸이 같으면 4부위 효과가 켜진다.
 * <ul>
 *   <li>{@link #PLAIN} 평상복 — 겉모습 효과 없음, 4부위로 안 셈 (수련생·길잡이, {@code sets.<id>.look_effects: false}).</li>
 *   <li>{@link #ANY} 어느 겉모습이든 — 자기 숨은 효과는 없고, 4부위를 셀 때 나머지 세 칸의 겉모습으로 센다 (악몽의 왕관).</li>
 * </ul>
 * 순수 — Bukkit 의존 없음.
 */
public enum ArmorLook {
    HEAVY("heavy"),
    LIGHT("light"),
    CLOTH("cloth"),
    PLAIN("plain"),
    ANY("any");

    /** 숨은 효과·4부위 효과가 있는 세 겉모습. */
    public static final ArmorLook[] REAL = {HEAVY, LIGHT, CLOTH};

    private final String id;

    ArmorLook(String id) { this.id = id; }

    /** items.yml · config.yml 의 이름 (heavy · light · cloth · plain · any). */
    public String id() { return id; }

    /** 숨은 효과가 있는 겉모습인가 (판금·가죽·천). */
    public boolean real() { return this == HEAVY || this == LIGHT || this == CLOTH; }

    /**
     * 요구 능력치의 앞(가장 큰 몫) 능력치가 될 수 있는 것 (look_spec §3.1): 판금·방패 체력 · 가죽 민첩 · 천 지능 또는 정신.
     * 평상복·any 는 자유 (빈 집합).
     */
    public Set<Stat> leadStats() {
        return switch (this) {
            case HEAVY -> Set.of(Stat.VIT);
            case LIGHT -> Set.of(Stat.DEX);
            case CLOTH -> Set.of(Stat.INT, Stat.WIS);
            default -> Set.of();
        };
    }

    /** 이름 → 겉모습. 모르면 null. */
    public static ArmorLook byId(String id) {
        if (id == null) return null;
        String k = id.trim().toLowerCase(Locale.ROOT);
        for (ArmorLook l : values()) if (l.id.equals(k)) return l;
        return null;
    }
}
