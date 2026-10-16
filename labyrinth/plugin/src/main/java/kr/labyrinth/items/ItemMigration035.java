package kr.labyrinth.items;

import java.util.LinkedHashMap;
import java.util.Map;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.Range;

/**
 * 0.3.4 → 0.3.5 이미 가진 장비의 굴림 옮기기 (순수 — 단위 테스트 대상). 깃발 = {@code Keys.ITEM_COMBAT_VER} {@value #VERSION}.
 * <ul>
 *   <li>무기 피해: 0.3.5 에서 무기마다 한 방 피해 범위가 바뀐다 (공격 간격·스탯 1%/점 보정). PDC 에 박힌 옛 굴림값을
 *       <b>같은 위치</b>로 옮긴다: t = (옛 값 − 옛 최소) ÷ (옛 최대 − 옛 최소), 새 값 = round(새 최소 + t × (새 최대 − 새 최소)).
 *       옛 범위 밖 값(관리자 지급 등)은 가운데값 비율로. 옛 범위는 {@link #OLD_DAMAGE} (0.3.4 items.yml 131개).</li>
 *   <li>강화 단계·다른 스탯 굴림·시드는 그대로.</li>
 *   <li>새 범위 = 지금 items.yml. 범위가 같으면 아무것도 안 바뀐다.</li>
 * </ul>
 * <ul>
 *   <li>방어구 스탯 줄 이름 (look_spec §3.3 + review2 A2): 요구 능력치 짝에 맞춰 세트의 스탯 줄 이름만 바꾼다 —
 *       굴린 값·강화·시드는 그대로, PDC 의 키만 ({@link #ARMOR_RENAME}, 0.3.4 에 있던 8세트).</li>
 * </ul>
 * 같은 깃발로 다른 0.3.5 옮기기를 더할 때는 {@link #migrate} 안에 단계를 덧붙인다 — 깃발은 한 번만 찍힌다.
 */
public final class ItemMigration035 {

    /** 이 판 이후로 만든·옮긴 장비의 깃발 값. */
    public static final int VERSION = 35;

