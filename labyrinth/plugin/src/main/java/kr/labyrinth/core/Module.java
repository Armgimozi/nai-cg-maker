package kr.labyrinth.core;

/**
 * 플러그인 기능 단위. {@code LabyrinthPlugin} 이 등록 순서대로 enable, 역순으로 disable 한다.
 * enable 에서 예외가 나면 그 모듈만 비활성으로 로그를 남기고 나머지는 계속 켠다.
 */
public interface Module {

    /** 로그용 이름 (예: "items"). */
    String name();

    void enable() throws Exception;

    default void disable() throws Exception {}

    /** {@code /labadmin reload} 후 (설정·콘텐츠가 바뀐 다음) 호출된다. */
    default void reload() throws Exception {}
}
