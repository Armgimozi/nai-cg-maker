package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.util.UUID;
import kr.labyrinth.pvp.PvpRules.Kind;
import kr.labyrinth.pvp.PvpRules.Side;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** 파티 규칙 PvP (GDD §18): 적/아군 표 · 마을 안전지대 · 피해 배율/상한 · config 읽기. */
class PvpRulesTest {

    static final PvpConfig ON = PvpConfig.DEFAULT;

    static Side player(String party) { return Side.player(UUID.randomUUID(), party); }

    static Side of(Kind k) { return Side.of(k, UUID.randomUUID()); }

    static boolean enemy(Side a, Side b) { return PvpRules.isEnemy(ON, a, b); }

    @Test
    void samePartyNeverFightsAnywhere() {
        Side a = player("p1"), b = player("p1");
        assertFalse(enemy(a, b));
        assertFalse(enemy(b, a));
        assertTrue(PvpRules.isAlly(a, b), "같은 파티 = 치유·버프 대상");
        // 안전지대 밖이든 안이든 같은 파티는 적이 아님
        assertFalse(enemy(a.inSafeZone(true), b));
    }

    @Test
    void otherPartiesAndSolosCanFight() {
        Side p1 = player("p1"), p2 = player("p2"), solo = player(null), solo2 = player(null);
        assertTrue(enemy(p1, p2));
        assertTrue(enemy(p2, p1));
        assertTrue(enemy(p1, solo), "파티 → 솔로");
        assertTrue(enemy(solo, p1), "솔로 → 파티");
        assertTrue(enemy(solo, solo2), "솔로끼리는 다른 파티");
        assertFalse(PvpRules.isAlly(p1, p2));
        assertFalse(PvpRules.isAlly(solo, solo2), "솔로끼리는 서로 치유 대상이 아님");
    }

    @Test
    void selfIsAllyNeverEnemy() {
        Side a = player("p1"), solo = player(null);
        assertFalse(enemy(a, a));
        assertTrue(PvpRules.isAlly(a, a));
        assertFalse(enemy(solo, solo));
        assertTrue(PvpRules.isAlly(solo, solo), "솔로도 자기 자신은 치유");
    }

    @Test
    void mobsAndNpcs() {
        Side p = player("p1"), mob = of(Kind.MOB), mob2 = of(Kind.MOB), hostile = of(Kind.HOSTILE), npc = of(Kind.NPC), cow = of(Kind.OTHER);
        assertTrue(enemy(p, mob), "플레이어 → 커스텀 몹");
        assertTrue(enemy(mob, p), "커스텀 몹 → 플레이어");
        assertTrue(enemy(p, hostile), "미궁 밖 바닐라 적대 몹");
        assertFalse(enemy(hostile, p), "바닐라 몹은 스킬 판정의 공격자가 아님");
        assertFalse(enemy(p, npc), "NPC 는 누구의 적도 아님");
        assertFalse(enemy(npc, p));
        assertFalse(enemy(mob, npc));
        assertFalse(enemy(p, cow), "동물");
        assertFalse(enemy(mob, mob2), "몹끼리");
        assertTrue(PvpRules.isAlly(mob, mob2), "몹끼리 아군 (몹 치유 스킬)");
        assertFalse(PvpRules.isAlly(p, mob));
        assertFalse(PvpRules.isAlly(p, npc));
        assertFalse(PvpRules.isAlly(mob, p));
    }

    @Test
    void invulnerableTargetsAreNotEnemies() {
        Side p1 = player("p1"), creative = player("p2").invulnerable(true), mob = of(Kind.MOB);
        assertFalse(enemy(p1, creative), "크리에이티브·관전·쓰러짐");
        assertFalse(enemy(mob, creative));
        assertTrue(enemy(creative, p1), "무적인 쪽이 때리는 건 막지 않음 (바닐라도 크리에이티브는 때릴 수 있음)");
        assertFalse(enemy(p1, mob.invulnerable(true)), "죽은 몹");
    }

