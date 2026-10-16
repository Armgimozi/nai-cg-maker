package kr.labyrinth.mat036;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.MobDef;
import org.junit.jupiter.api.Test;

/**
 * 몹 몸에 맞는 드롭 (§0 주인 늦은 결정 4 — design036/drops 검토판). 주인: "용한테서 돌갑충 껍질이 나오는 건 이상".
 * 몹마다 자기 몸에서 나온 부위만 떨어뜨린다 — 아래 주제 표(drops_spec mob_drops·elite_drops·boss_drops 를 옮겨 적음)에 없는 부위가
 * 그 몹 표에 있으면 실패. 정령·원령(몸 없음)은 부위가 없다(정수만).
 */
class MobDropThemeTest {

    /** 몹·정예 id · 보스 루팅 표 id → 떨어뜨려도 되는 몬스터 부위. */
    static final Map<String, Set<String>> THEME = Map.ofEntries(
            Map.entry("moss_crawler", Set.of("moss_fiber")),
            Map.entry("root_shambler", Set.of("moss_fiber")),
            Map.entry("lantern_wisp", Set.of()),
            Map.entry("stone_beetle", Set.of("beetle_shell")),
            Map.entry("moss_drakeling", Set.of("moss_scale")),
            Map.entry("thorn_kobold", Set.of("moss_fiber", "moss_scale")),
            Map.entry("tunnel_skitter", Set.of("spider_silk")),
            Map.entry("rusted_miner", Set.of()),
            Map.entry("ore_mimic", Set.of("tunnel_fang")),
            Map.entry("echo_bat", Set.of("tunnel_fang")),
            Map.entry("kobold_sapper", Set.of("tunnel_fang")),
            Map.entry("tunnel_wyrm", Set.of("tunnel_fang")),
            Map.entry("capcap", Set.of("hypha_thread", "spore_cap")),
            Map.entry("mycelid_shambler", Set.of("hypha_thread", "spore_cap")),
            Map.entry("spore_turret", Set.of("hypha_thread", "spore_cap")),
            Map.entry("glowcap_moth", Set.of("spore_cap")),
            Map.entry("spore_harpy", Set.of("spore_cap")),
            Map.entry("myconid_centaur", Set.of("hypha_thread", "spore_cap")),
            Map.entry("sluice_drowner", Set.of("brine_pearl")),
            Map.entry("brine_spitter", Set.of("brine_pearl")),
            Map.entry("rust_eel", Set.of("eel_scale")),
            Map.entry("bubble_jelly", Set.of("brine_pearl")),
            Map.entry("bog_drake", Set.of("eel_scale")),
            Map.entry("tide_naga", Set.of("brine_pearl", "eel_scale")),
            Map.entry("slag_golem", Set.of("ember_soul")),
            Map.entry("cinder_imp", Set.of("ember_soul")),
            Map.entry("bellows_hound", Set.of("ember_soul")),
            Map.entry("forge_acolyte", Set.of("ember_soul")),
            Map.entry("ember_drake", Set.of("cinder_scale")),
            Map.entry("forge_dragonkin", Set.of("cinder_scale")),
            Map.entry("rime_mourner", Set.of()),
            Map.entry("crypt_hound", Set.of("grave_bone")),
            Map.entry("frozen_knight", Set.of("grave_bone")),
            Map.entry("icicle_wraith", Set.of()),
            Map.entry("frost_wyvern", Set.of("rime_talon")),
            Map.entry("barrow_lich", Set.of("grave_bone")),
            Map.entry("shard_skitterer", Set.of()),
            Map.entry("prism_sentinel", Set.of()),
            Map.entry("echo_wisp", Set.of()),
            Map.entry("geode_brute", Set.of("resonant_sinew")),
            Map.entry("crystal_dragonkin", Set.of("resonant_sinew")),
            Map.entry("prism_centaur", Set.of("resonant_sinew")),
            Map.entry("ink_wraith", Set.of("ink_essence")),
            Map.entry("page_swarm", Set.of("old_page")),
            Map.entry("biting_tome", Set.of("old_page")),
            Map.entry("archive_sentinel", Set.of("ink_essence", "old_page")),
            Map.entry("ink_naga", Set.of("ink_essence")),
            Map.entry("quill_harpy", Set.of("ink_essence")),
            Map.entry("gear_hound", Set.of("clock_oil")),
            Map.entry("clockwork_sentry", Set.of("clock_oil")),
            Map.entry("spring_jumper", Set.of("clock_oil")),
            Map.entry("chrono_moth", Set.of("chrono_dust")),
            Map.entry("clockwork_wyvern", Set.of("clock_oil")),
            Map.entry("brass_minotaur", Set.of("clock_oil")),
            Map.entry("void_stalker", Set.of("abyss_ichor")),
            Map.entry("echo_colossus", Set.of("sculk_tendril")),
            Map.entry("abyss_eye", Set.of("abyss_ichor")),
            Map.entry("hollow_choir", Set.of("sculk_tendril")),
            Map.entry("void_drake", Set.of("abyss_ichor", "abyss_scale")),
            Map.entry("abyss_dragonkin", Set.of("abyss_ichor", "abyss_scale")),
            Map.entry("moss_crawler_alpha", Set.of("moss_fiber")),
            Map.entry("foreman_gorrak", Set.of()),
            Map.entry("spore_mother", Set.of("hypha_thread", "spore_cap")),
            Map.entry("verdigris_crab", Set.of("brine_pearl")),
            Map.entry("forge_executioner", Set.of("ember_soul")),
            Map.entry("crypt_bellringer", Set.of("grave_bone")),
            Map.entry("resonance_tuner", Set.of("resonant_sinew")),
            Map.entry("forbidden_keeper", Set.of("ink_essence", "old_page")),
            Map.entry("grand_regulator", Set.of("clock_oil")),
            Map.entry("abyss_gatekeeper", Set.of("abyss_ichor", "sculk_tendril")),
            Map.entry("floor01_boss", Set.of("moss_fiber")),
            Map.entry("floor02_boss", Set.of("spider_silk", "tunnel_fang")),
            Map.entry("floor03_boss", Set.of("hypha_thread", "spore_cap")),
            Map.entry("floor04_boss", Set.of("brine_pearl")),
            Map.entry("floor05_boss", Set.of("ember_soul")),
            Map.entry("floor06_boss", Set.of("grave_bone")),
            Map.entry("floor07_boss", Set.of()),
            Map.entry("floor08_boss", Set.of("ink_essence", "old_page")),
            Map.entry("floor09_boss", Set.of("chrono_dust", "clock_oil")),
            Map.entry("floor10_boss", Set.of("abyss_ichor", "sculk_tendril")));

