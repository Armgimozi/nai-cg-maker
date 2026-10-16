package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Settings;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.ItemTooltip;
import org.bukkit.configuration.MemoryConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 0.3.6.1 주인 결정 2 — 활로 직접 치면 피해 절반 + 툴팁 한 줄 ({@link BowMelee}, config combat.bow_melee_mult). */
class BowMeleeTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @AfterEach
    void resetTooltip() { ItemTooltip.bowMelee(BowMelee.DEFAULT_MULT); }

    @Test
    void holdingABowHalvesMeleeOnly() {
        WeaponAttack bow = WeaponAttack.of(content.item("grove_rootstring_bow"));
        WeaponAttack dirk = WeaponAttack.of(content.item("moss_dirk"));
        assertTrue(bow.ranged());
        assertEquals(0.5, BowMelee.mult(bow, 0.5), 1e-12, "활 = 절반");
        assertEquals(1.0, BowMelee.mult(dirk, 0.5), 1e-12, "단도는 그대로");
        assertEquals(1.0, BowMelee.mult(WeaponAttack.UNARMED, 0.5), 1e-12, "맨손(요구 미달 활 포함)은 그대로");
        assertEquals(1.0, BowMelee.mult(null, 0.5), 1e-12);
        assertEquals(0.5, BowMelee.mult(WeaponAttack.vanilla(0, true), 0.5), 1e-12, "바닐라 활도 활");
        assertEquals(1.0, BowMelee.mult(bow, 1.0), 1e-12, "1 = 예전 그대로");
        assertEquals(1.0, BowMelee.mult(bow, 3.0), 1e-12, "1 보다 세게는 안 됨");
        assertEquals(0.0, BowMelee.mult(bow, -1), 1e-12);
        assertEquals(BowMelee.DEFAULT_MULT, BowMelee.clamp(Double.NaN), 1e-12);
    }

    @Test
    void bowMeleeIsNowWeakerThanTheDagger() {
        // 예전: 파수궁으로 직접 치면 단도보다 26% 셌다 (bowfeel mech §1). 이제 절반 → 단도보다 약하다
        double as = CombatMath.attackSpeed(7, 0);
        ItemDef bowDef = content.item("grove_rootstring_bow"), dirkDef = content.item("moss_dirk");
        double bowHit = bowDef.stats().get("damage").lerp(0.5);
        double bowCycle = CombatMath.cycle(WeaponAttack.of(bowDef), as, CombatMath.MIN_INTERVAL);
        double dirkHit = dirkDef.stats().get("damage").lerp(0.5);
        double dirkInterval = CombatMath.cycle(WeaponAttack.of(dirkDef), as, CombatMath.MIN_INTERVAL);
        double before = bowHit / bowCycle, after = before * BowMelee.mult(WeaponAttack.of(bowDef), BowMelee.DEFAULT_MULT);
        double dirk = dirkHit / dirkInterval;
        assertTrue(before > dirk, "예전 활 직접 치기 " + before + " > 단도 " + dirk);
        assertTrue(after < dirk, "이제 활 직접 치기 " + after + " < 단도 " + dirk);
    }

    @Test
    void configKeyHasADefaultForOldConfigFiles() throws Exception {
        assertEquals(0.5, new Settings(new MemoryConfiguration()).bowMeleeMult(), 1e-12, "키가 없는 예전 config.yml = 0.5");
        YamlConfiguration jar = new YamlConfiguration();
        jar.load(new java.io.File("src/main/resources/config.yml"));
        assertTrue(jar.contains("combat.bow_melee_mult"), "jar config.yml 에 키가 있다");
        assertEquals(0.5, new Settings(jar).bowMeleeMult(), 1e-12);
        YamlConfiguration c = new YamlConfiguration();
        c.set("combat.bow_melee_mult", 0.75);
        assertEquals(0.75, new Settings(c).bowMeleeMult(), 1e-12);
        c.set("combat.bow_melee_mult", 7);
        assertEquals(1.0, new Settings(c).bowMeleeMult(), 1e-12, "1 로 자름");
    }

    @Test
    void bowTooltipSaysSoInOnePlainLine() {
        assertEquals("활로 직접 치면 피해 절반", BowMelee.tooltipText(0.5));
        assertNull(BowMelee.tooltipText(1.0), "예전 그대로면 줄 없음");
        assertEquals("활로 직접 치면 피해 70%", BowMelee.tooltipText(0.7));
        assertEquals("활로 직접 치면 피해 없음", BowMelee.tooltipText(0));
        int bows = 0;
        for (ItemDef d : content.items().values()) {
            if (!d.isWeapon()) continue;
            List<String> plain = ItemTooltip.lines(content, d, null).stream().map(Text::strip).toList();
            boolean ranged = WeaponAttack.of(d).ranged();
            int speed = -1;
            for (int i = 0; i < plain.size(); i++) if (plain.get(i).startsWith("공격 속도 초당")) speed = i;
            assertTrue(speed >= 0, d.id());
            if (ranged) {
                bows++;
                assertEquals("활로 직접 치면 피해 절반", plain.get(speed + 1), d.id() + ": 공격 속도 바로 아래");
            } else {
                assertFalse(plain.contains("활로 직접 치면 피해 절반"), d.id() + " 는 활이 아님");
            }
        }
        assertTrue(bows >= 30, "활 " + bows);
        ItemTooltip.bowMelee(1.0);
        List<String> plain = ItemTooltip.lines(content, content.item("grove_rootstring_bow"), null).stream().map(Text::strip).toList();
        assertTrue(plain.stream().noneMatch(l -> l.startsWith("활로 직접 치면")), "배율 1 이면 줄 없음");
    }
}
