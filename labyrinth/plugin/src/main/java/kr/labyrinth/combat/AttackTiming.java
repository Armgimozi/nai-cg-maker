package kr.labyrinth.combat;

import java.util.UUID;

/**
 * 플레이어 한 명의 기본 공격 시계 (0.3.5 · 0.3.6.1, 순수 — 단위 테스트 대상). 게이지 대신 서버가 무기 간격을 지킨다 (combat_spec §2).
 * <ul>
 *   <li>{@link #click}: 다음 공격 가능 시각 − 허용 오차(50ms) 이후면 {@link Result#ACCEPT} (온전한 피해). 다음 시각 =
 *       (아직 안 된 시각이었으면 그 시각, 아니면 지금) + 간격 — 틱(50ms) 반올림으로 속도가 새지 않는다.</li>
 *   <li>너무 이르면 막는다. 남은 시간이 기억창(0.35초, 간격이 더 짧으면 간격) 안이면 {@link Result#BUFFER} — 그 대상을 한 번 기억했다가
 *       시각이 되면 넣는다(새 클릭이 오면 대상만 바꿈). 더 이르면 {@link Result#EARLY}. 대상 {@link #AIR} = 시전 무기의 허공 클릭(마법탄).</li>
 *   <li>기억한 클릭을 넣으면 다음 시각 = 그 시각 + 간격.</li>
 *   <li>무기를 바꾸면 새 무기의 첫 공격 = 지금 + 새 주기 × 0.5 뒤부터 ({@link #swap}), 기억한 클릭은 지운다.</li>
 *   <li>활도 같은 시계를 쓴다 (0.3.6.1 규칙, 주인 결정 3) — <b>공격마다 제 시간을 쓰고 겹치지 않는다</b>:
 *       근접 한 대 = 친 뒤 그 무기 간격, 화살 한 발 = 쏘기 전 끝까지 당기는 시간 + 쏜 뒤 다시 메기기 0.15초.
 *       {@link #nextReady} = 다음 근접이 되는 시각 = 활 당김을 세기 시작하는 시각 ({@link #bowDrawnMs}). 쏘면 다음 시각 = 쏜 시각 + 0.15초
 *       ({@link #shot}). 그래서 활만 쓰면 예전과 똑같이 한 발 주기(당김 + 0.15초)마다 한 발이고, 쏜 직후 단도로 바꾸면
 *       max(0.15초, 단도 간격 × 0.5) ≈ 0.2초 뒤에 찌른다. 대신 근접 한 대 뒤의 당김은 그 무기 간격이 끝난 뒤부터 찬다.</li>
 *   <li>번갈아 쓰기 증명: 화살 한 발과 근접 한 대를 번갈아 쓰면 한 바퀴 ≥ 당김 + max(0.15초, 바꿈 대기) + 근접 간격 ≥ 활 한 발 주기 + 근접 간격.
 *       한 바퀴 피해 = 화살 + 근접이므로 초당 피해 = (D활 + D근접) ÷ (T활 + T근접) — 두 무기 초당 피해의 가중 평균이라
 *       더 센 무기 하나만 쓴 것을 넘지 못한다 ({@code BowSwapRuleTest}).</li>
 * </ul>
 * 시간은 모두 ms. 스레드 안전하지 않다 (메인 스레드에서만).
 */
public final class AttackTiming {

    public enum Result { ACCEPT, BUFFER, EARLY }

    /**
     * 기억할 대상이 '허공' (0.3.6.1 시전 무기 마법탄 — 몹이 아니라 조준선으로 쏘는 클릭). 시각이 되면 그때 바라보는 쪽으로 나간다.
     */
    public static final UUID AIR = new UUID(0L, 0L);

    private long nextReady = Long.MIN_VALUE / 4;
    /** 마지막으로 통과한 근접·마법탄의 시각 (그 공격의 시계 시각) — 같은 종류 아이템으로 바꿀 때 바닐라 게이지와 맞춘다 ({@link #swapSameItem}). */
    private long lastAttack = Long.MIN_VALUE / 4;
    private UUID bufferedTarget;
    private long bufferedAt;
    private String bufferedWeapon;
    private long lastWhoosh = Long.MIN_VALUE / 4;