    /** 층마다 몬스터 부위 (drops_spec floor_parts). */
    static final Map<Integer, List<String>> FLOOR_PARTS = Map.of(
            1, List.of("moss_fiber", "beetle_shell", "moss_scale"), 2, List.of("spider_silk", "tunnel_fang"),
            3, List.of("spore_cap", "hypha_thread"), 4, List.of("brine_pearl", "eel_scale"), 5, List.of("cinder_scale", "ember_soul"),
            6, List.of("grave_bone", "rime_talon"), 7, List.of("resonant_sinew"), 8, List.of("ink_essence", "old_page"),
            9, List.of("clock_oil", "chrono_dust"), 10, List.of("abyss_ichor", "sculk_tendril", "abyss_scale"));

    /** 용·드레이크·와이번 몸에 없는 것 (껍질·이끼·실·갓·진주·뼈·책). */
    static final Set<String> NOT_ON_DRAGONS = Set.of("beetle_shell", "moss_fiber", "spider_silk", "spore_cap", "hypha_thread",
            "brine_pearl", "grave_bone", "old_page", "ink_essence", "sculk_tendril");

    static Set<String> allParts() {
        Set<String> s = new HashSet<>();
        FLOOR_PARTS.values().forEach(s::addAll);
        return s;
    }

    @Test
    void everyMobDropsOnlyItsOwnBodyParts() {
        Content c = Mat036.content();
        Set<String> parts = allParts();
        List<String> bad = new ArrayList<>();
        int checked = 0;
        for (MobDef m : c.mobs().values()) {
            if (m.drops() == null || "add".equals(m.rank())) continue;
            Set<String> allowed = THEME.get(m.id());
            assertNotNull(allowed, m.id() + " 가 주제 표에 없다 (새 몹이면 몸에 맞는 부위를 정해 표에 더할 것)");
            Set<String> got = Mat036.expand(c, m.drops(), new HashSet<>());
            got.retainAll(parts);
            for (String p : got) if (!allowed.contains(p)) bad.add(m.id() + "(" + m.name() + ") → " + p);
            checked++;
        }
        assertEquals(List.of(), bad, "몸에 없는 부위를 떨어뜨리는 몹");
        assertTrue(checked >= 70, "몹 " + checked);
    }

