package kr.souls.start;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Config;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.data.Profile;
import kr.souls.data.WorldState;
import kr.souls.item.WeaponGuard;
import kr.souls.progression.Origins;
import kr.souls.ui.OriginDialog;
import kr.souls.ui.SettingsDialog;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 처음 들어왔을 때의 차례 (1.3, 5.7, 5.10): 리소스팩을 다 싣고 → (세계 설정이 없거나 잠정이면 정할 사람에게) "세계를 정한다" 창 → 출신이
 * 없으면 "너는 누구였나" 창. 망가진 상태가 없게:
 * <ul>
 *   <li>세계 설정은 창을 띄우기 전에 잠정 기본값 (difficulty.default, pvp.default, confirmed=false) 으로 먼저 적는다 (검토 T5). 창을 닫으면
 *       잠정 그대로 게임을 하고, 정할 사람이 다음에 들어올 때와 화톳불에서 쉴 때 다시 묻는다.</li>
 *   <li>정하는 사람은 한 번에 하나 (chooser 잠금, 검토 T16). 나중에 들어온 사람은 기다리지 않고 잠정 설정으로 곧바로 출신 창으로 간다
 *       (검토 join-blocking). 정해지면 접속한 모두에게 알린다.</li>
 *   <li>출신 창을 닫으면 출신이 없는 채 시작 자리 둘레 (start.unborn-radius) 에서만 걷는다: 공격·구르기·우클릭·F·Q·물체·화톳불 입력은
 *       버리고 창을 다시 띄운다 (start.reopen-cooldown 에 한 번). 적과 다른 플레이어에게 맞지 않는다 (PvpGuard). 언제든 고르면 된다.</li>
 * </ul>
 * 창이 뜨는 때: 접속할 때 팩을 이미 실었으면 (설정 단계에서 보낸 판) 곧바로, 아니면 SUCCESSFULLY_LOADED 를 받고 start.pack-wait 틱 뒤
 * (검토 T14). 팩을 싣지 않으면 (선택 팩을 거절, 팩 꺼짐) 접속 start.no-pack-wait 틱 뒤에 바닐라 그림으로.
 */
public final class StartFlow implements Listener {
    private final Souls plugin;
    /** 지금 세계 설정 창을 보고 있는 사람 (한 번에 하나) */
    private UUID chooser;
    /** 이번 접속에서 차례를 시작한 사람 */
    private final Set<UUID> begun = new HashSet<>();
    /** 이 접속에서 출신을 지운 사람 (관리자 지우기·다시 고르기): 시험 봇이라도 자동으로 고르지 않고 창을 받는다 */
    private final Set<UUID> resetSinceJoin = new HashSet<>();
    /** 출신이 없는 사람에게 창을 다시 띄운 틱 */
    private final Map<UUID, Long> reopenAt = new HashMap<>();

    public StartFlow(Souls plugin) {
        this.plugin = plugin;
    }

    private Config.StartCfg cfg() {
        return plugin.cfg().start;
    }

    /** 켤 때: 시험 모드의 start.auto ("normal,off") 는 세계 설정이 없으면 그 값으로 확정한다 (봇 묶음이 창에 막히지 않게). */
    public void enable() {
        if (!plugin.cfg().testMode || cfg().auto().isBlank() || plugin.worldState().get() != null) return;
        String[] a = cfg().auto().split(",");
        String d = WorldState.normalize(a[0]);
        boolean pvp = a.length > 1 && List.of("on", "true", "1").contains(a[1].trim().toLowerCase(Locale.ROOT));
        if (!plugin.cfg().difficulties.containsKey(d)) d = plugin.cfg().difficultyDefault;
        apply(new WorldState.Settings(d, pvp, true, 1, null, "auto", System.currentTimeMillis(), "auto"), null);
    }

    // ------------------------------------------------------------------ 상태

    public boolean unborn(Player p) {
        return !plugin.profiles().of(p).born();
    }

    /** 세계 설정을 정할 수 있는 사람인가 (start.setup-by: first 면 처음 연 사람 또는 관리자, op 면 관리자만). */
    public boolean eligible(Player p) {
        if (p.isOp()) return true;
        if (!"first".equals(cfg().setupBy())) return false;
        WorldState.Settings s = plugin.worldState().get();
        return s == null || s.byId() == null || s.byId().equals(p.getUniqueId());
    }

