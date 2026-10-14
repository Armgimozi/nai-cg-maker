package kr.labyrinth.mobs;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;
import kr.labyrinth.Services;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.MobDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * 살아 있는 커스텀 몹 (CustomMob 구현): 투명·무음 바닐라 히트박스 + {@link ModelRig} + 자체 HP 풀 + 위협 표 + AI 상태.
 * AI 타입(melee/ranged/caster/charger/swarm/turret)과 스킬은 {@link MobAi}·{@link MobSkills} 가 처리하고,
 * 이 클래스는 상태·피해·사망·보상을 맡는다.
 */
public final class LabMob implements CustomMob {

    final Services services;
    final MobServiceImpl service;
    final MobDef def;
    final MobStats stats;
    final InstanceContext ctx;
    final boolean eliteVariant;
    final List<MobDef.MobSkillDef> skills;
    final Mob entity;
    final ModelRig rig;
    final ThreatTable threat = new ThreatTable();
    final Location home;
    final long seed;
    /** 비행형 (YAML flying 또는 비행 베이스: 중력 끔 + 선회 이동). */
    final boolean flying;

    // 상태
    double hp;
    double shieldHp;
    long shieldUntil;
    double shieldReduction;
    long reductionUntil;
    double reflectRatio;
    long reflectUntil;
    double buffDamage = 1, buffSpeed = 1;
    long buffUntil;
    boolean enraged;
    double enrageDamage = 1, enrageSpeed = 1;
    long stealthUntil;
    boolean stealthRevealOnHit;
    double pendingFirstHitMult = 1;
    boolean ambushing;
    double ambushRevealRange;
    ItemDisplay disguise;
    UUID targetId;
    long nextAttack;
    long globalSkillReady;
    long busyUntil;
    long staggerUntil;
    final Map<Integer, Long> skillReady = new HashMap<>();
    final Map<Integer, Long> passiveNext = new HashMap<>();
    final List<MobFx.Handle> handles = new ArrayList<>();
    final List<UUID> summons = new ArrayList<>();
    LabMob summoner;

    // 애니메이션 상태
    long attackTick = -100;
    int attackArm;
    long castTick = -100;
    long hurtTick = -100;
    long deathTick = -1;
    float bodyYaw;
    float headYaw, headPitch;
    double moveSpeed;
    Location lastLoc;
    long lastHurtSound;
    double flyAngle;
    long lastRepath;
    Location lastPathGoal;
    UUID lastDamager;
    private boolean dead;
    private boolean removed;
    private Component lastPlate;

    LabMob(Services services, MobServiceImpl service, MobDef def, MobStats stats, InstanceContext ctx, boolean eliteVariant,
           List<MobDef.MobSkillDef> skills, Mob entity, ModelRig rig, boolean flying) {
        this.flying = flying;
        this.services = services;
        this.service = service;
        this.def = def;
        this.stats = stats;
        this.ctx = ctx;
        this.eliteVariant = eliteVariant;
        this.skills = skills;
        this.entity = entity;
        this.rig = rig;
        this.hp = stats.maxHp();
        this.home = entity.getLocation();
        this.lastLoc = home.clone();
        this.bodyYaw = home.getYaw();
        this.seed = entity.getUniqueId().getLeastSignificantBits();
    }

    // ── CustomMob ────────────────────────────────────────────────────────

    @Override
    public String id() { return def.id(); }

    @Override
    public String displayName() {
        if (eliteVariant) return "<gold>★ 정예</gold> <yellow>" + def.name() + "</yellow>";
        if (def.isElite()) return "<gold>" + def.name() + "</gold>";
        return def.name();
    }

    @Override
    public LivingEntity entity() { return entity; }

    @Override
    public InstanceContext instance() { return ctx; }

    @Override
    public double damage() {
        long now = service.now();
        double mult = (now < buffUntil ? buffDamage : 1) * (enraged ? enrageDamage : 1);
        if (services.effects().has(entity, "weaken")) mult *= 0.8;
        return stats.damage() * mult;
    }

    public MobDef def() { return def; }

