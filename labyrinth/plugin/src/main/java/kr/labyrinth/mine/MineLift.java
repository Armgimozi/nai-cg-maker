package kr.labyrinth.mine;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import kr.labyrinth.core.Text;
import kr.labyrinth.ui.Button;
import kr.labyrinth.ui.Menu;
import kr.labyrinth.ui.UiTheme;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;

/**
 * 승강기 (계약 §2.5): 6층 모두 깊이 순 + "마을로". <b>잠김 없음</b> — 레벨·곡괭이 조건이 어디에도 없다.
 * 타면 2초(config mine.lift_seconds) 어둠 + 쇠사슬·수레 소리, 움직이면 멈춘다. 도착 부제목 = 층 색 + 층 이름 (층 번호 글자 없음).
 * 0.3.7: PvP 구역에서 싸우는 중에 타면 5초 · 맞아도 멈춤 ({@link MinePvp#exitCastSeconds}).
 */
final class MineLift {

    private final MineModule module;
    private final Map<UUID, BukkitTask> riding = new HashMap<>();
    /** 0.3.7: PvP 구역에서 싸우는 중에 탄 승강기 (나가기 시전과 같음 — 끊으면 쓰러짐). */
    private final java.util.Set<UUID> combatRides = new java.util.HashSet<>();

    MineLift(MineModule module) { this.module = module; }

    boolean riding(Player p) { return riding.containsKey(p.getUniqueId()); }

    /** 0.3.7: 싸우는 중이라 5초 걸리는 승강기를 타는 중인가. */
    boolean combatRiding(Player p) { return p != null && combatRides.contains(p.getUniqueId()); }

    void cancelAll() {
        for (BukkitTask t : riding.values()) t.cancel();
        riding.clear();
        combatRides.clear();
    }

    /** 타는 중이면 조용히 멈춘다 (광산 PvP 쓰러짐 · 끊김 — "움직여서 멈췄습니다" 글 없이). */
    void cancel(Player p) {
        if (p == null || !riding(p)) return;
        stop(p);
        if (p.isOnline()) {
            p.removePotionEffect(PotionEffectType.BLINDNESS);
            p.stopSound(Sound.ENTITY_MINECART_RIDING);
        }
    }

    /** 승강기 메뉴. inMine = 광산 안 (마을로 버튼). */
    void open(Player p) {
        new LiftMenu(p, module.isMineWorld(p.getWorld())).open(p);
    }

    /** glyphs.yml menus.mine_lift: 마을로 0 · 층 4·13·22·31·40·49 (위에서 아래로 깊어짐) · 닫기 8. */
    static final int[] LEVEL_SLOTS = {4, 13, 22, 31, 40, 49};

    private final class LiftMenu extends Menu {
        private final boolean inMine;

        LiftMenu(Player p, boolean inMine) {
            super(6, UiTheme.title("mine_lift", 6, "<#e8c58a>승강기"));
            this.inMine = inMine;
        }

        @Override
        protected void build(Player viewer) {
            UiTheme.frame(this, "mine_lift", 6);
            List<MineLevel> levels = module.levels();
            int[] slots = LEVEL_SLOTS;
            MineLevel here = module.levelAt(viewer.getLocation());
            for (int i = 0; i < levels.size() && i < slots.length; i++) {
                MineLevel l = levels.get(i);
                int[] st = module.veins().status(l);
                List<String> lore = new ArrayList<>();
                lore.add("<gray>" + Text.escape(l.def.atmosphere()));
                lore.add("");
                lore.add("<gray>나는 광석: <white>" + Text.escape(ores(l)));
                lore.add("<gray>광맥 <white>" + st[0] + "</white>/" + st[1] + " · 보석 <white>" + st[2] + "</white>/" + st[3]);
                int miners = module.minersAt(l);
                if (miners > 0) lore.add("<gray>캐는 사람 <white>" + miners + "명");
                lore.add("");
                boolean cur = here != null && here.n == l.n && inMine;
                if (module.pvpEnabled()) lore.add(MinePvpRules.LIFT_LORE);
                lore.add(cur ? "<dark_gray>지금 이 층에 있습니다" : "<yellow>클릭: 내려가기");
                Material icon = icon(l.n);
                var stack = Button.icon(icon, l.coloredName(), lore);
                if (cur) UiTheme.glint(stack, true);
                set(slots[i], stack, ctx -> {
                    ctx.player().closeInventory();
                    if (!cur) ride(ctx.player(), l);
                });
            }
            if (inMine) {
                set(0, Button.icon(Material.OAK_DOOR, "<#ffd36b>마을로", List.of("<gray>광산을 나가 마을로 올라갑니다.", "", "<yellow>클릭: 올라가기")),
                        ctx -> {
                            ctx.player().closeInventory();
                            rideUp(ctx.player());
                        });
            }
            set(8, UiTheme.close(), ctx -> ctx.player().closeInventory());
        }
    }

    static Material icon(int n) {
        return switch (n) {
            case 1 -> Material.RAW_COPPER;
            case 2 -> Material.RAW_IRON;
            case 3 -> Material.QUARTZ;
            case 4 -> Material.RAW_GOLD;
            case 5 -> Material.AMETHYST_SHARD;
            default -> Material.NETHERITE_SCRAP;
        };
    }

