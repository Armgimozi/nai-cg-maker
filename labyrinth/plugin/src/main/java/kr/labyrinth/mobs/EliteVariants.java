package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;

/**
 * 정예 변종의 추가 스킬 1개 고르기 (AI 타입에 어울리는 후보 중 몹이 아직 없는 타입). Bukkit 무관 — 단위 테스트 대상.
 * 후보 수치는 일반 몹 스킬 표(GDD §9.1) 범위 안에서 정했다.
 */
public final class EliteVariants {

    private EliteVariants() {}

    private static MobDef.MobSkillDef s(String type, double cooldown, Map<String, Object> params) {
        return new MobDef.MobSkillDef(type, cooldown, Params.of(params));
    }

    static List<MobDef.MobSkillDef> candidates(String ai, String projectileFx) {
        List<MobDef.MobSkillDef> out = new ArrayList<>();
        switch (ai == null ? "melee" : ai) {
            case "ranged", "turret" -> {
                out.add(s("projectile", 7, Map.of("fx", projectileFx == null ? "proj_wisp_spark" : projectileFx, "speed", 0.85,
                        "damage", 0.8, "count", 3, "spread", 30, "range", 14, "windup", 0.6)));
                out.add(s("blink", 10, Map.of("range", 8, "behind", false, "damage", 0)));
                out.add(s("snare", 12, Map.of("range", 10, "root", 1.2, "radius", 1.8, "windup", 0.9, "damage", 0.5)));
            }
            case "caster" -> {
                out.add(s("debuff", 12, Map.of("range", 12, "radius", 3, "effect", "vulnerable", "amount", 0.12, "duration", 5,
                        "windup", 0.9, "particle", "WITCH")));
                out.add(s("shield", 18, Map.of("amount", 0.15, "duration", 5, "self_only", false, "radius", 8)));
                out.add(s("heal_allies", 14, Map.of("radius", 10, "amount", 0.12)));
            }
            case "charger" -> {
                out.add(s("slam", 9, Map.of("radius", 3.2, "damage", 1.4, "windup", 0.8, "knockback", 0.7)));
                out.add(s("enrage", 0, Map.of("threshold", 0.35, "damage_mult", 1.3, "speed_mult", 1.2)));
                out.add(s("shield", 14, Map.of("amount", 0.2, "duration", 4, "reduction", 0.4, "self_only", true)));
            }
            case "swarm" -> {
                out.add(s("explode_on_death", 0, Map.of("radius", 2.5, "damage", 0.9, "delay", 0.6)));
                out.add(s("leap", 7, Map.of("power", 0.9, "damage", 1.2, "range", 8, "windup", 0.5)));
                out.add(s("enrage", 0, Map.of("threshold", 0.4, "damage_mult", 1.3, "speed_mult", 1.2)));
            }
            default -> {
                out.add(s("slam", 9, Map.of("radius", 3, "damage", 1.4, "windup", 0.8, "knockback", 0.6)));
                out.add(s("cleave", 8, Map.of("angle", 100, "length", 4.5, "damage", 1.5, "windup", 0.7)));
                out.add(s("leap", 8, Map.of("power", 1.0, "damage", 1.3, "range", 9, "radius", 2, "windup", 0.7)));
                out.add(s("enrage", 0, Map.of("threshold", 0.35, "damage_mult", 1.3, "speed_mult", 1.15)));
            }
        }
        return out;
    }

    /** 스폰 때 비행형이 되는 베이스 (MobServiceImpl 과 같은 규칙: BAT·BLAZE·ALLAY + BAT 로 대체되는 VEX·PHANTOM). */
    public static boolean isFlyingBase(String base) {
        if (base == null) return false;
        return switch (base.toUpperCase(java.util.Locale.ROOT)) {
            case "BAT", "BLAZE", "ALLAY", "VEX", "PHANTOM" -> true;
            default -> false;
        };
    }

    /** 몹이 아직 갖지 않은 타입 중 하나 (seed 로 결정적). 전부 겹치면 null. */
    public static MobDef.MobSkillDef pick(MobDef def, long seed) {
        Set<String> have = new HashSet<>();
        for (MobDef.MobSkillDef sd : def.skills()) have.add(sd.type());
        List<MobDef.MobSkillDef> c = new ArrayList<>();
        boolean flies = def.flying() || isFlyingBase(def.base());
        for (MobDef.MobSkillDef sd : candidates(def.ai(), MobAi.basicFx(def))) {
            if (have.contains(sd.type())) continue;
            if (flies && (sd.type().equals("leap") || sd.type().equals("charge"))) continue; // 중력 없는 비행형은 도약·돌진이 어색함
            c.add(sd);
        }
        if (c.isEmpty()) return null;
        return c.get((int) Math.floorMod(seed, (long) c.size()));
    }
}
