package kr.labyrinth.dungeon;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.gen.MazePlan;
import kr.labyrinth.dungeon.gen.RoomType;
import kr.labyrinth.dungeon.rooms.Room;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.text.format.TextColor;
import org.bukkit.entity.Player;

/**
 * 탐험 지도 (/미궁 지도 · 메뉴 버튼 · 지도 들고 우클릭) — 채팅에 층 격자를 그린다 (GDD §5.4).
 * 같은 글자(█)만 써서 줄이 어긋나지 않는다. 셀 = 짝수 칸, 그 사이 통로 = 홀수 칸, 맨 아래 줄 = 보스 문.
 * 지나간 셀만 보이고(안개), 지나간 셀에서 이어지는 아직 안 가 본 길은 어둡게 암시만 한다. 현재 위치·파티원·방 종류 색·찾은 보스 문·
 * 연 비밀 통로. 마우스를 올리면 설명. 시작방에서 보스 쪽을 알려 주지는 않는다.
 */
public final class ExplorationMap {

    static final String GLYPH = "█";
    static final TextColor FOG = TextColor.color(0x16131b);
    static final TextColor HINT = TextColor.color(0x3d3747);
    static final TextColor PASS = TextColor.color(0x6f6979);
    static final TextColor HALL = TextColor.color(0x9a94a4);
    static final TextColor ME = TextColor.color(0xffffff);
    static final TextColor ALLY = TextColor.color(0x5ef2ff);
    static final TextColor BOSS_DOOR = TextColor.color(0xff2a2a);
    static final TextColor SECRET = TextColor.color(0xffb347);

    private ExplorationMap() {}

    static TextColor roomColor(RoomType t, boolean cleared) {
        return switch (t) {
            case START -> TextColor.color(0x4f7dff);
            case COMBAT -> TextColor.color(cleared ? 0x9a4a4a : 0xff6b6b);
            case ELITE -> TextColor.color(cleared ? 0x7a2a2a : 0xd0302f);
            case TREASURE -> TextColor.color(cleared ? 0xa08a50 : 0xffd36b);
            case GIMMICK -> TextColor.color(cleared ? 0x7d63a0 : 0xc79bff);
            case REST -> TextColor.color(0x7fe07f);
            default -> HALL;
        };
    }

