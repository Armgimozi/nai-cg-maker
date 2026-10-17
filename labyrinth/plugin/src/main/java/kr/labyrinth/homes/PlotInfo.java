package kr.labyrinth.homes;

import java.util.List;
import java.util.UUID;

/**
 * 집터 하나의 소유 기록 (0.3.7, {@code labyrinth-plots.yml plots.<id>}) — 메뉴·표지판·관리자 명령이 읽는다. 소유: 묶음 B.
 *
 * @param owner        주인 (빈 집이면 null)
 * @param name         집 이름 (없으면 "<주인>의 집")
 * @param trusted      초대한 사람들 (최대 homes.max_trusted)
 * @param guests       손님 허용
 * @param claimedAt    받은 때 (epoch ms, 빈 집 0)
 * @param ownerLastSeen 주인 마지막 접속 (epoch ms, 모르면 0 — 오래 안 옴 표시용)
 */
public record PlotInfo(PlotGeom plot, UUID owner, String ownerName, String name, List<UUID> trusted, List<String> trustedNames,
                       boolean guests, long claimedAt, long ownerLastSeen) {

    public PlotInfo {
        trusted = trusted == null ? List.of() : List.copyOf(trusted);
        trustedNames = trustedNames == null ? List.of() : List.copyOf(trustedNames);
        ownerName = ownerName == null ? "" : ownerName;
        name = name == null ? "" : name;
    }

    public static PlotInfo empty(PlotGeom plot, boolean guestsDefault) {
        return new PlotInfo(plot, null, "", "", List.of(), List.of(), guestsDefault, 0, 0);
    }

    public boolean vacant() { return owner == null; }
}
