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
 * 정해진 재생 (사람 수 무관) · 가방 가득 · 보석 노드 결정 · 곡괭이 구성요소 · 광산 밖 블록 표 · 광산 PvP 설정 · 안전 구역 ·
 * PvP 아닌 피해 막기 · 몹 스폰 막기.
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

    /**
     * 안전 구역 (n층): 내리는 자리 · 승강기 · (1층) 관리소 · 갱도 입구 안쪽 (x ±8.5 · z 7.5) 은 안전, 바로 밖 (x ±9.5 · z 8.5)과 갱도
     * (0.5, F+1, 14.5) 는 PvP 구역, 층 사이 높이는 안전. 둘레 칸 수(safe_margin)를 바꿨으면 그만큼 옮겨 본다. PvP 켜짐과 상관없이 모양만.
     */
    private void zoneCheck(MineLevel l, World w) {
        MineSafeZones z = module.zones();
        int m = z.margin();
        double f = l.def.floorY() + 1;
        MineBlueprint.Marker lift = l.bp.marker("lift");
        double lx = lift == null ? 0 : lift.bx(), lz = lift == null ? 0 : lift.bz();
        Location land = l.landing(w);
        List<String> bad = new ArrayList<>();
        java.util.function.BiConsumer<String, double[]> safe = (name, p) -> {
            if (!z.safe(p[0], p[1], p[2])) bad.add(name + " PvP");
        };
        java.util.function.BiConsumer<String, double[]> ground = (name, p) -> {
            if (z.safe(p[0], p[1], p[2])) bad.add(name + " 안전");
        };
        safe.accept("내리는 자리", new double[] {land.getX(), land.getY(), land.getZ()});
        safe.accept("승강기", new double[] {lx + 0.5, f, lz + 0.5});
        for (MineBlueprint.Marker o : l.bp.markers(MineNames.MARKER_OFFICE)) safe.accept("관리소", new double[] {o.bx() + 0.5, f, o.bz() + 0.5});
        double in = MineSafeZones.HALL_HALF_X + m + 0.5, out = in + 1;
        double sIn = MineSafeZones.HALL_SOUTH + m + 0.5, sOut = sIn + 1;
        safe.accept("서쪽 입구", new double[] {lx - in + 1, f, lz + 0.5});
        safe.accept("동쪽 입구", new double[] {lx + in, f, lz + 0.5});
        safe.accept("남쪽 입구", new double[] {lx + 0.5, f, lz + sIn});
        ground.accept("서쪽 갱도", new double[] {lx - out + 1, f, lz + 0.5});
        ground.accept("동쪽 갱도", new double[] {lx + out, f, lz + 0.5});
        ground.accept("남쪽 갱도", new double[] {lx + 0.5, f, lz + sOut});
        ground.accept("남쪽 갱도 안", new double[] {lx + 0.5, f, lz + 14.5});
        safe.accept("층 사이", new double[] {lx + 30.5, l.boxBottom() - 2.5, lz + 30.5});
        check("안전 구역 (" + l.n + "층)", bad.isEmpty(), bad.isEmpty() ? z.rects().stream().filter(r -> r.level() == l.n).map(MineSafeZones.Rect::blocks)
                .reduce((a, b) -> a + " + " + b).orElse("-") + " · 홀 밖 PvP" : String.join(", ", bad));
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
            // 3. 정해진 재생 (사람 수 무관 — 0.3.7 주인 결정)
            double regen = cfg.regenSeconds(n);
            double eta = st.etaSeconds(low.key());
            int r1 = veins.tickWith(regen - 1);
            boolean stillEmpty = st.isDepleted(low.key()) && b.getBlockData().equals(l.depleted);
            int r2 = veins.tickWith(2);
            check("정해진 재생 (사람 수 무관)", Math.abs(eta - regen) < 1e-6 && stillEmpty && r1 == 0 && r2 >= 1 && !st.isDepleted(low.key())
                            && b.getBlockData().equals(low.full()),
                    "남은 " + Math.round(eta) + "초 = " + cfg.regenMinutes().get(n - 1) + "분 · " + Math.round(regen - 1) + "초 → 빈 채로 · 2초 더 → 다시 참");
            // 4. 가방 가득
            Inventory full = Bukkit.createInventory(null, 36);
            for (int i = 0; i < 36; i++) full.setItem(i, ItemStack.of(Material.COBBLESTONE, 64));
            MineVeins.Harvest f = veins.harvest(null, low, best, full, rnd, true);
            check("가방 가득 → 캐지지 않음", f.result() == MineVeins.Result.BAG_FULL && b.getBlockData().equals(low.full()) && !st.isDepleted(low.key()),
                    f.result() + " → " + MineNames.BAG_FULL);
            // 5. 보석 노드
            if (!l.gems.isEmpty()) {
                // 0.3.6.1: 보석 노드 = 네모난 광석 블록 하나 (결정 ItemDisplay 없음)
                MineLevel.Vein g = l.gems.get(0);
                int full0 = veins.fullGemBlocks();
                MineVeins.Harvest gh = veins.harvest(null, g, best, bag, rnd, true);
                touched.add(g);
                Block gb = w.getBlockAt(g.x(), g.y(), g.z());
                boolean ok = gh.result() == MineVeins.Result.OK && gb.getBlockData().equals(l.depleted);
                veins.tickWith(cfg.gemRegenSeconds() + 1);
                int crystals = veins.leftoverCrystals();
                check("보석 노드 (" + g.node().name() + ")", ok && gb.getBlockData().equals(g.full()) && veins.fullGemBlocks() == full0 && crystals == 0
                                && MineNames.GEM_BLOCKS.get(g.node().id()).equals(g.node().block()),
                        gh.result() + " · " + g.node().block() + " · 결정 " + crystals);
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
                    && module.isMineBlock(Material.INFESTED_CRACKED_STONE_BRICKS) && !module.isMineBlock(Material.MAGMA_BLOCK)
                    && !module.isMineBlock(Material.STONE), null);
            // 0.3.7 광산 PvP: 월드 규칙 = pvp.enabled && mine.pvp.enabled · 안전 구역 · PvP 아닌 피해는 그대로 0
            Boolean pvp = w.getGameRuleValue(GameRules.PVP);
            boolean want = cfg.pvp().enabled() && module.services().targets().pvpConfig().enabled();
            check("광산 PvP 설정", Boolean.valueOf(want).equals(pvp) && module.pvpEnabled() == want,
                    "월드 pvp=" + pvp + " · mine.pvp.enabled=" + cfg.pvp().enabled() + " · pvp.enabled="
                            + module.services().targets().pvpConfig().enabled() + " · 둘레 " + cfg.pvp().safeMargin() + "칸");
            zoneCheck(l, w);
            boolean causes = true;
            for (org.bukkit.event.entity.EntityDamageEvent.DamageCause c : new org.bukkit.event.entity.EntityDamageEvent.DamageCause[] {
                    org.bukkit.event.entity.EntityDamageEvent.DamageCause.FALL, org.bukkit.event.entity.EntityDamageEvent.DamageCause.FIRE_TICK,
                    org.bukkit.event.entity.EntityDamageEvent.DamageCause.LAVA, org.bukkit.event.entity.EntityDamageEvent.DamageCause.POISON,
                    org.bukkit.event.entity.EntityDamageEvent.DamageCause.WITHER, org.bukkit.event.entity.EntityDamageEvent.DamageCause.VOID,
                    org.bukkit.event.entity.EntityDamageEvent.DamageCause.KILL, org.bukkit.event.entity.EntityDamageEvent.DamageCause.CUSTOM}) {
                if (MinePvpRules.vanillaPvpCause(c)) causes = false;
            }
            causes &= MinePvpRules.vanillaPvpCause(org.bukkit.event.entity.EntityDamageEvent.DamageCause.ENTITY_ATTACK)
                    && MinePvpRules.vanillaPvpCause(org.bukkit.event.entity.EntityDamageEvent.DamageCause.PROJECTILE);
            check("PvP 아닌 피해 막기", causes, "떨어짐·불·용암·독·시듦·공허·/kill = 0 · 플레이어 근접·화살·물약·가시·폭죽만 PvP 판정");
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
            check("안전 (PvP 말고 피해 0)", module.safe() && module.isMineWorld(w), "mine.safe=" + module.safe());
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
