package kr.labyrinth.items.weaponskills;

import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.items.weaponskills.mechanics.MechanicsSpec;

/**
 * 무기 스킬 피해 종류 (combat_spec §4.2, 순수 — 단위 테스트 대상). 물리는 힘, 마법은 지능이 키운다.
 * 실제 피해({@link SkillCast#kind()} · 조합형 {@code MechanicsEngine})와 꼬리표 검사(SkillKindTagsTest)가 같은 규칙을 쓴다.
 * <ul>
 *   <li>params.damage_type 이 있으면 그것 (melee·ranged = 물리, magic = 마법, true = 고정, hybrid = 혼합)</li>
 *   <li>없으면 구현이 정한 기본 (slash_wave 물리 · beam·chain_bolt·vortex·sanctuary 마법), 그 밖은 무기 {@code attack.kind}</li>
 *   <li>조합형 효과: damage·execute·explosion = damage_type → {@code magic: true} → 기본, lightning = 마법, percent = 고정</li>
 *   <li>상태이상 지속 피해: 불태움(ignite·burn) 마법 · 독·출혈·시듦 물리</li>
 * </ul>
 * 꼬리표 = 피해 부분 종류의 모음: 물리만 physical, 마법만 magic, 둘 다 hybrid, 피해 없음 none (고정만 있으면 fixed).
 */
public final class SkillKinds {

    private SkillKinds() {}

    /** 피해 효과 (조합형). */
    private static final Set<String> DAMAGE_EFFECTS = Set.of("damage", "execute", "explosion");
    /** 지속 피해를 거는 조합형 효과 → 종류. */
    private static final Map<String, DamageKind> DOT_EFFECTS = Map.of("ignite", DamageKind.MAGIC, "poison", DamageKind.PHYSICAL,
            "bleed", DamageKind.PHYSICAL, "wither", DamageKind.PHYSICAL);
    /** 기본 구현 스킬의 params.effect 중 지속 피해. */
    private static final Map<String, DamageKind> DOT_STATUS = Map.of("burn", DamageKind.MAGIC, "poison", DamageKind.PHYSICAL,
            "bleed", DamageKind.PHYSICAL);

    /** params.damage_type 문자열 → 종류 (없거나 모르면 def). */
    public static DamageKind ofType(String damageType, DamageKind def) {
        if (damageType == null || damageType.isBlank()) return def;
        return switch (damageType.trim().toLowerCase(Locale.ROOT)) {
            case "melee", "ranged", "physical" -> DamageKind.PHYSICAL;
            case "magic" -> DamageKind.MAGIC;
            case "true", "fixed" -> DamageKind.FIXED;
            case "hybrid" -> DamageKind.HYBRID;
            default -> def;
        };
    }

    /** 구현 키의 기본 종류 (damage_type 이 없을 때). */
    public static DamageKind implDefault(String impl, DamageKind weaponKind) {
        if (impl == null) return weaponKind;
        return switch (impl) {
            case "slash_wave" -> DamageKind.PHYSICAL;
            case "beam", "chain_bolt", "vortex", "sanctuary" -> DamageKind.MAGIC;
            default -> weaponKind;
        };
    }

    /** 기본 구현 스킬(SkillCast.hit) 한 번의 피해 종류. */
    public static DamageKind hitKind(String impl, Params p, DamageKind weaponKind) {
        return ofType(p == null ? null : p.str("damage_type"), implDefault(impl, weaponKind));
    }

    /** 조합형 효과 하나의 피해 종류 (피해 효과만 뜻이 있다). */
    public static DamageKind effectKind(MechanicsSpec.Effect e, DamageKind weaponKind) {
        if ("lightning".equals(e.type())) return DamageKind.MAGIC;
        if ("percent".equals(e.type())) return DamageKind.FIXED;
        DamageKind def = e.p().bool("magic", false) ? DamageKind.MAGIC : weaponKind;
        return ofType(e.p().str("damage_type"), def);
    }

    /** 무기의 기본 피해 종류 = attack.kind. */
    public static DamageKind weaponKind(ItemDef weapon) { return WeaponAttack.of(weapon).kind(); }

    /** 무기 스킬 하나의 꼬리표 (physical · magic · hybrid · none · fixed) — 데이터에서 계산. */
    public static String tag(ItemDef weapon, ItemDef.WeaponSkillDef s) {
        return tag(parts(weapon, s));
    }

    /** 피해 부분 종류 모음 (physical · magic · hybrid · fixed). */
    public static Set<String> parts(ItemDef weapon, ItemDef.WeaponSkillDef s) {
        DamageKind wk = weaponKind(weapon);
        Params p = s.params() == null ? Params.EMPTY : s.params();
        Set<String> parts = new TreeSet<>();
        switch (s.id()) {
            case "mechanics" -> {
                MechanicsSpec.Result r = MechanicsSpec.parse(p.get("mechanics"));
                walk(r.parts(), wk, parts);
            }
            case "mend", "empower" -> { }
            case "sanctuary" -> {
                if (p.dbl("damage", 0) > 0) parts.add(name(hitKind(s.id(), p, wk)));
            }
            case "riposte" -> {
                parts.add(name(hitKind(s.id(), p, wk)));
                if (p.dbl("reflect", 0) > 0) parts.add("fixed");
            }
            default -> {
                if (p.dbl("damage", 0) > 0 || p.dbl("counter_damage", 0) > 0) parts.add(name(hitKind(s.id(), p, wk)));
                DamageKind dot = DOT_STATUS.get(p.str("effect", ""));
                if (dot != null) parts.add(name(dot));
            }
        }
        return parts;
    }

    private static void walk(List<MechanicsSpec.Part> list, DamageKind wk, Set<String> out) {
        for (MechanicsSpec.Part part : list) {
            effects(part.effects(), wk, out);
            for (List<MechanicsSpec.Part> child : part.children().values()) walk(child, wk, out);
        }
    }

    private static void effects(Collection<MechanicsSpec.Effect> effects, DamageKind wk, Set<String> out) {
        for (MechanicsSpec.Effect e : effects) {
            if (DAMAGE_EFFECTS.contains(e.type()) || "lightning".equals(e.type()) || "percent".equals(e.type())) {
                out.add(name(effectKind(e, wk)));
            } else if (DOT_EFFECTS.containsKey(e.type())) {
                out.add(name(DOT_EFFECTS.get(e.type())));
            }
        }
    }

    /** 부분 모음 → 꼬리표. */
    public static String tag(Set<String> parts) {
        Set<String> dmg = new TreeSet<>(parts);
        dmg.remove("fixed");
        if (dmg.isEmpty()) return parts.contains("fixed") ? "fixed" : "none";
        if (dmg.equals(Set.of("physical"))) return "physical";
        if (dmg.equals(Set.of("magic"))) return "magic";
        return "hybrid";
    }

    private static String name(DamageKind k) { return k.name().toLowerCase(Locale.ROOT); }
}
