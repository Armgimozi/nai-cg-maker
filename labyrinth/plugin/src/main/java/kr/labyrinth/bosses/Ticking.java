package kr.labyrinth.bosses;

/**
 * 보스가 소유하는 진행형 효과(경고 장판·투사체·표식·테더·지연 실행·잔류 장판). {@link Boss} 의 틱 루프 하나가 전부 돌린다 →
 * BukkitTask 가 흩어지지 않고, 페이즈 전환·보스 종료 때 한 번에 정리된다.
 */
public interface Ticking {

    /** 한 틱 진행. @return true = 끝났다(목록에서 제거) */
    boolean tick(long now);

    /** 강제 종료 (디스플레이 제거, 발동 안 함). 여러 번 불려도 안전해야 한다. */
    void cancel();

    /** 페이즈 전환 시 함께 취소되는가 (GDD §8.3 — 진행 중인 경고 정리). 기본 true. */
    default boolean phaseBound() { return true; }
}
