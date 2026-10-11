package kr.souls.enemy;

/**
 * Foes.hit 의 결과 (M1 P1-0 계약). raw: 받은 원피해, def: 방어력, dealt: 깎은 가상 체력, hp: 남은 가상 체력, killed: 이 한 대로 쓰러졌다.
 * landed: 한 대가 들어갔다 (거짓이면 우리 적이 아니거나 이미 쓰러졌다: 다른 값은 0). 나중 묶음이 칸 (staggered, blocked …) 을 더할 때는
 * 만드는 곳 (Foes) 만 고치면 된다. 읽는 쪽은 이름으로 읽는다.
 */
public record HitResult(boolean landed, double raw, double def, double dealt, double hp, boolean killed) {
    /** 들어가지 않은 한 대 */
    public static final HitResult NONE = new HitResult(false, 0, 0, 0, 0, false);
}
