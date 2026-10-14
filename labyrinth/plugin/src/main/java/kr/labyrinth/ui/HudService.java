package kr.labyrinth.ui;

import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
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
     * viewer 화면에서 target 의 이름표(·탭 목록 이름) 색. null = 기본색. pvp 모듈이 1초마다 파티원을 초록색으로 맞춘다
     * (보는 사람마다 다르게 — 각자 자기 파티원이 초록).
     */
    default void nameTagColor(Player viewer, Player target, NamedTextColor color) {}
}
