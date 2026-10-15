package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.Map;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatCalculator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 초반 솔로 완화 데이터: 1·2층 몹 기본 공격 간격, 정예 소환 수 솔로 값, 그림자·비전술사 기본 체력. */
class EarlySoloDataTest {

    private static final double EPS = 1e-9;

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void earlyFloorMobsAttackSlower() {
        // 1층 1.5초 · 2층 1.35초 (정예·소환물 포함). MobAi.attackInterval 이 읽는 키, 없으면 1.2초
        int seen = 0;
        for (MobDef m : content.mobs().values()) {
            if (m.floor() != 1 && m.floor() != 2) continue;
            double want = m.floor() == 1 ? 1.5 : 1.35;
            assertEquals(want, m.raw().dbl("attack_interval", 1.2), EPS, m.id());
            assertTrue(Math.abs(want * 20 - Math.round(want * 20)) < 1e-6, "틱으로 딱 떨어짐: " + m.id());
            seen++;
        }
        assertEquals(16, seen, "1층 8종 + 2층 8종");
    }

    @Test
    void eliteSummonsAreSmallerSoloOnly() {
        // id → {솔로 count, 솔로 max_alive, 파티 count, 파티 max_alive}
        Map<String, int[]> want = Map.of(
                "moss_crawler_alpha", new int[] {1, 2, 2, 4},
                "foreman_gorrak", new int[] {1, 2, 2, 3},
                "spore_mother", new int[] {1, 2, 2, 3}); // 0.3.5: 3층 정예방 20~90초 (소환 줄임)
        for (Map.Entry<String, int[]> e : want.entrySet()) {
            Params p = summonParams(content.mob(e.getKey()));
            assertNotNull(p, e.getKey() + " 소환 스킬");
            int[] w = e.getValue();
            assertEquals(w[0], p.scaledInt("count", 1, 2), e.getKey() + " 솔로 count");
            assertEquals(w[1], p.scaledInt("max_alive", 1, 4), e.getKey() + " 솔로 max_alive");
            for (int n : new int[] {2, 4, 10}) {
                assertEquals(w[2], p.scaledInt("count", n, 2), e.getKey() + " " + n + "인 count");
                assertEquals(w[3], p.scaledInt("max_alive", n, 4), e.getKey() + " " + n + "인 max_alive");
            }
            // solo_ 키를 모르는 읽기(p.integer)도 파티 값 그대로
            assertEquals(w[2], p.integer("count", 2));
            assertEquals(w[3], p.integer("max_alive", 4));
        }
    }

    @Test
    void floorThreeEliteSummonsSlowerAndHealWeaker() {
        // 0.3.5 (review2 · 주인 결정 7): 3층 정예방이 소환체 때문에 4분대로 늘어지던 것 — 소환 24초마다, 군락 치유 25초마다 5%
        MobDef m = content.mob("spore_mother");
        double summonCd = -1, healCd = -1, heal = -1;
        for (MobDef.MobSkillDef s : m.skills()) {
            if ("summon".equals(s.type())) summonCd = s.cooldown();
            if ("heal_allies".equals(s.type())) {
                healCd = s.cooldown();
                heal = s.params().dbl("amount", 0);
            }
        }
        assertTrue(summonCd >= 24, "소환 재사용 ≥ 24초: " + summonCd);
        assertTrue(healCd >= 25 && heal <= 0.05 + EPS, "치유 25초 · 5% 이하: " + healCd + " / " + heal);
    }

    @Test
    void soloSummonValuesNeverExceedParty() {
        for (MobDef m : content.mobs().values()) {
            for (MobDef.MobSkillDef s : m.skills()) {
                if (!"summon".equals(s.type())) continue;
                Params p = s.params();
                int solo = p.scaledInt("count", 1, 2), soloMax = p.scaledInt("max_alive", 1, 4);
                assertTrue(solo >= 1 && solo <= soloMax, m.id() + ": 솔로 count 1 이상, max_alive 이하");
                assertTrue(solo <= p.integer("count", 2), m.id() + ": 솔로 count ≤ 파티");
                assertTrue(soloMax <= p.integer("max_alive", 4), m.id() + ": 솔로 max_alive ≤ 파티");
            }
        }
    }

    @Test
    void shadowAndArcanistStartSturdier() {
        // Lv1 맨몸 최대 HP = base_hp + VIT×8 → 그림자 115 + 5×8, 비전술사 110 + 4×8
        ClassDef shadow = content.classDef("shadow");
        ClassDef arcanist = content.classDef("arcanist");
        assertEquals(115 + 5 * 8, lv1Hp(shadow), EPS);
        assertEquals(110 + 4 * 8, lv1Hp(arcanist), EPS);
        assertEquals(2.0, arcanist.skillByInput("SWAP").params().dbl("damage", 0), EPS, "마력탄");
        // 탱커보다는 낮다
        double guardian = lv1Hp(content.classDef("guardian"));
        assertTrue(lv1Hp(shadow) < guardian && lv1Hp(arcanist) < guardian);
    }

    private static double lv1Hp(ClassDef c) {
        return StatCalculator.compute(c, 1, Map.of(), new StatBlock(), 0.05, 1.5).maxHp();
    }

    private static Params summonParams(MobDef m) {
        if (m == null) return null;
        for (MobDef.MobSkillDef s : m.skills()) if ("summon".equals(s.type())) return s.params();
        return null;
    }
}