    /** 지도 줄 목록 (머리말 + 격자 + 범례). viewer 가 null 이면 현재 위치 표시 없음 (자가 진단). */
    public static List<Component> render(FloorState fs, Player viewer) {
        MazePlan plan = fs.layout().plan();
        Exploration ex = fs.exploration();
        int n = plan.size();
        Map<Integer, Room> roomByCell = new HashMap<>();
        for (Room r : fs.rooms()) if (r.info().cell() >= 0) roomByCell.put(r.info().cell(), r);
        int me = viewer == null ? -1 : cellOf(fs, viewer);
        Map<Integer, List<String>> allies = new HashMap<>();
        for (Player p : fs.alivePlayers()) {
            if (viewer != null && p.getUniqueId().equals(viewer.getUniqueId())) continue;
            int c = cellOf(fs, p);
            if (c >= 0) allies.computeIfAbsent(c, k -> new ArrayList<>()).add(p.getName());
        }
        Map<Integer, Boolean> secretOpen = new HashMap<>();
        for (var s : fs.layout().secretRooms()) secretOpen.put(s.cell(), fs.secrets().isOpen(s.index()));

        List<Component> out = new ArrayList<>();
        int used = plan.usedCount();
        out.add(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>" + Text.escape(fs.def().subtitle() == null ? "지하 " + fs.floor() + "층" : fs.def().subtitle())
                + " 탐험 지도</b></gradient> <gray>· 지나간 길 <white>" + ex.visitedCount() + "</white>/" + used + "칸"
                + (ex.secretsFound() > 0 ? " · <#ffb347>비밀 통로 " + ex.secretsFound() + "</#ffb347>" : "")
                + (ex.bossDoorFound() ? " · <#ff6b6b>수호자의 문 발견</#ff6b6b>" : "")));
        for (int r = 0; r < 2 * n; r++) {
            TextComponent.Builder row = Component.text();
            for (int q = 0; q < 2 * n - 1; q++) {
                int x = q / 2, z = r / 2;
                int c = plan.index(x, Math.min(n - 1, z));
                if (r == 2 * n - 1) {
                    // 보스 문 줄 (마지막 줄 셀 아래)
                    if (q % 2 == 0 && c == plan.bossAttach() && ex.bossDoorFound()) row.append(glyph(BOSS_DOOR, "<#ff6b6b><b>수호자의 문</b>\n<gray>이 아래로 보스방이 이어진다"));
                    else row.append(glyph(FOG, null));
                    continue;
                }
                if (r % 2 == 0 && q % 2 == 0) {
                    row.append(cell(fs, plan, ex, c, me, allies.get(c), roomByCell.get(c), secretOpen.get(c)));
                } else if (r % 2 == 0) {
                    row.append(link(plan, ex, c, MazePlan.EAST));
                } else if (q % 2 == 0) {
                    row.append(link(plan, ex, c, MazePlan.SOUTH));
                } else {
                    row.append(glyph(FOG, null));
                }
            }
            out.add(row.build());
        }
        out.add(Text.mm("<white>█</white><gray>나 <#5ef2ff>█</#5ef2ff>동료 <#4f7dff>█</#4f7dff>시작 <#ff6b6b>█</#ff6b6b>전투 "
                + "<#d0302f>█</#d0302f>정예 <#ffd36b>█</#ffd36b>보물 <#c79bff>█</#c79bff>시련 <#7fe07f>█</#7fe07f>휴식 "
                + "<#ffb347>█</#ffb347>비밀 <#ff2a2a>█</#ff2a2a>문"));
        return out;
    }

    /** 플레이어가 서 있는 셀 (격자 밖이면 -1). */
    static int cellOf(FloorState fs, Player p) {
        if (!fs.onThisFloor(p.getLocation())) return -1;
        return fs.layout().cellAt(fs.tileX(p.getLocation()), fs.tileZ(p.getLocation()));
    }

    private static Component cell(FloorState fs, MazePlan plan, Exploration ex, int c, int me, List<String> allies, Room room,
                                  Boolean secretOpen) {
        if (!plan.used(c)) return glyph(FOG, null);
        if (!ex.visited(c)) {
            for (int d = 0; d < 4; d++) {
                int o = plan.step(c, d);
                if (o >= 0 && plan.open(c, d) && ex.visited(o)) return glyph(HINT, "<dark_gray>아직 가 보지 않은 곳");
            }
            return glyph(FOG, null);
        }
        RoomType t = plan.type(c);
        boolean cleared = room != null && room.cleared();
        String name = t == RoomType.HALL ? plan.style(c) == null ? "복도" : plan.style(c).displayName() : t.displayName();
        StringBuilder hover = new StringBuilder("<white>").append(Text.escape(name)).append("</white>");
        if (room != null && t != RoomType.START && t != RoomType.REST) hover.append(cleared ? " <green>(정리됨)" : " <gray>(아직)");
        TextColor col = t == RoomType.HALL ? HALL : roomColor(t, cleared);
        if (Boolean.TRUE.equals(secretOpen)) {
            col = SECRET;
            hover.append("\n<#ffb347>무너진 금 간 벽 — 숨은 방");
        }
        if (c == plan.bossAttach() && ex.bossDoorFound()) hover.append("\n<#ff6b6b>남쪽으로 수호자의 문");
        if (allies != null && !allies.isEmpty()) {
            col = ALLY;
            hover.append("\n<#5ef2ff>").append(Text.escape(String.join(", ", allies)));
        }
        if (c == me) {
            col = ME;
            hover.append("\n<yellow>현재 위치");
        }
        return glyph(col, hover.toString());
    }

    private static Component link(MazePlan plan, Exploration ex, int c, int dir) {
        int o = plan.step(c, dir);
        if (o < 0 || !plan.open(c, dir)) return glyph(FOG, null);
        boolean a = ex.visited(c), b = ex.visited(o);
        if (a && b) return glyph(PASS, null);
        if (a || b) return glyph(HINT, null);
        return glyph(FOG, null);
    }

    private static Component glyph(TextColor color, String hoverMm) {
        Component g = Component.text(GLYPH, color);
        return hoverMm == null ? g : g.hoverEvent(HoverEvent.showText(Text.mm(hoverMm)));
    }

    /** 채팅으로 보낸다. */
    public static void show(FloorState fs, Player to) {
        for (Component line : render(fs, to)) to.sendMessage(line);
    }
}
