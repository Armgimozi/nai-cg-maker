package kr.labyrinth.pvp;

import java.util.Set;
import kr.labyrinth.combat.HealKind;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;

/**
 * PvP 피해·회복 한 건의 결정 (pvp_spec §3·§6·§8) — 순수 로직. {@link PvpModule} 의 DamageService 훅·{@link PvpState} 가 부른다.
 */
public final class PvpDamage {

    private PvpDamage() {}

    /** 다른 피해를 옮겨 받는 피해 — 이미 PvP 배율을 거친 피해라 다시 줄이지 않는다 (수호의 맹세 피해 나눠 받기). */
    static final Set<String> RELAYED = Set.of("guardian_oath");

    public static boolean relayed(String sourceId) { return sourceId != null && RELAYED.contains(sourceId); }

    /**
     * 플레이어 → 다른 파티 플레이어 피해 한 건.
     * @param attackerLevel 공격자 레벨
     * @param attackerClass 공격자 직업 id (없으면 null)
     * @param target        대상 (레벨 · 최대 HP · VIT · 방어)
     * @param skillMult     스킬 pvp_mult ({@link #skillMult})
     * @param percent       최대 HP 비율 피해 (레벨 곡선·완충 없음)
     */
    public record Hit(int attackerLevel, String attackerClass, PvpMath.Target target, double skillMult, boolean percent) {}

    /** 원피해에 곱할 값 = m(L) × 직업 보정 × 스킬 pvp_mult × (1 − 강인함) × H ÷ (H + B). */
    public static double factor(PvpConfig c, Hit h) {
        int l = PvpMath.level(h.attackerLevel(), h.target().level());
        return PvpMath.damageFactor(c, h.attackerLevel(), h.target(), c.classDamage().of(h.attackerClass(), l), h.skillMult(),
                h.percent());
    }

    /**
     * 피해 출처 → 스킬 pvp_mult (classes.yml {@code skills[].pvp_mult} · items.yml {@code weapon_skills[].pvp_mult}, 기본 1).
     * <ul>
     *   <li>{@code ws:<무기>:<입력>} · {@code mech:<무기>:<입력>} = 그 무기의 그 입력 무기 스킬</li>
     *   <li>{@code effect:*} (지속 피해) = 1 — 스킬의 직접 피해에만 곱한다</li>
     *   <li>그 밖의 스킬 피해 = 공격자 직업 스킬 id → 다른 직업 스킬 id → 손에 든 무기의 무기 스킬 id</li>
     * </ul>
     */
    public static double skillMult(Content content, ClassDef attackerClass, ItemDef heldWeapon, String sourceId, boolean skill) {
        if (sourceId == null || sourceId.isBlank() || sourceId.startsWith("effect:")) return 1.0;
        if (sourceId.startsWith("ws:") || sourceId.startsWith("mech:")) {
            String[] parts = sourceId.split(":");
            ItemDef item = parts.length > 2 && content != null ? content.item(parts[1]) : null;
            ItemDef.WeaponSkillDef ws = item == null ? null : item.weaponSkill(parts[2]);
            return ws == null ? 1.0 : PvpMath.clampSkill(ws.pvpMult());
        }
        if (!skill) return 1.0;
        if (attackerClass != null) {
            for (ClassDef.SkillDef s : attackerClass.skills()) if (sourceId.equals(s.id())) return PvpMath.clampSkill(s.pvpMult());
        }
        if (content != null) {
            for (ClassDef c : content.classes().values()) {
                for (ClassDef.SkillDef s : c.skills()) if (sourceId.equals(s.id())) return PvpMath.clampSkill(s.pvpMult());
            }
        }
        if (heldWeapon != null) {
            for (ItemDef.WeaponSkillDef ws : heldWeapon.weaponSkills()) {
                if (sourceId.equals(ws.id())) return PvpMath.clampSkill(ws.pvpMult());
            }
        }
        return 1.0;
    }

    // ── 회복 · 보호막 (PvP 전투 중일 때만) ─────────────────────────────────

    /** 받는 회복 배율 = (흡혈 lifesteal | 물약 healing × potion | 그 밖 healing) × 긴 싸움. 전투 밖이면 1. */
    public static double healFactor(PvpConfig c, HealKind kind, boolean inCombat, double fightSeconds) {
        if (!c.enabled() || !inCombat) return 1.0;
        double base = switch (kind == null ? HealKind.OTHER : kind) {
            case LIFESTEAL -> c.lifesteal();
            case POTION -> c.healing() * c.potion();
            default -> c.healing();
        };
        return base * PvpMath.longFight(c, fightSeconds);
    }

    /** 고정량 회복 몫의 추가 배율 = HP ÷ (HP + B(내 레벨)). 전투 밖·flat_heal_by_pool 꺼짐이면 1. */
    public static double flatHealFactor(PvpConfig c, boolean inCombat, double maxHp, int level) {
        if (!c.enabled() || !inCombat || !c.flatHealByPool()) return 1.0;
        return PvpMath.poolFactor(c, maxHp, level);
    }

    /** 실제로 넣을 회복량 = (pct + flat × 고정량 배율) × 회복 배율. */
    public static double healAmount(PvpConfig c, double pct, double flat, HealKind kind, boolean inCombat, double fightSeconds,
                                    double maxHp, int level) {
        return (Math.max(0, pct) + Math.max(0, flat) * flatHealFactor(c, inCombat, maxHp, level))
                * healFactor(c, kind, inCombat, fightSeconds);
    }

    /** 새로 얻는 보호막 배율 = shield × 긴 싸움. 전투 밖이면 1. */
    public static double shieldFactor(PvpConfig c, boolean inCombat, double fightSeconds) {
        if (!c.enabled() || !inCombat) return 1.0;
        return c.shield() * PvpMath.longFight(c, fightSeconds);
    }
}