    @Test
    void villageSafeZoneBlocksPvpOnly() {
        Side out = player("p1"), in = player("p2").inSafeZone(true), mob = of(Kind.MOB);
        assertFalse(enemy(out, in), "마을 안 사람을 밖에서 쏘기");
        assertFalse(enemy(in, out), "마을 안에서 밖으로 쏘기");
        assertFalse(enemy(in, player(null).inSafeZone(true)), "둘 다 마을 안");
        assertTrue(enemy(out, player(null)), "둘 다 밖");
        assertTrue(enemy(in, mob), "안전지대는 PvP 만 막는다");
    }

    @Test
    void disabledMeansNoPlayerFights() {
        Side p1 = player("p1"), p2 = player("p2"), mob = of(Kind.MOB);
        assertFalse(PvpRules.isEnemy(PvpConfig.OFF, p1, p2));
        assertFalse(PvpRules.canPlayersFight(PvpConfig.OFF, p1, p2));
        assertTrue(PvpRules.isEnemy(PvpConfig.OFF, p1, mob), "PvP 를 꺼도 몹은 적");
        assertTrue(PvpRules.isAlly(p1, player("p1")), "아군 판정은 PvP 설정과 무관");
    }

    @Test
    void noOneHitCapByDefault() {
        assertEquals(1.0, PvpConfig.DEFAULT.maxHitRatio(), 1e-9, "0.3.5: 한 방 상한 없음 (관리자용 키만 남음)");
        assertEquals(1.0, PvpConfig.DEFAULT.damageMultiplier(), 1e-9, "기본 대비 배율 1.0");
        assertFalse(PvpConfig.OFF.enabled());
    }

    @Test
    void configParsingAndClamps() throws InvalidConfigurationException {
        assertEquals(PvpConfig.DEFAULT, PvpConfig.from(null), "pvp 블록이 없으면 기본값");
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("pvp:\n  enabled: false\n  damage_multiplier: 9\n  max_hit_ratio: 0\n  safe_zone_margin: -3\n");
        PvpConfig c = PvpConfig.from(y.getConfigurationSection("pvp"));
        assertFalse(c.enabled());
        assertEquals(5.0, c.damageMultiplier(), 1e-9);
        assertEquals(0.05, c.maxHitRatio(), 1e-9);
        assertEquals(0, c.safeZoneMargin());
        assertTrue(c.safeZoneVillage(), "없는 키 = 기본값");
    }

    @Test
    void bundledConfigMatchesDefaults() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertNotNull(y.getConfigurationSection("pvp"), "config.yml 에 pvp: 블록");
        assertEquals(PvpConfig.DEFAULT, PvpConfig.from(y.getConfigurationSection("pvp")),
                "config.yml 기본값과 PvpConfig.DEFAULT 가 같아야 (키가 빠진 옛 설정도 같은 값)");
    }

    @Test
    void villageZoneFromMetadata() throws InvalidConfigurationException {
        UUID world = UUID.randomUUID();
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString("format: 1\nname: 등불 어귀 마을\ncenter: [100, 70, -40]\nradius: 32\n");
        VillageZone.Zone z = VillageZone.parse(y, world, 8);
        assertNotNull(z);
        assertEquals(40.0, z.radius(), 1e-9, "반경 + 여유");
        assertTrue(z.contains(world, 100.5, -39.5), "중심");
        assertTrue(z.contains(world, 100.5 + 39.9, -39.5), "경계 안");
        assertFalse(z.contains(world, 100.5 + 40.1, -39.5), "경계 밖");
        assertFalse(z.contains(UUID.randomUUID(), 100.5, -39.5), "다른 월드");
        YamlConfiguration broken = new YamlConfiguration();
        broken.loadFromString("name: x\n");
        assertNull(VillageZone.parse(broken, world, 8), "center/radius 없음 → 안전지대 없음");
        assertNull(VillageZone.parse(null, world, 8));
        assertTrue(VillageZone.within(0, 0, 5, 3, 4), "3-4-5 경계 포함");
        assertFalse(VillageZone.within(0, 0, 0, 0, 0), "반경 0 = 없음");
    }
}
