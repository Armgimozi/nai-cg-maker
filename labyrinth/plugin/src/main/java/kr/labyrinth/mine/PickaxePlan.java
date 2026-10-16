package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import java.util.function.ToDoubleFunction;
import kr.labyrinth.content.MineDef;
import kr.labyrinth.content.ToolSpec;

/**
 * 곡괭이 구성요소 계획 (순수 — {@code MinePickaxes} 가 이대로 아이템에 쓴다, 계약 §2.6).
 * <ul>
 *   <li>Tool 규칙: 캘 수 있는 광석·보석 블록마다 speed = {@link MineMath#toolSpeed}(단단함, 초), correct_for_drops = TRUE.
 *       그 밖의 블록 = 맨손 빠르기 1.0, 블록마다 내구 0.</li>
 *   <li>CAN_BREAK (어드벤처에서 부술 수 있는 것) = 같은 블록들 (tier ≤ 곡괭이 tier). 약한 곡괭이는 센 광석에 금도 안 간다.</li>
 *   <li>UNBREAKABLE · 공격 속성 비움 · TOOLTIP_DISPLAY 로 바닐라 줄(도구·부술 수 있음·파괴 불가·속성) 숨김 · 바탕 PAPER · 한 칸 1개.</li>
 * </ul>
 * 블록 설정(mine.yml block·base_seconds)이 바뀌면 {@link #signature} 가 달라져 접속 때 다시 쓴다.
 */
public record PickaxePlan(int tier, List<Rule> rules, List<String> canBreak, String signature) {

    /** 블록 키(minecraft:…) · speed · 그 블록의 광석·보석 id · 초. */
    public record Rule(String block, float speed, String node, double seconds) {}

    public static final String BASE_MATERIAL = "minecraft:paper";
    public static final boolean UNBREAKABLE = true;
    public static final float DEFAULT_SPEED = 1.0f;
    public static final int DAMAGE_PER_BLOCK = 0;

    /**
     * @param hardness 블록 키 → 바닐라 단단함 (서버: Material#getHardness, 시험: 표)
     * @return 곡괭이가 아니면 null
     */
    public static PickaxePlan of(ToolSpec tool, MineDef mine, ToDoubleFunction<String> hardness) {
        if (tool == null || !tool.isPickaxe() || mine == null) return null;
        List<Rule> rules = new ArrayList<>();
        List<MineDef.Node> nodes = new ArrayList<>(mine.ores().values());
        nodes.addAll(mine.gems().values());
        for (MineDef.Node n : nodes) {
            if (!tool.canMine(n.tier()) || n.block() == null || n.block().isBlank()) continue;
            double secs = MineMath.seconds(n, tool);
            float speed = MineMath.toolSpeed(hardness.applyAsDouble(n.block()), secs);
            if (speed <= 0) continue;
            rules.add(new Rule(n.block(), speed, n.id(), secs));
        }
        List<String> can = new ArrayList<>();
        for (Rule r : rules) can.add(r.block());
        StringBuilder sig = new StringBuilder("v1|t").append(tool.tier());
        for (Rule r : rules) sig.append('|').append(r.block()).append('=').append(String.format(java.util.Locale.ROOT, "%.4f", r.speed()));
        return new PickaxePlan(tool.tier(), List.copyOf(rules), List.copyOf(can), Integer.toHexString(sig.toString().hashCode()));
    }
}
