package kr.labyrinth.combat;

import java.util.UUID;

/**
 * 플레이어 한 명의 기본 공격 시계 (0.3.5, 순수 — 단위 테스트 대상). 게이지 대신 서버가 무기 간격을 지킨다 (combat_spec §2).
 * <ul>
 *   <li>{@link #click}: 다음 공격 가능 시각 − 허용 오차(50ms) 이후면 {@link Result#ACCEPT} (온전한 피해). 다음 시각 =
 *       (아직 안 된 시각이었으면 그 시각, 아니면 지금) + 간격 — 틱(50ms) 반올림으로 속도가 새지 않는다.</li>
 *   <li>너무 이르면 막는다. 남은 시간이 기억창(0.35초, 간격이 더 짧으면 간격) 안이면 {@link Result#BUFFER} — 그 대상을 한 번 기억했다가
 *       시각이 되면 넣는다(새 클릭이 오면 대상만 바꿈). 더 이르면 {@link Result#EARLY}.</li>
 *   <li>기억한 클릭을 넣으면 다음 시각 = 그 시각 + 간격.</li>
 *   <li>무기를 바꾸면 다음 시각 = max(다음 시각, 지금 + 새 간격 × 0.5), 기억한 클릭은 지운다.</li>
 *   <li>활도 같은 시계를 쓴다 — 한 주기(당김 + 0.15초)에 화살 한 발이나 근접 한 대 중 하나만. 당긴 시간은 '다음 시각 − 끝까지 당기는 시간'
 *       뒤부터만 친다 ({@link #bowDrawnMs}: 쏜 뒤·근접 뒤에는 다시 메기기 0.15초 뒤부터). 쏘면 다음 시각 = max(다음 시각, 쏜 시각 + 한 발 주기)
 *       ({@link #shot}).</li>
 * </ul>
 * 시간은 모두 ms. 스레드 안전하지 않다 (메인 스레드에서만).
 */
public final class AttackTiming {

    public enum Result { ACCEPT, BUFFER, EARLY }

    private long nextReady = Long.MIN_VALUE / 4;
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
        nextReady = base + Math.max(1, intervalMs);
        clearBuffer();
    }

    /** 기억한 클릭을 조용히 버린다 (대상이 죽음·멀어짐·무기 바뀜 등). */
    public void clearBuffer() {
        bufferedTarget = null;
        bufferedWeapon = null;
        bufferedAt = 0;
    }

    /** 손에 든 무기가 바뀜: 다음 시각 = max(다음 시각, 지금 + 새 간격 × fraction), 기억 지움. */
    public void swap(long now, long newIntervalMs, double fraction) {
        nextReady = Math.max(nextReady, now + Math.round(Math.max(0, newIntervalMs) * Math.max(0, fraction)));
        clearBuffer();
    }

    /**
     * 활: 서버가 인정하는 당긴 시간 (ms) = min(바닐라가 잰 당긴 시간, 지금 − (다음 시각 − 끝까지 당기는 시간)). 끝까지 당긴 화살이 다음 시각보다
     * 먼저 나가지 않는다 — 쏜 직후나 근접 직후에는 다시 메기기(한 발 주기 − 당김 = 0.15초) 뒤부터 세기가 0 에서 찬다. 허용 오차(toleranceMs)만큼
     * 일찍 당긴 것은 쳐 주고, 빌린 몫은 {@link #shot} 이 다음 시각에서 갚는다.
     */
    public long bowDrawnMs(long now, long usedMs, long fullDrawMs, long toleranceMs) {
        long since = now - (nextReady - Math.max(0, fullDrawMs)) + Math.max(0, toleranceMs);
        return Math.max(0, Math.min(Math.max(0, usedMs), since));
    }

    /**
     * 화살 한 발을 쐈다: 다음 시각 = max(다음 시각, 쏜 시각 + 한 발 주기(cycleMs = 당김 + 0.15초)) — 근접도 다음 당김도 이 시각을 기다린다.
     * 허용 오차로 빌려 끝까지 당겼으면 '쏜 시각' = 원래 끝까지 당겨질 시각 (근접의 허용 오차처럼 빨라지지 않는다). 기억한 근접 클릭은 지운다.
     */
    public void shot(long now, long usedMs, long fullDrawMs, long toleranceMs, long cycleMs) {
        long full = Math.max(0, fullDrawMs);
        long strict = Math.min(bowDrawnMs(now, usedMs, full, 0), full);
        long loose = Math.min(bowDrawnMs(now, usedMs, full, toleranceMs), full);
        long at = loose > strict ? Math.max(now, nextReady - full + loose) : now;
        nextReady = Math.max(nextReady, at + Math.max(1, cycleMs));
        clearBuffer();
    }

    /** 너무 이른 클릭의 '휙' 소리를 낼지 (minGapMs 에 한 번까지). */
    public boolean whoosh(long now, long minGapMs) {
        if (now - lastWhoosh < minGapMs) return false;
        lastWhoosh = now;
        return true;
    }

    public long nextReady() { return nextReady; }
}
