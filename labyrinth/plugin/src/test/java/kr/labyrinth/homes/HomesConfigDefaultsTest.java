package kr.labyrinth.homes;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** config.yml {@code homes:} (0.3.7) — 키가 없으면 기본값 · {@code homes: false} · 틀린 값 자르기 (review R16) · 배포 config 와 코드 기본값이 같음. */
class HomesConfigDefaultsTest {

    @Test
    void missingSectionGivesDefaults() {
        HomesConfig c = HomesConfig.fromRoot(new YamlConfiguration());
        assertEquals(HomesConfig.DEFAULT, c);
        assertTrue(c.enabled());
        assertTrue(c.terrainLock());
        assertEquals(List.of("south_west"), c.district().sites());
        assertEquals(8, c.maxTrusted());
        assertEquals(1440, c.reclaimCooldownMinutes(), "스스로 비운 뒤 24시간 (R13)");
        assertEquals(HomesConfig.Toggle.AUTO, c.homeTeleport(), "집 가기 = village.teleport_command 따름 (R11)");
        assertEquals(HomesConfig.Toggle.AUTO, c.visit());
        assertEquals(List.of("lava_bucket", "fire_charge"), c.denyUse(), "R21");
        assertFalse(c.denyPlace().contains("lava_bucket"));
        assertEquals(16, c.tickParts().total());
        assertEquals(8, c.tickParts().hoppers());
        assertEquals(24, c.entityCaps().animals());
        assertEquals(64, c.entityCaps().decorations());
    }

    @Test
    void falseTurnsEverythingOff() {
        YamlConfiguration y = new YamlConfiguration();
        y.set("homes", false);
        assertFalse(HomesConfig.fromRoot(y).enabled());
    }

    @Test
    void badValuesAreClamped() {
        YamlConfiguration y = new YamlConfiguration();
        y.set("homes.shop_price_multiplier", 0.0);
        y.set("homes.claim_cost", -50);
        y.set("homes.max_trusted", 999);
        y.set("homes.home_regen.hp", 5.0);
        y.set("homes.tick_parts.total", 4);
        y.set("homes.tick_parts.hoppers", 9);
        y.set("homes.home_teleport", false);
        y.set("homes.visit", "on");
        y.set("homes.deny_place", List.of("minecraft:TNT", "tnt", " "));
        HomesConfig c = HomesConfig.fromRoot(y);
        assertEquals(0.1, c.shopPriceMultiplier(), 1e-9);
        assertEquals(0, c.claimCost());
        assertEquals(32, c.maxTrusted());
        assertEquals(1.0, c.regen().hp(), 1e-9);
        assertEquals(4, c.tickParts().total());
        assertEquals(4, c.tickParts().hoppers(), "깔때기는 합을 넘지 않음");
        assertEquals(HomesConfig.Toggle.OFF, c.homeTeleport());
        assertEquals(HomesConfig.Toggle.ON, c.visit());
        assertEquals(List.of("tnt"), c.denyPlace());
    }

    @Test
    void toggleFollowsVillageTeleport() {
        assertTrue(HomesConfig.Toggle.AUTO.allowed(true));
        assertFalse(HomesConfig.Toggle.AUTO.allowed(false), "마을 텔레포트를 끈 서버는 집 가기도 꺼짐 (R11)");
        assertTrue(HomesConfig.Toggle.ON.allowed(false));
        assertFalse(HomesConfig.Toggle.OFF.allowed(true));
    }

    /** 배포 config.yml 의 homes: 절이 코드 기본값과 같다 (주석만 다름). */
    @Test
    void bundledConfigMatchesDefaults() throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(Files.readString(Path.of("src/main/resources/config.yml")));
        assertTrue(y.isConfigurationSection("homes"));
        assertEquals(HomesConfig.DEFAULT, HomesConfig.fromRoot(y));
    }
}
