package kr.augsky.weapon;

import kr.augsky.skill.HitEffect;
import kr.augsky.util.P;
import org.bukkit.Material;

import java.util.List;

public record WeaponDef(
        String id,
        String name,
        String pool,
        String source,
        String type,
        String element,
        double damage,
        double speed,
        double reach,
        double skillPower,
        Material material,
        String skill,
        String skill2,
        double passiveChance,
        String passiveDesc,
        List<HitEffect> passive,
        List<String> lore,
        P recipe,
        boolean droppable
) {
    public static String typeName(String type) {
        return switch (type) {
            case "sword" -> "검";
            case "greatsword" -> "대검";
            case "dagger" -> "단검";
            case "katana" -> "카타나";
            case "axe" -> "도끼";
            case "hammer" -> "망치";
            case "spear" -> "창";
            case "scythe" -> "낫";
            case "staff" -> "지팡이";
            case "wand" -> "마법봉";
            default -> type;
        };
    }
}
