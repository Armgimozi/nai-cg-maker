package kr.labyrinth.items;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageInterceptor;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.content.ArmorLook;
import kr.labyrinth.core.ArmorLooks;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Input;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerToggleSneakEvent;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 방어구 겉모습 4부위 효과의 런타임 (look_spec §1.3, items 모듈이 켬 — {@code services.looks()}).
 * <ul>
 *   <li><b>가죽 — 구르기</b>: 땅 위에서 웅크리기 키를 0.3초 안에 두 번 → 움직이던 방향으로 3.5칸 (방향 키가 없으면 뒤로 2칸),
 *       0.4초 동안 피할 수 있는 공격은 모두 회피({@link #tumbling} → DamageService), 5초에 한 번(주인 결정 D1). 판정은 순수
 *       {@link TumbleInput}. 다시 쓸 수 있게 되면 본인에게만 작은 가죽 소리. /스탯 에서 끌 수 있다 ({@link PlayerData#tumbleOff}).</li>
 *   <li><b>천 — 마나 보호막</b>: 받는 최종 피해의 20% 를 MP 가 대신 (MP 1 = 피해 2, MP 20% 아래면 쉼, 순수 {@link ManaShield}).
 *       무적·보호막 가로채기 뒤, 자동 부활 앞의 가로채기({@link DamageService#ORDER_MANA_SHIELD}, review2 C3) — 무적이면 MP 가 안 빠진다.</li>
 *   <li>판금 — 버팀은 파생 능력치(밀려남 저항 · 발 묶기 감소)로 바로 든다 — 여기서 할 일 없음.</li>
 * </ul>
 */
public final class ArmorLookService implements LookEffects, Listener, DamageInterceptor {

    /** ext 키: 처음 가죽 4부위를 입었을 때 한 번 알림. */
    static final String TUMBLE_HINT_KEY = "look.tumble_hint";
    /** ext 키: 0.3.5 겉모습 효과 접속 안내 (한 번). */
    static final String NOTICE_KEY = "look.notice_035";
    private static final long SHIELD_FX_MS = 300;

    private final Services services;
    private final Map<UUID, State> states = new ConcurrentHashMap<>();
    private BukkitTask task;

    private static final class State {
        final TumbleInput input = new TumbleInput();
        long tumblingUntil;
        long lastCombo = Long.MIN_VALUE;
        long lastShieldFx;
        boolean readyPending;
    }

    ArmorLookService(Services services) { this.services = services; }

    void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.damage().addInterceptor(this, DamageService.ORDER_MANA_SHIELD);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 10L, 5L);
    }

    void stop() {
        HandlerList.unregisterAll(this);
        services.damage().removeInterceptor(this);
        if (task != null) task.cancel();
        task = null;
        states.clear();
    }

    private State state(Player p) { return states.computeIfAbsent(p.getUniqueId(), u -> new State()); }

    private ArmorLooks cfg() { return services.settings().armorLooks(); }

    // ── LookEffects ──────────────────────────────────────────────────────

    @Override
    public boolean tumbling(Player player) {
        State s = player == null ? null : states.get(player.getUniqueId());
        return s != null && System.currentTimeMillis() < s.tumblingUntil;
    }

    @Override
    public void onSkill(Player player) {
        if (player != null && player.isSneaking()) state(player).lastCombo = System.currentTimeMillis();
    }

    // ── 가죽: 구르기 ─────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSneak(PlayerToggleSneakEvent e) {
        if (!e.isSneaking()) return;
        Player p = e.getPlayer();
        ArmorLooks cfg = cfg();
        if (!cfg.enabled()) return;
        DerivedStats st = services.stats().get(p);
        if (!st.full(ArmorLook.LIGHT)) return;
        State s = state(p);
        long now = System.currentTimeMillis();
        TumbleInput.Result r = s.input.onSneak(now, onGround(p), blocked(p), s.lastCombo, cfg.tumble());
        if (r == TumbleInput.Result.TUMBLE) tumble(p, s, cfg.tumble(), now);
    }

    /** 못 구르는 때: 끔 · 물속·헤엄·탈것·활공·비행·관전 · 기절·속박·빙결 (침묵은 됨 — 스킬이 아니다). */
    private boolean blocked(Player p) {
        if (services.data().get(p).tumbleOff()) return true;
        if (p.isInsideVehicle() || p.isGliding() || p.isFlying() || p.isSwimming() || p.isInWater() || p.isRiptiding()) return true;
        if (p.getGameMode() == GameMode.SPECTATOR) return true;
        var fx = services.effects();
        return fx.has(p, "stun") || fx.has(p, "root") || fx.has(p, "frozen");
    }

    /** 발밑이 막힌 블록인가 (바닐라 isOnGround 는 클라이언트가 보내는 값이라 쓰지 않음). */
    static boolean onGround(Player p) {
        return !p.getLocation().subtract(0, 0.08, 0).getBlock().isPassable();
    }

    private void tumble(Player p, State s, ArmorLooks.Tumble t, long now) {
        boolean f = false, b = false, l = false, r = false;
        try {
            Input in = p.getCurrentInput();
            f = in.isForward();
            b = in.isBackward();
            l = in.isLeft();
            r = in.isRight();
        } catch (Throwable ignored) {
            // 입력을 못 읽으면 뒤로
        }
        double[] dir = TumbleInput.direction(f, b, l, r, p.getLocation().getYaw(), t);
        double speed = TumbleInput.speedFor(dir[2]);
        p.setVelocity(new Vector(dir[0] * speed, 0.12, dir[1] * speed));
        s.tumblingUntil = now + Math.round(t.iframe() * 1000);
        s.readyPending = t.readySound();
        Location at = p.getLocation();
        p.getWorld().playSound(at, Sound.ENTITY_PLAYER_ATTACK_SWEEP, 0.35f, 1.7f);
        p.getWorld().spawnParticle(Particle.POOF, at.clone().add(0, 0.15, 0), 6, 0.3, 0.05, 0.3, 0.01);
    }

    // ── 천: 마나 보호막 ──────────────────────────────────────────────────

    @Override
    public double intercept(DamageContext ctx, double damage) {
        if (!(ctx.target() instanceof Player p) || !(damage > 0)) return damage;
        ArmorLooks cfg = cfg();
        if (!cfg.enabled() || !services.stats().get(p).full(ArmorLook.CLOTH)) return damage;
        var classes = services.classes();
        ManaShield.Split sp = ManaShield.split(damage, classes.mana(p), classes.maxMana(p), cfg.manaShield());
        if (!(sp.mpCost() > 0) || !classes.useMana(p, sp.mpCost())) return damage;
        State s = state(p);
        long now = System.currentTimeMillis();
        if (now - s.lastShieldFx >= SHIELD_FX_MS) {
            s.lastShieldFx = now;
            p.getWorld().spawnParticle(Particle.DUST, p.getLocation().add(0, 1.0, 0), 10, 0.35, 0.5, 0.35, 0,
                    new Particle.DustOptions(Color.fromRGB(0x9f, 0xd8, 0xff), 0.9f));
        }
        return sp.hpDamage();
    }

    // ── 타이머: 구르기 준비 소리 · 처음 알림 ──────────────────────────────

    private void tick() {
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                State s = states.get(p.getUniqueId());
                if (s != null && s.readyPending && now >= s.input.readyAt()) {
                    s.readyPending = false;
                    p.playSound(p, Sound.ITEM_ARMOR_EQUIP_LEATHER, 0.45f, 1.5f); // 본인에게만
                }
                if (!cfg().enabled() || !services.stats().get(p).full(ArmorLook.LIGHT)) continue;
                PlayerData d = services.data().get(p);
                if (Boolean.TRUE.equals(d.ext().get(TUMBLE_HINT_KEY)) || d.tumbleOff()) continue;
                d.ext().put(TUMBLE_HINT_KEY, true);
                d.markDirty();
                String c = cfg().color(ArmorLook.LIGHT);
                services.hud().actionBar(p, Text.mm("<" + c + ">가죽 4부위 · " + cfg().tumble().name() + "</" + c + "> <gray>웅크리기 두 번"
                        + " (/스탯 에서 끌 수 있음)"), 80);
            } catch (Throwable t) {
                Log.error("겉모습 타이머 오류", t);
            }
        }
    }

    // ── 접속 안내 (0.3.5 한 번) ───────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (!p.isOnline()) return;
            PlayerData d = services.data().get(p);
            if (Boolean.TRUE.equals(d.ext().get(NOTICE_KEY))) return;
            d.ext().put(NOTICE_KEY, true);
            d.markDirty();
            // 예전부터 하던 사람에게만 (처음 온 사람은 처음부터 이 규칙)
            if (cfg().enabled() && (d.classId() != null || d.level() > 1)) {
                Text.send(p, "<gray>방어구에 겉모습 효과가 생겼습니다. 판금·가죽·천의 장단점은 툴팁에서 보세요.");
            }
        }, 2L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) { states.remove(e.getPlayer().getUniqueId()); }
}
