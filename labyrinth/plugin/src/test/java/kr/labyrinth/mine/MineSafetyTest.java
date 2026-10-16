package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import kr.labyrinth.content.ItemDef;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Zombie;
import org.bukkit.inventory.ItemStack;
import org.junit.jupiter.api.Test;

/** 광산 안전 (계약 §2.2): 광산 월드 안 플레이어는 피해 0 — DamageService·상태 이상·안전지대·PvP 규칙이 모두 같은 검사를 부른다. */
class MineSafetyTest {

    @SuppressWarnings("unchecked")
    static <T> T fake(Class<T> type, Map<String, Object> answers) {
        return (T) Proxy.newProxyInstance(MineSafetyTest.class.getClassLoader(), new Class<?>[] {type}, (proxy, m, args) -> {
            switch (m.getName()) {
                case "equals": return proxy == args[0];
                case "hashCode": return System.identityHashCode(proxy);
                case "toString": return type.getSimpleName();
                default:
                    if (answers.containsKey(m.getName())) return answers.get(m.getName());
                    Class<?> r = m.getReturnType();
                    if (r == boolean.class) return false;
                    if (r == int.class || r == long.class) return 0;
                    if (r == double.class) return 0.0;
                    if (r == float.class) return 0f;
                    return null;
            }
        });
    }

    static MineApi api(boolean safe) {
        return new MineApi() {
            @Override public boolean enabled() { return true; }
            @Override public boolean isMineWorld(World w) { return w != null && MineNames.WORLD.equals(w.getName()); }
            @Override public void openLift(Player p) {}
            @Override public void openOffice(Player p) {}
            @Override public void openInfo(Player p) {}
            @Override public ItemStack applyPickaxe(ItemStack stack, ItemDef def) { return stack; }
            @Override public boolean safe() { return safe; }
        };
    }

    @Test
    void playerInMineIsProtected() {
        World mine = fake(World.class, Map.of("getName", MineNames.WORLD));
        World over = fake(World.class, Map.of("getName", "world"));
        Player inMine = fake(Player.class, Map.of("getWorld", mine));
        Player outside = fake(Player.class, Map.of("getWorld", over));
        Entity zombie = fake(Zombie.class, Map.of("getWorld", mine));
        assertTrue(MineSafety.protects(api(true), inMine));
        assertFalse(MineSafety.protects(api(true), outside));
        assertFalse(MineSafety.protects(api(true), zombie), "몹은 지키지 않음 (광산에는 몹이 없음)");
        assertFalse(MineSafety.protects(api(false), inMine), "config mine.safe: false");
        assertTrue(MineSafety.protects(null, inMine), "api 없음 = 이름으로");
        assertTrue(MineSafety.inMine(api(true), new Location(mine, 0, 136, 0)));
        assertFalse(MineSafety.inMine(api(true), new Location(over, 0, 64, 0)));
        assertFalse(MineSafety.inMine(api(true), (Location) null));
        assertTrue(MineSafety.inMine(new NoopMineApi(), mine), "광산이 꺼져도 이름이 같은 월드는 안전 (Noop)");
    }

    @Test
    void everyDamagePathAsksMineSafety() throws Exception {
        String dmg = Files.readString(Path.of("src/main/java/kr/labyrinth/combat/DamageService.java"));
        assertTrue(count(dmg, "MineSafety.protects(services.mine()") >= 2, "DamageService deal + applyToPlayer");
        String st = Files.readString(Path.of("src/main/java/kr/labyrinth/classes/LabyrinthStatusEffectService.java"));
        assertTrue(count(st, "MineSafety.protects(services.mine()") >= 3, "상태 이상 apply · 지속 피해 · 서리");
        String pvp = Files.readString(Path.of("src/main/java/kr/labyrinth/pvp/PvpModule.java"));
        assertTrue(pvp.contains("MineSafety.inMine(services.mine(), l)") && pvp.contains("config.enabled() && !mine"), "안전지대 + PvP 규칙 끔");
        String filter = Files.readString(Path.of("src/main/java/kr/labyrinth/pvp/DefaultTargetFilter.java"));
        assertTrue(filter.contains("MineSafety.inMine(services.mine(), location)"), "TargetFilter.inSafeZone");
        String listener = Files.readString(Path.of("src/main/java/kr/labyrinth/mine/MineListener.java"));
        assertTrue(listener.contains("onDamageEarly") && listener.contains("onDamageLate") && listener.contains("onCombust"), "바닐라 피해·불");
    }

    @Test
    void spawnWhitelist() {
        assertTrue(MineListener.SPAWN_WHITELIST.contains(org.bukkit.entity.EntityType.ITEM_DISPLAY));
        assertTrue(MineListener.SPAWN_WHITELIST.contains(org.bukkit.entity.EntityType.MANNEQUIN));
        assertFalse(MineListener.SPAWN_WHITELIST.contains(org.bukkit.entity.EntityType.ZOMBIE));
        assertFalse(MineListener.SPAWN_WHITELIST.contains(org.bukkit.entity.EntityType.BAT));
        assertTrue(MineListener.SPAWN_WHITELIST.size() == 6);
    }

    private static int count(String s, String part) {
        int n = 0;
        for (int i = s.indexOf(part); i >= 0; i = s.indexOf(part, i + 1)) n++;
        return n;
    }
}
