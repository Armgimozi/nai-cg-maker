package kr.labyrinth.mine;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import kr.labyrinth.content.ToolSpec;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;

/**
 * {@code /labadmin mine test [층]} — 손님(클라이언트) 없이 콘솔에서 광산을 시험하는 고리. 실제 수확 길({@link MineVeins#harvest})을
 * 가상 가방·가상 곡괭이로 돌린다: 약한 곡괭이·곡괭이 없음 · 캐기 → 진짜 블록이 빈 광맥 (공유) · 다시 캐기 = 빈 광맥 ·
 * 사람 수에 따른 재생 (4명 = 4배) · 가방 가득 · 보석 노드 결정 · 곡괭이 구성요소 · 광산 밖 블록 표 · PvP 끔 · 몹 스폰 막기.
 * 끝나면 건드린 광맥을 다 찬 상태로 되돌린다. 줄마다 "[광산 시험] … 통과|실패", 끝에 "[광산 시험] 결과: 통과 a/b".
 */
final class MineTestHook {

    private final MineModule module;
    private final List<String> lines = new ArrayList<>();
    private int pass, total;

    MineTestHook(MineModule module) { this.module = module; }

    private void check(String name, boolean ok, String detail) {
        total++;
        if (ok) pass++;
        lines.add("[광산 시험] " + name + ": " + (ok ? "통과" : "실패") + (detail == null || detail.isEmpty() ? "" : " (" + detail + ")"));
    }

