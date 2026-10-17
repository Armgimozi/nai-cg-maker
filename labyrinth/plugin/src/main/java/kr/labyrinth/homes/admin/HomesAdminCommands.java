package kr.labyrinth.homes.admin;

import kr.labyrinth.command.CommandService;
import kr.labyrinth.homes.HomesService;

/**
 * {@code /labadmin plot …} (0.3.7, plan §6·§11) — 뼈대: 아직 등록하지 않음. 소유: 묶음 B.
 * <p>
 * 채울 것: list · info [번지|이름] · tp &lt;번지&gt; · give &lt;번지&gt; &lt;이름&gt; (집 있는 사람 거절, R18) · reclaim &lt;번지|이름&gt; ·
 * convert &lt;이름&gt; &lt;x1&gt; &lt;z1&gt; &lt;x2&gt; &lt;z2&gt; [y1 y2] · unconvert &lt;번지&gt; · lock &lt;auto|on|off&gt; · grace &lt;일&gt; · legacy ·
 * name &lt;번지&gt; &lt;글&gt; · parcel &lt;이름&gt; · selftest ({@code service.selfTestLines()}).
 * 등록: {@code cmd.addSubcommand("labadmin", Commands.literal("plot") …)} (MineCommands 와 같은 방식).
 */
public final class HomesAdminCommands {

    private final HomesService service;

    public HomesAdminCommands(HomesService service) { this.service = service; }

    public void register(CommandService cmd) {
        // 묶음 B
    }

    HomesService service() { return service; }
}
