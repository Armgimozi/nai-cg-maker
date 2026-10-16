package kr.labyrinth.combat;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.ContentLoader;
import kr.labyrinth.core.Text;
import kr.labyrinth.items.ItemTooltip;
import kr.labyrinth.ui.menus.CodexMenu;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** 시전 무기 74자루 전부 마법탄 · 툴팁·도감 글 (0.3.6.1). */
class CasterBoltDataTest {

    static Content content;

    @BeforeAll
    static void load() {
        content = ContentLoader.load(Path.of("src/main/resources/content")).content();
    }

    @AfterEach
    void restore() { WeaponAttack.casterBolt(true); }

    private static List<ItemDef> casters() {
        return content.items().values().stream().filter(d -> d.isWeapon() && WeaponAttack.of(d).caster()).toList();
    }

    @Test
    void everyCasterWeaponFiresAMagicBolt() {
        List<ItemDef> cs = casters();
        assertTrue(cs.size() >= 74, "시전 무기 " + cs.size());
        for (ItemDef d : cs) {
            WeaponAttack a = WeaponAttack.of(d);
            assertTrue(a.firesBolt(), d.id());
            assertEquals(DamageKind.MAGIC, a.kind(), d.id() + " — 기본 공격 피해는 마법 (지능 배율)");
            List<String> pal = d.texture() == null ? List.of() : d.texture().strings("palette");
            int rgb = CasterBoltRules.trailColor(pal, -1);
            assertNotEquals(-1, rgb, d.id() + " — 팔레트에서 색을 못 고름");
            assertTrue(CasterBoltRules.vividness(rgb) > 0.05 || ((rgb >> 16 & 0xFF) + (rgb >> 8 & 0xFF) + (rgb & 0xFF)) > 600,
                    d.id() + " — 너무 칙칙한 색 " + Integer.toHexString(rgb));
        }
        for (ItemDef d : content.items().values()) {
            if (d.isWeapon() && !WeaponAttack.of(d).caster()) assertFalse(WeaponAttack.of(d).firesBolt(), d.id() + " — 근접·활은 그대로");
        }
    }

    @Test
    void tooltipAndCodexSayLeftClickBolt() {
        for (ItemDef d : casters()) {
            String speed = Text.strip(ItemTooltip.speedLine(d));
            assertTrue(speed.startsWith("공격 속도 초당 ") && speed.endsWith(" · 좌클릭 마법탄"), d.id() + ": " + speed);
            List<String> det = CodexMenu.detailLines(content, d, ArmorLooks.DEFAULT);
            assertTrue(det.stream().map(Text::strip).anyMatch(x -> x.startsWith("공격 방식 시전 (좌클릭 마법탄) · 피해 마법")),
                    d.id() + "\n" + String.join("\n", det));
        }
    }

    @Test
    void turningBoltsOffRestoresTheOldText() {
        ItemDef staff = casters().get(0);
        WeaponAttack.casterBolt(false);
        assertFalse(WeaponAttack.of(staff).firesBolt());
        assertFalse(Text.strip(ItemTooltip.speedLine(staff)).contains("마법탄"));
        assertTrue(CodexMenu.detailLines(content, staff, ArmorLooks.DEFAULT).stream().map(Text::strip)
                .anyMatch(x -> x.startsWith("공격 방식 시전 · 피해 마법")));
    }

    @Test
    void leftClickWeaponSkillsOnCastersStillExist() {
        // 좌클릭 무기 스킬(서리심장·공허의 심장 지팡이의 연사 등)은 마법탄과 같은 클릭에 함께 나간다 — 데이터가 남아 있는지
        long left = casters().stream().filter(d -> d.weaponSkill("LEFT") != null).count();
        assertTrue(left >= 2, "좌클릭 스킬이 붙은 시전 무기 " + left);
    }
}
