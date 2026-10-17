package kr.labyrinth.homes.play;

import java.util.List;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.homes.PlotGeom;
import kr.labyrinth.homes.PlotInfo;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.Sign;
import org.bukkit.block.sign.Side;
import org.bukkit.block.sign.SignSide;

/**
 * 대문 문패 표지판 글 (0.3.7, 설계 §3.4): {@code [3번지]} · 주인 (비면 "비어 있음") · 집 이름 · {@code /미궁 집}.
 * 받기·이름·비우기·회수 때 다시 쓴다 ({@link kr.labyrinth.homes.HomesUi#plotChanged}). 표지판은 구역 조각(묶음 A)이 밀랍칠·빛나는 글로 놓는다 —
 * 글만 바꾸고 밀랍·빛은 그대로 둔다. 구역 기록에 표지판 높이가 없으면 그 열에서 찾는다.
 */
public final class PlotSigns {

    private PlotSigns() {}

    /** 네 줄 (MiniMessage). */
    public static List<String> lines(PlotGeom plot, PlotInfo info) {
        String head = "<b>[" + Text.escape(plot.label()) + "]</b>";
        if (info == null || info.vacant()) return List.of(head, "비어 있음", "", "<gray>/미궁 집</gray>");
        String owner = Text.escape(info.ownerName());
        String name = info.name() == null ? "" : info.name();
        String def = info.ownerName() + "의 집";
        return List.of(head, owner, name.isBlank() || name.equals(def) ? "" : Text.escape(cut(name, 12)), "<gray>/미궁 집</gray>");
    }

    /** 액션바 "◆ 3번지 · 하린의 집" (빈 집이면 "빈 집"). */
    public static String enterLine(PlotGeom plot, PlotInfo info) {
        String what = info == null || info.vacant() ? "<#7fe07f>빈 집</#7fe07f> <dark_gray>— /미궁 집" : "<white>" + Text.escape(
                info.name() == null || info.name().isBlank() ? info.ownerName() + "의 집" : info.name());
        return "<#ffd36b>◆ " + Text.escape(plot.label()) + "</#ffd36b> <dark_gray>·</dark_gray> " + what;
    }

    static String cut(String s, int max) {
        return s.codePointCount(0, s.length()) <= max ? s : s.substring(0, s.offsetByCodePoints(0, max));
    }

    /** 표지판 칸 (없으면 null). 청크가 불러져 있어야 한다. */
    static Block find(World w, PlotGeom p) {
        if (w == null || p.custom()) return null;
        if (p.signY() != Integer.MIN_VALUE) {
            for (int dy : new int[] {0, 1, -1}) {
                Block b = w.getBlockAt(p.signX(), p.signY() + dy, p.signZ());
                if (b.getState(false) instanceof Sign) return b;
            }
        }
        for (int y = p.floorY() + 6; y >= p.floorY() - 6; y--) {
            Block b = w.getBlockAt(p.signX(), y, p.signZ());
            if (b.getState(false) instanceof Sign) return b;
        }
        return null;
    }

    /** 그 집 표지판을 다시 쓴다 (청크를 비동기로 불러 둔 뒤 다음 틱에). */
    static void write(org.bukkit.plugin.Plugin plugin, World w, PlotGeom p, PlotInfo info) {
        if (w == null || p == null || p.custom()) return;
        int cx = p.signX() >> 4, cz = p.signZ() >> 4;
        Runnable job = () -> {
            try {
                Block b = find(w, p);
                if (b == null || !(b.getState() instanceof Sign sign)) return;
                List<String> ls = lines(p, info);
                for (Side side : Side.values()) {
                    SignSide s = sign.getSide(side);
                    for (int i = 0; i < 4; i++) s.line(i, Text.mm(ls.get(i)));
                }
                sign.update(true, false);
            } catch (Throwable t) {
                Log.warn("[집] " + p.label() + " 표지판 쓰기 실패: " + t.getMessage());
            }
        };
        if (w.isChunkLoaded(cx, cz)) {
            job.run();
            return;
        }
        w.getChunkAtAsync(cx, cz).thenAccept(c -> Bukkit.getScheduler().runTask(plugin, job));
    }
}
