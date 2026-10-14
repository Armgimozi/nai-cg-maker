package kr.labyrinth.pvp;

import java.util.Objects;
import java.util.UUID;

/**
 * 적/아군 규칙 (GDD §18) — 순수 로직, Bukkit 무관 (단위 테스트 대상). {@link DefaultTargetFilter} 가 엔티티를 {@link Side} 로 바꿔 묻는다.
 * <ul>
 *   <li>플레이어 → 커스텀 몹·보스(미궁 밖에선 바닐라 적대 몹도): 적</li>
 *   <li>플레이어 → 플레이어: <b>같은 파티면 절대 적이 아니고</b>(야생·마을·미궁 전부), 다른 파티·솔로끼리는 적.
 *       단 PvP 꺼짐 · 자기 자신 · 맞는 쪽이 무적(크리에이티브·관전) · 둘 중 하나라도 마을 안전지대 안이면 적 아님</li>
 *   <li>커스텀 몹 → 무적이 아닌 플레이어: 적. NPC·동물 등은 누구의 적도 아님</li>
 *   <li>아군(치유·버프 대상) = 자기 자신 + 같은 파티. 몹끼리도 아군</li>
 * </ul>
 */
public final class PvpRules {

    private PvpRules() {}

    /** 판정용 분류. HOSTILE = 미궁 밖 바닐라 적대 몹 (미궁 월드 안의 바닐라 몹은 OTHER). */
    public enum Kind { PLAYER, MOB, HOSTILE, NPC, OTHER }

    /**
     * 판정 한쪽.
     * @param id           엔티티 UUID
     * @param party        파티 id (솔로·플레이어 아님 = null)
     * @param invulnerable 크리에이티브·관전·이미 쓰러짐
     * @param safeZone     마을 안전지대 안에 서 있음
     */
    public record Side(Kind kind, UUID id, String party, boolean invulnerable, boolean safeZone) {
        public Side {
            Objects.requireNonNull(kind);
            Objects.requireNonNull(id);
        }

        public static Side player(UUID id, String party) { return new Side(Kind.PLAYER, id, party, false, false); }

        public static Side of(Kind kind, UUID id) { return new Side(kind, id, null, false, false); }

        public Side invulnerable(boolean v) { return new Side(kind, id, party, v, safeZone); }

        public Side inSafeZone(boolean v) { return new Side(kind, id, party, invulnerable, v); }
    }

    /** 같은 사람이거나 같은 파티 (솔로끼리는 다른 파티). */
    public static boolean sameParty(Side a, Side b) {
        if (a.id().equals(b.id())) return true;
        return a.party() != null && a.party().equals(b.party());
    }

    /** 플레이어 a 가 플레이어 b 를 해칠 수 있는가 (PvP 규칙의 핵심). */
    public static boolean canPlayersFight(PvpConfig cfg, Side a, Side b) {
        if (cfg == null || !cfg.enabled()) return false;
        if (a.kind() != Kind.PLAYER || b.kind() != Kind.PLAYER) return false;
        if (sameParty(a, b)) return false;
        if (b.invulnerable()) return false;
        return !a.safeZone() && !b.safeZone();
    }

    /** source 가 target 을 공격해도 되는가. */
    public static boolean isEnemy(PvpConfig cfg, Side source, Side target) {
        if (source == null || target == null || source.id().equals(target.id())) return false;
        return switch (source.kind()) {
            case PLAYER -> switch (target.kind()) {
                case PLAYER -> canPlayersFight(cfg, source, target);
                case MOB, HOSTILE -> !target.invulnerable();
                default -> false;
            };
            case MOB -> target.kind() == Kind.PLAYER && !target.invulnerable();
            default -> false;
        };
    }

    /** source 의 아군인가 (자기 자신 포함 — 치유·버프 대상). */
    public static boolean isAlly(Side source, Side target) {
        if (source == null || target == null) return false;
        if (source.id().equals(target.id())) return true;
        if (source.kind() == Kind.PLAYER && target.kind() == Kind.PLAYER) return sameParty(source, target);
        return source.kind() == Kind.MOB && target.kind() == Kind.MOB;
    }
}
