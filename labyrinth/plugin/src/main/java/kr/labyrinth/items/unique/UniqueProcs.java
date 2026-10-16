package kr.labyrinth.items.unique;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 고유 효과의 순수 상태·계산 (Bukkit 무관 — 단위 테스트 대상, unique_spec §7 폭주 방지 · pvp_spec §11).
 * 시각은 모두 ms 로 받는다. {@link UniqueEffectService} 가 이것 하나를 들고 이벤트마다 묻는다.
 * <ul>
 *   <li>재발동 ({@link #ready}): 효과마다 전체 · 대상마다 · 때린 쪽마다</li>
 *   <li>N번째 공격 ({@link #nth}) · 첫 타 창 ({@link #firstHit}: 이 적을 최근 window 초 동안 안 때림, 보스는 30초에 한 번)</li>
 *   <li>같은 적 기절 면역 6초 ({@link #stunReady}) · 갑옷 부수기 중첩 ({@link #addShred}/{@link #shred}, 상한 40%)</li>
 *   <li>생명 흡수 초당 상한 ({@link #leechAllowed}) · 가속 중첩 ({@link #momentum}) · '다음 공격' 장전 ({@link #arm}/{@link #consume})</li>
 *   <li>전투 중 ({@link #markCombat}/{@link #inCombat}, 수호 기운)</li>
 * </ul>
 * 플레이어 대상: 곱하기 보정·덧 피해 × {@link #PVP_SCALE}, 중첩 상한 {@link #PVP_MAX_STACKS}. 기절·빙결은 그대로(느려짐으로 바꾸지 않음 —
 * 시간은 PvP 상태이상 규칙이 줄인다).
 */
public final class UniqueProcs {

    /** 플레이어 대상의 곱하기 보정·덧 피해·반사 배율 (pvp_spec §11 '×0.5 그대로'). */
    public static final double PVP_SCALE = 0.5;
    /** 플레이어 대상 중첩 상한 (출혈·독·갑옷 부수기). */
    public static final int PVP_MAX_STACKS = 3;
    /** 같은 적은 이 시간 동안 다시 기절하지 않는다 (초, 몹·플레이어 모두). */
    public static final double STUN_IMMUNITY = 6.0;
    /** 선제: 보스는 이 간격(초)에 한 번. */
    public static final double FIRST_STRIKE_BOSS = 30.0;
    /** 마무리: 보스에게는 보너스의 이만큼. */
    public static final double BOSS_EXECUTE = 0.6;
    /** 약점 파고들기: 상태이상 2개 이상이면 보너스 × 이 값. */
    public static final double EXPLOIT_TWO = 1.6;
    /** 갑옷 부수기 방어 깎기 상한. */
    public static final double SHRED_CAP = 0.4;
    /** 기절·빙결 면역(보스)에게 대신 거는 받는 피해 증가의 시간 (초). */
    public static final double BOSS_VULN_SECONDS = 3.0;
    /** imbue 서리 5중첩 → 빙결 시간 (초). 무기 스킬·몹이 건 서리는 그대로 4초. */
    public static final double IMBUE_FREEZE = 1.0;
    /** imbue 서리 5중첩 · 보스 → 받는 피해 증가. */
    public static final double IMBUE_BOSS_VULN = 0.05;
    /** 관통: 꿰뚫을 때마다 피해 −20%. */
    public static final double PIERCE_FALLOFF = 0.2;
    /** 연쇄 번개가 튀는 거리 (주 대상 기준, 칸). */
    public static final double CHAIN_RANGE = 6.0;
    /** 과부하 폭발 대상 상한. */
    public static final int OVERCHARGE_TARGETS = 4;
    /** 시체 폭발 대상 상한 (연쇄 없음). */
    public static final int BURST_TARGETS = 8;
    /** 수호 기운: 최근 이 시간(초) 안에 피해를 주거나 받았을 때만. */
    public static final double WARD_COMBAT = 5.0;
    /** 수호 기운 대상 상한 (자신 포함). */
    public static final int WARD_TARGETS = 5;
    /** 추격: 처치 뒤 '다음 공격'을 기다리는 시간 (초). */
    public static final double BLOODRUSH_WINDOW = 10.0;
    /** 흘려치기·추격 이동 속도 버프 시간 (초). */
    public static final double COUNTERSTEP_MOVE_SECONDS = 2.0;
    /** 등 뒤 = 대상이 보는 방향 뒤쪽 이 각도. */
    public static final double BACK_CONE = 120.0;
    /** 축성: 혼자면 자신에게 이만큼. 치유력 몫. */
    public static final double SANCTIFY_SOLO = 0.5;
    public static final double SANCTIFY_HEAL_POWER = 0.3;

    // ── 순수 계산 ─────────────────────────────────────────────────────────

    /** 대상이 플레이어면 ×0.5, 아니면 1. */
    public static double pvp(boolean targetIsPlayer) { return targetIsPlayer ? PVP_SCALE : 1.0; }

    /** 중첩 상한 (플레이어 대상은 3). */
    public static int maxStacks(int cap, boolean targetIsPlayer) {
        int c = Math.max(1, cap);
        return targetIsPlayer ? Math.min(c, PVP_MAX_STACKS) : c;
    }

    /** 마무리 보너스: HP 비율 ≤ thr 이면 pct (보스 × 0.6, 플레이어 × 0.5), 아니면 0. */
    public static double executeBonus(double hpRatio, double thr, double pct, boolean boss, boolean targetIsPlayer) {
        if (hpRatio > thr + 1e-9) return 0;
        return pct * (boss ? BOSS_EXECUTE : 1.0) * pvp(targetIsPlayer);
    }

    /** 약점 파고들기 보너스: 상태이상 0개 = 0 · 1개 = pct · 2개 이상 = pct × 1.6 (플레이어 × 0.5). */
    public static double exploitBonus(int statuses, double pct, boolean targetIsPlayer) {
        if (statuses <= 0) return 0;
        return pct * (statuses >= 2 ? EXPLOIT_TWO : 1.0) * pvp(targetIsPlayer);
    }

    /** 광기 보너스: 잃은 HP 10% 마다 pct (플레이어 대상 × 0.5). */
    public static double berserkBonus(double hpRatio, double pct, boolean targetIsPlayer) {
        double missing = Math.max(0, Math.min(1, 1 - hpRatio));
        return Math.floor(missing * 10 + 1e-9) * pct * pvp(targetIsPlayer);
    }

    /**
     * 등 뒤인가: 대상이 보는 방향(fx, fz)과 대상 → 공격자(ax, az) 사이가 뒤쪽 {@link #BACK_CONE}° 안.
     * 방향이 없으면 false.
     */
    public static boolean behind(double fx, double fz, double ax, double az) {
        double fl = Math.hypot(fx, fz), al = Math.hypot(ax, az);
        if (fl < 1e-6 || al < 1e-6) return false;
        double cos = (fx * ax + fz * az) / (fl * al);
        return cos <= -Math.cos(Math.toRadians(BACK_CONE / 2.0)) + 1e-9;
    }

    /** 갑옷 부수기 방어 깎기 = 중첩 × pct (상한 40%). */
    public static double shredOf(int stacks, double pct) { return Math.min(SHRED_CAP, Math.max(0, stacks) * Math.max(0, pct)); }

    /** 기절 대신 거는 효과: 보스 = 받는 피해 증가(vulnerable), 그 밖(몹·플레이어) = 기절 그대로. */
    public static String stunEffect(boolean boss) { return boss ? "vulnerable" : "stun"; }

    /** 관통 k번째(1부터) 대상의 피해 배율. */
    public static double pierceMult(int k) { return Math.max(0, 1.0 - PIERCE_FALLOFF * k); }

    // ── 상태 ──────────────────────────────────────────────────────────────

    private final Map<String, Long> icd = new HashMap<>();
    private final Map<String, Integer> counters = new HashMap<>();
    private final Map<String, Long> lastHit = new HashMap<>();
    private final Map<UUID, Long> stunImmune = new HashMap<>();
    private final Map<UUID, Shred> shreds = new HashMap<>();
    private final Map<UUID, double[]> leech = new HashMap<>();
    private final Map<UUID, long[]> momentum = new HashMap<>();
    private final Map<String, Armed> armed = new HashMap<>();
    private final Map<UUID, Long> combat = new HashMap<>();
    private final Map<UUID, Long> nextAura = new HashMap<>();

    private static final class Shred {
        int stacks;
        double pct;
        long until;
    }

    /** '다음 공격' 장전 (추격·흘려치기·과부하). */
    public record Armed(double pct, long until) {}

    private static long ms(double seconds) { return Math.round(Math.max(0, seconds) * 1000); }

    private static String key(UUID a, String effect, UUID b) { return a + "|" + effect + "|" + (b == null ? "" : b.toString()); }

    /**
     * 재발동: 지금 켜도 되면 true 를 돌려주고 다음 시각을 잡는다. other = 대상(대상마다)·때린 쪽(가시 반격) · null = 전체.
     * seconds ≤ 0 이면 늘 true.
     */
    public boolean ready(UUID player, String effect, UUID other, double seconds, long now) {
        if (seconds <= 0) return true;
        String k = key(player, effect, other);
        Long at = icd.get(k);
        if (at != null && at > now) return false;
        icd.put(k, now + ms(seconds));
        return true;
    }

    /** N번째 공격: 기본 공격마다 하나씩 세어 n 의 배수에서 true. */
    public boolean nth(UUID player, String effect, int n) {
        int every = Math.max(1, n);
        int c = counters.merge(player + "|" + effect, 1, Integer::sum);
        if (c >= every) {
            counters.put(player + "|" + effect, 0);
            return true;
        }
        return false;
    }

    /**
     * 첫 타: 이 적을 최근 window 초 동안 안 때렸으면 true (보스는 마지막 발동에서 30초가 지났으면). 때린 시각은 매번 남긴다.
     */
    public boolean firstHit(UUID player, UUID target, boolean boss, double windowSeconds, long now) {
        String k = player + "|" + target;
        Long last = lastHit.put(k, now);
        if (boss) return ready(player, "first_strike_boss", target, FIRST_STRIKE_BOSS, now);
        return last == null || now - last >= ms(windowSeconds);
    }

    /** 같은 적 기절 면역: 지금 기절시켜도 되면 true (그리고 6초 면역 시작). */
    public boolean stunReady(UUID target, long now) {
        Long until = stunImmune.get(target);
        if (until != null && until > now) return false;
        stunImmune.put(target, now + ms(STUN_IMMUNITY));
        return true;
    }

    /** 갑옷 부수기 한 중첩 (cap = 중첩 상한, 플레이어 대상은 {@link #maxStacks} 로 줄여 넘긴다). @return 지금 중첩 */
    public int addShred(UUID target, double pct, int cap, double seconds, long now) {
        Shred s = shreds.computeIfAbsent(target, u -> new Shred());
        if (s.until <= now) {
            s.stacks = 0;
            s.pct = 0;
        }
        s.stacks = Math.min(Math.max(1, cap), s.stacks + 1);
        s.pct = Math.max(s.pct, pct);
        s.until = now + ms(seconds);
        return s.stacks;
    }

    /** 지금 대상 방어 깎기 비율 (0 ~ 0.4). */
    public double shred(UUID target, long now) {
        Shred s = shreds.get(target);
        return s == null || s.until <= now ? 0 : shredOf(s.stacks, s.pct);
    }

    public int shredStacks(UUID target, long now) {
        Shred s = shreds.get(target);
        return s == null || s.until <= now ? 0 : s.stacks;
    }

    /** 생명 흡수: 이번 1초 창에서 아직 회복할 수 있는 만큼만 돌려준다 (초당 상한 = cap). */
    public double leechAllowed(UUID player, double want, double capPerSecond, long now) {
        if (want <= 0) return 0;
        double[] w = leech.computeIfAbsent(player, u -> new double[] {now, 0});
        if (now - (long) w[0] >= 1000) {
            w[0] = now;
            w[1] = 0;
        }
        double left = Math.max(0, capPerSecond - w[1]);
        double got = Math.min(want, left);
        w[1] += got;
        return got;
    }

    /** 가속: 적중마다 +1 중첩 (상한 max). decay 초 쉬었으면 1 부터. @return 지금 중첩 */
    public int momentum(UUID player, int max, double decaySeconds, long now) {
        long[] m = momentum.computeIfAbsent(player, u -> new long[] {0, 0});
        if (now - m[1] > ms(decaySeconds)) m[0] = 0;
        m[0] = Math.min(Math.max(1, max), m[0] + 1);
        m[1] = now;
        return (int) m[0];
    }

    public void arm(UUID player, String effect, double pct, double seconds, long now) {
        armed.put(player + "|" + effect, new Armed(pct, now + ms(seconds)));
    }

    /** 장전된 '다음 공격' 보너스를 꺼낸다 (없거나 지났으면 null). */
    public Armed consume(UUID player, String effect, long now) {
        Armed a = armed.remove(player + "|" + effect);
        return a == null || a.until() <= now ? null : a;
    }

    public boolean armed(UUID player, String effect, long now) {
        Armed a = armed.get(player + "|" + effect);
        return a != null && a.until() > now;
    }

    public void markCombat(UUID player, long now) { combat.put(player, now); }

    public boolean inCombat(UUID player, double seconds, long now) {
        Long t = combat.get(player);
        return t != null && now - t <= ms(seconds);
    }

    /** 주기 기운: 이번에 켤 차례면 true (그리고 다음 차례를 period 초 뒤로). */
    public boolean auraDue(UUID player, double periodSeconds, long now) {
        Long next = nextAura.get(player);
        if (next != null && next > now) return false;
        nextAura.put(player, now + ms(periodSeconds));
        return true;
    }

    /** 나간 플레이어의 상태 지우기. */
    public void forget(UUID player) {
        String p = player + "|";
        icd.keySet().removeIf(k -> k.startsWith(p));
        counters.keySet().removeIf(k -> k.startsWith(p));
        lastHit.keySet().removeIf(k -> k.startsWith(p));
        armed.keySet().removeIf(k -> k.startsWith(p));
        leech.remove(player);
        momentum.remove(player);
        combat.remove(player);
        nextAura.remove(player);
        stunImmune.remove(player);
        shreds.remove(player);
    }

    /** 오래된 기록 정리 (몇 초마다). */
    public void prune(long now) {
        icd.values().removeIf(t -> t <= now);
        lastHit.values().removeIf(t -> now - t > 60_000);
        stunImmune.values().removeIf(t -> t <= now);
        shreds.values().removeIf(s -> s.until <= now);
        armed.values().removeIf(a -> a.until() <= now);
        combat.values().removeIf(t -> now - t > 60_000);
    }
}