    private boolean lockFree(Player p) {
        if (chooser == null || chooser.equals(p.getUniqueId())) return true;
        Player c = Bukkit.getPlayer(chooser);
        if (c == null || !c.isOnline() || !SettingsDialog.ID.equals(plugin.ui().openDialog(c))) {
            chooser = null;
            return true;
        }
        return false;
    }

    /** 잠정 설정이고 이 사람이 정할 사람이라 휴식 창에 "세계를 정한다" 를 보인다. */
    public boolean canSetNow(Player p) {
        WorldState.Settings s = plugin.worldState().get();
        return (s == null || !s.confirmed()) && eligible(p) && lockFree(p);
    }

    // ------------------------------------------------------------------ 접속

    @EventHandler(priority = EventPriority.LOW)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        // 능력치를 속성에 건다 (최대 HP 는 저장된 수정자, 이동 속도와 하트 배율은 접속마다)
        plugin.attributes().apply(p);
        begun.remove(p.getUniqueId());
        // 시험 봇: 접속하는 그 자리에서 출신을 정한다 (봇이 첫 명령을 보내기 전에 태어나 있게. 창 차례는 그대로 돈다)
        if (autoOrigin(p)) chooseOrigin(p, cfg().autoOrigin(), "auto");
        boolean packReady = plugin.hud().hasPack(p) || !plugin.cfg().pack.enabled() || !plugin.pack().ready();
        Bukkit.getScheduler().runTaskLater(plugin, () -> begin(p, "pack"), packReady ? cfg().packWait() : cfg().noPackWait());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onPack(PlayerResourcePackStatusEvent e) {
        if (e.getStatus() != PlayerResourcePackStatusEvent.Status.SUCCESSFULLY_LOADED) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> begin(p, "loaded"), cfg().packWait());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        begun.remove(id);
        reopenAt.remove(id);
        resetSinceJoin.remove(id);
        if (id.equals(chooser)) chooser = null;
    }

    /**
     * 시험 모드의 start.auto-origin: 이름이 start.auto-names 의 앞머리 (기본 Souls = 시험 봇) 로 시작하는 사람은 출신을 묻지 않고 그것으로 고른다. 출신 창 자체를
     * 시험하는 봇은 /souls origin reset 으로 출신을 지운 뒤 창을 받는다 (지운 뒤에는 이 자동 고르기를 하지 않는다: 접속할 때만 본다).
     */
    private boolean autoOrigin(Player p) {
        String auto = cfg().autoOrigin();
        return plugin.cfg().testMode && !auto.isBlank() && cfg().autoName(p.getName()) && plugin.origins().get(auto) != null
                && unborn(p) && !resetSinceJoin.contains(p.getUniqueId());
    }

    /** 차례를 시작한다 (접속마다 한 번). */
    public void begin(Player p, String why) {
        if (!p.isOnline() || !begun.add(p.getUniqueId())) return;
        WorldState.Settings s = plugin.worldState().get();
        if (s == null) {
            // 창을 띄우기 전에 잠정 기본값을 먼저 적는다 (창의 답이 오지 않아도 설정 없는 세계가 남지 않게)
            boolean mine = eligible(p);
            s = new WorldState.Settings(plugin.cfg().difficultyDefault, plugin.cfg().pvp.def(), false, 0,
                    mine ? p.getUniqueId().toString() : null, mine ? p.getName() : null, System.currentTimeMillis(), "default");
            apply(s, null);
            if (mine && lockFree(p)) {
                showSettings(p, "fresh");
                return;
            }
        } else if (!s.confirmed() && eligible(p) && lockFree(p)) {
            showSettings(p, "unconfirmed");
            return;
        }
        if (!s.confirmed() && !eligible(p)) {
            Component waitWhy = "op".equals(cfg().setupBy()) ? Lang.c(p, "start.op-only") : Lang.c(p, "start.waiting");
            plugin.titles().notice(p, plugin.ticker().now(), waitWhy);
        }
        originStep(p);
    }

    private void showSettings(Player p, String reason) {
        chooser = p.getUniqueId();
        plugin.test(p, "START_DIALOG who=" + p.getName() + " reason=" + reason + " t=" + plugin.ticker().now());
        SettingsDialog.show(plugin, p);
    }

    /** 세계 설정 창을 (관리자·휴식 창이) 띄운다. 다른 사람이 보고 있으면 false. */
    public boolean openSettings(Player p, String reason) {
        if (!lockFree(p)) return false;
        showSettings(p, reason);
        return true;
    }

    /** 출신 단계: 출신이 없으면 창, 있으면 바뀐 설정 알림과 그 사이 새로 만들 수 있게 된 시작 아이템. */
    public void originStep(Player p) {
        Profile pr = plugin.profiles().of(p);
        WorldState.Settings s = plugin.worldState().get();
        if (!pr.born()) {
            if (autoOrigin(p)) {
                chooseOrigin(p, cfg().autoOrigin(), "auto");
                return;
            }
            p.sendMessage(notice(p, s));
            if (s != null && !s.confirmed()) p.sendMessage(Lang.c(p, "start.provisional-chat"));
            plugin.test(p, "START_NOTICE to=" + p.getName() + " " + (s == null ? "-" : s.line()));
            OriginDialog.show(plugin, p);
            return;
        }
        if (s != null && pr.settingsSeen() < s.rev()) {
            p.sendMessage(Lang.c(p, "start.changed", "difficulty", diffName(p, s.difficulty()), "pvp", pvpName(p, s.pvp())));
            pr.setSettingsSeen(s.rev());
        }
        Origins.Origin o = plugin.origins().get(pr.origin());
        if (o != null) {
            List<String> late = Origins.grant(p, o, pr, plugin.weapons());
            if (!late.isEmpty()) {
                plugin.test(p, "KIT_LATE given=" + String.join(",", late));
                afterKit(p);
            }
        }
        plugin.profiles().save(p, false);
    }

    /** "이 세계: 보통 · PvP 끔" */
    public Component notice(Player p, WorldState.Settings s) {
        String d = s == null ? plugin.cfg().difficultyDefault : s.difficulty();
        boolean pvp = s == null ? plugin.cfg().pvp.def() : s.pvp();
        return Lang.c(p, "start.notice", "difficulty", diffName(p, d), "pvp", pvpName(p, pvp));
    }

    public static Component diffName(Player p, String id) {
        return Lang.c(p, "difficulty." + id + ".name"); // lang-dyn: difficulty.*.name
    }

    public static Component pvpName(Player p, boolean on) {
        return on ? Lang.c(p, "pvp.on") : Lang.c(p, "pvp.off");
    }

    // ------------------------------------------------------------------ 세계 설정

    /** 세계 설정 창의 난이도 단추 (via=dialog), 시험 명령, 관리자 명령 (via=command). difficulty 는 config 의 난이도 id 만. */
    public boolean chooseSettings(Player p, String difficulty, boolean pvp, String via) {
        String d = WorldState.normalize(difficulty);
        if (!plugin.cfg().difficulties.containsKey(d)) {
            plugin.test(p, "SETTINGS_DENY why=unknown difficulty=" + difficulty);
            return false;
        }
        WorldState.Settings old = plugin.worldState().get();
        int rev = old == null ? 1 : old.rev() + 1;
        WorldState.Settings s = new WorldState.Settings(d, pvp, true, rev, p == null ? null : p.getUniqueId().toString(),
                p == null ? "console" : p.getName(), System.currentTimeMillis(), via);
        if (p != null && p.getUniqueId().equals(chooser)) chooser = null;
        apply(s, p);
        if (p != null && "dialog".equals(via)) {
            if (unborn(p)) originStep(p);
            else plugin.ui().close(p);
        }
        return true;
    }

    /** 세계 설정 창을 닫았다 (Esc, "나중에 정한다"): 잠정 그대로, 출신 단계로. */
    public void settingsLater(Player p) {
        WorldState.Settings old = plugin.worldState().get();
        if (old == null || !old.confirmed()) {
            WorldState.Settings s = new WorldState.Settings(old == null ? plugin.cfg().difficultyDefault : old.difficulty(),
                    old == null ? plugin.cfg().pvp.def() : old.pvp(), false, old == null ? 0 : old.rev(), p.getUniqueId().toString(), p.getName(),
                    System.currentTimeMillis(), "esc");
            plugin.worldState().set(plugin.worlds().world(), s);
            plugin.test(p, "SETTINGS " + s.line());
        }
        if (p.getUniqueId().equals(chooser)) chooser = null;
        plugin.titles().notice(p, plugin.ticker().now(), Lang.c(p, "start.provisional"));
        if (unborn(p)) originStep(p);
        else plugin.ui().close(p);
    }

    /** 세계 설정을 적고 듣게 한다: 바닐라 pvp 규칙, 접속한 모두에게 알림 (확정이면). */
    private void apply(WorldState.Settings s, Player by) {
        WorldState.Settings old = plugin.worldState().get();
        plugin.worldState().set(plugin.worlds().world(), s);
        plugin.worlds().applyPvp();
        plugin.test(by, "SETTINGS " + s.line());
        if (!s.confirmed()) return;
        boolean changed = old != null && old.confirmed();
        for (Player o : Bukkit.getOnlinePlayers()) {
            Component line = changed
                    ? Lang.c(o, "start.changed", "difficulty", diffName(o, s.difficulty()), "pvp", pvpName(o, s.pvp()))
                    : notice(o, s);
            plugin.titles().notice(o, plugin.ticker().now(), line);
            o.sendMessage(line);
            Profile pr = plugin.profiles().of(o);
            if (pr.born()) pr.setSettingsSeen(s.rev());
        }
    }

    // ------------------------------------------------------------------ 출신

    /** 출신 확인 창의 "이 출신으로" (via=dialog), 시험 명령, 시험 서버의 auto. 이미 출신이 있으면 거절 (ORIGIN_DENY why=chosen). */
    public boolean chooseOrigin(Player p, String id, String via) {
        Profile pr = plugin.profiles().of(p);
        if (pr.born()) {
            plugin.test(p, "ORIGIN_DENY why=chosen origin=" + pr.origin() + " t=" + plugin.ticker().now());
            plugin.ui().close(p);
            return false;
        }
        Origins.Origin o = plugin.origins().get(id);
        if (o == null) {
            plugin.test(p, "ORIGIN_DENY why=unknown id=" + id);
            return false;
        }
        pr.setOrigin(o.id(), System.currentTimeMillis());
        pr.setStats(o.stats());
        WorldState.Settings s = plugin.worldState().get();
        if (s != null) pr.setSettingsSeen(s.rev());
        List<String> given = Origins.grant(p, o, pr, plugin.weapons());
        plugin.attributes().apply(p);
        p.setHealth(kr.souls.skill.Combat.maxHealth(p));
        plugin.stamina().refill(p);
        plugin.ui().close(p);
        afterKit(p);
        plugin.profiles().save(p, true);
        plugin.test(p, "ORIGIN id=" + o.id() + " level=" + o.level() + " kit=" + (given.isEmpty() ? "-" : String.join(",", given))
                + " pending=" + String.join(",", Origins.pending(o, pr, plugin.weapons())) + " via=" + via + " t=" + plugin.ticker().now());
        return true;
    }

    /** 시작 아이템을 준 뒤: 막기 성분 다시 맞추기, 무게 다시 셈하기. */
    private void afterKit(Player p) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (!p.isOnline()) return;
            new WeaponGuard(plugin).refresh(p);
            plugin.load().refresh(p);
        });
    }

    /** 출신 창을 닫았다 (Esc, "나중에 고른다"). */
    public void originLater(Player p) {
        reopenAt.put(p.getUniqueId(), plugin.ticker().now());
        plugin.titles().notice(p, plugin.ticker().now(), Lang.c(p, "origin.none"));
        plugin.test(p, "ORIGIN_LATER t=" + plugin.ticker().now());
    }

    /** 출신이 없는 사람이 무엇을 하려 했다: 버리고 창을 다시 띄운다 (start.reopen-cooldown 에 한 번). */
    public void reopen(Player p, String why) {
        long now = plugin.ticker().now();
        Long last = reopenAt.get(p.getUniqueId());
        if (plugin.ui().open(p) || (last != null && now - last < cfg().reopenCooldown())) return;
        reopenAt.put(p.getUniqueId(), now);
        plugin.test(p, "ORIGIN_REOPEN why=" + why + " t=" + now);
        if (chooser != null && chooser.equals(p.getUniqueId())) SettingsDialog.show(plugin, p);
        else OriginDialog.show(plugin, p);
    }

    /**
     * 출신 다시 고르기 (휴식 창, 아직 레벨을 하나도 올리지 않았을 때 한 번. 검토 caster-trap): 시작 아이템을 거두고 출신·능력치·장부를
     * 지운 뒤 (소울은 남긴다) 출신 창을 띄운다.
     */
    public boolean repick(Player p) {
        Profile pr = plugin.profiles().of(p);
        Origins.Origin o = plugin.origins().get(pr.origin());
        if (o == null || pr.stats().level() != o.level()) {
            plugin.test(p, "REPICK_DENY why=" + (o == null ? "no_origin" : "leveled"));
            return false;
        }
        int items = Origins.removeSoulsItems(p);
        plugin.profiles().reset(p, true);
        plugin.attributes().apply(p);
        plugin.load().refresh(p);
        plugin.profiles().save(p, true);
        resetSinceJoin.add(p.getUniqueId());
        plugin.test(p, "REPICK from=" + o.id() + " items=" + items);
        OriginDialog.show(plugin, p);
        return true;
    }

    /** 관리자의 출신 지우기 (5.10): 출신·능력치 (모두 10)·소울 (0)·장부를 지우고, keepItems 가 아니면 souls 아이템을 거둔다. */
    public int resetOrigin(Player target, String by, boolean keepItems) {
        int items = keepItems ? 0 : Origins.removeSoulsItems(target);
        plugin.profiles().reset(target, false);
        plugin.attributes().apply(target);
        plugin.load().refresh(target);
        plugin.hud().invalidate(target);
        plugin.profiles().save(target, true);
        plugin.getLogger().info("출신 지우기: " + target.getName() + " (by " + by + ", 거둔 아이템 " + items + (keepItems ? ", keep-items: 다시 고르면 아이템이 겹친다" : "") + ")");
        resetSinceJoin.add(target.getUniqueId());
        plugin.test(target, "ORIGIN_RESET who=" + target.getName() + " by=" + by + " items=" + items);
        reopenAt.remove(target.getUniqueId());
        OriginDialog.show(plugin, target);
        return items;
    }

    // ------------------------------------------------------------------ 출신이 없는 사람의 입력

    @EventHandler(priority = EventPriority.LOWEST)
    public void onAttack(PrePlayerAttackEntityEvent e) {
        if (unborn(e.getPlayer())) {
            e.setCancelled(true);
            reopen(e.getPlayer(), "attack");
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onInteract(PlayerInteractEvent e) {
        if (e.getAction() == Action.PHYSICAL || !unborn(e.getPlayer())) return;
        e.setCancelled(true);
        reopen(e.getPlayer(), e.getAction().isLeftClick() ? "attack" : "use");
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onInteractEntity(PlayerInteractEntityEvent e) {
        if (!unborn(e.getPlayer())) return;
        e.setCancelled(true);
        reopen(e.getPlayer(), "use");
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onSwap(PlayerSwapHandItemsEvent e) {
        if (!unborn(e.getPlayer())) return;
        e.setCancelled(true);
        reopen(e.getPlayer(), "swap");
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onDrop(PlayerDropItemEvent e) {
        if (!unborn(e.getPlayer())) return;
        e.setCancelled(true);
        reopen(e.getPlayer(), "drop");
    }

    /** 출신이 없는 사람은 시작 자리 둘레에서만 걷는다 (정찰·레버·줍기를 막는다, 검토 unborn-exploit). */
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onMove(PlayerMoveEvent e) {
        int r = cfg().unbornRadius();
        if (r <= 0 || !e.hasChangedBlock() || !unborn(e.getPlayer())) return;
        Player p = e.getPlayer();
        if (!plugin.worlds().isGameWorld(p.getWorld())) return;
        Location home = plugin.worlds().roomSpawn();
        Location to = e.getTo();
        if (home.getWorld() == null || !home.getWorld().equals(to.getWorld())) return;
        double dx = to.getX() - home.getX(), dz = to.getZ() - home.getZ();
        if (dx * dx + dz * dz <= (double) r * r) return;
        Location back = e.getFrom().clone();
        back.setYaw(to.getYaw());
        back.setPitch(to.getPitch());
        e.setTo(back);
        reopen(p, "walk");
    }
}
