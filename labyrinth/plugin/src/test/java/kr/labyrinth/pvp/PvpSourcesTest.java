package kr.labyrinth.pvp;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.lang.reflect.Proxy;
import java.util.Map;
import org.bukkit.entity.AreaEffectCloud;
import org.bukkit.entity.Arrow;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LightningStrike;
import org.bukkit.entity.Player;
import org.bukkit.entity.Skeleton;
import org.bukkit.entity.Snowball;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.Zombie;
import org.junit.jupiter.api.Test;

/** 책임 플레이어 찾기 (쏜 사람·불붙인 사람·구름 주인·번개 주인). 서버 없이 인터페이스 가짜로. */
class PvpSourcesTest {

    /** 정해 둔 메서드만 답하는 가짜 엔티티 (나머지는 null/false/0). */
    @SuppressWarnings("unchecked")
    static <T> T fake(Class<T> type, Map<String, Object> answers) {
        return (T) Proxy.newProxyInstance(PvpSourcesTest.class.getClassLoader(), new Class<?>[] {type}, (proxy, m, args) -> {
            switch (m.getName()) {
                case "equals": return proxy == args[0];
                case "hashCode": return System.identityHashCode(proxy);
                case "toString": return type.getSimpleName();
                default:
                    if (answers.containsKey(m.getName())) return answers.get(m.getName());
                    Class<?> r = m.getReturnType();
                    if (r == boolean.class) return false;
                    if (r == int.class || r == long.class || r == short.class || r == byte.class) return 0;
                    if (r == double.class) return 0.0;
                    if (r == float.class) return 0f;
                    return null;
            }
        });
    }

    @Test
    void directAndProjectileAndExplosives() {
        Player p = fake(Player.class, Map.of());
        Skeleton skel = fake(Skeleton.class, Map.of());
        assertSame(p, PvpSources.playerBehind(p, null), "근접 = 때린 사람");
        assertSame(p, PvpSources.playerBehind(fake(Arrow.class, Map.of("getShooter", p)), null), "화살 = 쏜 사람");
        assertSame(p, PvpSources.playerBehind(fake(Snowball.class, Map.of("getShooter", p)), null), "눈덩이");
        assertNull(PvpSources.playerBehind(fake(Arrow.class, Map.of("getShooter", skel)), null), "스켈레톤 화살");
        assertSame(p, PvpSources.playerBehind(fake(TNTPrimed.class, Map.of("getSource", p)), null), "TNT = 불붙인 사람");
        assertNull(PvpSources.playerBehind(fake(TNTPrimed.class, Map.of()), null), "주인 없는 TNT = 환경");
        assertSame(p, PvpSources.playerBehind(fake(AreaEffectCloud.class, Map.of("getSource", p)), null), "잔류 물약 구름");
        assertSame(p, PvpSources.playerBehind(fake(LightningStrike.class, Map.of("getCausingPlayer", p)), null), "집전 번개");
        assertNull(PvpSources.playerBehind(fake(Zombie.class, Map.of()), null), "몹");
        assertNull(PvpSources.playerBehind(null, null));
    }

    @Test
    void causingEntityFromDamageSource() {
        Player p = fake(Player.class, Map.of());
        Entity crystal = fake(org.bukkit.entity.EnderCrystal.class, Map.of());
        org.bukkit.damage.DamageSource src = fake(org.bukkit.damage.DamageSource.class, Map.of("getCausingEntity", p));
        assertSame(p, PvpSources.playerBehind(crystal, src), "엔드 수정 폭발 = 깨뜨린 사람 (바닐라 피해 원인)");
    }
}
