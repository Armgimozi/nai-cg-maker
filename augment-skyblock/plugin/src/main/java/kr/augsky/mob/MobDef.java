package kr.augsky.mob;

import org.bukkit.entity.EntityType;

import java.util.List;
import java.util.Map;
import java.util.Set;

public record MobDef(
        String id,
        String name,
        EntityType type,
        double health,
        double damage,
        double speed,
        double armor,
        double scale,
        double knockbackResistance,
        double followRange,
        double skillPower,
        boolean boss,
        String bossColor,
        boolean burnInDay,
        boolean glowing,
        boolean baby,
        int size,
        Map<String, String> equipment,
        List<Potion> effects,
        List<Ability> abilities,
        List<Drop> drops,
        int xp,
        boolean vanillaDrops,
        Natural natural
) {
    public record Potion(String effect, int amplifier) {}

    public record Ability(String skill, String trigger, double cooldown, double range, double chance, double threshold) {}

    public record Drop(String item, int min, int max, double chance) {}

    /** nether: 하늘 네더에서도 바꾼다 (아니면 하늘에서만. 하늘 네더는 바닐라 네더 몹이 기본이다). */
    public record Natural(Set<EntityType> replace, double chance, Set<String> worlds, boolean nether) {}

    public record Rift(String id, String name, List<String> mobs, int maxAlive, double interval, double radius,
                       String boss) {}
}
