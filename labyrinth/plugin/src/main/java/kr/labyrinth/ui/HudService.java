package kr.labyrinth.ui;

import java.util.List;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import org.bukkit.entity.Player;

/**
 * HUD (액션바: HP/MP 바·레벨·골드, 사이드바: 층·남은 적·파티원 HP, 보스바). 소유: ui+titles 담당.
 * 기본 구현 {@link BasicHudService}: 텍스트 액션바 + 보스바 표시만.
 */
public interface HudService {

    /** key 로 구분되는 보스바 표시 (같은 key 면 교체). */
    void showBossBar(Player player, String key, BossBar bar);

    void hideBossBar(Player player, String key);

    /** 기본 HUD 대신 ticks 동안 이 액션바를 보여 준다 (시전 바·경고 문구 등). */
    void actionBar(Player player, Component text, int ticks);

    /** 값이 바뀌었으니 다음 틱에 다시 그리라는 힌트 (HP/MP/골드 변화). */
    void refresh(Player player);

    // ── ui+titles 담당 추가 (기본 구현은 아무것도 안 함 → 안전) ─────────────────

    /** 이름표 접두어 (칭호). HUD 구현이 개인 스코어보드 팀으로 모든 플레이어 화면에 반영한다. */
    default void nameTagPrefix(Player target, Component prefix) {}

    /**
     * 파티 대전 HUD (사이드바 + 보스바). pvp 모듈이 매치 중 1초마다(또는 값이 바뀔 때) 참가자·관전자 각자에게 보낸다.
     * {@link #clearPvpMatch} 로 끈다. 미궁 사이드바보다 우선한다.
     */
    default void pvpMatch(Player viewer, PvpHud state) {}

    /** 파티 대전 HUD 끄기 (매치 종료·이탈). */
    default void clearPvpMatch(Player viewer) {}

    /**
     * 파티 대전 HUD 상태.
     * @param phase        prep(준비) | fight(전투) | sudden_death(서든데스) | between(라운드 사이) | end(종료)
     * @param round        현재 라운드 (1부터)
     * @param roundsToWin  선승 라운드 수 (best-of-3 이면 2)
     * @param scoreUs      보는 사람 팀의 라운드 승수
     * @param scoreThem    상대 팀 라운드 승수
     * @param secondsLeft  이 단계 남은 초
     * @param phaseSeconds 이 단계 전체 초 (보스바 진행도)
     * @param usName       우리 팀 이름(파티장 이름 등)
     * @param themName     상대 팀 이름
     * @param us           우리 팀원 (보는 사람 포함)
     * @param them         상대 팀원
     */
    record PvpHud(String matchId, String phase, int round, int roundsToWin, int scoreUs, int scoreThem,
                  int secondsLeft, int phaseSeconds, String usName, String themName,
                  List<TeamMember> us, List<TeamMember> them) {}

    /** 팀원 한 명: hpRatio 0~1, alive = 이번 라운드 생존. */
    record TeamMember(String name, double hpRatio, boolean alive) {}
}
