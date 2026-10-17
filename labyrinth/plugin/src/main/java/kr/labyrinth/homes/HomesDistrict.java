package kr.labyrinth.homes;

import java.util.List;
import kr.labyrinth.Services;

/**
 * 집 구역 상태 알림 (0.3.7) — 순수 자료 + 우편함. 소유: 묶음 A (더하기만).
 * <p>
 * 마을 모듈(구역 기계, 묶음 A)이 구역 기록을 읽거나 짓거나 지울 때마다 {@link #publish} 를 부른다. 마을 모듈이 집 모듈보다 먼저 켜지므로
 * 마지막 값을 {@link #current()} 에 들고 있다가 {@link HomesModule} 이 켜질 때 넘긴다.
 *
 * @param state   "none" | "building" | "built" | "removed" (구역 기록 state, 파일이 없으면 none)
 * @param buildId 구역 기록 build_id (다시 지으면 바뀜 — 주인 기록과 맞대어 봄)
 * @param site    지은 자리 (south_west · here …)
 * @param plots   지은 집터 (지어지기 전·지운 뒤엔 빈 목록)
 */
public record HomesDistrict(String state, String buildId, String site, List<PlotGeom> plots) {

    public static final HomesDistrict NONE = new HomesDistrict("none", "", "", List.of());

    private static volatile HomesDistrict current = NONE;

    public HomesDistrict {
        state = state == null ? "none" : state;
        buildId = buildId == null ? "" : buildId;
        site = site == null ? "" : site;
        plots = plots == null ? List.of() : List.copyOf(plots);
    }

    public boolean built() { return "built".equals(state); }

    /** 마지막으로 알린 상태 (아직 없으면 {@link #NONE}). */
    public static HomesDistrict current() { return current; }

    /** 마을 모듈이 부른다: 상태를 기억하고 지금 집 모듈에 넘긴다 (켜지기 전이면 기억만). */
    public static void publish(HomesDistrict d) {
        current = d == null ? NONE : d;
        try {
            Services.get().homes().districtChanged(current);
        } catch (IllegalStateException notStarted) {
            // 플러그인이 아직 안 켜짐 (시험) — 기억만
        }
    }
}