    /**
     * 공격 클릭 하나.
     * @param intervalMs  지금 실제 간격 (민첩·공속 반영, 하한 적용 뒤)
     * @param toleranceMs 이만큼 이른 클릭은 그냥 통과 (지연 보정)
     * @param bufferMs    기억창 (0 = 끔)
     * @param weaponKey   손에 든 무기 표시 (기억한 클릭을 넣을 때 같은 무기인지 본다)
     */
    public Result click(long now, long intervalMs, long toleranceMs, long bufferMs, UUID target, String weaponKey) {
        if (now >= nextReady - Math.max(0, toleranceMs)) {
            long base = nextReady > now ? nextReady : now;
            lastAttack = base;
            nextReady = base + Math.max(1, intervalMs);
            clearBuffer();
            return Result.ACCEPT;
        }
        long remaining = nextReady - now;
        long window = Math.min(bufferMs, intervalMs);
        if (bufferMs > 0 && remaining <= window) {
            bufferedTarget = target;
            bufferedAt = now;
            bufferedWeapon = weaponKey;
            return Result.BUFFER;
        }
        return Result.EARLY;
    }

    public boolean hasBuffer() { return bufferedTarget != null; }

    /** 기억한 클릭을 넣을 시각이 되었는가. */
    public boolean bufferReady(long now) { return bufferedTarget != null && now >= nextReady; }

    public UUID bufferedTarget() { return bufferedTarget; }

    public long bufferedAt() { return bufferedAt; }

    public String bufferedWeapon() { return bufferedWeapon; }

    /** 기억한 클릭이 너무 오래되었는가 (클릭한 지 maxAgeMs 넘음). */
    public boolean bufferExpired(long now, long maxAgeMs) { return bufferedTarget != null && now - bufferedAt > maxAgeMs; }

    /** 기억한 클릭을 넣었다: 다음 시각 = 그 시각 + 간격 (서버가 늦은 틱이면 지금 − 허용 오차 기준). */
    public void fireBuffered(long now, long intervalMs, long toleranceMs) {
        long base = Math.max(nextReady, now - Math.max(0, toleranceMs));
        lastAttack = base;
        nextReady = base + Math.max(1, intervalMs);
        clearBuffer();
    }

    /**
     * 같은 종류 아이템끼리 바꿈 (0.3.7.1 — 미궁 근접·시전 무기는 모두 종이 아이템): 바닐라 게이지는 이때 처음부터 다시 차지 않고
     * '마지막 공격 뒤 지난 시간 ÷ 새 간격' 으로 보인다. 서버도 같게 — 다음 시각 = 마지막 공격 + 새 간격 (기억 지움). 게이지가 꽉 찬 클릭을
     * 서버가 버리지 않는다. 번갈아 써도 한 번 친 뒤 그 무기 간격을 다 기다리므로 두 무기 중 센 쪽보다 빨라지지 않는다.
     */
    public void swapSameItem(long newIntervalMs) {
        if (lastAttack > Long.MIN_VALUE / 4) nextReady = lastAttack + Math.max(1, newIntervalMs);
        clearBuffer();
    }

    /** 기억한 클릭을 조용히 버린다 (대상이 죽음·멀어짐·무기 바뀜 등). */
    public void clearBuffer() {
        bufferedTarget = null;
        bufferedWeapon = null;
        bufferedAt = 0;
    }

    /** 손에 든 무기가 바뀜 (근접·시전 무기): 다음 시각 = max(다음 시각, 지금 + 새 주기 × fraction), 기억 지움. */
    public void swap(long now, long newCycleMs, double fraction) {
        swap(now, newCycleMs, fraction, 0);
    }

