package kr.labyrinth.items;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import java.io.File;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

/** config cosmetics.armor_pieces — 키가 없으면 코드 기본값, 이상한 값은 범위 안으로, 기본 config.yml 은 코드 기본값과 같다. */
class ArmorCosmeticsConfigTest {

    private static ArmorCosmetics.Config read(String yaml) throws Exception {
        YamlConfiguration y = new YamlConfiguration();
        y.loadFromString(yaml);
        return ArmorCosmetics.Config.from(y.getConfigurationSection("cosmetics.armor_pieces"));
    }

    @Test
    void missingSectionUsesCodeDefaults() throws Exception {
        assertEquals(ArmorCosmetics.Config.DEFAULT, read("other: 1\n"));
        assertEquals(ArmorCosmetics.Config.DEFAULT, ArmorCosmetics.Config.from(null));
        ArmorCosmetics.Config d = ArmorCosmetics.Config.DEFAULT;
        assertEquals(true, d.enabled());
        assertEquals(2, d.updateTicks());
        assertEquals(0.6f, d.viewRange(), 1e-6);
    }

    @Test
    void partialAndOutOfRangeValues() throws Exception {
        ArmorCosmetics.Config c = read("cosmetics:\n  armor_pieces:\n    enabled: false\n");
        assertFalse(c.enabled());
        assertEquals(2, c.updateTicks());
        c = read("cosmetics:\n  armor_pieces:\n    update_ticks: 0\n    view_range: -3\n");
        assertEquals(1, c.updateTicks());
        assertEquals(0.6f, c.viewRange(), 1e-6);
        c = read("cosmetics:\n  armor_pieces:\n    update_ticks: 500\n    view_range: 9\n");
        assertEquals(20, c.updateTicks());
        assertEquals(4f, c.viewRange(), 1e-6);
    }

    @Test
    void bundledConfigMatchesCodeDefaults() {
        YamlConfiguration y = YamlConfiguration.loadConfiguration(new File("src/main/resources/config.yml"));
        assertEquals(ArmorCosmetics.Config.DEFAULT,
                ArmorCosmetics.Config.from(y.getConfigurationSection("cosmetics.armor_pieces")));
    }
}
