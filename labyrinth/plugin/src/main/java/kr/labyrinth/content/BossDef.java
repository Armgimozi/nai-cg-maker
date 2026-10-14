package kr.labyrinth.content;

import java.util.List;
import java.util.Map;

/** bosses.yml 의 층 보스. 패턴 로직은 bosses/impl, 여기에는 수치·이름·모델. */
public record BossDef(
        String id,
        String name,
        int floor,
        String title,
        String core,
        String description,
        String base,
        double scale,
        double hp,
        double damage,
        double defense,
        double speed,
        List<Double> phases,
        double xp,
        IntRange gold,
        String drops,
        String bossbar,
        Params arena,
        Map<String, String> lines,
        Map<Integer, List<String>> rotation,
        Map<String, Params> patterns,
        Params sounds,
        ModelDef model,
        boolean flying,
        Params raw) {

    public Params pattern(String key) { return patterns.getOrDefault(key, Params.EMPTY); }

    /** HP 비율(0~1)에 해당하는 페이즈 번호(1부터). phases = [1.0, 0.6, 0.25] → 0.5 이면 2. */
    public int phaseAt(double hpRatio) {
        int phase = 1;
        for (int i = 0; i < phases.size(); i++) {
            if (hpRatio <= phases.get(i) + 1e-9) phase = i + 1;
        }
        return Math.max(1, phase);
    }

    public String line(String key) { return lines.get(key); }
}
