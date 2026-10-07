package kr.augsky.vfx;

import kr.augsky.AugSky;
import kr.augsky.mob.MobDef;
import kr.augsky.skill.Mechanics;
import kr.augsky.skill.SkillContext;
import kr.augsky.skill.SkillDef;
import kr.augsky.skill.Targets;
import kr.augsky.weapon.WeaponDef;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerResourcePackStatusEvent;
import org.bukkit.event.world.EntitiesUnloadEvent;
import org.bukkit.event.world.WorldUnloadEvent;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Set;
import java.util.UUID;
import java.util.function.IntConsumer;

/**
 * 스킬 연출 서비스. 시전마다 CastFx 를 만들고, 띄운 표시 엔티티(조각)를 한 곳에서 매 틱 움직이고 지운다.
 * 판정·피해·재사용 대기는 전혀 건드리지 않는다. 연출 쪽 오류는 여기서 삼켜 기술이 멈추지 않게 한다.
 */
public final class Vfx implements Listener {
    public static final String TAG = "augsky_vfx";
    static final int GLOBAL_SPRITES = 200;
    static final int TELE_RESERVE = 30;

    final AugSky plugin;
    final Models models;
    private BukkitTask task;
    long tick;
    int decalSeq;

    private List<Sprite> live = new ArrayList<>();
    final Map<UUID, Sprite> byId = new HashMap<>();
    private final Set<Entity> adopted = new HashSet<>();
    private final PriorityQueue<Job> queue = new PriorityQueue<>();
    private long jobSeq;

    private final Set<UUID> packOk = new HashSet<>();
    final Map<UUID, Integer> visCount = new HashMap<>();
    final Map<UUID, Long> lastFlash = new HashMap<>();
    /** 지금 진행 중인 보스 예고 자리. 이 안에서는 플레이어 연출을 어둡게 해 예고가 묻히지 않게 한다 */
    final List<TeleZone> teleZones = new ArrayList<>();
    private final Map<String, Long> logAt = new HashMap<>();

    private List<Viewer> viewers = List.of();
    private long viewersAt = -1;
    private Map<String, WeaponDef> bySkill = new HashMap<>();
    private long bySkillAt = -100000;

    private boolean enabled, sprites, assumePack, debug;
    private double density;

    record TeleZone(Footprint f, long until) {}

    private record Job(long due, long seq, Runnable r) implements Comparable<Job> {
        @Override
        public int compareTo(Job o) {
            return due != o.due ? Long.compare(due, o.due) : Long.compare(seq, o.seq);
        }
    }

    /** 이번 틱의 보는 사람 정보 (눈 위치·시선·팩 여부, 이번 틱 받은 입자 패킷 수) */
    public static final class Viewer {
        public final Player p;
        public final UUID id;
        public final World w;
        public final Vector eye, look;
        public final boolean pack;
        int pk;

        Viewer(Player p, boolean pack) {
            this.p = p;
            this.id = p.getUniqueId();
            this.w = p.getWorld();
            Location e = p.getEyeLocation();
            this.eye = e.toVector();
            this.look = e.getDirection();
            this.pack = pack;
        }

        public double dist2(Location l) {
            double dx = l.getX() - eye.getX(), dy = l.getY() - eye.getY(), dz = l.getZ() - eye.getZ();
            return dx * dx + dy * dy + dz * dz;
        }
    }

    public Vfx(AugSky plugin) {
        this.plugin = plugin;
        this.models = new Models(plugin);
        reloadSettings();
    }

    public void reloadSettings() {
        var c = plugin.getConfig();
        enabled = c.getBoolean("vfx.enabled", true);
        density = Math.max(0.3, Math.min(1.5, c.getDouble("vfx.density", 1.0)));
        // 기본은 입자로만 그린다 (팩 그림 조각은 리소스팩에 이펙트 모델이 있을 때만 켤 수 있다)
        sprites = c.getBoolean("vfx.sprites", false) && c.getBoolean("resource-pack.custom-models", true)
                && c.getBoolean("resource-pack.enabled", true);
        assumePack = c.getBoolean("vfx.assume-pack", false);
        debug = c.getBoolean("vfx.debug", false);
    }

