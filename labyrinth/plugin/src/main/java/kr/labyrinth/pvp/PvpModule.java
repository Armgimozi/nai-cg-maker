package kr.labyrinth.pvp;

import com.mojang.brigadier.Command;
import io.papermc.paper.command.brigadier.Commands;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
import org.bukkit.scheduler.BukkitTask;

/**
 * PvP = 따로 신청하는 대전 없이 <b>파티 규칙</b> 하나 (GDD §18): 같은 파티원끼리는 야생·마을·미궁 어디서든 서로 피해를 줄 수 없고,
 * 그 밖의 플레이어끼리는 피해를 줄 수 있다. config {@code pvp:} (켜기 · 피해 배율 · 한 방 상한 · 마을 안전지대 · 파티원 이름표 색).
 * <ul>
 *   <li>{@link TargetFilter} 를 config 를 따르는 {@link DefaultTargetFilter} 로 교체 → 근접·화살(CombatListener)·직업 스킬·
 *       무기 스킬·장판이 모두 같은 규칙</li>
 *   <li>DamageService 훅: 같은 파티원 피해 차단(늦게 도착한 지속 피해 등) · 플레이어끼리 배율 · 한 방 상한 · 마지막 피해 기록</li>
 *   <li>{@link PvpListener}: 바닐라 경로(물약·잔류 구름·발화·폭발·늑대·낚싯대) · 죽음 메시지 · 월드 PvP 스위치</li>
 *   <li>1초마다: 파티원 이름표 초록색(보는 사람 기준) · 모든 월드의 바닐라 PvP 게임 규칙을 config 와 맞춤</li>
 * </ul>
 */
public final class PvpModule implements Module {

    /** "PvP" 액션바를 다시 보여 주기까지 조용해야 하는 시간. */
    static final long NOTICE_QUIET_MS = 15_000;
    /**
     * 죽음 메시지용 "막타" 판정 시간. 사망은 피해를 적용하는 그 자리(같은 틱)에서 일어나므로 아주 짧게 —
     * PvP 로 맞고 몇 초 뒤 낙사한 것 같은 죽음은 바닐라 메시지 그대로 둔다.
     */
    static final long KILLING_BLOW_MS = 250;

    /** 죽음 메시지용 마지막 PvP 피해. */
    record Hit(UUID attacker, String attackerName, String label, double amount, long at) {}

    private final Services services;
    private final VillageZone zone = new VillageZone();
    private final Map<UUID, Long> lastCombat = new ConcurrentHashMap<>();
    private final Map<UUID, Hit> lastHit = new ConcurrentHashMap<>();
    private volatile PvpConfig config = PvpConfig.OFF;
    private PvpListener listener;
    private DamageService.Hook hook;
    private BukkitTask task;

    public PvpModule(Services services) { this.services = services; }

    @Override
    public String name() { return "pvp"; }