    @Test
    void bossesDropOnlyTheirOwnParts() {
        Content c = Mat036.content();
        Set<String> parts = allParts();
        for (int f = 1; f <= 10; f++) {
            BossDef b = c.bossOfFloor(f);
            Set<String> allowed = THEME.get(b.drops());
            assertNotNull(allowed, b.drops());
            Set<String> got = Mat036.own(c, b.drops());
            got.retainAll(parts);
            for (String p : got) assertTrue(allowed.contains(p), b.drops() + " → " + p);
        }
    }

    @Test
    void dragonsNeverDropShellsOrFibers() {
        Content c = Mat036.content();
        int dragons = 0;
        for (MobDef m : c.mobs().values()) {
            if (m.drops() == null) continue;
            String n = m.name();
            if (!(n.contains("용") || n.contains("드레이크") || n.contains("와이번"))) continue;
            dragons++;
            Set<String> got = Mat036.expand(c, m.drops(), new HashSet<>());
            for (String p : NOT_ON_DRAGONS) assertTrue(!got.contains(p), m.id() + "(" + n + ") 이 " + p + " 를 떨어뜨린다");
        }
        assertTrue(dragons >= 8, "용 몸 몹 " + dragons);
    }

    @Test
    void spiritsDropNoParts() {
        Content c = Mat036.content();
        Set<String> parts = allParts();
        for (String id : List.of("lantern_wisp", "rime_mourner", "icicle_wraith", "echo_wisp")) {
            MobDef m = c.mobs().get(id);
            assertNotNull(m, id);
            Set<String> got = Mat036.expand(c, m.drops(), new HashSet<>());
            got.retainAll(parts);
            assertEquals(Set.of(), got, id + " 는 몸이 없어 부위를 떨어뜨리지 않는다");
        }
    }

    @Test
    void everyFloorPartIsStillObtainableOnItsFloor() {
        // 층마다 제작·강화 재료(부위)를 그 층 몹·정예·보스·상자에서 얻을 수 있다 (그 층 부위가 하나도 빠지지 않음)
        Content c = Mat036.content();
        for (var e : FLOOR_PARTS.entrySet()) {
            int f = e.getKey();
            Set<String> got = new HashSet<>();
            for (MobDef m : c.mobs().values()) if (m.floor() == f && m.drops() != null) got.addAll(Mat036.expand(c, m.drops(), new HashSet<>()));
            got.addAll(Mat036.expand(c, c.bossOfFloor(f).drops(), new HashSet<>()));
            got.addAll(Mat036.expand(c, "treasure_floor_" + f, new HashSet<>()));
            for (String p : e.getValue()) {
                assertNotNull(c.item(p), p);
                assertTrue(got.contains(p), f + "층 부위 " + p + " 를 그 층에서 얻을 수 없다");
            }
        }
    }
}
