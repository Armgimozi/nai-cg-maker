package kr.augsky.vfx;

/** 스킬 하나만의 전용 연출. 기본 연출 위에 덧붙이거나(on), 기본 연출을 대신한다(replaces) */
public interface Signature {
    default void cast(CastFx fx) {}

    default boolean replaces(Class<? extends Ev> kind) {
        return false;
    }

    default Track on(CastFx fx, Ev ev) {
        return Track.NOOP;
    }

    /** 몬스터 스킬: 판정 없는 단계 변화인지 (바닥 고리 대신 세로로 솟는 연출을 쓴다) */
    default boolean harmless() {
        return false;
    }

    Signature NONE = new Signature() {};
}