    public boolean isEliteVariant() { return eliteVariant; }

    @Override
    public Location location() { return dead || !entity.isValid() ? lastLoc.clone() : entity.getLocation(); }

    @Override
    public void addThreat(Player player, double amount) {
        if (player == null || dead) return;
        threat.add(player.getUniqueId(), amount);
        if (targetId == null) targetId = player.getUniqueId();
    }

    @Override
    public void taunt(Player player, double seconds) {
        if (player == null || dead) return;
        threat.taunt(player.getUniqueId(), service.now() + Math.round(seconds * 20));
        targetId = player.getUniqueId();
        MobFx.dust(location().add(0, entity.getHeight() + 0.6, 0), Color.fromRGB(255, 80, 60), 1.4f, 6, 0.2);
    }

    @Override
    public Player target() {
        if (targetId == null) return null;
        Player p = Bukkit.getPlayer(targetId);
        return p != null && validTarget(p) ? p : null;
    }

    @Override
    public void remove() {
        if (removed) return;
        removed = true;
        dead = true;
        cancelHandles();
        if (disguise != null) service.fx().discard(disguise);
        if (entity.isValid()) entity.remove();
        rig.remove();
        service.unregister(this);
    }

    // ── HealthPool ───────────────────────────────────────────────────────

    @Override
    public double health() { return hp; }

    @Override
    public double maxHealth() { return stats.maxHp(); }

    @Override
    public double defense() { return stats.defense(); }

    @Override
    public double damageReduction() {
        return service.now() < reductionUntil ? Math.max(0, Math.min(0.9, shieldReduction)) : 0;
    }

    @Override
    public double damageTaken() {
        return services.effects().has(entity, "vulnerable") ? 0.15 : 0;
    }

    @Override
    public boolean invulnerable() { return dead; }

    @Override
    public boolean isAlive() { return !dead && hp > 0; }

    @Override
    public double applyDamage(double amount, DamageContext dctx) {
        if (dead || amount <= 0) return 0;
        long now = service.now();
        if (ambushing) MobSkills.revealAmbush(this);
        if (now < stealthUntil && stealthRevealOnHit) MobSkills.endStealth(this);
        Player attacker = dctx == null ? null : dctx.attackerPlayer();
        double remaining = amount;
        if (shieldHp > 0 && now < shieldUntil) {
            double absorbed = Math.min(shieldHp, remaining);
            shieldHp -= absorbed;
            remaining -= absorbed;
            if (absorbed > 0) {
                MobFx.dust(location().add(0, entity.getHeight() * 0.6, 0), Color.fromRGB(140, 200, 255), 1.1f, 4, 0.4);
                if (attacker != null) threat.add(attacker.getUniqueId(), absorbed);
            }
        }
        double dealt = Math.min(hp, remaining);
        hp -= dealt;
        hurtTick = now;
        if (attacker != null) {
            lastDamager = attacker.getUniqueId();
            if (targetId == null) targetId = attacker.getUniqueId();
        }
        if (now - lastHurtSound > 6) {
            lastHurtSound = now;
            sound("hurt", 0.8f);
        }
        // 반사
        if (now < reflectUntil && reflectRatio > 0 && dctx != null && dctx.attacker() != null
                && !"reflect".equals(dctx.sourceId()) && !(dctx.attacker().equals(entity))) {
            double back = (dealt + (amount - remaining)) * reflectRatio;
            if (back >= 1) {
                services.damage().deal(DamageContext.raw(entity, dctx.attacker(), back, DamageType.TRUE).source("reflect").noCrit());
                MobFx.particle(Particle.ENCHANTED_HIT, location().add(0, entity.getHeight() * 0.6, 0), 8, 0.3, 0.4, 0.3, 0.1);
            }
        }
        if (hp <= 0.0001) {
            hp = 0;
            die(attacker);
        } else {
            MobSkills.onHurt(this);
            refreshNameplate();
        }
        return dealt;
    }