    /**
     * 손에 든 무기가 바뀜: 새 무기의 첫 공격은 지금 + 새 주기 × fraction 뒤부터, 기억 지움.
     * @param leadMs 그 무기의 공격이 시계 시각보다 얼마나 늦게 나가는가 — 활 = 끝까지 당기는 시간 (화살은 당김을 세기 시작한 뒤 이만큼 지나야
     *               나간다), 근접·시전 = 0. 다음 시각 = max(다음 시각, 지금 + 새 주기 × fraction − leadMs)
     */
    public void swap(long now, long newCycleMs, double fraction, long leadMs) {
        long wait = Math.round(Math.max(0, newCycleMs) * Math.max(0, fraction)) - Math.max(0, leadMs);
        nextReady = Math.max(nextReady, now + wait);
        clearBuffer();
    }

    /**
     * 활: 서버가 인정하는 당긴 시간 (ms) = min(바닐라가 잰 당긴 시간, 지금 − 다음 시각). 당김은 다음 시각부터 센다 — 쏜 직후에는 다시 메기기
     * 0.15초 뒤부터, 근접 직후에는 그 무기 간격이 끝난 뒤부터 세기가 0 에서 찬다 (0.3.6.1: 근접의 남은 간격과 겹쳐 당기지 않는다).
     * 허용 오차(toleranceMs)만큼 일찍 센 것은 쳐 주고, 빌린 몫은 {@link #shot} 이 갚는다.
     */
    public long bowDrawnMs(long now, long usedMs, long toleranceMs) {
        long since = now - nextReady + Math.max(0, toleranceMs);
        return Math.max(0, Math.min(Math.max(0, usedMs), since));
    }

    /**
     * 화살 한 발을 쐈다: 그 화살은 [다음 시각, 다음 시각 + 인정한 당김] 을 쓰고 그 뒤 다시 메기기(nockMs = 0.15초) — 다음 시각 =
     * max(쏜 시각, 다음 시각 + 인정한 당김) + 0.15초. 다음 근접·다음 당김이 이 시각을 기다린다. 다음 화살은 거기서 다시 끝까지 당겨야 하므로
     * 활만 쓰면 한 발 주기(당김 + 0.15초)마다 한 발 (0.3.6.1 전과 같음).
     * <ul>
     *   <li>허용 오차로 빌려 끝까지 당겼으면 '쏜 시각' = 원래 끝까지 당겨질 시각 (근접의 허용 오차처럼 빨라지지 않는다).</li>
     *   <li>다음 시각 전에 놓은 화살(근접 간격 안에 덜 당겨 쏜 약한 화살)도 다시 메기기 0.15초는 시계를 민다 — 공짜 화살이 없다.</li>
     * </ul>
     * 기억한 근접 클릭은 지운다.
     */
    public void shot(long now, long usedMs, long fullDrawMs, long toleranceMs, long nockMs) {
        long full = Math.max(0, fullDrawMs);
        long credited = Math.min(bowDrawnMs(now, usedMs, toleranceMs), full); // 세기를 셀 때와 같은 값 (AttackClock.draw)
        long at = Math.max(now, nextReady + credited);
        nextReady = Math.max(nextReady, at + Math.max(1, nockMs));
        clearBuffer();
    }

    /** 너무 이른 클릭의 '휙' 소리를 낼지 (minGapMs 에 한 번까지). */
    public boolean whoosh(long now, long minGapMs) {
        if (now - lastWhoosh < minGapMs) return false;
        lastWhoosh = now;
        return true;
    }

    public long nextReady() { return nextReady; }

    /**
     * 활 당김을 막아 둘 시간 (ms, 0.3.6.1 손맛 검토 1): 지금부터 당김을 세기 시작하는 때(다음 시각 − 허용 오차, {@link #bowDrawnMs})까지.
     * 그 전에 당기면 화면의 활은 차는데 서버는 세지 않아 덜 당긴 화살이 나간다 — 근접 한 대·무기 바꿈 뒤 이만큼 활에 바닐라 재사용 대기
     * (하얀 막대, 그동안 당겨지지 않음)를 건다 ({@code AttackClock}). 그 뒤에 당기기 시작하면 화면과 서버가 같다. 0 = 바로 당겨도 다 센다.
     */
    public long drawBlockedMs(long now, long toleranceMs) {
        return Math.max(0, nextReady - Math.max(0, toleranceMs) - now);
    }
}
