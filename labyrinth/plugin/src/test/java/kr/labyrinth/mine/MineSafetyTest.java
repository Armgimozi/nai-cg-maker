package kr.labyrinth.mine;

import static org.junit.jupiter.api.Assertions.assertEquals;
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

/**
 * 광산 안전 (계약 §2.2): 광산 월드 안 플레이어는 피해 0 — DamageService·상태 이상·안전지대·PvP 규칙이 모두 같은 검사를 부른다.
 * 0.3.7: 다른 파티 플레이어가 PvP 구역에서 준 피해만 통과 ({@link MineSafety#protects(MineApi, Entity, Entity)} · {@link MineSafety#noPvp}).
 */
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

    /** 0.3.7: 광산 PvP 판정을 흉내 내는 api — pvpAllows 는 정한 값, pvpSafeAt 은 x 가 safeX 보다 작으면 안전. */
    static MineApi pvpApi(boolean allows, double safeX) {
        return new MineApi() {
            @Override public boolean enabled() { return true; }
            @Override public boolean isMineWorld(World w) { return w != null && MineNames.WORLD.equals(w.getName()); }
            @Override public void openLift(Player p) {}
            @Override public void openOffice(Player p) {}
            @Override public void openInfo(Player p) {}
            @Override public ItemStack applyPickaxe(ItemStack stack, ItemDef def) { return stack; }
            @Override public boolean pvpEnabled() { return true; }
            @Override public boolean pvpAllows(Player a, Player v) { return allows; }
            @Override public boolean pvpSafeAt(Location l) { return l.getX() < safeX; }
        };
    }

    @Test
    void onlyAllowedPlayerDamageGetsThrough() {
        World mine = fake(World.class, Map.of("getName", MineNames.WORLD));
        World over = fake(World.class, Map.of("getName", "world"));
        Player victim = fake(Player.class, Map.of("getWorld", mine));
        Player enemy = fake(Player.class, Map.of("getWorld", mine));
        Entity zombie = fake(Zombie.class, Map.of("getWorld", mine));
        Player outside = fake(Player.class, Map.of("getWorld", over));
        assertFalse(MineSafety.protects(pvpApi(true, 0), victim, enemy), "PvP 구역 · 다른 파티 = 들어감");
        assertTrue(MineSafety.protects(pvpApi(false, 0), victim, enemy), "규칙이 막으면 (같은 파티 · 안전 구역 · 꺼짐) 0");
        assertTrue(MineSafety.protects(pvpApi(true, 0), victim, null), "때린 사람 없음 (환경 · 떨어짐 · 효과) = 0");
        assertTrue(MineSafety.protects(pvpApi(true, 0), victim, zombie), "몹 = 0 (광산에는 몹이 없음)");
        assertTrue(MineSafety.protects(pvpApi(true, 0), victim, victim), "자기 자신 = 0");
        assertTrue(MineSafety.protects(api(true), victim, enemy), "기본 api (Noop 처럼 pvpAllows 거짓) = 0.3.6 처럼 0");
        assertTrue(MineSafety.protects(null, victim, enemy), "api 없음 = 0");
        assertFalse(MineSafety.protects(pvpApi(false, 0), outside, enemy), "광산 밖은 광산 규칙 아님");
        assertFalse(MineSafety.protects(api(false), victim, null), "config mine.safe: false");
        assertTrue(MineSafety.protects(new NoopMineApi(), victim, enemy), "광산이 꺼져도 이름이 같은 월드는 안전 (Noop)");
    }

    @Test
    void noPvpOnlyInsideTheMineWorld() {
        World mine = fake(World.class, Map.of("getName", MineNames.WORLD));
        World over = fake(World.class, Map.of("getName", "world"));
        MineApi a = pvpApi(true, 0);
        assertTrue(MineSafety.noPvp(a, new Location(mine, -3, 136, 0)), "안전 구역");
        assertFalse(MineSafety.noPvp(a, new Location(mine, 3, 136, 0)), "PvP 구역");
        assertFalse(MineSafety.noPvp(a, new Location(over, -3, 64, 0)), "광산 밖 = 광산 규칙 아님 (마을 안전지대는 PvpModule 이 따로)");
        assertFalse(MineSafety.noPvp(a, null));
        assertTrue(MineSafety.noPvp(null, new Location(mine, 3, 136, 0)), "api 없음 = 안전");
        assertTrue(MineSafety.noPvp(new NoopMineApi(), new Location(mine, 3, 136, 0)), "Noop (광산 꺼짐) = 0.3.6 처럼 전부 안전");
    }

    @Test
    void everyDamagePathAsksMineSafety() throws Exception {
        String dmg = Files.readString(Path.of("src/main/java/kr/labyrinth/combat/DamageService.java"));
        assertTrue(count(dmg, "MineSafety.protects(services.mine()") >= 2, "DamageService deal + applyToPlayer");
        assertTrue(dmg.contains("MineSafety.protects(services.mine(), targetPlayer, ctx.attacker())")
                && dmg.contains("MineSafety.protects(services.mine(), p, attacker)"), "0.3.7: 때린 사람을 넘김");
        String st = Files.readString(Path.of("src/main/java/kr/labyrinth/classes/LabyrinthStatusEffectService.java"));
        assertTrue(count(st, "MineSafety.protects(services.mine(), target, source)") >= 3, "상태 이상 apply · 지속 피해 · 서리 (건 사람을 넘김)");
        String pvp = Files.readString(Path.of("src/main/java/kr/labyrinth/pvp/PvpModule.java"));
        assertTrue(pvp.contains("MineSafety.inMine(services.mine(), l)") && pvp.contains("MineSafety.noPvp(services.mine(), l)"),
                "안전지대 = 광산 안전 구역");
        assertTrue(pvp.contains("config.enabled() && (!mine || services.mine().pvpEnabled())"), "광산 PvP 규칙 = pvp.enabled && mine.pvp");
        String filter = Files.readString(Path.of("src/main/java/kr/labyrinth/pvp/DefaultTargetFilter.java"));
        assertTrue(filter.contains("MineSafety.inMine(services.mine(), location)"), "TargetFilter.inSafeZone");
        String listener = Files.readString(Path.of("src/main/java/kr/labyrinth/mine/MineListener.java"));
        assertTrue(listener.contains("onDamageEarly") && listener.contains("onDamageLate") && listener.contains("onCombust"), "바닐라 피해·불");
        assertEquals(2, count(listener, "!module.pvp().allowVanilla(e)) e.setCancelled(true)"), "바닐라 피해 문 둘 다 PvP 만 통과");
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
