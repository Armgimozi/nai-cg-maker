package kr.labyrinth.items.unique;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.random.RandomGenerator;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.SkillFx;
import kr.labyrinth.classes.skills.Targeting;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageKind;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.combat.HealKind;
import kr.labyrinth.combat.HealthPool;
import kr.labyrinth.content.ItemDef;
import kr.labyrinth.content.UniqueDef;
import kr.labyrinth.items.EquipRules;
import kr.labyrinth.stats.DerivedStats;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

/**
 * 무기 고유 효과 26개의 실제 동작 (unique_spec §2·§7·§9, pvp_spec §11, review2 A12·C2·C4). 손에 든 무기의 {@link UniqueDef} 하나만 켜진다
 * — 요구 능력치를 못 채우면 무기 스킬처럼 꺼진다. 상태·재발동·중첩은 순수 {@link UniqueProcs}.
 * <ul>
 *   <li>공격자 보정 ({@link #before}): 피 냄새 · 마무리 · 약점 파고들기 · 등 찌르기 · 선제 · 광기 · 관통 사격 거리 · 추격·흘려치기 '다음 공격'</li>
 *   <li>받는 피해 ({@link #absorb}): 굳건함 · 넉백 면역은 1초 타이머가 버프로</li>
 *   <li>적중 뒤 ({@link #after}): 찢는 치명 · 원소 부여 · 갑옷 부수기 · 광기 흡혈 (스킬 적중에도) · 생명 흡수 · 휩쓸기 · 연쇄 번개 · 연타 ·
 *       방패 강타 · 축성 · 가속 · 관통 · 과부하 (기본 공격만) · 처치(포식 · 시체 폭발 · 추격 · 마력 흡수) · 맞은 쪽 가시 반격</li>
 *   <li>회피 ({@link #evaded}): 흘려치기. 지속 피해는 회피할 수 없어 여기 오지 않는다</li>
 *   <li>스킬 사용 ({@link #onSkill}): 과부하 장전 · 1초 타이머: 수호 기운 · 굳건함 넉백 면역</li>
 * </ul>
 * 폭주 방지: 고유 효과가 낸 피해({@code source "unique:<id>"})·지속 피해({@code effect:*})는 어떤 고유 효과도 켜지 않는다.
 * 플레이어 대상은 곱하기 보정·덧 피해 × 0.5, 중첩 3까지. 기절·빙결은 그대로 걸고 시간만 PvP 상태이상 규칙이 줄인다.
 * <p>
 * 관통: 미궁 화살은 맞는 순간 바닐라 피해를 취소하고 지우므로(바닐라 관통은 취소된 피해에서 튕겨 나온다) 바닐라 {@code setPierceLevel}
 * 대신 화살이 날던 줄 위의 뒤쪽 적을 찾아 같은 화살 피해 × (1 − 0.2 × k) 를 준다.
 */
public final class UniqueEffectService implements UniqueEffects, DamageService.Hook, Listener {

    static final String STEADFAST_BUFF = "unique:steadfast";

    private final Services services;
    private final UniqueProcs procs = new UniqueProcs();
    private final Map<UUID, Held> held = new ConcurrentHashMap<>();
    /** 가시 반격의 '줄기 전 피해' — PvP 배율이 곱해지기 전에 잡아 둔다 (훅 순서: items 가 pvp 보다 먼저 등록). */
    private final Map<DamageContext, Double> thornsBase = new WeakHashMap<>();
    private final RandomGenerator rng = RandomGenerator.getDefault();
    private BukkitTask task;
    private long ticks;

    private record Held(String weaponId, UniqueDef unique) {}

    public UniqueEffectService(Services services) { this.services = services; }

