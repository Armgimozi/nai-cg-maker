package kr.labyrinth.classes;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.GuardianSkills;
import kr.labyrinth.classes.skills.ShadowSkills;
import kr.labyrinth.classes.skills.SkillContext;
import kr.labyrinth.classes.skills.SkillFx;
import kr.labyrinth.classes.skills.Targeting;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageService;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.Params;
import kr.labyrinth.core.Text;
import kr.labyrinth.stats.StatBlock;
import kr.labyrinth.stats.StatContributor;
import org.bukkit.Bukkit;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

/**
 * 직업 패시브 6종 (classes.yml passive) + 수호의 맹세 피해 분담 + 독날 적중 효과.
 * <ul>
 *   <li>강철 의지(수호기사): 받는 피해 −10%(스탯), 위협 ×2, HP 30% 이하 → 5초 피해 감소 +20% (60초 1회)</li>
 *   <li>피의 분노(광전사): 잃은 HP 비례 피해 +최대 25%(HP 50% 이하부터), 기본 공격 적중 시 MP 3</li>
 *   <li>매의 눈(사냥꾼): 끝까지 당긴 화살 +30%·MP 3, 12칸 이상 적에게 치명타 +8%. 활 당기며 걷기(draw_move, 어디서나)는
 *       {@link kr.labyrinth.combat.BowDrawMove} · items.EquipmentListener (활 아이템 구성요소라 피해 훅이 아님)</li>
 *   <li>비전 공명(비전술사): 3명 이상 적중 시 MP 50% 환급(SkillContext), 서로 다른 스킬 4초 안 연계 +10%</li>
 *   <li>은총(사제): 마법 피해 +2% → Lv.45 +18% ({@link #graceMagicDamage}), 넘친 치유 → 보호막, 치유 시 MP (SkillContext.heal)</li>
 *   <li>급소 찌르기(그림자): 치명타 피해 +50%, 등 뒤 치명타 +20%, 독 중첩 대상 치명타 시 독 지속시간 갱신</li>
 * </ul>
 */
public final class ClassPassives implements DamageService.Hook, StatContributor {

    private final Services services;
    private final Map<UUID, Long> ironWillReady = new ConcurrentHashMap<>();
    private final Map<UUID, Double> bloodrageApplied = new ConcurrentHashMap<>();
    /** 비전 공명 연계: 대상 → (스킬 id, 시각). */
    private final Map<UUID, Map<UUID, Object[]>> arcaneCombo = new ConcurrentHashMap<>();
    private BukkitTask task;

    public ClassPassives(Services services) { this.services = services; }

    public void start() {
        services.damage().addHook(this);
        services.stats().addContributor(this);
        task = Bukkit.getScheduler().runTaskTimer(services.plugin(), this::tick, 10L, 10L);
    }

    public void stop() {
        if (task != null) task.cancel();
        services.damage().removeHook(this);
        services.stats().removeContributor(this);
        GuardianSkills.OathLinks.clear();
    }

    public void forget(Player p) {
        ironWillReady.remove(p.getUniqueId());
        bloodrageApplied.remove(p.getUniqueId());
        arcaneCombo.remove(p.getUniqueId());
    }

    private ClassDef cls(LivingEntity e) { return e instanceof Player p ? services.classes().classOf(p) : null; }

    private static boolean passive(ClassDef c, String id) { return c != null && c.passive() != null && id.equals(c.passive().id()); }

    private static boolean isDot(DamageContext ctx) { return ctx.sourceId() != null && ctx.sourceId().startsWith("effect:"); }

    // ── StatContributor ──────────────────────────────────────────────────

    @Override
    public void contribute(Player player, StatBlock block) {
        ClassDef c = services.classes().classOf(player);
        if (c == null || c.passive() == null) return;
        Params pp = c.passive().params();
        switch (c.passive().id()) {
            case "iron_will" -> block.add("damage_reduction", pp.dbl("damage_reduction", 0.10));
            case "vital_point" -> block.add("crit_damage", pp.dbl("crit_damage", 0.50));
            case "grace" -> block.add("magic_damage", graceMagicDamage(services.data().get(player).level(),
                    pp.dbl("magic_damage", 0.02), pp.dbl("magic_damage_per_level", 0.0036), pp.dbl("magic_damage_max", 0.20)));
            case "bloodrage" -> {
                double bonus = bloodrageApplied.getOrDefault(player.getUniqueId(), 0.0);
                if (bonus > 0) block.add("damage_mult", bonus);
            }
            default -> { }
        }
    }

