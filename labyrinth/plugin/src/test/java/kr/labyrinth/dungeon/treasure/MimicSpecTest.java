package kr.labyrinth.dungeon.treasure;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.ModelDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.ContentValidator;
import kr.labyrinth.dungeon.DungeonConfig;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * 0.3.6 미믹 (GDD §5.6): 미믹 상자는 상자 괴물 그 자체로 나온다 — 층 일반 몹 무리가 아니다. 어느 미믹이 몇 층에 나오는지 · 층 수치
 * (그 층 일반 몹 평균 × 배율, 정예보다 약하게) · 깊은 층의 새끼 미믹 하나 · 모델(뚜껑 턱 경첩·혀) · 옛 키 호환.
 */
class MimicSpecTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @Test
    void mimicsAreTheChestMonstersNotTheOreMimic() {
        for (String id : List.of("chest_mimic", "gilded_mimic", "mimic_whelp")) {
            MobDef d = content.mob(id);
            assertNotNull(d, id);
            assertTrue(MimicSpec.isMimic(d), id);
            assertEquals(0, d.floor(), id + ": 어느 층에나 (floor 0)");
            assertNull(d.drops(), id + ": 보상은 다시 나타나는 상자");
        }
        assertEquals("elite", content.mob("chest_mimic").rank());
        assertEquals("elite", content.mob("gilded_mimic").rank());
        assertEquals("add", content.mob("mimic_whelp").rank());
        // 2층 광맥 흉내쟁이는 그대로 보통 층 몹 (돌 위장 · 기습)
        MobDef ore = content.mob("ore_mimic");
        assertFalse(MimicSpec.isMimic(ore));
        assertEquals(2, ore.floor());
        assertEquals("normal", ore.rank());
        assertTrue(content.floor(2).mobs().contains("ore_mimic"));
        assertTrue(ore.skills().stream().anyMatch(s -> "ambush".equals(s.type())));
        for (int f = 1; f <= content.maxFloor(); f++) {
            for (String id : content.floor(f).mobs()) assertFalse(MimicSpec.isMimic(content.mob(id)), "층 몹 목록에 미믹 없음: " + id);
        }
    }

    @Test
    void oneMimicPerChestAndOneWhelpFromFloorSix() {
        for (int f = 1; f <= content.maxFloor(); f++) {
            List<MobDef> pack = MimicSpec.pack(content, f);
            assertEquals(f >= 6 ? 2 : 1, pack.size(), "지하 " + f + "층 미믹 수");
            assertEquals(f >= 6 ? "gilded_mimic" : "chest_mimic", pack.get(0).id(), "지하 " + f + "층 큰 미믹");
            if (pack.size() > 1) assertEquals("mimic_whelp", pack.get(1).id());
            for (MobDef d : pack) {
                assertEquals(f, d.floor());
                assertTrue(MimicSpec.isMimic(d));
            }
        }
        assertNull(MimicSpec.companion(content, content.mob("chest_mimic")));
        assertEquals("mimic_whelp", MimicSpec.companion(content, content.mob("gilded_mimic")).id());
    }

    @Test
    void statsFollowTheFloorLikeOtherElitesButStayBelowTheFloorElite() {
        double prevHp = 0, prevDmg = 0;
        for (int f = 1; f <= content.maxFloor(); f++) {
            List<MobDef> fm = MimicSpec.floorMobs(content, f);
            double avgHp = fm.stream().mapToDouble(MobDef::hp).average().orElseThrow();
            double avgDmg = fm.stream().mapToDouble(MobDef::damage).average().orElseThrow();
            MobDef big = MimicSpec.pack(content, f).get(0);
            String at = "지하 " + f + "층";
            assertTrue(big.hp() >= avgHp * 3 && big.hp() <= avgHp * 5, at + " HP " + big.hp() + " vs 층 평균 " + avgHp);
            assertTrue(big.damage() > avgDmg && big.damage() <= avgDmg * 1.6, at + " 피해 " + big.damage());
            assertTrue(big.xp() > 0 && big.gold().max() > 0, at + " 경험치·골드");
            MobDef elite = content.mob(content.floor(f).elite());
            assertTrue(big.hp() < elite.hp(), at + ": 정예보다 약함 (" + big.hp() + " < " + elite.hp() + ")");
            assertTrue(big.hp() > prevHp && big.damage() > prevDmg, at + ": 깊을수록 셈");
            prevHp = big.hp();
            prevDmg = big.damage();
            if (f >= 6) {
                MobDef whelp = MimicSpec.pack(content, f).get(1);
                assertTrue(whelp.hp() < big.hp() / 2, at + ": 새끼 미믹은 작다");
                assertTrue(whelp.damage() < big.damage(), at);
            }
        }
        // 공격 간격은 그 층 몹을 따른다 (1층 1.5초 · 2층 1.35초)
        assertEquals(1.5, MimicSpec.pack(content, 1).get(0).raw().dbl("attack_interval", 0), 1e-9);
        assertEquals(1.35, MimicSpec.pack(content, 2).get(0).raw().dbl("attack_interval", 0), 1e-9);
        assertEquals(1.2, MimicSpec.pack(content, 7).get(0).raw().dbl("attack_interval", 0), 1e-9);
    }

    @Test
    void scaledCopyKeepsIdModelAndSkills() {
        MobDef base = content.mob("gilded_mimic");
        MobDef s = MimicSpec.scaled(base, MimicSpec.floorMobs(content, 8), 8);
        assertEquals(base.id(), s.id(), "리소스팩 모델(mob/<id>/…)을 같이 쓴다");
        assertEquals(base.model(), s.model());
        assertEquals(base.skills(), s.skills());
        assertEquals(base.name(), s.name());
        assertEquals(base.rank(), s.rank());
        // 층 몹이 없으면 YAML 값 그대로
        MobDef raw = MimicSpec.scaled(base, List.of(), 3);
        assertEquals(base.hp(), raw.hp(), 1e-9);
        assertEquals(3, raw.floor());
    }

    @Test
    void noMimicInOldMobsFileMeansOldAmbush() {
        Content empty = Content.empty();
        assertNull(MimicSpec.forFloor(empty, 3));
        assertTrue(MimicSpec.pack(empty, 3).isEmpty(), "옛 mobs.yml → 예전처럼 층 일반 몹 (treasure.mimic_mobs)");
    }

    @Test
    void chestModelHasAHingedLidJawAndATongue() {
        for (String id : List.of("chest_mimic", "gilded_mimic", "mimic_whelp")) {
            List<ModelDef.Part> parts = content.mob(id).model().parts();
            ModelDef.Part body = parts.stream().filter(p -> p.name().equals("body")).findFirst().orElseThrow();
            ModelDef.Part lid = parts.stream().filter(p -> p.name().equals("lid")).findFirst().orElseThrow();
            ModelDef.Part tongue = parts.stream().filter(p -> p.name().equals("tongue")).findFirst().orElseThrow();
            assertEquals("lid", lid.anim(), id);
            double bodyTop = body.pivotY() + body.sizeY() / 32.0, bodyBack = body.pivotZ() - body.sizeZ() / 32.0;
            assertEquals(bodyTop, lid.jointY(), 1e-6, id + ": 경첩 = 몸통 윗면");
            assertEquals(bodyBack, lid.jointZ(), 1e-6, id + ": 경첩 = 뒤 모서리");
            assertEquals(body.sizeX(), lid.sizeX(), 1e-9, id + ": 뚜껑 = 상자 폭");
            assertEquals("tail", tongue.anim(), id);
            assertTrue(tongue.sizeY() > 1.4 * tongue.sizeZ(), id + ": 혀는 늘어진 진자");
            assertTrue(tongue.pivotZ() > body.pivotZ() + body.sizeZ() / 32.0, id + ": 혀는 앞 입술에 걸침");
            assertTrue(parts.stream().noneMatch(p -> "legs_walk".equals(p.anim())), id + ": 다리 없이 깡충");
        }
    }

    @Test
    void validatorIsHappyWithTheMimics() {
        ContentValidator.Report r = ContentValidator.validate(content);
        assertTrue(r.ok(), () -> String.join("\n", r.errors()));
        for (String w : r.warnings()) assertFalse(w.contains("mimic"), w);
    }

    @Test
    void oldMimicMobsKeyStillParses() {
        YamlConfiguration y = new YamlConfiguration();
        y.set("treasure.mimic_mobs", 5);
        y.set("treasure.mimic_lock_seconds", 40);
        DungeonConfig c = DungeonConfig.of(y);
        assertEquals(5, c.mimicMobs(), "옛 키는 그대로 읽힌다 (미믹 몹이 없을 때만 씀)");
        assertEquals(40, c.traps().mimicLockSeconds());
        assertEquals(2, DungeonConfig.defaults().mimicMobs());
    }
}