    @Override
    public void enable() {
        loadConfig();
        services.setTargets(new PartyTargetFilter(services, this));
        listener = new PvpListener(services, this);
        Bukkit.getPluginManager().registerEvents(listener, services.plugin());
        hook = new PvpHook();
        services.damage().addHook(hook);
        applyWorldRules(true);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 20L, 20L);
        services.commands().addSubcommand("labadmin", Commands.literal("pvp").executes(c -> {
            CommandService.safeRun(c, () -> status(c.getSource().getSender()));
            return Command.SINGLE_SUCCESS;
        }));
        Log.info(config.enabled()
                ? "PvP 켜짐: 같은 파티원끼리는 피해 없음, 그 밖의 플레이어끼리 피해 ×" + config.damageMultiplier()
                        + " (한 번에 최대 HP " + Math.round(config.maxHitRatio() * 100) + "%까지)"
                        + (config.safeZoneVillage() ? ", 마을 안 금지" : "")
                : "PvP 꺼짐 (config pvp.enabled: false) — 플레이어끼리 서로 피해를 줄 수 없습니다.");
    }

    @Override
    public void disable() {
        if (task != null) task.cancel();
        task = null;
        if (listener != null) HandlerList.unregisterAll(listener);
        listener = null;
        if (hook != null) services.damage().removeHook(hook);
        hook = null;
        services.setTargets(new DefaultTargetFilter(services));
        lastCombat.clear();
        lastHit.clear();
    }

    @Override
    public void reload() {
        loadConfig();
        zone.invalidate();
        applyWorldRules(true);
    }

    private void loadConfig() {
        config = PvpConfig.from(services.plugin().getConfig().getConfigurationSection("pvp"));
    }

    PvpConfig config() { return config; }

    boolean inSafeZone(Location l) {
        PvpConfig c = config;
        return c.safeZoneVillage() && zone.contains(l, c.safeZoneMargin());
    }

    /** /labadmin pvp — 지금 규칙·배율·안전지대·월드별 PvP 게임 규칙 (콘솔 가능). */
    void status(CommandSender to) {
        PvpConfig c = config;
        to.sendMessage(Text.mm(Text.PREFIX + "<white>PvP " + (c.enabled() ? "<green>켜짐" : "<red>꺼짐")
                + "</white> <gray>— 같은 파티원끼리는 어디서든 피해 없음, 그 밖의 플레이어끼리는 피해 가능"));
        to.sendMessage(Text.mm("<gray> 플레이어끼리 피해 ×" + c.damageMultiplier() + " · 한 번에 최대 HP "
                + Text.pct(c.maxHitRatio()) + " · 파티원 이름표 초록 " + (c.partyNameColor() ? "켬" : "끔")));
        VillageZone.Zone z = c.safeZoneVillage() ? zone.current(c.safeZoneMargin()) : null;
        to.sendMessage(Text.mm("<gray> 마을 안전지대: " + (!c.safeZoneVillage() ? "끔 (safe_zone_village: false)"
                : z == null ? "없음 (주 월드 폴더에 " + VillageZone.FILE + " 없음)"
                : "중심 (" + Math.round(z.x()) + ", " + Math.round(z.z()) + ") 반경 " + Math.round(z.radius()) + "칸")));
        StringBuilder worlds = new StringBuilder();
        for (World w : Bukkit.getWorlds()) {
            Boolean v = w.getGameRuleValue(GameRules.PVP);
            worlds.append(worlds.isEmpty() ? "" : " · ").append(w.getName()).append(' ').append(Boolean.TRUE.equals(v) ? "켬" : "끔");
        }
        to.sendMessage(Text.mm("<gray> 월드 PvP 게임 규칙: " + Text.escape(worlds.toString())
                + " · 판정 " + services.targets().getClass().getSimpleName()));
    }

    // ── 월드 PvP 스위치 ───────────────────────────────────────────────────

    /** 모든 월드(labyrinth_world 포함)의 바닐라 PvP 게임 규칙 = pvp.enabled. server.properties 를 몰라도 된다. */
    void applyWorldRules(boolean log) {
        for (World w : Bukkit.getWorlds()) applyWorldRule(w, log);
    }

    void applyWorldRule(World w, boolean log) {
        boolean want = config.enabled();
        try {
            Boolean cur = w.getGameRuleValue(GameRules.PVP);
            if (cur != null && cur == want) return;
            w.setGameRule(GameRules.PVP, want);
        } catch (Throwable t) {
            Log.warnOnce("pvp-rule:" + w.getName(), "월드 " + w.getName() + " 의 PvP 규칙을 바꾸지 못했습니다: " + t.getMessage());
            return;
        }
        if (log) Log.info("월드 " + w.getName() + " PvP " + (want ? "켬" : "끔") + " (config pvp.enabled)");
    }

    // ── 1초마다 ───────────────────────────────────────────────────────────

    private void tick() {
        try {
            applyWorldRules(false);
            syncNameTags();
        } catch (Throwable t) {
            Log.error("PvP 갱신 오류", t);
        }
    }

    /** 내 화면에서 파티원 이름표(·탭 목록 이름)를 초록색으로. 파티가 바뀌면 1초 안에 따라간다. */
    private void syncNameTags() {
        boolean on = config.partyNameColor();
        var online = Bukkit.getOnlinePlayers();
        if (online.size() < 2) return;
        for (Player viewer : online) {
            for (Player target : online) {
                if (viewer.equals(target)) continue;
                boolean mate = on && services.party().partyOf(viewer).isPresent() && services.party().sameParty(viewer, target);
                services.hud().nameTagColor(viewer, target, mate ? NamedTextColor.GREEN : null);
            }
        }
    }

    // ── 알림 · 기록 ───────────────────────────────────────────────────────

    /** 다른 파티 플레이어와 처음(15초 넘게 조용하다가) 싸우기 시작하면 양쪽 액션바에 짧게 "PvP". */
    void noticeHit(Player attacker, Player victim) {
        long now = System.currentTimeMillis();
        notice(attacker, now, "<#ff6b6b><b>⚔ PvP</b></#ff6b6b> <gray>" + Text.escape(victim.getName()) + " 님을 공격했습니다");
        notice(victim, now, "<#ff6b6b><b>⚔ PvP</b></#ff6b6b> <gray>" + Text.escape(attacker.getName()) + " 님이 공격합니다!");
    }

    private void notice(Player p, long now, String mm) {
        Long last = lastCombat.put(p.getUniqueId(), now);
        if (last != null && now - last < NOTICE_QUIET_MS) return;
        services.hud().actionBar(p, Text.mm(mm), 40);
    }

    void recordHit(Player attacker, Player victim, String label, double amount) {
        lastHit.put(victim.getUniqueId(), new Hit(attacker.getUniqueId(), attacker.getName(), label, amount, System.currentTimeMillis()));
    }

    /** 방금(같은 틱) 들어간 PvP 피해 — 이 피해로 쓰러졌으면 죽음 메시지에 쓴다. */
    Hit killingBlow(Player victim) {
        Hit h = lastHit.get(victim.getUniqueId());
        return h != null && System.currentTimeMillis() - h.at() <= KILLING_BLOW_MS ? h : null;
    }

    void forget(UUID u) {
        lastCombat.remove(u);
        lastHit.remove(u);
    }

    /** 피해 출처 이름 (죽음 메시지): 직업 스킬 · 무기 스킬 · 들고 있던 무기 · 피해 유형. */
    String label(DamageContext ctx, Player attacker) {
        String id = ctx.sourceId();
        if (id != null && !id.isBlank()) {
            if (id.startsWith("effect:")) {
                return switch (id.substring(7)) {
                    case "poison", "venom" -> "독";
                    case "bleed" -> "출혈";
                    case "burn" -> "화상";
                    case "infection" -> "감염";
                    default -> "지속 피해";
                };
            }
            if (id.startsWith("mech:")) {
                String[] parts = id.split(":");
                ItemDef item = parts.length > 1 ? services.content().item(parts[1]) : null;
                if (item != null) {
                    var ws = parts.length > 2 ? item.weaponSkill(parts[2]) : null;
                    return Text.strip(ws != null && ws.name() != null && !ws.name().isBlank() ? ws.name() : item.name());
                }
            }
            for (ClassDef c : services.content().classes().values()) {
                for (ClassDef.SkillDef s : c.skills()) if (id.equals(s.id())) return Text.strip(s.name());
            }
            ItemDef held = services.items().heldWeapon(attacker);
            if (held != null) {
                for (ItemDef.WeaponSkillDef ws : held.weaponSkills()) {
                    if (id.equals(ws.id()) && ws.name() != null && !ws.name().isBlank()) return Text.strip(ws.name());
                }
            }
            if (ctx.isSkill()) return "스킬";
        }
        if (ctx.type() == DamageType.MELEE) {
            ItemDef held = services.items().heldWeapon(attacker);
            return held != null ? Text.strip(held.name()) : "근접 공격";
        }
        return switch (ctx.type()) {
            case RANGED -> "원거리 공격";
            case MAGIC -> "마법";
            case TRUE -> "지속 피해";
            default -> "공격";
        };
    }

    // ── DamageService 훅 ──────────────────────────────────────────────────

    /** 플레이어 → 다른 플레이어 피해에만 끼어든다 (몹·보스 피해는 그대로). */
    private final class PvpHook implements DamageService.Hook {

        /** 다른 피해를 옮겨 받는 피해 (배율 중복 방지). */
        private static final java.util.Set<String> RELAYED = java.util.Set.of("guardian_oath");

        private Player victimOf(DamageContext ctx) {
            Player a = ctx.attackerPlayer();
            return a != null && ctx.target() instanceof Player v && !a.equals(v) ? v : null;
        }

        @Override
        public boolean allow(DamageContext ctx) {
            Player v = victimOf(ctx);
            return v == null || services.targets().isEnemy(ctx.attackerPlayer(), v);
        }

        @Override
        public void before(DamageContext ctx) {
            // 수호의 맹세(피해 나눠 받기)는 이미 배율이 적용된 피해를 옮겨 받는 것이라 다시 줄이지 않는다
            if (victimOf(ctx) != null && !RELAYED.contains(ctx.sourceId())) ctx.amount(ctx.amount() * config.damageMultiplier());
        }

        @Override
        public double absorb(DamageContext ctx, double dmg) {
            Player v = victimOf(ctx);
            if (v == null) return dmg;
            if (config.maxHitRatio() < 1.0) dmg = Math.min(dmg, services.damage().maxHp(v) * config.maxHitRatio());
            // 적용 직전에 기록: 쓰러지면 PlayerDeathEvent 가 적용 도중에 오므로 after() 로는 늦다
            Player a = ctx.attackerPlayer();
            recordHit(a, v, label(ctx, a), dmg);
            return dmg;
        }

        @Override
        public void after(DamageContext ctx) {
            Player v = victimOf(ctx);
            if (v == null || ctx.cancelled() || ctx.evaded()) return;
            noticeHit(ctx.attackerPlayer(), v);
        }
    }

    /** config 를 따르는 적/아군 판정 (규칙 = {@link PvpRules}). */
    static final class PartyTargetFilter extends DefaultTargetFilter {
        private final PvpModule module;

        PartyTargetFilter(Services services, PvpModule module) {
            super(services);
            this.module = module;
        }

        @Override
        public PvpConfig pvpConfig() { return module.config(); }

        @Override
        public boolean inSafeZone(Location location) { return module.inSafeZone(location); }
    }
}
