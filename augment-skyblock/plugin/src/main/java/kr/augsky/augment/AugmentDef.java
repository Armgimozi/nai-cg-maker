package kr.augsky.augment;

import kr.augsky.util.P;
import org.bukkit.Material;

import java.util.List;

public record AugmentDef(
        String id,
        Tier tier,
        String name,
        Material icon,
        List<String> description,
        int maxStacks,
        int weight,
        List<Effect> effects
) {
    /** 증강 효과 한 줄. type 이 효과 종류, p 가 수치들. */
    public record Effect(String type, P p) {}
}