    @Override
    public double heal(double amount) {
        if (dead || amount <= 0) return 0;
        double h = Math.min(stats.maxHp() - hp, amount);
        hp += h;
        if (h > 0) refreshNameplate();
        return h;
    }

    // ── 대상 ─────────────────────────────────────────────────────────────

    boolean validTarget(Player p) {
        if (p == null || !p.isOnline() || p.isDead() || p.getWorld() != entity.getWorld()) return false;
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return false;
        if (p.getLocation().distanceSquared(location()) > 48 * 48) return false;
        return services.targets().isEnemy(entity, p);
    }

    boolean validTarget(UUID id) {
        Player p = Bukkit.getPlayer(id);
        return p != null && validTarget(p);
    }

    // ── 틱 ───────────────────────────────────────────────────────────────

    /** 서비스가 매 틱 호출. */
    void tick(long now) {
        if (removed) return;
        if (dead) {
            int dt = (int) (now - deathTick);
            if (dt % 2 == 0) rig.animate(bodyYaw, animState(now), 2);
            if (dt > RigMath.DEATH_TICKS + 2) {
                rig.remove();
                removed = true;
                service.unregister(this);
            }
            return;
        }
        if (!entity.isValid()) {
            // 청크 언로드·공허 낙하 등으로 히트박스가 사라짐 → 보상 없이 정리
            remove();
            return;
        }
        Location loc = entity.getLocation();
        double moved = Math.sqrt(Math.pow(loc.getX() - lastLoc.getX(), 2) + Math.pow(loc.getZ() - lastLoc.getZ(), 2));
        moveSpeed = moveSpeed * 0.6 + moved * 0.4;
        lastLoc = loc.clone();
        if (rig.broken()) {
            remove();
            return;
        }
        rig.follow(loc);

        int lod = service.lod(loc);
        try {
            MobSkills.tickPassives(this, now);
            if (ambushing) {
                if (now % 5 == 0) MobSkills.checkAmbush(this);
            } else if (lod < 3) {
                MobAi.tick(this, now);
            } else if (entity.isAware() && !flying) {
                entity.getPathfinder().stopPathfinding();
            }
        } catch (Throwable t) {
            Log.error("몹 AI 오류 (" + def.id() + ")", t);
        }
        int interval = lod <= 1 ? 2 : lod == 2 ? 5 : 0;
        if (interval > 0 && (now + (seed & 3)) % interval == 0) rig.animate(bodyYaw, animState(now), interval);
        if (now % 20 == 0) refreshNameplate();
    }

    RigMath.AnimState animState(long now) {
        int atk = now - attackTick <= RigMath.ATTACK_TICKS + 2 ? (int) (now - attackTick) : -1;
        int cast = now - castTick <= 16 ? (int) (now - castTick) : -1;
        int hurt = now - hurtTick < RigMath.HURT_TICKS ? (int) (now - hurtTick) : -1;
        int death = deathTick >= 0 ? (int) (now - deathTick) : -1;
        return new RigMath.AnimState(now, moveSpeed, atk, attackArm, cast, hurt, headYaw, headPitch, death,
                targetId != null, seed);
    }

    // ── 이름표 ───────────────────────────────────────────────────────────

    void refreshNameplate() {
        if (dead) return;
        double ratio = stats.maxHp() <= 0 ? 0 : hp / stats.maxHp();
        int segs = 14;
        int full = (int) Math.ceil(ratio * segs);
        String color = ratio > 0.6 ? "#5ee65e" : ratio > 0.3 ? "#ffd84d" : "#ff4d4d";
        StringBuilder bar = new StringBuilder();
        bar.append("<").append(color).append(">").append("|".repeat(Math.max(0, full))).append("</").append(color).append(">");
        bar.append("<#3a3a3a>").append("|".repeat(Math.max(0, segs - full))).append("</#3a3a3a>");
        String shield = shieldHp > 0 && service.now() < shieldUntil ? " <#8cc8ff>◆" + Text.num(shieldHp) + "</#8cc8ff>" : "";
        String tags = (enraged ? " <red>분노</red>" : "") + (service.now() < reflectUntil ? " <aqua>반사</aqua>" : "");
        String text = displayName() + tags + "\n<b>" + bar + "</b> <gray>" + Text.num(hp) + "<dark_gray>/</dark_gray>"
                + Text.num(stats.maxHp()) + "</gray>" + shield;
        Component c = Text.mm(text);
        if (!c.equals(lastPlate)) {
            lastPlate = c;
            rig.nameplate(c);
        }
    }