    /**
     * 사제 은총의 마법 피해 가산 = base + perLevel × (레벨 − 1), 0 ~ max. 초반(Lv.10 +5%)은 낮고 깊은 층(Lv.45 +18%)은 높다 —
     * 0.3.5 기대값 모델에서 사제가 초반 +11% · 후반 −9% 로 벌어지던 것을 ±6% 안으로 (combat_spec §6.2).
     */
    static double graceMagicDamage(int level, double base, double perLevel, double max) {
        double v = base + perLevel * (Math.max(1, level) - 1);
        return Math.max(0, Math.min(max, v));
    }

    /** 광전사 피의 분노 보너스 = max_bonus × (threshold − HP비율) / threshold (0~max). */
    static double bloodrageBonus(double hpRatio, double threshold, double maxBonus) {
        if (threshold <= 0 || hpRatio >= threshold) return 0;
        return maxBonus * Math.min(1.0, (threshold - Math.max(0, hpRatio)) / threshold);
    }

    private void tick() {
        long cutoff = System.currentTimeMillis() - 10_000;
        for (Map<UUID, Object[]> m : arcaneCombo.values()) m.values().removeIf(v -> (Long) v[1] < cutoff);
        for (Player p : Bukkit.getOnlinePlayers()) {
            ClassDef c = services.classes().classOf(p);
            if (!passive(c, "bloodrage")) {
                if (bloodrageApplied.remove(p.getUniqueId()) != null) services.stats().markDirty(p);
                continue;
            }
            Params pp = c.passive().params();
            double ratio = services.stats().currentHp(p) / Math.max(1, services.stats().maxHp(p));
            double bonus = bloodrageBonus(ratio, pp.dbl("threshold", 0.50), pp.dbl("max_bonus", 0.25));
            double old = bloodrageApplied.getOrDefault(p.getUniqueId(), 0.0);
            if (Math.abs(bonus - old) > 0.01) {
                bloodrageApplied.put(p.getUniqueId(), bonus);
                services.stats().markDirty(p);
            }
            if (bonus > 0.12 && services.dungeon().isInLabyrinth(p)) {
                SkillFx.burst(p.getLocation().add(0, 1.0, 0), Particle.DUST, 2, 0.35, 0, SkillFx.dust(0xb01010, 1.0f));
            }
        }
    }

    // ── DamageService.Hook ───────────────────────────────────────────────

    @Override
    public void before(DamageContext ctx) {
        if (isDot(ctx)) return;
        Player atk = ctx.attackerPlayer();
        ClassDef c = cls(atk);
        if (c == null || c.passive() == null) return;
        Params pp = c.passive().params();
        LivingEntity target = ctx.target();
        switch (c.passive().id()) {
            case "iron_will" -> ctx.threat(ctx.threatMultiplier() * pp.dbl("threat_mult", 2.0));
            case "keen_eye" -> {
                if (ctx.type() == DamageType.RANGED && !ctx.isSkill() && ctx.usesAttackPower() && ctx.attackMultiplier() >= 0.999) {
                    ctx.amount(ctx.amount() * (1 + pp.dbl("full_draw_bonus", 0.30)));
                }
                if (atk.getLocation().distanceSquared(target.getLocation()) >= Math.pow(pp.dbl("far_distance", 12), 2)) {
                    ctx.critBonus(pp.dbl("far_crit", 0.08));
                }
            }
            case "arcane_resonance" -> {
                if (!ctx.isSkill() || ctx.sourceId() == null) break;
                Map<UUID, Object[]> m = arcaneCombo.get(atk.getUniqueId());
                Object[] last = m == null ? null : m.get(target.getUniqueId());
                if (last != null && !ctx.sourceId().equals(last[0])
                        && System.currentTimeMillis() - (Long) last[1] <= pp.dbl("combo_window", 4) * 1000) {
                    ctx.amount(ctx.amount() * (1 + pp.dbl("combo_bonus", 0.10)));
                }
            }
            case "vital_point" -> {
                if (Targeting.isBehind(atk, target, pp.dbl("back_angle", 100))) ctx.critBonus(pp.dbl("back_crit", 0.20));
            }
            default -> { }
        }
    }

