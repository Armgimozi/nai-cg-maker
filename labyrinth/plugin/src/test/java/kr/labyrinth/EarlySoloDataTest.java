package kr.labyrinth;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import kr.labyrinth.combat.WeaponAttack;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.content.Range;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.items.ItemMigration035;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatCalculator;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 초반 솔로 완화 데이터: 1·2층 몹 기본 공격 간격, 정예 소환 수 솔로 값, 그림자·비전술사 기본 체력, 1·2층 무기 초당 피해. */
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

    /**
     * 0.3.5 P0b: 1·2층 무기(직업마다 받는 시작 무기 포함)는 무기마다 간격이 생긴 뒤에도 초당 피해 등가(한 방 ÷ 간격)가
     * 0.3.4 숙련(게이지 꽉 차게 친) 초당 피해보다 낮지 않다 — 초반 솔로가 약해지지 않게 (c(L) ≈ 1.18~1.3 배).
     */
    @Test
    void earlyWeaponsHitAtLeastAsHardPerSecondAsBefore() throws IOException {
        JsonObject spec = JsonParser.parseString(Files.readString(Path.of("../tools/data/035/combat_spec.json"), StandardCharsets.UTF_8))
                .getAsJsonObject().getAsJsonObject("weapons");
        int n = 0;
        for (Map.Entry<String, Range> e : ItemMigration035.OLD_DAMAGE.entrySet()) {
            ItemDef d = content.item(e.getKey());
            if (d == null || d.floor() > 2) continue;
            // 0.3.4 의 주기 = 그때 파일의 옛 키 (명세 old_type) — 활은 끝까지 당긴 화살 ×1.25 였다
            String old = spec.getAsJsonObject(d.id()).get("old_type").getAsString();
            WeaponAttack then = WeaponAttack.legacy(Params.of(Map.of("weapon_type", old)));
            double oldDps = (e.getValue().min() + e.getValue().max()) / 2 / then.interval() * (then.ranged() ? 1.25 : 1.0);
            Range now = d.stats().get("damage");
            double newDps = (now.min() + now.max()) / 2 / d.attack().interval();
            assertTrue(newDps >= oldDps * 1.05, d.id() + " 초당 " + newDps + " < 0.3.4 " + oldDps);
            n++;
        }
        assertTrue(n >= 24, "1·2층 무기 " + n);
        for (ClassDef c : content.classes().values()) {
            ItemDef w = content.item(c.starterWeapon());
            assertNotNull(w, c.id());
            assertTrue(w.floor() == 1, c.id() + " 시작 무기 " + w.id());
        }
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
