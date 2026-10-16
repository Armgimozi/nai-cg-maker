package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.data.BlockData;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Mob;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitTask;

/**
 * {@code /labadmin mine selftest} — 한 줄 (계약 §3.7, §0 뒤 손 닿는 한도 칸 reach_max 는 뺌):
 * {@code [광산 자가 진단] 결과: 예외 0 · levels=6/6 · mismatched=0 · veins=362 · gems=18 · unreachable=0 · lifts=6/6 · office=1 · tool_mismatch=0 · mobs=0}
 * <ul>
 *   <li>levels = 지문이 jar 와 같게 지어진 층 · mismatched = 청사진과 다른 칸 (광맥·보석 칸은 다 찬 블록이나 그 층 빈 광맥 블록이면 맞음)</li>
 *   <li>unreachable = 보이는 면이 없거나 바닐라 손 닿는 거리(4.5)로 캘 수 없는 광맥·보석 (청사진 검사)</li>
 *   <li>lifts·office = 승강기·관리소 칸이 제 블록인가 · tool_mismatch = items.yml 곡괭이를 ItemService 로 만들었을 때 구성요소가 계획과 다른 수</li>
 *   <li>mobs = 광산 월드의 몹 수</li>
 * </ul>
 * 칸 비교는 틱마다 한 층씩 나눠 한다.
 */
final class MineSelfTest {

    private final MineModule module;
    private int errors;
    private int mismatched;
    private final List<String> notes = new ArrayList<>();

    MineSelfTest(MineModule module) { this.module = module; }

    void run(CommandSender to) {
        if (!module.active()) {
            Text.error(to, "광산이 꺼져 있습니다.");
            Log.info("[광산 자가 진단] 결과: 예외 0 · 꺼짐");
            return;
        }
        if (module.builder().running()) {
            Text.error(to, "광산을 짓는 중입니다. 끝난 뒤 다시 해 주세요.");
            return;
        }
        List<MineLevel> levels = new ArrayList<>(module.levels());
        int[] i = {0};
        BukkitTask[] task = new BukkitTask[1];
        task[0] = Bukkit.getScheduler().runTaskTimer(module.services().plugin(), () -> {
            try {
                if (i[0] < levels.size()) {
                    compare(levels.get(i[0]++));
                    return;
                }
            } catch (Throwable t) {
                errors++;
                Log.error("[광산 자가 진단] 칸 비교 오류", t);
                i[0]++;
                return;
            }
            task[0].cancel();
            finish(to, levels);
        }, 1L, 1L);
    }

    private void compare(MineLevel l) {
        World w = module.world();
        MineBlueprint bp = l.bp;
        int[] bad = {0};
        bp.forEachCell((x, y, z, cp) -> {
            BlockData want = l.expected(cp);
            if (want == null) {
                bad[0]++;
                return;
            }
            Block b = w.getBlockAt(bp.ox + x, bp.oy + y, bp.oz + z);
            BlockData got = b.getBlockData();
            if (got.equals(want)) return;
            String s = bp.state(cp);
            if (s != null && (s.startsWith(MineBlueprint.VEIN) || s.startsWith(MineBlueprint.GEM)) && got.equals(l.depleted)) return;
            bad[0]++;
            if (notes.size() < 5) notes.add(l.def.id() + " (" + b.getX() + "," + b.getY() + "," + b.getZ() + ") " + got.getAsString()
                    + " ≠ " + want.getAsString());
        });
        mismatched += bad[0];
    }

    private void finish(CommandSender to, List<MineLevel> levels) {
        int expectedLevels = module.mineDef().levels().size();
        int ready = 0, lifts = 0, office = 0, unreachable = 0, veins = 0, gems = 0;
        World w = module.world();
        for (MineLevel l : levels) {
            try {
                if (module.ready(l.n)) ready++;
                veins += l.veins.size();
                gems += l.gems.size();
                unreachable += l.bp.unreachable();
                MineBlueprint.Marker lift = l.bp.marker("lift");
                if (lift != null && cellOk(w, l, lift) && MineNames.INTERACT_LIFT.equals(module.interactAt(w.getBlockAt(lift.bx(), lift.by(), lift.bz())))) lifts++;
                for (MineBlueprint.Marker m : l.bp.markers("office")) if (cellOk(w, l, m)) office++;
            } catch (Throwable t) {
                errors++;
                Log.error("[광산 자가 진단] " + l.def.id() + " 오류", t);
            }
        }
        int tools = 0, toolBad = 0;
        try {
            for (ItemDef def : module.services().content().items().values()) {
                if (!def.isTool()) continue;
                tools++;
                ItemStack s = module.services().items().create(def.id());
                String why = module.pickaxes().mismatch(s, def.tool());
                if (why != null) {
                    toolBad++;
                    if (notes.size() < 8) notes.add(def.id() + ": " + why);
                }
            }
        } catch (Throwable t) {
            errors++;
            Log.error("[광산 자가 진단] 곡괭이 검사 오류", t);
        }
        int mobs = 0;
        for (Entity e : w.getEntities()) if (e instanceof Mob) mobs++;
        String line = "[광산 자가 진단] 결과: 예외 " + errors + " · levels=" + ready + "/" + expectedLevels + " · mismatched=" + mismatched
                + " · veins=" + veins + " · gems=" + gems + " · unreachable=" + unreachable + " · lifts=" + lifts + "/" + expectedLevels
                + " · office=" + office + " · tool_mismatch=" + toolBad + " · mobs=" + mobs
                + " · tools=" + tools + " · nodes=" + module.veins().displayCount() + "/" + gems + " · empty=" + module.veins().state().count();
        Log.info(line);
        for (String n : notes) Log.info("[광산 자가 진단]   " + n);
        if (!(to instanceof org.bukkit.command.ConsoleCommandSender)) {
            Text.send(to, "<gray>" + Text.escape(line));
            for (String n : notes) Text.send(to, "<dark_gray>  " + Text.escape(n));
        }
    }

    private static boolean cellOk(World w, MineLevel l, MineBlueprint.Marker m) {
        int x = m.bx() - l.bp.ox, y = m.by() - l.bp.oy, z = m.bz() - l.bp.oz;
        BlockData want = l.expected(l.bp.cell(x, y, z));
        return want != null && w.getBlockAt(m.bx(), m.by(), m.bz()).getBlockData().equals(want) && !want.getMaterial().isAir();
    }
}