    /** 0.3.4 무기 피해 범위 (combat_spec migration.items.old_damage — 0.3.4 items.yml 그대로). */
    public static final Map<String, Range> OLD_DAMAGE = Map.ofEntries(
            Map.entry("corridor_longsword", new Range(7, 8)),
            Map.entry("mossback_warhammer", new Range(7, 8)),
            Map.entry("grove_warden_maul", new Range(9, 10)),
            Map.entry("minewarden_mace", new Range(8, 10)),
            Map.entry("silkguard_falchion", new Range(10, 11)),
            Map.entry("sporeward_broadsword", new Range(12, 14)),
            Map.entry("sporecap_warhammer", new Range(14, 16)),
            Map.entry("mycelking_guard_blade", new Range(16, 19)),
            Map.entry("sluice_breaker_mace", new Range(18, 21)),
            Map.entry("brine_falchion", new Range(19, 21)),
            Map.entry("emberforge_warhammer", new Range(24, 27)),
            Map.entry("anvil_oath_broadsword", new Range(26, 30)),
            Map.entry("dawnbringer", new Range(30, 34)),
            Map.entry("frostgrave_mace", new Range(30, 35)),
            Map.entry("resonant_longsword", new Range(35, 41)),
            Map.entry("amethyst_falchion", new Range(39, 44)),
            Map.entry("inkseal_warhammer", new Range(49, 55)),
            Map.entry("index_keeper_sword", new Range(55, 62)),
            Map.entry("clockguard_mace", new Range(54, 62)),
            Map.entry("void_falchion", new Range(65, 74)),
            Map.entry("abyss_sentinel_longsword", new Range(76, 86)),
            Map.entry("celestial_oathkeeper", new Range(85, 94)),
            Map.entry("rootcutter_greatsword", new Range(10, 12)),
            Map.entry("rootbound_scythe", new Range(11, 13)),
            Map.entry("ore_splitter_axe", new Range(12, 15)),
            Map.entry("silkspan_glaive", new Range(15, 17)),
            Map.entry("silkqueen_reaper", new Range(19, 22)),
            Map.entry("capsplitter_cleaver", new Range(18, 22)),
            Map.entry("mycel_scythe", new Range(22, 25)),
            Map.entry("drowned_anchor_cleaver", new Range(28, 32)),
            Map.entry("drowned_glaive", new Range(29, 33)),
            Map.entry("osric_drowned_axe", new Range(33, 38)),
            Map.entry("cinderdrake_glaive", new Range(37, 42)),
            Map.entry("slagforged_greatsword", new Range(40, 46)),
            Map.entry("ember_greatsword", new Range(46, 52)),
            Map.entry("rime_reaper_scythe", new Range(47, 54)),
            Map.entry("amethyst_cleaver", new Range(54, 63)),
            Map.entry("geode_scythe", new Range(60, 68)),
            Map.entry("lore_glaive", new Range(75, 86)),
            Map.entry("geode_sunderer", new Range(73, 82)),
            Map.entry("regulator_greatsword", new Range(84, 97)),
            Map.entry("void_scythe", new Range(101, 115)),
            Map.entry("doomclock_executioner", new Range(103, 116)),
            Map.entry("bloodmoon_reaver", new Range(132, 146)),
            Map.entry("corridor_longbow", new Range(9, 10)),
            Map.entry("mossvine_hornbow", new Range(9, 10)),
            Map.entry("grove_rootstring_bow", new Range(11, 13)),
            Map.entry("silkstring_recurve", new Range(10, 12)),
            Map.entry("skitter_bladebow", new Range(13, 14)),
            Map.entry("glowcap_longbow", new Range(15, 18)),
            Map.entry("mycel_hornbow", new Range(19, 21)),
            Map.entry("eelbone_recurve", new Range(23, 27)),
            Map.entry("brine_bladebow", new Range(24, 28)),
            Map.entry("slagedge_bladebow", new Range(31, 35)),
            Map.entry("bellows_composite_bow", new Range(34, 39)),
            Map.entry("tidecaller_bow", new Range(30, 34)),
            Map.entry("frostbone_longbow", new Range(39, 45)),
            Map.entry("prismstring_longbow", new Range(45, 53)),
            Map.entry("prism_hornbow", new Range(50, 57)),
            Map.entry("inkquill_hornbow", new Range(63, 72)),
            Map.entry("galewing_bow", new Range(60, 69)),
            Map.entry("springloaded_bow", new Range(71, 81)),
            Map.entry("abyss_bladebow", new Range(85, 97)),
            Map.entry("quicksilver_longbow", new Range(86, 97)),
            Map.entry("tempest_bow", new Range(111, 122)),
            Map.entry("lantern_staff", new Range(7, 8)),
            Map.entry("wayfarer_spiral_staff", new Range(8, 9)),
            Map.entry("grove_heartwood_staff", new Range(10, 11)),
            Map.entry("ore_crystal_staff", new Range(9, 11)),
            Map.entry("miners_fork_staff", new Range(11, 12)),
            Map.entry("mycelium_staff", new Range(13, 15)),
            Map.entry("glowcap_spiral_staff", new Range(16, 18)),
            Map.entry("brine_orb_staff", new Range(20, 23)),
            Map.entry("tide_fork_staff", new Range(21, 24)),
            Map.entry("osric_tide_trident", new Range(23, 27)),
            Map.entry("cinder_spiral_staff", new Range(26, 30)),
            Map.entry("cinder_crystal_staff", new Range(29, 33)),
            Map.entry("rimeheart_staff", new Range(36, 41)),
            Map.entry("rimebell_staff", new Range(33, 38)),
            Map.entry("resonance_staff", new Range(38, 45)),
            Map.entry("resonant_fork_staff", new Range(42, 48)),
            Map.entry("ink_spiral_staff", new Range(53, 61)),
            Map.entry("inkwell_staff", new Range(61, 69)),
            Map.entry("orrery_staff", new Range(60, 69)),
            Map.entry("void_fork_staff", new Range(72, 82)),
            Map.entry("tesla_coil_staff", new Range(73, 82)),
            Map.entry("voidheart_staff", new Range(94, 104)),
            Map.entry("acolyte_scepter", new Range(6, 7)),
            Map.entry("grove_chalice", new Range(7, 8)),
            Map.entry("miners_lamp_censer", new Range(8, 9)),
            Map.entry("miners_bell_scepter", new Range(9, 10)),
            Map.entry("silkqueen_spindle_censer", new Range(12, 13)),
            Map.entry("bloom_scepter", new Range(11, 13)),
            Map.entry("bloom_chalice", new Range(14, 15)),
            Map.entry("mycelking_scepter", new Range(15, 18)),
            Map.entry("tidebell_censer", new Range(17, 20)),
            Map.entry("brine_bell_scepter", new Range(18, 20)),
            Map.entry("crucible_chalice", new Range(22, 26)),
            Map.entry("embersong_scepter", new Range(25, 28)),
            Map.entry("sanctum_scepter", new Range(31, 35)),
            Map.entry("frost_vigil_censer", new Range(29, 33)),
            Map.entry("prism_censer", new Range(33, 39)),
            Map.entry("crystal_bell_scepter", new Range(37, 42)),
            Map.entry("ink_chalice", new Range(46, 53)),
            Map.entry("twin_light_scepter", new Range(44, 50)),
            Map.entry("pendulum_censer", new Range(52, 59)),
            Map.entry("abyss_bell_scepter", new Range(62, 71)),
            Map.entry("aurora_scepter", new Range(72, 82)),
            Map.entry("seraph_scepter", new Range(81, 89)),
            Map.entry("moss_dirk", new Range(4, 5)),
            Map.entry("corridor_katar", new Range(4, 5)),
            Map.entry("skitter_fang", new Range(5, 6)),
            Map.entry("silk_sickle", new Range(6, 7)),
            Map.entry("silkqueen_fang", new Range(8, 9)),
            Map.entry("spore_kris", new Range(7, 9)),
            Map.entry("spore_katar", new Range(9, 10)),
            Map.entry("mycelking_sporefang", new Range(10, 11)),
            Map.entry("eel_kris", new Range(11, 13)),
            Map.entry("eelfin_sickle", new Range(12, 13)),
            Map.entry("slag_katar", new Range(15, 17)),
            Map.entry("cinder_fang", new Range(16, 19)),
            Map.entry("soulflame_kris", new Range(20, 23)),
            Map.entry("gravefrost_katar", new Range(19, 21)),
            Map.entry("shardglass_dagger", new Range(22, 25)),
            Map.entry("shardglass_sickle", new Range(24, 27)),
            Map.entry("lorekeeper_katar", new Range(30, 34)),
            Map.entry("nightshade_dagger", new Range(34, 38)),
            Map.entry("mainspring_dagger", new Range(34, 39)),
            Map.entry("abyss_sickle", new Range(40, 46)),
            Map.entry("viper_fang", new Range(47, 53)),
            Map.entry("eclipse_blade", new Range(53, 58)));

