package kr.labyrinth.dungeon.treasure;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.content.Content;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.content.IntRange;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;

/**
 * 미믹 몹 고르기·층 수치 (순수 — 단위 테스트 대상, GDD §5.6). mobs.yml 의 {@code mimic:} 블록이 있는 몹이 미믹이다:
 * <pre>
 *   mimic: {floors: [처음, 끝], hp, damage, defense, xp, gold, companion}
 * </pre>
 * 층 수치 = 그 층 일반 몹(floors.yml {@code mobs}) 평균 × 배율. 공격 간격도 그 층 일반 몹 평균(1층 1.5초 · 2층 1.35초)을 따른다.
 * 난이도·인원·솔로 배율은 다른 몹처럼 소환할 때(InstanceContext) 그 위에 곱한다. floors 가 없는 미믹(새끼 미믹)은 큰 미믹으로 나오지 않고
 * {@code companion} 으로만 나온다. mobs.yml 에 미믹이 하나도 없으면(직접 고친 옛 판) {@link #forFloor} 가 null → 예전처럼 층 일반 몹이 기습.
 */
public final class MimicSpec {

    private MimicSpec() {}

    /** 이 몹이 미믹인가 (mobs.yml {@code mimic:} 블록). */
    public static boolean isMimic(MobDef d) {
        return d != null && d.raw() != null && !d.raw().sub("mimic").isEmpty();
    }

    /** mimic.floors = [처음, 끝] (없으면 null). */
    public static int[] floors(MobDef d) {
        if (!isMimic(d)) return null;
        List<Double> f = d.raw().sub("mimic").doubles("floors");
        if (f.isEmpty()) return null;
        int a = (int) Math.round(f.get(0)), b = (int) Math.round(f.size() > 1 ? f.get(1) : f.get(0));
        return new int[] {Math.min(a, b), Math.max(a, b)};
    }

    /**
     * 이 층의 큰 미믹 — floors 가 이 층을 품는 첫 미믹(YAML 순서). 품는 것이 없으면 floors 가 가장 가까운 미믹, 미믹이 없으면 null.
     */
    public static MobDef forFloor(Content c, int floor) {
        if (c == null) return null;
        MobDef best = null;
        int bestGap = Integer.MAX_VALUE;
        for (MobDef d : c.mobs().values()) {
            int[] r = floors(d);
            if (r == null) continue;
            int gap = floor < r[0] ? r[0] - floor : floor > r[1] ? floor - r[1] : 0;
            if (gap < bestGap) {
                best = d;
                bestGap = gap;
            }
        }
        return best;
    }

    /** 함께 튀어나오는 작은 미믹 (mimic.companion, 없거나 없는 몹이면 null). */
    public static MobDef companion(Content c, MobDef main) {
        if (c == null || !isMimic(main)) return null;
        MobDef d = c.mob(main.raw().sub("mimic").str("companion"));
        return d == null || d == main ? null : d;
    }

    /** 그 층 일반 몹 정의 (floors.yml mobs, 없는 id 는 건너뜀). */
    public static List<MobDef> floorMobs(Content c, int floor) {
        List<MobDef> out = new ArrayList<>();
        FloorDef f = c == null ? null : c.floor(floor);
        if (f == null) return out;
        for (String id : f.mobs()) {
            MobDef m = c.mob(id);
            if (m != null && !isMimic(m)) out.add(m);
        }
        return out;
    }

    /**
     * 층에 맞춘 사본: hp·damage·defense·xp·gold = 층 일반 몹 평균 × mimic 배율, 공격 간격 = 층 일반 몹 평균(0.05초 단위),
     * floor = 그 층. 층 몹이 없으면 YAML 값 그대로(floor 만 바꿈). 모델·스킬·이름·id 는 그대로라 리소스팩 모델을 같이 쓴다.
     */
    public static MobDef scaled(MobDef mimic, List<MobDef> floorMobs, int floor) {
        Params k = mimic.raw() == null ? Params.EMPTY : mimic.raw().sub("mimic");
        double hp = mimic.hp(), dmg = mimic.damage(), def = mimic.defense(), xp = mimic.xp();
        IntRange gold = mimic.gold();
        Map<String, Object> raw = new LinkedHashMap<>(mimic.raw() == null ? Map.of() : mimic.raw().asMap());
        if (floorMobs != null && !floorMobs.isEmpty()) {
            double sh = 0, sd = 0, sf = 0, sx = 0, gmin = 0, gmax = 0, ai = 0;
            for (MobDef m : floorMobs) {
                sh += m.hp();
                sd += m.damage();
                sf += m.defense();
                sx += m.xp();
                gmin += m.gold() == null ? 0 : m.gold().min();
                gmax += m.gold() == null ? 0 : m.gold().max();
                ai += m.raw() == null ? 1.2 : m.raw().dbl("attack_interval", 1.2);
            }
            int n = floorMobs.size();
            hp = Math.max(1, Math.round(sh / n * k.dbl("hp", 4.0)));
            dmg = round1(sd / n * k.dbl("damage", 1.3));
            def = round1(sf / n * k.dbl("defense", 1.0));
            xp = Math.round(sx / n * k.dbl("xp", 3.0));
            double g = k.dbl("gold", 3.0);
            gold = new IntRange((int) Math.round(gmin / n * g), (int) Math.round(gmax / n * g));
            raw.put("attack_interval", Math.round(ai / n * 20) / 20.0);
        }
        return new MobDef(mimic.id(), mimic.name(), mimic.description(), floor, mimic.rank(), mimic.base(), mimic.scale(),
                hp, dmg, def, mimic.speed(), xp, gold, mimic.ai(), mimic.skills(), mimic.drops(), mimic.flying(),
                mimic.sounds(), mimic.model(), Params.of(raw));
    }

    /** 이 층에 나올 미믹 무리 (큰 미믹 + 있으면 작은 미믹 하나), 층 수치 적용. 미믹이 없으면 빈 목록. */
    public static List<MobDef> pack(Content c, int floor) {
        List<MobDef> out = new ArrayList<>();
        MobDef main = forFloor(c, floor);
        if (main == null) return out;
        List<MobDef> fm = floorMobs(c, floor);
        out.add(scaled(main, fm, floor));
        MobDef comp = companion(c, main);
        if (comp != null) out.add(scaled(comp, fm, floor));
        return out;
    }

    private static double round1(double v) { return Math.round(v * 10) / 10.0; }
}