    @Override
    public double absorb(DamageContext ctx, double damage) {
        if (!"guardian_oath".equals(ctx.sourceId())) return GuardianSkills.OathLinks.redirect(services, ctx, damage);
        return damage;
    }

    @Override
    public void after(DamageContext ctx) {
        if (ctx.cancelled()) return;
        // 수호기사: 위기 시 강철 의지 발동 (피해를 받은 쪽)
        if (ctx.target() instanceof Player victim && passive(cls(victim), "iron_will") && ctx.dealt() > 0 && !victim.isDead()) {
            Params pp = cls(victim).passive().params();
            double ratio = services.stats().currentHp(victim) / Math.max(1, services.stats().maxHp(victim));
            long now = System.currentTimeMillis();
            if (ratio <= pp.dbl("low_hp", 0.30) && ironWillReady.getOrDefault(victim.getUniqueId(), 0L) <= now) {
                ironWillReady.put(victim.getUniqueId(), now + (long) (pp.dbl("emergency_cooldown", 60) * 1000));
                services.effects().applyBuff(victim, Map.of("damage_reduction", pp.dbl("emergency_dr", 0.20)),
                        pp.dbl("emergency_duration", 5), "iron_will_emergency");
                SkillFx.helix(victim.getLocation(), 0.8, 2.2, 24, Particle.DUST, SkillFx.dust(0x7fb2ff, 1.4f));
                SkillFx.sound(victim.getLocation(), Sound.ITEM_ARMOR_EQUIP_NETHERITE, 1f, 0.8f);
                if (services.hud().skillMessages()) services.hud().actionBar(victim, Text.mm("<#7fb2ff><b>강철 의지!</b> <gray>— 피해 감소 +"
                        + Text.pct(pp.dbl("emergency_dr", 0.20)) + " (" + (int) pp.dbl("emergency_duration", 5) + "초)"), 40);
            }
        }
        if (isDot(ctx) || ctx.evaded()) return;
        Player atk = ctx.attackerPlayer();
        ClassDef c = cls(atk);
        if (c == null) return;
        LivingEntity target = ctx.target();
        // 독날 활성: 적중마다 독 중첩
        if (ctx.dealt() > 0 && services.effects().hasBuff(atk, "venom_blades") && services.targets().isEnemy(atk, target)) {
            ShadowSkills.VenomBlades.onHit(services, atk, target, c);
        }
        if (c.passive() == null) return;
        Params pp = c.passive().params();
        switch (c.passive().id()) {
            case "bloodrage" -> {
                if (!ctx.isSkill() && ctx.type() == DamageType.MELEE && ctx.dealt() > 0 && ctx.sourceId() == null) {
                    services.classes().restoreMana(atk, pp.dbl("mana_on_hit", 3));
                }
            }
            case "keen_eye" -> {
                if (ctx.type() == DamageType.RANGED && !ctx.isSkill() && ctx.usesAttackPower() && ctx.attackMultiplier() >= 0.999
                        && ctx.dealt() > 0) {
                    services.classes().restoreMana(atk, pp.dbl("mana_on_full_draw", 3));
                }
            }
            case "arcane_resonance" -> {
                if (ctx.isSkill() && ctx.sourceId() != null) {
                    arcaneCombo.computeIfAbsent(atk.getUniqueId(), u -> new ConcurrentHashMap<>())
                            .put(target.getUniqueId(), new Object[] {ctx.sourceId(), System.currentTimeMillis()});
                }
            }
            case "vital_point" -> {
                if (ctx.crit() && pp.bool("refresh_venom", true) && services.effects().stacks(target, "venom") > 0) {
                    services.effects().apply(target, "venom", 6, SkillContext.dotRatio(0.10, SkillContext.skillScale(c)), atk);
                }
            }
            default -> { }
        }
    }
}