    /**
     * 세트 id → {옛 스탯 키 → 새 스탯 키} (tools/data/035/armor_looks.json stats_rename 중 0.3.4 에 있던 세트).
     * 0.3.5 에 새로 들어오는 세트(균사 갑각·수로 잠수부·색인 방벽·잿불 성가자)는 처음부터 새 이름이라 옮길 것이 없다.
     */
    public static final Map<String, Map<String, String>> ARMOR_RENAME = Map.of(
            "verdigris_guard", Map.of("STR", "WIS"),
            "rimefang", Map.of("LUK", "STR"),
            "shard_dancer", Map.of("LUK", "STR"),
            "inkveil", Map.of("LUK", "INT"),
            "spore_sage", Map.of("INT", "VIT"),
            "lorekeeper", Map.of("WIS", "VIT"),
            "abyss_walker", Map.of("LUK", "STR"),
            "starless_choir", Map.of("WIS", "VIT"));

    private ItemMigration035() {}

    /** 옮길 것이 있는가 (깃발이 35 보다 낮은 장비). */
    public static boolean needed(ItemDef def, int combatVersion) {
        return def != null && def.isGear() && combatVersion < VERSION;
    }

    /** 옛 굴림값 → 0.3.5 굴림값 (바뀐 것이 없으면 같은 내용의 새 맵). */
    public static Map<String, Double> migrate(ItemDef def, Map<String, Double> rolls) {
        Map<String, Double> out = new LinkedHashMap<>(rolls);
        if (def != null && def.type() == kr.labyrinth.content.ItemType.ARMOR) return renameArmor(def, out);
        if (def == null || !def.isWeapon()) return out;
        Double v = rolls.get("damage");
        Range old = OLD_DAMAGE.get(def.id());
        Range now = def.stats().get("damage");
        if (v == null || old == null || now == null) return out;
        out.put("damage", (double) migrateDamage(v, old, now));
        return out;
    }

    /**
     * 방어구 스탯 줄 이름 바꾸기: 옛 키가 굴림에 있고, 새 키는 지금 정의에만 있고(옛 키는 없음) 굴림에는 아직 없을 때만 —
     * 값은 그대로, 줄 순서도 그대로.
     */
    static Map<String, Double> renameArmor(ItemDef def, Map<String, Double> rolls) {
        String set = def.setBonus() != null ? def.setBonus() : def.armorSet();
        Map<String, String> ren = set == null ? null : ARMOR_RENAME.get(set);
        if (ren == null) return rolls;
        Map<String, Double> out = new LinkedHashMap<>();
        rolls.forEach((k, v) -> {
            String to = ren.get(k);
            boolean move = to != null && !rolls.containsKey(to) && def.stats().containsKey(to) && !def.stats().containsKey(k);
            out.put(move ? to : k, v);
        });
        return out;
    }

    /** 같은 위치로 옮긴 피해 (범위 밖이면 가운데값 비율). */
    public static long migrateDamage(double v, Range old, Range now) {
        if (Math.abs(old.min() - now.min()) < 1e-9 && Math.abs(old.max() - now.max()) < 1e-9) return Math.round(v);
        if (v >= old.min() - 1e-9 && v <= old.max() + 1e-9) {
            double t = old.max() - old.min() > 1e-9 ? (v - old.min()) / (old.max() - old.min()) : 0.5;
            return Math.round(now.min() + t * (now.max() - now.min()));
        }
        double oldMid = (old.min() + old.max()) / 2.0;
        double newMid = (now.min() + now.max()) / 2.0;
        return Math.max(1, Math.round(v * (oldMid > 0 ? newMid / oldMid : 1.0)));
    }
}