    public void start() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        services.damage().addHook(this);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 20L, 20L);
    }

    public void stop() {
        if (task != null) task.cancel();
        HandlerList.unregisterAll(this);
        services.damage().removeHook(this);
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (services.effects().hasBuff(p, STEADFAST_BUFF)) services.effects().removeBuff(p, STEADFAST_BUFF);
        }
        held.clear();
    }

    private static long now() { return System.currentTimeMillis(); }

    // ── UniqueEffects ────────────────────────────────────────────────────

    @Override
    public UniqueDef current(Player p) {
        if (p == null) return null;
        ItemDef w = services.items().heldWeapon(p);
        if (w == null) return null;
        Held h = held.get(p.getUniqueId());
        if (h != null && h.weaponId().equals(w.id())) return h.unique();
        // 장비 재계산 전(손을 막 바꾼 틱): 직접 판정해 둔다
        UniqueDef u = w.unique() != null && EquipRules.usable(w, services.stats().requirementStats(p)) ? w.unique() : null;
        held.put(p.getUniqueId(), new Held(w.id(), u));
        return u;
    }

    /**
     * 이 피해에 쓸 고유 효과의 무기 id (순수): 화살은 쏜 활 ({@link DamageContext#firedWith}, 0.3.6.1 — 날아가는 동안 바꿔 쥔 무기가 아님),
     * 그 밖은 지금 든 무기. "" (미궁 활이 아닌 것으로 쏜 화살) = 없음 → null.
     */
    static String uniqueWeaponId(String firedWith, String heldId) {
        if (firedWith == null) return heldId;
        return firedWith.isEmpty() ? null : firedWith;
    }

    /** 피해 한 건의 고유 효과 — 지금 든 무기면 {@link #current}, 쏜 활이 따로면 그 활 (요구 능력치를 못 채우면 꺼짐). */
    private UniqueDef uniqueFor(Player p, DamageContext ctx) {
        ItemDef held = services.items().heldWeapon(p);
        String id = uniqueWeaponId(ctx.firedWith(), held == null ? null : held.id());
        if (id == null) return null;
        if (held != null && id.equals(held.id())) return current(p);
        ItemDef w = services.content().item(id);
        return w != null && w.unique() != null && EquipRules.usable(w, services.stats().requirementStats(p)) ? w.unique() : null;
    }

    @Override
    public void held(Player p, ItemDef weapon, boolean usable) {
        if (p == null) return;
        if (weapon == null) held.remove(p.getUniqueId());
        else held.put(p.getUniqueId(), new Held(weapon.id(), usable ? weapon.unique() : null));
    }

    @Override
    public void onSkill(Player p) {
        UniqueDef u = current(p);
        if (u == null || !u.is("overcharge")) return;
        long now = now();
        if (!procs.ready(p.getUniqueId(), "overcharge", null, u.effect().icd(), now)) return;
        procs.arm(p.getUniqueId(), "overcharge", u.num("pct"), u.num("window"), now);
        SkillFx.burst(p.getLocation().add(0, 1.2, 0), Particle.ELECTRIC_SPARK, 10, 0.4, 0.05, null);
        SkillFx.sound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 0.4f, 1.8f);
    }

    @Override
    public double defenseShred(LivingEntity target) { return target == null ? 0 : procs.shred(target.getUniqueId(), now()); }

    // ── DamageService.Hook ───────────────────────────────────────────────

    private static boolean isUnique(DamageContext ctx) { return ctx.sourceId() != null && ctx.sourceId().startsWith("unique:"); }

    private static boolean isDot(DamageContext ctx) { return ctx.sourceId() != null && ctx.sourceId().startsWith("effect:"); }

    /** 고유 효과를 켤 수 있는 피해인가 (고유 효과 피해·지속 피해·최대 HP 비율 피해는 아님). */
    private static boolean procable(DamageContext ctx) { return !ctx.cancelled() && !ctx.isPercent() && !isUnique(ctx) && !isDot(ctx); }

    @Override
    public void before(DamageContext ctx) {
        if (!procable(ctx)) return;
        LivingEntity t = ctx.target();
        if (t instanceof Player victim && ctx.attacker() != null && ctx.type() == DamageType.MELEE) {
            UniqueDef vu = current(victim);
            if (vu != null && vu.is("thorns")) {
                synchronized (thornsBase) {
                    thornsBase.put(ctx, ctx.amount());
                }
            }
        }
        Player p = ctx.attackerPlayer();
        if (p == null || t == null || t.equals(p)) return;
        boolean basic = ctx.isBasicAttack(), skill = ctx.isSkill();
        if (!basic && !skill) return;
        UniqueDef u = uniqueFor(p, ctx); // 화살은 쏜 활의 고유 효과 (0.3.6.1)
        if (u == null || u.effect() == null) return;
        boolean tp = t instanceof Player;
        UUID me = p.getUniqueId();
        long now = now();
        // '다음 공격' 보너스 (추격은 스킬도 된다, 흘려치기는 기본 공격만)
        if (u.is("bloodrush")) {
            UniqueProcs.Armed a = procs.consume(me, "bloodrush", now);
            if (a != null) mult(ctx, 1 + a.pct() * UniqueProcs.pvp(tp));
        } else if (u.is("counterstep") && basic) {
            UniqueProcs.Armed a = procs.consume(me, "counterstep", now);
            if (a != null) {
                ctx.critBonus(1.0);
                mult(ctx, 1 + a.pct() * UniqueProcs.pvp(tp));
            }
        }
        if (!basic && !u.effect().onSkill()) return;
        switch (u.id()) {
            case "hemorrhage" -> {
                if (services.effects().has(t, "bleed")) {
                    ctx.critBonus(u.num("cc"));
                    ctx.critDamageAdd(u.num("cd"));
                }
            }
            case "execute" -> mult(ctx, 1 + UniqueProcs.executeBonus(hpRatio(t), u.num("thr"), u.num("pct"), isBoss(t), tp));
            case "exploit" -> mult(ctx, 1 + UniqueProcs.exploitBonus(statusCount(t), u.num("pct"), tp));
            case "backstab" -> {
                if (Targeting.isBehind(p, t, UniqueProcs.BACK_CONE)) mult(ctx, 1 + u.num("pct") * UniqueProcs.pvp(tp));
            }
            case "first_strike" -> {
                if (procs.firstHit(me, t.getUniqueId(), isBoss(t), u.num("window"), now)) {
                    mult(ctx, 1 + u.num("pct") * UniqueProcs.pvp(tp));
                    ctx.critBonus(u.num("cc"));
                }
            }
            case "berserk" -> mult(ctx, 1 + UniqueProcs.berserkBonus(hpRatio(p), u.num("pct"), tp));
            case "longshot" -> {
                double d = u.num("dist");
                if (basic && ctx.type() == DamageType.RANGED && p.getLocation().distanceSquared(t.getLocation()) >= d * d) {
                    mult(ctx, 1 + u.num("pct") * UniqueProcs.pvp(tp));
                }
            }
            default -> { }
        }
    }

    @Override
    public double absorb(DamageContext ctx, double damage) {
        if (damage <= 0 || !(ctx.target() instanceof Player v)) return damage;
        UniqueDef u = current(v);
        if (u == null || !u.is("steadfast")) return damage;
        return hpRatio(v) >= u.num("thr") - 1e-9 ? damage * Math.max(0, 1 - u.num("dr")) : damage;
    }

    @Override
    public void evaded(DamageContext ctx) {
        if (!(ctx.target() instanceof Player v) || ctx.attacker() == null || ctx.attacker().equals(v)) return;
        UniqueDef u = current(v);
        if (u == null || !u.is("counterstep")) return;
        long now = now();
        if (!procs.ready(v.getUniqueId(), "counterstep", null, u.effect().icd(), now)) return;
        procs.arm(v.getUniqueId(), "counterstep", u.num("pct"), u.num("window"), now);
        services.effects().applyBuff(v, Map.of("move_speed", u.num("ms")), UniqueProcs.COUNTERSTEP_MOVE_SECONDS, "unique:counterstep");
        SkillFx.burst(v.getLocation().add(0, 1, 0), Particle.CLOUD, 6, 0.3, 0.02, null);
        SkillFx.sound(v.getLocation(), Sound.ENTITY_BREEZE_JUMP, 0.5f, 1.6f);
    }

    @Override
    public void after(DamageContext ctx) {
        if (ctx.cancelled()) return;
        long now = now();
        LivingEntity t = ctx.target();
        Player p = ctx.attackerPlayer();
        Double base;
        synchronized (thornsBase) {
            base = thornsBase.remove(ctx);
        }
        if (!ctx.evaded() && !isDot(ctx)) {
            if (p != null) procs.markCombat(p.getUniqueId(), now);
            if (t instanceof Player v && ctx.attacker() != null) procs.markCombat(v.getUniqueId(), now);
        }
        if (base != null && t instanceof Player victim && !ctx.evaded()) thorns(victim, ctx.attacker(), base, now);
        if (p == null || t == null || t.equals(p) || !procable(ctx)) return;
        boolean basic = ctx.isBasicAttack(), skill = ctx.isSkill();
        if (!basic && !skill) return;
        UniqueDef u = uniqueFor(p, ctx); // 화살은 쏜 활의 고유 효과 (0.3.6.1)
        if (u == null || u.effect() == null) return;
        if (ctx.killed()) onKill(p, u, t, now, ctx);
        if (ctx.evaded() || ctx.dealt() <= 0) return;
        if (!basic && !u.effect().onSkill()) return;
        UUID me = p.getUniqueId();
        boolean tp = t instanceof Player;
        boolean alive = !ctx.killed() && t.isValid() && !t.isDead();
        switch (u.id()) {
            case "rend" -> {
                if (alive && ctx.crit() && procs.ready(me, "rend", t.getUniqueId(), u.effect().icd(), now)) {
                    double perStack = DamageService.rawAmount(stats(p), hitW(p, ctx), DamageKind.PHYSICAL, u.num("pct")); // 화살 = 쏜 활 W
                    services.effects().applyStacks(t, "bleed", u.num("duration"), perStack, 1,
                            UniqueProcs.maxStacks(u.count("max_stacks"), tp), p);
                }
            }
            case "imbue" -> {
                if (alive && rng.nextDouble() < u.num("chance") && procs.ready(me, "imbue", t.getUniqueId(), u.effect().icd(), now)) {
                    imbue(p, u, t, tp);
                }
            }
            case "armor_break" -> {
                if (alive && procs.ready(me, "armor_break", t.getUniqueId(), u.effect().icd(), now)) {
                    int n = procs.addShred(t.getUniqueId(), u.num("pct"), UniqueProcs.maxStacks(u.count("max_stacks"), tp),
                            u.num("duration"), now);
                    if (n >= 3) SkillFx.burst(t.getLocation().add(0, t.getHeight() * 0.6, 0), Particle.CRIT, 4 + n, 0.3, 0.05, null);
                }
            }
            case "berserk" -> {
                if (hpRatio(p) <= u.num("thr") + 1e-9) services.damage().lifesteal(p, t, ctx.dealt() * u.num("ls"), false);
            }
            default -> { }
        }
        if (!basic) return;
        switch (u.id()) {
            case "leech" -> {
                double got = procs.leechAllowed(me, ctx.dealt() * u.num("pct"), services.stats().maxHp(p) * u.num("cap"), now);
                if (got > 0) services.damage().lifesteal(p, t, got, false);
            }
            case "cleave" -> cleave(p, u, t, hitW(p, ctx), hitKind(p, ctx));
            case "chain_spark" -> {
                if (rng.nextDouble() < u.num("chance") && procs.ready(me, "chain_spark", null, u.effect().icd(), now)) chain(p, u, t, hitW(p, ctx));
            }
            case "flurry" -> {
                if (procs.nth(me, "flurry", u.count("n")) && alive) {
                    hit(p, t, u.num("pct"), hitKind(p, ctx), DamageContext.Base.PER_HIT, "flurry", hitW(p, ctx));
                    SkillFx.burst(t.getLocation().add(0, t.getHeight() * 0.6, 0), Particle.SWEEP_ATTACK, 1, 0.1, 0, null);
                }
            }
            case "bash_stun" -> {
                if (procs.nth(me, "bash_stun", u.count("n"))) bash(p, u, t, alive, now, hitW(p, ctx), hitKind(p, ctx));
            }
            case "sanctify" -> {
                if (procs.ready(me, "sanctify", null, u.effect().icd(), now)) sanctify(p, u, ctx);
            }
            case "momentum" -> {
                int n = procs.momentum(me, u.count("max_stacks"), u.num("decay"), now);
                services.effects().applyBuff(p, Map.of("attack_speed", u.num("as") * n), u.num("decay"), "unique:momentum");
            }
            case "longshot" -> {
                if (ctx.type() == DamageType.RANGED && u.count("pierce") > 0) pierce(p, u, t, ctx.attackMultiplier(), hitW(p, ctx), hitKind(p, ctx));
            }
            case "overcharge" -> {
                UniqueProcs.Armed a = procs.consume(me, "overcharge", now);
                if (a != null) overcharge(p, u, t, a.pct());
            }
            default -> { }
        }
    }

    // ── 효과 ─────────────────────────────────────────────────────────────

    /** 처치 효과. 화살·마법탄으로 처치하면 쏜 무기 기준 (피해 종류 · 재사용 대기를 줄일 무기) — 날아가는 사이 바꿔 쥔 무기가 아님. */
    private void onKill(Player p, UniqueDef u, LivingEntity victim, long now, DamageContext ctx) {
        UUID me = p.getUniqueId();
        double icd = u.effect().icd();
        switch (u.id()) {
            case "feast" -> {
                if (!procs.ready(me, "feast", null, icd, now)) return;
                services.damage().heal(p, services.stats().maxHp(p) * u.num("heal"), 0, HealKind.OTHER, true);
                services.effects().applyBuff(p, Map.of("lifesteal", u.num("ls")), u.num("duration"), "unique:feast");
            }
            case "death_burst" -> {
                // 플레이어를 처치하면 터지지 않는다 · 폭발로 죽은 적은 다시 터지지 않는다(고유 효과 피해라 훅이 안 켜짐)
                if (victim instanceof Player || !procs.ready(me, "death_burst", null, icd, now)) return;
                Location at = victim.getLocation().add(0, victim.getHeight() * 0.5, 0);
                int n = 0;
                for (LivingEntity x : services.targets().enemiesIn(p, at, u.num("radius"))) {
                    if (x.equals(victim)) continue;
                    hit(p, x, u.num("pct"), hitKind(p, ctx), DamageContext.Base.SKILL, "death_burst", Double.NaN);
                    if (++n >= UniqueProcs.BURST_TARGETS) break;
                }
                SkillFx.burst(at, Particle.EXPLOSION, 1, 0, 0, null);
                SkillFx.sound(at, Sound.ENTITY_GENERIC_EXPLODE, 0.4f, 1.4f);
            }
            case "bloodrush" -> {
                if (!procs.ready(me, "bloodrush", null, icd, now)) return;
                procs.arm(me, "bloodrush", u.num("pct"), UniqueProcs.BLOODRUSH_WINDOW, now);
                services.effects().applyBuff(p, Map.of("move_speed", u.num("ms")), u.num("duration"), "unique:bloodrush");
                SkillFx.burst(p.getLocation().add(0, 1, 0), Particle.DUST, 8, 0.3, 0, SkillFx.dust(0xb01010, 1.0f));
            }
            case "siphon" -> {
                if (!procs.ready(me, "siphon", null, icd, now)) return;
                services.classes().restoreMana(p, services.classes().maxMana(p) * u.num("mp"));
                ItemDef w = services.items().heldWeapon(p);
                String wid = uniqueWeaponId(ctx.firedWith(), w == null ? null : w.id()); // 쏜 지팡이·활 (그 밖은 든 무기)
                if (wid != null) services.weaponSkills().reduceCooldowns(p, wid, u.num("cdr"));
                SkillFx.burst(p.getLocation().add(0, 1.2, 0), Particle.WITCH, 6, 0.3, 0.02, null);
            }
            default -> { }
        }
    }

    private void thorns(Player victim, LivingEntity attacker, double raw, long now) {
        if (attacker == null || attacker.equals(victim) || !attacker.isValid() || attacker.isDead() || raw <= 0) return;
        UniqueDef u = current(victim);
        if (u == null || !u.is("thorns")) return;
        if (attacker.getLocation().distanceSquared(victim.getLocation()) > 36) return; // 근접만
        if (!services.targets().isEnemy(victim, attacker)) return;
        if (!procs.ready(victim.getUniqueId(), "thorns", attacker.getUniqueId(), u.effect().icd(), now)) return;
        double amount = raw * u.num("pct") * UniqueProcs.pvp(attacker instanceof Player);
        services.damage().deal(DamageContext.raw(victim, attacker, amount, DamageType.TRUE).source("unique:thorns")
                .noCrit().noEvade().noBlock().noLifesteal());
        SkillFx.burst(attacker.getLocation().add(0, attacker.getHeight() * 0.6, 0), Particle.CRIT, 6, 0.3, 0.05, null);
    }

    private void imbue(Player p, UniqueDef u, LivingEntity t, boolean tp) {
        switch (u.text("element", "burn")) {
            case "poison" -> {
                double perStack = DamageService.rawAmount(stats(p), DamageContext.Base.SKILL, DamageKind.PHYSICAL, u.num("pct"));
                services.effects().applyStacks(t, "poison", u.num("duration"), perStack, 1, UniqueProcs.maxStacks(5, tp), p);
            }
            case "frost" -> services.effects().applyFrost(t, 1, UniqueProcs.IMBUE_FREEZE, UniqueProcs.IMBUE_BOSS_VULN, p);
            default -> services.effects().apply(t, "burn", u.num("duration"), u.num("pct"), p);
        }
    }

    private void cleave(Player p, UniqueDef u, LivingEntity t, double w, DamageKind kind) {
        Location at = t.getLocation();
        int n = 0;
        for (LivingEntity x : services.targets().enemiesIn(p, at, u.num("radius"))) {
            if (x.equals(t)) continue;
            hit(p, x, u.num("pct"), kind, DamageContext.Base.PER_HIT, "cleave", w);
            if (++n >= u.count("targets")) break;
        }
        if (n > 0) SkillFx.burst(at.clone().add(0, 1, 0), Particle.SWEEP_ATTACK, 2, 0.6, 0, null);
    }

    private void chain(Player p, UniqueDef u, LivingEntity t, double w) {
        Location from = t.getLocation().add(0, t.getHeight() * 0.6, 0);
        int n = 0;
        for (LivingEntity x : services.targets().enemiesIn(p, from, UniqueProcs.CHAIN_RANGE)) {
            if (x.equals(t)) continue;
            Location to = x.getLocation().add(0, x.getHeight() * 0.6, 0);
            SkillFx.line(from, to, 0.4, Particle.ELECTRIC_SPARK, null);
            hit(p, x, u.num("pct"), DamageKind.MAGIC, DamageContext.Base.PER_HIT, "chain_spark", w);
            from = to;
            if (++n >= u.count("targets")) break;
        }
        if (n > 0) SkillFx.sound(t.getLocation(), Sound.ENTITY_LIGHTNING_BOLT_IMPACT, 0.3f, 1.8f);
    }

    private void bash(Player p, UniqueDef u, LivingEntity t, boolean alive, long now, double w, DamageKind kind) {
        if (!alive) return;
        hit(p, t, u.num("pct"), kind, DamageContext.Base.PER_HIT, "bash_stun", w);
        if (!t.isValid() || t.isDead()) return;
        boolean boss = isBoss(t);
        if (boss) {
            services.effects().apply(t, UniqueProcs.stunEffect(true), UniqueProcs.BOSS_VULN_SECONDS, u.num("vuln"), p);
        } else if (procs.stunReady(t.getUniqueId(), now)) {
            // 플레이어도 기절 그대로 — 시간은 PvP 상태이상 규칙(×0.8 · 최대 1초 · 줄어듦 · 끝나면 면역)이 줄인다
            services.effects().apply(t, UniqueProcs.stunEffect(false), u.num("stun"), 1, p);
        }
        SkillFx.sound(t.getLocation(), Sound.ITEM_SHIELD_BLOCK, 0.6f, 0.7f);
    }

    /** 무기 W·종류는 이 피해의 것 ({@link #hitW} · {@link #hitKind} — 화살·마법탄은 쏜 무기). */
    private void sanctify(Player p, UniqueDef u, DamageContext ctx) {
        DerivedStats st = stats(p);
        double amount = hitW(p, ctx) * st.power(hitKind(p, ctx)) * u.num("pct") + st.healPower() * UniqueProcs.SANCTIFY_HEAL_POWER;
        if (amount <= 0) return;
        List<Player> allies = services.targets().alliesIn(p, p.getLocation(), u.num("radius"));
        boolean solo = allies.stream().allMatch(a -> a.equals(p));
        if (solo) {
            if (hpRatio(p) < 0.999) services.damage().heal(p, 0, amount * UniqueProcs.SANCTIFY_SOLO, HealKind.SKILL, true);
            return;
        }
        Player worst = allies.stream().filter(a -> hpRatio(a) < 0.999).min(Comparator.comparingDouble(this::hpRatio)).orElse(null);
        if (worst == null) return;
        services.damage().heal(worst, 0, amount, HealKind.SKILL, true);
        SkillFx.burst(worst.getLocation().add(0, 1.2, 0), Particle.HAPPY_VILLAGER, 4, 0.3, 0, null);
    }

    /** 관통: 화살이 날던 줄 위, 주 대상 뒤 10칸 안의 적 pierce 명에게 같은 화살 피해 × (1 − 0.2k). */
    private void pierce(Player p, UniqueDef u, LivingEntity t, double arrowMult, double w, DamageKind kind) {
        Location eye = p.getEyeLocation();
        Location center = t.getLocation().add(0, t.getHeight() * 0.5, 0);
        Vector dir = center.toVector().subtract(eye.toVector());
        if (dir.lengthSquared() < 1e-6) return;
        dir.normalize();
        double reach = 10.0;
        List<Object[]> line = new ArrayList<>();
        for (LivingEntity x : services.targets().enemiesIn(p, center, reach)) {
            if (x.equals(t)) continue;
            Vector rel = x.getLocation().add(0, x.getHeight() * 0.5, 0).toVector().subtract(center.toVector());
            double along = rel.dot(dir);
            if (along <= 0 || along > reach) continue;
            double off = rel.clone().subtract(dir.clone().multiply(along)).length();
            if (off <= 0.6 + x.getWidth() * 0.5) line.add(new Object[] {along, x});
        }
        line.sort(Comparator.comparingDouble(o -> (Double) o[0]));
        double far = u.num("dist");
        int k = 0;
        for (Object[] o : line) {
            LivingEntity x = (LivingEntity) o[1];
            k++;
            double m = arrowMult * UniqueProcs.pierceMult(k);
            if (p.getLocation().distanceSquared(x.getLocation()) >= far * far) m *= 1 + u.num("pct") * UniqueProcs.pvp(x instanceof Player);
            services.damage().deal(DamageContext.attack(p, x, m, DamageType.RANGED).kind(kind).weaponHit(w).source("unique:longshot"));
            SkillFx.line(center, x.getLocation().add(0, x.getHeight() * 0.5, 0), 0.5, Particle.CRIT, null);
            if (k >= u.count("pierce")) break;
        }
    }

    private void overcharge(Player p, UniqueDef u, LivingEntity t, double pct) {
        Location at = t.getLocation();
        int n = 0;
        for (LivingEntity x : services.targets().enemiesIn(p, at, u.num("radius"))) {
            hit(p, x, pct, DamageKind.MAGIC, DamageContext.Base.SKILL, "overcharge", Double.NaN);
            if (++n >= UniqueProcs.OVERCHARGE_TARGETS) break;
        }
        SkillFx.burst(at.clone().add(0, 1, 0), Particle.ELECTRIC_SPARK, 24, 0.8, 0.1, null);
        SkillFx.sound(at, Sound.ENTITY_ZOMBIE_VILLAGER_CURE, 0.25f, 2.0f);
    }

    /** 수호 기운: 전투 중(최근 5초)이고 안전지대 밖이면 period 초마다 반경 안 아군(나 + 같은 파티, 최대 5명)에게 보호막. */
    private void ward(Player p, UniqueDef u, long now) {
        UUID me = p.getUniqueId();
        if (!procs.inCombat(me, UniqueProcs.WARD_COMBAT, now) || services.targets().inSafeZone(p.getLocation())) return;
        if (!procs.auraDue(me, u.num("period"), now)) return;
        List<Player> allies = new ArrayList<>(services.targets().alliesIn(p, p.getLocation(), u.num("radius")));
        allies.sort(Comparator.comparingDouble(a -> a.getLocation().distanceSquared(p.getLocation())));
        int n = 0;
        for (Player a : allies) {
            services.effects().addShield(a, services.stats().maxHp(a) * u.num("pct"), u.num("duration"), "unique:ward");
            if (++n >= UniqueProcs.WARD_TARGETS) break;
        }
        SkillFx.circle(p.getLocation().add(0, 0.2, 0), 1.2, 16, Particle.END_ROD, null);
    }

    // ── 공통 ─────────────────────────────────────────────────────────────

    /**
     * 고유 효과 덧 피해 한 건 (치명 가능 · 흡혈 없음 · 다른 고유 효과 안 켬). 플레이어 대상은 × 0.5.
     * @param w 기준이 PER_HIT 일 때 무기 한 방 W (화살 = 쏜 활 W, NaN = 지금 든 무기 — {@link #hitW})
     */
    private void hit(Player p, LivingEntity x, double mult, DamageKind kind, DamageContext.Base base, String id, double w) {
        if (x == null || !x.isValid() || x.isDead() || mult <= 0) return;
        DamageType type = kind == DamageKind.MAGIC ? DamageType.MAGIC : DamageType.MELEE;
        services.damage().deal(DamageContext.attack(p, x, mult * UniqueProcs.pvp(x instanceof Player), type).kind(kind).base(base)
                .weaponHit(w).source("unique:" + id).noLifesteal());
    }

    /**
     * 덧 피해의 무기 한 방 W (0.3.6.1 안전 검토 3): 화살은 쏜 순간의 활 W ({@link DamageContext#weaponHit}) — 날아가는 사이 단도로 바꿔도
     * 휩쓸기·연타·방패 강타·연쇄 번개·관통·찢는 치명이 활 W 로. 근접은 지금 든 무기 (ctx 에 W 가 없음).
     */
    private double hitW(Player p, DamageContext ctx) { return ctx.hasWeaponHit() ? ctx.weaponHit() : stats(p).weaponDamage(); }

    /** {@link #hitW} 의 순수 판 (시험용): 쏜 무기 W 가 ctx 에 있으면 그것, 없으면 지금 든 무기 W. */
    static double hitW(DamageContext ctx, double heldW) { return ctx.hasWeaponHit() ? ctx.weaponHit() : heldW; }

    /** 덧 피해의 피해 종류: 화살·마법탄은 쏜 무기의 종류 (ctx), 근접은 지금 든 무기. */
    private DamageKind hitKind(Player p, DamageContext ctx) { return hitKind(ctx, weaponKind(p)); }

    /** {@link #hitKind(Player, DamageContext)} 의 순수 판 (시험용). */
    static DamageKind hitKind(DamageContext ctx, DamageKind heldKind) {
        return ctx.firedWith() != null && ctx.kind() != null ? ctx.kind() : heldKind;
    }

    private static void mult(DamageContext ctx, double m) {
        if (m > 0 && Math.abs(m - 1) > 1e-9) ctx.amount(ctx.amount() * m);
    }

    private DerivedStats stats(Player p) { return services.stats().get(p); }

    private DamageKind weaponKind(Player p) { return stats(p).weaponKind(); }

    private boolean isBoss(LivingEntity e) { return services.bosses().byEntity(e).isPresent(); }

    /** 상태이상 몇 가지가 걸렸나 (약점 파고들기: 불태움·독·출혈·서리·느려짐·약화·실명·표식). */
    private int statusCount(LivingEntity t) {
        var fx = services.effects();
        int n = 0;
        if (fx.has(t, "burn")) n++;
        if (fx.has(t, "poison") || fx.has(t, "venom")) n++;
        if (fx.has(t, "bleed")) n++;
        if (fx.has(t, "frost") || fx.has(t, "frozen")) n++;
        if (fx.has(t, "slow")) n++;
        if (fx.has(t, "weaken")) n++;
        if (fx.has(t, "blind")) n++;
        if (fx.has(t, "mark")) n++;
        return n;
    }

    private double hpRatio(LivingEntity e) {
        if (e instanceof Player p) return services.stats().currentHp(p) / Math.max(1, services.stats().maxHp(p));
        HealthPool pool = services.damage().poolOf(e).orElse(null);
        if (pool != null) return pool.health() / Math.max(1, pool.maxHealth());
        var a = e.getAttribute(Attribute.MAX_HEALTH);
        double max = a == null ? 20.0 : a.getValue();
        return e.getHealth() / Math.max(1, max);
    }

    // ── 타이머 · 리스너 ──────────────────────────────────────────────────

    private void tick() {
        long now = now();
        ticks++;
        for (Player p : Bukkit.getOnlinePlayers()) {
            try {
                UniqueDef u = current(p);
                boolean steady = u != null && u.is("steadfast") && !p.isDead() && hpRatio(p) >= u.num("thr") - 1e-9;
                if (steady) {
                    if (ticks % 2 == 0 || !services.effects().hasBuff(p, STEADFAST_BUFF)) {
                        services.effects().applyBuff(p, Map.of("knockback_immune", 1.0), 2.5, STEADFAST_BUFF);
                    }
                } else if (services.effects().hasBuff(p, STEADFAST_BUFF)) {
                    services.effects().removeBuff(p, STEADFAST_BUFF);
                }
                if (u != null && u.is("ward_aura") && !p.isDead()) ward(p, u, now);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("고유 효과 타이머 오류 (" + p.getName() + ")", t);
            }
        }
        if (ticks % 10 == 0) procs.prune(now);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        held.remove(e.getPlayer().getUniqueId());
        procs.forget(e.getPlayer().getUniqueId());
    }
}