    /** "구리 광석 · 철 광석 · 은 광석" (많은 순, 층 번호 글자 없음). */
    String ores(MineLevel l) {
        List<String> out = new ArrayList<>();
        l.def.oreWeights().entrySet().stream().sorted((a, b) -> Integer.compare(b.getValue(), a.getValue()))
                .forEach(e -> out.add(MineVeins.name(module.mineDef().ores().get(e.getKey()))));
        return String.join(" · ", out);
    }

    // ── 타기 ────────────────────────────────────────────────────────────

    /** 그 층 승강장으로 (어디서든: 광산 안 · 구역 승강장 · /미궁 광산). */
    void ride(Player p, MineLevel l) {
        World w = module.world();
        if (w == null || !module.ready(l.n)) {
            Text.error(p, "광산을 짓는 중입니다. 잠시 뒤 다시 타 주세요.");
            return;
        }
        Location to = l.landing(w);
        go(p, to, "<" + l.def.titleColor() + ">" + Text.escape(l.def.name()), () -> {
            p.playSound(p.getLocation(), Sound.BLOCK_CHAIN_PLACE, 0.6f, 0.9f);
        });
    }

    /** 마을로: 구역 승강장 mine_exit → 마을 광장 → 주 월드 스폰. */
    void rideUp(Player p) {
        Location to = module.exitLocation();
        if (to == null) {
            Text.error(p, "올라갈 곳을 찾지 못했습니다.");
            return;
        }
        go(p, to, "<#ffd36b>마을", null);
    }

    /**
     * 타기: lift_seconds(2초) 어둠, 움직이면 멈춤. 0.3.7: PvP 구역에서 싸우는 중이면 (승강기 메뉴는 /미궁 광산·메인 메뉴로 광산 어디서든 열린다)
     * 마을로든 다른 층으로든 {@code death.penalty.combat_exit_seconds}(5초) 이상 걸리고, 그동안 맞아도 멈춘다 — 승강기로 싸움을 빠져나가지 못하게.
     * 승강기 블록은 안전 구역 한가운데라 거기서 타면 지금처럼 2초.
     */
    private void go(Player p, Location to, String subtitle, Runnable arrived) {
        if (riding(p)) return;
        double cast = module.pvp().exitCastSeconds(p);
        boolean combat = cast > 0;
        double secs = Math.max(module.config().liftSeconds(), cast);
        int ticks = (int) Math.round(secs * 20);
        Location start = p.getLocation().clone();
        long startHurt = module.pvp().combat().lastHurt(p.getUniqueId());
        if (combat) Text.send(p, String.format(java.util.Locale.ROOT, MinePvpRules.LIFT_CAST, kr.labyrinth.core.DeathPenaltyRules.seconds(secs)));
        if (ticks > 0) {
            p.addPotionEffect(new PotionEffect(PotionEffectType.BLINDNESS, ticks + 20, 0, false, false, false));
            p.playSound(p.getLocation(), Sound.ENTITY_MINECART_RIDING, 0.6f, 0.8f);
            p.playSound(p.getLocation(), Sound.BLOCK_CHAIN_PLACE, 0.5f, 0.7f);
            module.services().hud().actionBar(p, Text.mm("<gray>승강기가 움직입니다… <dark_gray>(" + (combat ? "움직이거나 맞으면" : "움직이면") + " 멈춤)"), ticks);
        }
        int[] t = {0};
        BukkitTask task = Bukkit.getScheduler().runTaskTimer(module.services().plugin(), () -> {
            if (!p.isOnline() || !p.getWorld().equals(start.getWorld())
                    || horizontal(p.getLocation(), start) > 0.36 || Math.abs(p.getLocation().getY() - start.getY()) > 1.5) {
                stop(p);
                if (p.isOnline()) {
                    p.removePotionEffect(PotionEffectType.BLINDNESS);
                    p.stopSound(Sound.ENTITY_MINECART_RIDING);
                    Text.error(p, "움직여서 승강기가 멈췄습니다.");
                }
                return;
            }
            if (combat && module.pvp().combat().lastHurt(p.getUniqueId()) > startHurt) {
                stop(p);
                p.removePotionEffect(PotionEffectType.BLINDNESS);
                p.stopSound(Sound.ENTITY_MINECART_RIDING);
                Text.error(p, MinePvpRules.LIFT_HIT);
                return;
            }
            if (++t[0] < ticks) return;
            stop(p);
            p.stopSound(Sound.ENTITY_MINECART_RIDING);
            p.setFallDistance(0);
            module.pvp().runBypassed(p, () -> kr.labyrinth.core.Teleports.to(p, to));
            p.removePotionEffect(PotionEffectType.BLINDNESS);
            p.showTitle(Title.title(Component.empty(), Text.mm(subtitle),
                    Title.Times.times(Duration.ofMillis(150), Duration.ofMillis(1600), Duration.ofMillis(500))));
            if (arrived != null) arrived.run();
            module.afterArrive(p);
        }, 1L, 1L);
        riding.put(p.getUniqueId(), task);
        if (combat) combatRides.add(p.getUniqueId());
    }

    private void stop(Player p) {
        BukkitTask t = riding.remove(p.getUniqueId());
        combatRides.remove(p.getUniqueId());
        if (t != null) t.cancel();
    }

    private static double horizontal(Location a, Location b) {
        double dx = a.getX() - b.getX(), dz = a.getZ() - b.getZ();
        return dx * dx + dz * dz;
    }
}
