package kr.labyrinth.combat;

import kr.labyrinth.content.ClassDef;

/**
 * 활 당기며 걷기 (0.3.6.1, bowfeel FIX_PLAN 안 1 · 주인 결정 1) — 순수 로직 (단위 테스트 대상).
 * <ul>
 *   <li>바닐라는 아이템을 쓰는 동안(활 당김) 걷기 입력을 ×0.2 로 줄이고 달리기를 끈다 — 아이템 구성요소 {@code use_effects}
 *       의 기본값 {@code UseEffects.DEFAULT = (can_sprint false, interact_vibrations true, speed_multiplier 0.2)}. 클라이언트가
 *       쓰고 있는 아이템에서 이 값을 읽어 제 움직임에 곱한다.</li>
 *   <li>사냥꾼(패시브 {@code keen_eye} 의 {@code draw_move})이 미궁 활을 들면 <b>어디서나</b>(미궁·야생·마을·PvP) 그 활에
 *       {@code speed_multiplier = draw_move} 를 붙인다 (달리기는 그대로 꺼짐). 다른 직업이 들면 구성요소를 지워 바닐라 0.2 로 둔다.</li>
 *   <li>값은 아이템에 붙으므로 '든 사람'을 따라가야 한다 — {@code items.EquipmentListener} 가 능력치를 다시 셀 때마다(손 칸 바꿈·양손 바꿈·
 *       손 칸 아이템 바뀜(줍기·거래·상자에서 꺼냄)·가방 닫기·전직·접속·부활·월드 이동) 손(주손·보조손)의 미궁 활을 그 사람에 맞춰 다음 틱에 고쳐 쓴다.
 *       가방·상자 속 활은 손에 들 때 고친다 (손에 없는 활은 당길 수 없어 값이 쓰이지 않는다).</li>
 * </ul>
 */
public final class BowDrawMove {

    /** 바닐라 당김 중 이동 배율 (UseEffects.DEFAULT.speedMultiplier). */
    public static final double VANILLA = 0.2;
    /** 이 배율을 주는 패시브 (사냥꾼 매의 눈). */
    public static final String PASSIVE = "keen_eye";
    /** 패시브 params 키. 0.2 = 끔. */
    public static final String PARAM = "draw_move";
    /**
     * classes.yml 에 키가 없을 때(직접 고쳐 새 기본값을 안 받은 파일) 매의 눈의 값 = jar 값. 방 시뮬(bowfeel/fix)에서 시작 활(회랑 장궁)이
     * 단검 치고 빠지기보다 방 시간 ×0.96 · 받은 피해 ×0.90 이 되는 값.
     */
    public static final double DEFAULT_HUNTER = 0.60;

    private BowDrawMove() {}

    /**
     * 원하는 당김 중 이동 배율 (0.2~1.0). 패시브가 {@link #PASSIVE} 가 아니면 {@link #VANILLA}. 어디에 있는지는 보지 않는다 (주인 결정 1 — 어디서나).
     * @param passiveId 직업 패시브 id (없으면 null)
     * @param drawMove  패시브 params 의 draw_move (없으면 NaN → {@link #DEFAULT_HUNTER})
     */
    public static double want(String passiveId, double drawMove) {
        if (!PASSIVE.equals(passiveId)) return VANILLA;
        double v = Double.isNaN(drawMove) ? DEFAULT_HUNTER : drawMove;
        return Math.max(VANILLA, Math.min(1.0, v));
    }

    /** 직업 정의에서 바로 ({@link #want(String, double)}). 직업이 없으면 바닐라. */
    public static double want(ClassDef cls) {
        if (cls == null || cls.passive() == null) return VANILLA;
        ClassDef.PassiveDef p = cls.passive();
        double v = p.params() == null ? Double.NaN : p.params().dbl(PARAM, Double.NaN);
        return want(p.id(), v);
    }

    /** 바닐라와 다른가 (= 활에 구성요소를 붙여야 하는가). */
    public static boolean custom(double want) { return Math.abs(want - VANILLA) > 1e-4; }

    /**
     * 활이 이미 원하는 상태인가.
     * @param present     활에 use_effects 구성요소가 붙어 있는가
     * @param speed       붙어 있다면 그 speed_multiplier
     * @param canSprint   붙어 있다면 그 can_sprint
     * @param want        {@link #want} 결과
     */
    public static boolean matches(boolean present, double speed, boolean canSprint, double want) {
        // 바닐라를 원할 때: 없거나, 있어도 바닐라 값이면 맞다 (지운 뒤에도 원형 값이 보이는 판에서 매 틱 다시 쓰지 않게)
        if (!custom(want)) return !present || (!canSprint && Math.abs(speed - VANILLA) <= 1e-4);
        return present && !canSprint && Math.abs(speed - want) <= 1e-4;
    }
}