    void run(CommandSender to, int levelArg) {
        if (!module.active()) {
            Text.error(to, "광산이 꺼져 있습니다.");
            return;
        }
        int n = levelArg <= 0 ? 1 : levelArg;
        MineLevel l = module.level(n);
        if (l == null || !module.ready(n)) {
            Text.error(to, n + "층이 아직 준비되지 않았습니다.");
            return;
        }
        World w = module.world();
        MineVeins veins = module.veins();
        VeinState st = veins.state();
        MineConfig cfg = module.config();
        Random rnd = new Random(36);
        ToolSpec best = new ToolSpec(ToolSpec.PICKAXE, 6, Map.of(1, 2.0, 2, 2.0, 3, 2.0, 4, 2.0, 5, 2.0, 6, 2.0), 0.1);
        ToolSpec weak = new ToolSpec(ToolSpec.PICKAXE, 1, Map.of(1, 1.0), 0.0);
        Inventory bag = Bukkit.createInventory(null, 36);
        List<MineLevel.Vein> touched = new ArrayList<>();
        try {
            MineLevel.Vein low = null, hard = null;
            for (MineLevel.Vein v : l.veins) {
                if (st.isDepleted(v.key())) continue;
                if (low == null && v.node().tier() == 1) low = v;
                if (hard == null && v.node().tier() >= 2) hard = v;
            }
            if (low == null) low = l.veins.get(0);
            // 1. 단단함 규칙
            if (hard != null) {
                MineVeins.Harvest h = veins.harvest(null, hard, weak, bag, rnd, true);
                Block b = w.getBlockAt(hard.x(), hard.y(), hard.z());
                check("약한 곡괭이 (" + hard.node().name() + ")", h.result() == MineVeins.Result.TOO_WEAK && b.getBlockData().equals(hard.full())
                        && !st.isDepleted(hard.key()), h.result() + " → " + TierRule.message(TierRule.Verdict.TOO_WEAK));
            }
            MineVeins.Harvest none = veins.harvest(null, low, null, bag, rnd, true);
            check("곡괭이 없음", none.result() == MineVeins.Result.NO_PICKAXE, String.valueOf(none.result()));
            // 2. 캐기 → 진짜 블록이 빈 광맥
            Block b = w.getBlockAt(low.x(), low.y(), low.z());
            MineVeins.Harvest h = veins.harvest(null, low, best, bag, rnd, true);
            touched.add(low);
            int inBag = 0;
            for (ItemStack s : bag.getContents()) if (s != null) inBag += s.getAmount();
            check("캐기 (" + low.node().name() + " " + low.key() + ")", h.result() == MineVeins.Result.OK && inBag >= 1,
                    h.result() + " · 가방 " + inBag + "개 · " + MineMath.seconds(low.node(), best) + "초 곡괭이");
            check("빈 광맥 블록 (모두에게)", b.getBlockData().equals(l.depleted) && st.isDepleted(low.key()),
                    b.getType().getKey() + " = " + l.def.depletedBlock());
            MineVeins.Harvest again = veins.harvest(null, low, best, bag, rnd, true);
            check("빈 광맥 다시 캐기", again.result() == MineVeins.Result.DEPLETED, String.valueOf(again.result()));
            // 3. 사람 수 재생
            double regen = cfg.regenSeconds(n);
            double eta1 = st.etaSeconds(low.key(), 1), eta4 = st.etaSeconds(low.key(), 4), eta9 = st.etaSeconds(low.key(), 9);
            check("재생 시간 ÷ 사람 수", Math.abs(eta1 - regen) < 1e-6 && Math.abs(eta4 - regen / 4) < 1e-6 && Math.abs(eta9 - regen / cfg.regenPlayersCap()) < 1e-6,
                    "1명 " + Math.round(eta1) + "초 · 4명 " + Math.round(eta4) + "초 · 9명 " + Math.round(eta9) + "초 (최대 ÷" + cfg.regenPlayersCap() + ")");
            int r1 = veins.tickWith(regen / 4 + 1, 1);
            boolean stillEmpty = st.isDepleted(low.key()) && b.getBlockData().equals(l.depleted);
            int r4 = veins.tickWith(regen / 4 + 1, 4);
            check("4명이면 4배 빨리 참", stillEmpty && r1 == 0 && r4 >= 1 && !st.isDepleted(low.key()) && b.getBlockData().equals(low.full()),
                    "1명으로 " + Math.round(regen / 4 + 1) + "초 → 빈 채로 · 그 뒤 4명으로 " + Math.round(regen / 4 + 1) + "초 → 다시 참");
            // 4. 가방 가득
            Inventory full = Bukkit.createInventory(null, 36);
            for (int i = 0; i < 36; i++) full.setItem(i, ItemStack.of(Material.COBBLESTONE, 64));
            MineVeins.Harvest f = veins.harvest(null, low, best, full, rnd, true);
            check("가방 가득 → 캐지지 않음", f.result() == MineVeins.Result.BAG_FULL && b.getBlockData().equals(low.full()) && !st.isDepleted(low.key()),
                    f.result() + " → " + MineNames.BAG_FULL);
            // 5. 보석 노드
            if (!l.gems.isEmpty()) {
                MineLevel.Vein g = l.gems.get(0);
                int before = veins.displayCount();
                MineVeins.Harvest gh = veins.harvest(null, g, best, bag, rnd, true);
                touched.add(g);
                Block gb = w.getBlockAt(g.x(), g.y(), g.z());
                int during = veins.displayCount();
                boolean ok = gh.result() == MineVeins.Result.OK && gb.getBlockData().equals(l.depleted) && during == before - 1;
                veins.tickWith(cfg.gemRegenSeconds() + 1, 1);
                int after = veins.displayCount();
                check("보석 노드 (" + g.node().name() + ")", ok && gb.getBlockData().equals(g.full()) && after == before,
                        gh.result() + " · 결정 " + before + "→" + during + "→" + after);
            }
            // 6. 곡괭이 구성요소
            ToolSpec mid = new ToolSpec(ToolSpec.PICKAXE, 3, Map.of(1, 1.4, 2, 1.4, 3, 1.4), 0.04);
            ItemStack pick = module.pickaxes().apply(ItemStack.of(Material.STICK), mid);
            String why = module.pickaxes().mismatch(pick, mid);
            PickaxePlan plan = module.pickaxes().plan(mid);
            check("곡괭이 구성요소 (tier 3)", why == null, why == null ? "Tool 규칙 " + plan.rules().size() + " · CAN_BREAK " + plan.canBreak().size()
                    + " · UNBREAKABLE · PAPER · 구리 광석 " + String.format(java.util.Locale.ROOT, "%.2f", plan.rules().get(0).seconds()) + "초" : why);
            // 7. 광산 밖 블록 표 · PvP · 몹
            check("광산 블록 12종 표", module.isMineBlock(Material.COPPER_ORE) && module.isMineBlock(Material.ANCIENT_DEBRIS)
                    && module.isMineBlock(Material.MAGMA_BLOCK) && !module.isMineBlock(Material.STONE), null);
            Boolean pvp = w.getGameRuleValue(GameRules.PVP);
            check("광산 월드 PvP 끔", Boolean.FALSE.equals(pvp), "pvp=" + pvp);
            Location at = l.landing(w);
            Entity z = null;
            try {
                z = w.spawnEntity(at, EntityType.ZOMBIE);
            } catch (Throwable ignored) {
                // 막혔으면 예외가 날 수도 있다
            }
            boolean blocked = z == null || !z.isValid();
            if (z != null && z.isValid()) z.remove();
            check("몹 스폰 막기", blocked, z == null ? "생기지 않음" : z.isValid() ? "생김!" : "취소됨");
            check("안전 (피해 0 대상)", module.safe() && module.isMineWorld(w), "mine.safe=" + module.safe());
        } catch (Throwable t) {
            total++;
            lines.add("[광산 시험] 예외: " + t);
            Log.error("[광산 시험] 오류", t);
        } finally {
            for (MineLevel.Vein v : touched) {
                if (st.isDepleted(v.key())) veins.refill(w, v, false);
            }
        }
        lines.add("[광산 시험] 결과: 통과 " + pass + "/" + total);
        for (String s : lines) {
            Log.info(s);
            if (!(to instanceof org.bukkit.command.ConsoleCommandSender)) Text.send(to, "<gray>" + Text.escape(s));
        }
    }
}