    // ── 사망 ─────────────────────────────────────────────────────────────

    boolean isDead() { return dead; }

    private void die(Player killer) {
        if (dead) return;
        dead = true;
        long now = service.now();
        deathTick = now;
        cancelHandles();
        Location at = entity.getLocation();
        lastLoc = at.clone();
        if (disguise != null) service.fx().discard(disguise);
        rig.setHidden(false);
        rig.nameplateVisible(false);
        sound("death", 1.0f);
        MobFx.particle(Particle.POOF, at.clone().add(0, entity.getHeight() / 2, 0), 14, 0.4, 0.4, 0.4, 0.04);
        if (killer == null && lastDamager != null) killer = Bukkit.getPlayer(lastDamager);
        entity.remove(); // 사망은 remove() (GDD §9.3 — 바닐라 드롭·분열 방지)
        try {
            MobSkills.onDeath(this, at);
        } catch (Throwable t) {
            Log.error("몹 사망 스킬 오류 (" + def.id() + ")", t);
        }
        service.reward(this, killer, at);
        for (UUID u : summons) service.byUuid(u).ifPresent(m -> { if (m.isAlive()) m.summoner = null; });
    }

    void cancelHandles() {
        for (MobFx.Handle h : handles) h.cancel();
        handles.clear();
    }

    void track(MobFx.Handle h) {
        handles.removeIf(MobFx.Handle::done);
        handles.add(h);
    }

    // ── 유틸 ─────────────────────────────────────────────────────────────

    void sound(String key, float volume) {
        Params s = def.sounds();
        String id = s.str(key);
        if (id == null || id.isBlank() || !entity.getWorld().equals(lastLoc.getWorld())) return;
        float pitch = (float) s.dbl("pitch", 1.0);
        try {
            lastLoc.getWorld().playSound(lastLoc, id, volume, pitch * (0.92f + ThreadLocalRandom.current().nextFloat() * 0.16f));
        } catch (Throwable ignored) {
            // 잘못된 사운드 키는 무시
        }
    }

    /** 몹 시선 높이. */
    Location eye() { return location().add(0, Math.max(0.4, entity.getHeight() * 0.75), 0); }

    /** 대상 방향 수평 벡터 (정규화). */
    Vector dirTo(Location to) {
        Vector v = to.toVector().subtract(location().toVector()).setY(0);
        if (v.lengthSquared() < 1e-6) return new Vector(Geometry.yawX(bodyYaw), 0, Geometry.yawZ(bodyYaw));
        return v.normalize();
    }

    /** 스킬 피해 배율 → 원피해. */
    double skillDamage(Params p, String key, double def) {
        return damage() * p.dbl(key, def);
    }

    /** 경고 시간(틱) — 난이도 telegraph 배율 + 최소 0.5초. */
    int windupTicks(Params p, double defSeconds) {
        double w = p.dbl("windup", defSeconds);
        double secs = ctx != null ? ctx.windup(w) : services.settings().difficulty().windup(w);
        return (int) Math.round(secs * 20);
    }

    boolean isEnemy(Entity e) { return services.targets().isEnemy(entity, e); }

    List<Player> enemiesNear(Location c, double r) {
        List<Player> out = new ArrayList<>();
        if (c.getWorld() == null) return out;
        for (Player p : c.getWorld().getPlayers()) {
            if (p.getLocation().distanceSquared(c) <= r * r && validTarget(p)) out.add(p);
        }
        return out;
    }

    /** 반경 안 아군 커스텀 몹 (자신 포함). */
    List<LabMob> alliesNear(double r) {
        return service.mobsNear(location(), r);
    }
}