    public void start() {
        plugin.getServer().getPluginManager().registerEvents(this, plugin);
        task = Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 1, 1);
        // 서버가 갑자기 꺼져 남은 조각을 지운다 (저장하지 않지만, 다시 읽기 등으로 남을 수 있다)
        Bukkit.getScheduler().runTask(plugin, this::sweep);
        plugin.getLogger().info("스킬 연출: 이펙트 모델 " + models.count() + "개" + (enabled ? "" : " (꺼짐)"));
    }

    private void sweep() {
        int n = 0;
        for (World w : Bukkit.getWorlds()) {
            for (Display d : w.getEntitiesByClass(Display.class)) {
                if (byId.containsKey(d.getUniqueId()) || adopted.contains(d)) continue;
                Set<String> tags = d.getScoreboardTags();
                if (tags.contains(TAG) || tags.contains(Mechanics.FX_TAG)) {
                    d.remove();
                    n++;
                }
            }
        }
        if (n > 0) plugin.getLogger().info("남아 있던 스킬 연출 조각 " + n + "개를 지웠습니다");
    }

    /** onDisable 맨 끝에서 부른다. 플러그인이 이미 꺼진 상태라 hide/show 는 쓰지 않고 지우기만 한다 */
    public void shutdown() {
        if (task != null) task.cancel();
        for (Sprite s : live) {
            try {
                if (s.e != null) s.e.remove();
            } catch (Throwable ignored) {
                // 하나 실패해도 나머지는 지운다
            }
        }
        for (Entity e : adopted) {
            try {
                e.remove();
            } catch (Throwable ignored) {
                // 위와 같음
            }
        }
        live.clear();
        byId.clear();
        adopted.clear();
        queue.clear();
        visCount.clear();
    }

    // ------------------------------------------------------------------ 설정

    public boolean enabled() {
        return enabled;
    }

    public boolean spritesOn() {
        return sprites && models.count() > 0;
    }

    public double density() {
        return density;
    }

    public boolean debug() {
        return debug;
    }

    public boolean hasPack(Player p) {
        if (assumePack) return true;
        if (packOk.contains(p.getUniqueId())) return true;
        try {
            return p.getResourcePackStatus() == PlayerResourcePackStatusEvent.Status.SUCCESSFULLY_LOADED;
        } catch (Throwable t) {
            return false;
        }
    }

    public Models models() {
        return models;
    }

    // ------------------------------------------------------------------ 시전

    public CastFx begin(SkillContext ctx, SkillDef def) {
        if (!enabled) return CastFx.off(this, ctx.caster);
        try {
            LivingEntity c = ctx.caster;
            Tier tier;
            Palette pal;
            int slot = 0;
            Tier.Weight wt;
            if (c instanceof Player p) {
                WeaponDef w = plugin.weapons().of(p.getInventory().getItemInMainHand());
                if (w != null) slot = slotOf(w, def.id());
                if (w == null || slot == 0) {
                    WeaponDef alt = weaponBySkill(def.id());
                    if (alt != null) {
                        w = alt;
                        slot = slotOf(alt, def.id());
                    }
                }
                tier = w == null ? Tier.BASIC : Tier.ofPool(w.pool());
                pal = w == null ? Palette.of("iron") : paletteOf(w);
                wt = Tier.Weight.of(slot, def.cooldown());
            } else if (Targets.isAlly(c)) {
                tier = Tier.ISLAND;
                pal = Palette.of("shadow");
                wt = Tier.Weight.LIGHT;
            } else {
                String id = plugin.mobs() == null ? null : plugin.mobs().idOf(c);
                MobDef md = id == null ? null : plugin.mobs().registry().get(id);
                boolean boss = Targets.isBoss(c) || (md != null && md.boss());
                tier = boss ? Tier.BOSS_MOB : Tier.MOB;
                pal = Palette.forMob(id, def.id());
                // 보스의 단계 변화 기술은 재사용 대기 1초로 한 번만 나간다
                wt = !boss ? Tier.Weight.LIGHT : def.cooldown() <= 1 ? Tier.Weight.ULT : Tier.Weight.HEAVY;
            }
            CastFx fx = new CastFx(this, ctx, def.id(), tier, wt, pal, slot);
            fx.sig = Signatures.get(def.id());
            fx.start();
            if (debug) log("cast", "시전 " + def.id() + " tier=" + tier + " weight=" + wt + " pal=" + pal.id());
            return fx;
        } catch (Throwable t) {
            warn("begin", "연출 준비 실패 (" + def.id() + "): " + t);
            return CastFx.off(this, ctx.caster);
        }
    }

    static Palette paletteOf(WeaponDef w) {
        if ("genesis_staff".equals(w.id())) return Palette.of("genesis");
        return Palette.of(w.element());
    }

    private static int slotOf(WeaponDef w, String skill) {
        for (int i = 1; i <= 3; i++) if (skill.equals(w.skillOf(i))) return i;
        return 0;
    }

    /** 같은 스킬을 여러 무기가 쓰면 높은 등급 무기 기준 */
    private WeaponDef weaponBySkill(String skill) {
        if (tick - bySkillAt > 1200) {
            Map<String, WeaponDef> m = new HashMap<>();
            for (WeaponDef w : plugin.weapons().all().values()) {
                for (int i = 1; i <= 3; i++) {
                    String s = w.skillOf(i);
                    if (s == null) continue;
                    WeaponDef prev = m.get(s);
                    if (prev == null || Tier.ofPool(prev.pool()).rank < Tier.ofPool(w.pool()).rank) m.put(s, w);
                }
            }
            bySkill = m;
            bySkillAt = tick;
        }
        return bySkill.get(skill);
    }

    /** 기존 기술 부품이 띄우는 표시 엔티티(투사체 모델 등)도 꺼질 때 같이 지우도록 맡아 둔다 */
    public void adopt(Entity e) {
        if (e != null) adopted.add(e);
    }

    // ------------------------------------------------------------------ 시간표

    public void after(int ticks, Runnable r) {
        if (ticks <= 0) {
            safe("after", r);
            return;
        }
        queue.add(new Job(tick + ticks, jobSeq++, r));
    }

    /** period 틱마다 times 번 (0, 1, 2...) */
    public void every(int delay, int period, int times, IntConsumer f) {
        for (int i = 0; i < times; i++) {
            int n = i;
            after(delay + i * Math.max(1, period), () -> f.accept(n));
        }
    }

    // ------------------------------------------------------------------ 매 틱

    private void tick() {
        tick++;
        while (!queue.isEmpty() && queue.peek().due() <= tick) {
            Job j = queue.poll();
            safe("job", j.r());
        }
        List<Sprite> cur = live;
        live = new ArrayList<>(cur.size() + 8);
        for (Sprite s : cur) {
            boolean keep;
            try {
                keep = s.step();
            } catch (Throwable t) {
                warn("sprite", "연출 조각 처리 오류: " + t);
                keep = false;
            }
            if (keep) live.add(s);
            else s.kill();
        }
        if (tick % 20 == 0) {
            adopted.removeIf(e -> !e.isValid());
            teleZones.removeIf(z -> z.until() < tick);
        }
    }

    void register(Sprite s) {
        live.add(s);
        if (s.e != null) byId.put(s.e.getUniqueId(), s);
    }

    void unregister(Sprite s) {
        if (s.e != null) byId.remove(s.e.getUniqueId());
    }

    public int liveCount() {
        return live.size();
    }

    List<Viewer> viewers() {
        if (viewersAt != tick) {
            List<Viewer> v = new ArrayList<>();
            for (Player p : Bukkit.getOnlinePlayers()) v.add(new Viewer(p, spritesOn() && hasPack(p)));
            viewers = v;
            viewersAt = tick;
        }
        return viewers;
    }

    Viewer viewer(Player p) {
        for (Viewer v : viewers()) if (v.p == p) return v;
        return null;
    }

    void markTele(Footprint f, int ticks) {
        teleZones.add(new TeleZone(f, tick + ticks));
    }

    boolean inTele(Location l) {
        for (TeleZone z : teleZones) if (z.until() >= tick && z.f().contains(l)) return true;
        return false;
    }

    // ------------------------------------------------------------------ 이벤트

    @EventHandler
    public void onPack(PlayerResourcePackStatusEvent e) {
        switch (e.getStatus()) {
            case SUCCESSFULLY_LOADED -> packOk.add(e.getPlayer().getUniqueId());
            case DECLINED, FAILED_DOWNLOAD, FAILED_RELOAD, DISCARDED, INVALID_URL -> packOk.remove(e.getPlayer().getUniqueId());
            default -> { }
        }
        if (debug) log("pack", "팩 상태 " + e.getPlayer().getName() + ": " + e.getStatus());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        UUID id = e.getPlayer().getUniqueId();
        packOk.remove(id);
        visCount.remove(id);
        lastFlash.remove(id);
        for (Sprite s : live) s.shown.remove(id);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onUnload(EntitiesUnloadEvent e) {
        for (Entity en : e.getEntities()) {
            if (!(en instanceof Display)) continue;
            Sprite s = byId.get(en.getUniqueId());
            if (s != null) s.dead = true;
            if (adopted.remove(en) || s != null || en.getScoreboardTags().contains(TAG)) en.remove();
        }
    }

    @EventHandler
    public void onWorldUnload(WorldUnloadEvent e) {
        for (Sprite s : live) if (s.e != null && s.e.getWorld() == e.getWorld()) s.dead = true;
        adopted.removeIf(en -> {
            if (en.getWorld() != e.getWorld()) return false;
            en.remove();
            return true;
        });
    }

    // ------------------------------------------------------------------ 기록

    void safe(String where, Runnable r) {
        try {
            r.run();
        } catch (Throwable t) {
            warn(where, "연출 오류(" + where + "): " + t);
        }
    }

    /** 같은 종류의 경고는 1분에 한 번만 */
    void warn(String key, String msg) {
        Long last = logAt.get(key);
        long now = System.currentTimeMillis();
        if (last != null && now - last < 60000) return;
        logAt.put(key, now);
        plugin.getLogger().warning(msg);
    }

    void log(String key, String msg) {
        plugin.getLogger().info("[vfx] " + msg);
    }

    Iterator<Sprite> liveIterator() {
        return live.iterator();
    }
}
