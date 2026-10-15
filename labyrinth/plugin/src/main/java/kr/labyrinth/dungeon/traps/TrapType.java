package kr.labyrinth.dungeon.traps;

import java.util.Locale;

/**
 * 함정 종류 (floors.yml {@code traps.types} 의 닫힌 목록, GDD §5.5). id = yml 이름.
 * <ul>
 *   <li>trigger: STEP = 밟으면 경고 시간 뒤 발동 · PERIODIC = 일정 박자로 계속 (틈에 지나가기)</li>
 *   <li>shape: LINE = 복도를 가로지르는 한 줄(1~3칸) · WALL = 한 줄 + 양옆 벽에 발사구 · PIT = 두 줄(바닥이 꺼짐) · SAW = 2~3칸 줄(톱날이 오감)</li>
 *   <li>basePct = 최대 HP 비율 TRUE 피해 기준 (층·난이도 배율 전, 파티 인원 무관 — {@link TrapMath#pct})</li>
 *   <li>telegraph = 밟은 뒤 발동까지 틱 (난이도 telegraph 배율 전), cooldown = 발동 뒤 다시 장전까지 틱 (0 = 한 번만)</li>
 * </ul>
 */
public enum TrapType {
    SPIKE("spike", "가시 발판", Trigger.STEP, Shape.LINE, 0.12, 8, 70),
    ARROW_WALL("arrow_wall", "화살 벽", Trigger.STEP, Shape.WALL, 0.10, 6, 80),
    FLAME_JET("flame_jet", "화염 분사구", Trigger.PERIODIC, Shape.LINE, 0.07, 16, 0),
    FALLING_ROCK("falling_rock", "낙석", Trigger.STEP, Shape.LINE, 0.16, 20, 160),
    POISON_GAS("poison_gas", "독 안개", Trigger.STEP, Shape.LINE, 0.03, 4, 180),
    PITFALL("pitfall", "함정 구덩이", Trigger.STEP, Shape.PIT, 0.10, 8, 60),
    ALARM_RUNE("alarm_rune", "경보 룬", Trigger.STEP, Shape.LINE, 0.0, 12, 0),
    CURRENT("current", "물살", Trigger.STEP, Shape.LINE, 0.05, 4, 40),
    ICE_SLIDE("ice_slide", "얼음 미끄럼", Trigger.STEP, Shape.LINE, 0.06, 2, 40),
    CRYSTAL_BEAM("crystal_beam", "수정 광선", Trigger.PERIODIC, Shape.WALL, 0.08, 16, 0),
    INK_BURST("ink_burst", "먹물 분출", Trigger.STEP, Shape.LINE, 0.05, 6, 100),
    SAW_BLADE("saw_blade", "회전 톱날", Trigger.PERIODIC, Shape.SAW, 0.08, 0, 0),
    VOID_RIFT("void_rift", "공허 균열", Trigger.STEP, Shape.LINE, 0.09, 10, 120);

    public enum Trigger { STEP, PERIODIC }

    public enum Shape { LINE, WALL, PIT, SAW }

    private final String id;
    private final String displayName;
    private final Trigger trigger;
    private final Shape shape;
    private final double basePct;
    private final int telegraph;
    private final int cooldown;

    TrapType(String id, String displayName, Trigger trigger, Shape shape, double basePct, int telegraph, int cooldown) {
        this.id = id;
        this.displayName = displayName;
        this.trigger = trigger;
        this.shape = shape;
        this.basePct = basePct;
        this.telegraph = telegraph;
        this.cooldown = cooldown;
    }

    public String id() { return id; }
    public String displayName() { return displayName; }
    public Trigger trigger() { return trigger; }
    public Shape shape() { return shape; }
    public double basePct() { return basePct; }
    public int telegraph() { return telegraph; }
    public int cooldown() { return cooldown; }
    public boolean periodic() { return trigger == Trigger.PERIODIC; }

    /** yml id → 종류 (없으면 null). */
    public static TrapType byId(String id) {
        if (id == null) return null;
        String k = id.trim().toLowerCase(Locale.ROOT);
        for (TrapType t : values()) if (t.id.equals(k)) return t;
        return null;
    }
}
