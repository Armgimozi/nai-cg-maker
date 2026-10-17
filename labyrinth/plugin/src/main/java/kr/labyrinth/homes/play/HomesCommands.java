package kr.labyrinth.homes.play;

import kr.labyrinth.command.CommandService;
import kr.labyrinth.homes.HomesService;

/**
 * {@code /미궁 집} ({@code /lab 집}, {@code /lab home}) (0.3.7, plan §6) — 뼈대: 아직 등록하지 않음. 소유: 묶음 C.
 * <p>
 * 채울 것: (없음) 메뉴 · 가기 · 받기 [번지] · 초대 &lt;이름&gt; · 내보내기 &lt;이름&gt; · 이름 &lt;글&gt; · 손님 [켬|끔] · 방문 &lt;이름&gt; · 짐 ·
 * 비우기 [확인] · 여기. 일은 {@code service.claim/vacate/invite/…} (묶음 B), 글·메뉴·이동은 여기.
 * 등록: {@code cmd.addSubcommand("lab", Commands.literal("집") …)} · {@code "home"}.
 */
public final class HomesCommands {

    private final HomesService service;

    public HomesCommands(HomesService service) { this.service = service; }

    public void register(CommandService cmd) {
        // 묶음 C
    }

    HomesService service() { return service; }
}
