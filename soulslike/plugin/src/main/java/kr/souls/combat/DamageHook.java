package kr.souls.combat;

import io.papermc.paper.event.player.PrePlayerAttackEntityEvent;
import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.item.Weapons;
import kr.souls.progression.StatBlock;
import kr.souls.progression.Stats;
import kr.souls.skill.Combat;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Tag;
import org.bukkit.damage.DamageType;
import org.bukkit.tag.DamageTypeTags;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;
import org.bukkit.event.player.PlayerQuitEvent;

import java.util.EnumSet;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 플레이어가 받는 피해의 한 곳 (3.7, 검토 T10). 구르기 무적 (Roll, HIGH) 이 피한 것은 오지 않는다 (가장 높은 단계, 취소된 것은 건너뛴다).
 * <ul>
 *   <li>환경 피해 (원인 물체가 없는 낙하·용암·불·불붙음·뜨거운 바닥·물에 빠짐·끼임·접촉·얼음·공허·독·시듦 …): × 최대 HP / 20.
 *       플레이어 체력이 큰 숫자 (400~1500) 라 바닐라만큼 위험하게 (EnvDamage, 3.7). 캠프파이어 (화톳불) 피해는 없다.</li>
 *   <li>원인 물체가 있는 피해: 적이면 원피해 × 난이도 enemy-damage (5.7). 플레이어 (PvP 켬) 면 피해가 어디서 왔는지로 단위를 고른다
 *       (검토 pvp-indirect-unscaled: 빼고 남은 것을 HP 단위로 보지 않는다):
 *       <ul>
 *         <li>플러그인 술·스킬 (skill/Combat.damage 안, Combat.inSkill) 과 시험 pvphit: 이미 HP 단위라 그대로 (from=player_skill).
 *             같은 틱에 휘두른 한 대가 있어도 이것이 먼저다.</li>
 *         <li>바로 이 틱에 그 사람을 때린 근접 한 대 (PrePlayerAttackEntityEvent 로 적어 둔 것): souls 근접 무기면 공격력으로 바꾼다
 *             (M1 의 동작 실행기 전의 다리, 검토 T9: AR × (0.2 + 0.8 × 회복²) × pvp.damage-scale, from=player_melee). 그 밖 (맨손, 활로
 *             때리기, 바닐라 아이템) 은 바닐라 × 최대 HP / 20 × pvp.damage-scale (player_vanilla). 휩쓸기 (같은 틱의 곁 피해) 도 같다
 *             (player_sweep).</li>
 *         <li>나머지 모두 (투사체: 화살·눈덩이·투척 물약 player_projectile, 잔류 구름·가시·번개·TNT 같은 간접 피해 player_indirect):
 *             바닐라 × 최대 HP / 20 × pvp.damage-scale.</li>
 *       </ul>
 *       그다음 방어: 피해 = 원피해² / (원피해 + 방어). 피해 종류가 술 (souls:magic, 태그 #souls:magic) 이면 마법 저항, 아니면 방어력 (체력).</li>
 * </ul>
 * 시험 피해 (/soulstest hit, rollhit, warn) 는 날 피해를 보는 시험이라 이 고리를 지나지 않는다 (TestHits.raw). def 깃발을 주면 지난다.
 * M1 에서 적의 공격이 DamageCalc 를 먼저 지나면 그 피해에 표시를 달아 여기서 두 번 줄이지 않는다.
 * <p>
 * 적을 칠 때 (플레이어가 아닌 것, onHitFoe): souls 근접 무기로 바로 그것을 친 한 대면 바닐라 피해 (주먹 1 + 치명타) 를 공격력으로
 * 바꾼다: AR × (0.2 + 0.8 × 회복²) × pve.bridge-scale (M1 의 동작 실행기 전의 다리, 검토 stat-values-without-effect. 직검 72 → 6.4,
 * 양손 대검 123 → 11.1, 단도 52 → 4.7: 바닐라 철검·다이아 도끼쯤). 그래서 근력·양손 잡기가 혼자 할 때도 듣는다. 회복은 든 무기 분류의
 * 공격 속도 (AttributeApplier.weaponSpeed: 민첩이 빠르게 한다) 로 찬다. 스킬 피해와 휩쓸기는 그대로.
 */
public final class DamageHook implements Listener {
    /** 술 피해 종류 (데이터팩 souls:magic) 와 태그 */
    public static final Key MAGIC = Key.key(Keys.NS, "magic");
    /** 최대 HP / 20 을 곱하는 환경 피해 */
    private static final Set<DamageCause> ENV = EnumSet.of(DamageCause.FALL, DamageCause.FIRE, DamageCause.FIRE_TICK, DamageCause.LAVA,
            DamageCause.HOT_FLOOR, DamageCause.DROWNING, DamageCause.SUFFOCATION, DamageCause.CONTACT, DamageCause.FREEZE, DamageCause.VOID,
            DamageCause.POISON, DamageCause.WITHER, DamageCause.MAGIC, DamageCause.LIGHTNING, DamageCause.CRAMMING, DamageCause.FLY_INTO_WALL,
            DamageCause.WORLD_BORDER, DamageCause.FALLING_BLOCK, DamageCause.BLOCK_EXPLOSION, DamageCause.STARVATION, DamageCause.DRYOUT);

    private final Souls plugin;
    /** 근접 한 대: 맞은 이, 틱, 직전의 바닐라 공격 대기 (0..1, 피해 이벤트 때는 이미 0 으로 돌아가 있다) */
    private record Swing(UUID victim, long tick, float cooldown) {}

    private final Map<UUID, Swing> swings = new HashMap<>();

    public DamageHook(Souls plugin) {
        this.plugin = plugin;
    }

    /** 이 피해 종류가 술 (마법 저항으로 줄인다) 인가: souls:magic 이거나 태그 #souls:magic 에 들었다. */
    public static boolean magic(DamageType t) {
        if (t == null) return false;
        if (MAGIC.equals(t.key())) return true;
        try {
            Tag<DamageType> tag = Bukkit.getTag(DamageTypeTags.REGISTRY_DAMAGE_TYPES, Keys.of("magic"), DamageType.class);
            return tag != null && tag.isTagged(t);
        } catch (RuntimeException ex) {
            return false;
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSwing(PrePlayerAttackEntityEvent e) {
        if (e.isCancelled()) return;
        swings.put(e.getPlayer().getUniqueId(), new Swing(e.getAttacked().getUniqueId(), plugin.ticker().now(), e.getPlayer().getAttackCooldown()));
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        swings.remove(e.getPlayer().getUniqueId());
    }

    /** a 가 이 틱에 휘두른 한 대 (없으면 null). */
    private Swing swingNow(Player a) {
        Swing s = swings.get(a.getUniqueId());
        return s != null && s.tick() == plugin.ticker().now() ? s : null;
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p) || TestHits.raw()) return;
        if (!plugin.worlds().ours(p.getWorld())) return;
        Entity cause = e.getDamageSource().getCausingEntity();
        DamageCause dc = e.getCause();
        if (dc == DamageCause.CAMPFIRE) {
            e.setCancelled(true);
            return;
        }
        if (cause == null || cause == p) {
            if (ENV.contains(dc)) e.setDamage(e.getDamage() * Combat.maxHealth(p) / 20.0);
            return;
        }
        double raw = e.getDamage();
        String from = "foe";
        if (cause instanceof Player a) {
            Entity direct = e.getDamageSource().getDirectEntity();
            Swing sw = direct == a ? swingNow(a) : null;
            double scale = Combat.maxHealth(p) / 20.0 * plugin.cfg().pvp.damageScale();
            if (Combat.inSkill()) {
                // 플러그인 술·스킬과 시험 pvphit: 이미 HP 단위 (같은 틱의 휘두름보다 먼저 본다)
                from = "player_skill";
            } else if (sw != null && dc == DamageCause.ENTITY_ATTACK && sw.victim().equals(p.getUniqueId())) {
                Weapons.Def w = plugin.weapons().of(a.getInventory().getItemInMainHand());
                if (Stats.isMelee(w)) {
                    from = "player_melee";
                    raw = DamageCalc.pvpMelee(ar(a, w), sw.cooldown(), plugin.cfg().pvp.damageScale());
                } else {
                    from = "player_vanilla";
                    raw = raw * scale;
                }
            } else if (sw != null && dc == DamageCause.ENTITY_SWEEP_ATTACK) {
                from = "player_sweep";
                raw = raw * scale;
            } else {
                // 투사체 (화살·눈덩이·투척 물약) 와 간접 피해 (잔류 구름·가시·번개·TNT …): 바닐라 단위
                from = direct instanceof Projectile ? "player_projectile" : "player_indirect";
                raw = raw * scale;
            }
        } else {
            raw = raw * plugin.difficulty().enemyDamage();
        }
        boolean mag = magic(e.getDamageSource().getDamageType());
        StatBlock s = plugin.stats().of(p);
        double def = mag ? DamageCalc.magicRes(plugin.cfg().stats, s.level(), s.mnd()) : DamageCalc.defense(plugin.cfg().stats, s.level(), s.vig());
        double dealt = DamageCalc.reduce(raw, def);
        e.setDamage(dealt);
        plugin.test(p, String.format(Locale.ROOT, "DEF from=%s kind=%s raw=%.2f def=%.1f dealt=%.2f t=%d", from, mag ? "magic" : "physical",
                raw, def, dealt, plugin.ticker().now()));
    }

    /** a 가 든 근접 무기 w 의 공격력 (근력, 양손 잡기). */
    private double ar(Player a, Weapons.Def w) {
        StatBlock s = plugin.stats().of(a);
        return DamageCalc.ar(plugin.cfg().stats, Stats.arms(w), s.str(), plugin.stats().twoHanded(a, w));
    }

    /** 플레이어가 적 (플레이어가 아닌 것) 을 souls 근접 무기로 친 한 대: 공격력 다리 (위 클래스 설명). */
    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onHitFoe(EntityDamageByEntityEvent e) {
        if (e.getEntity() instanceof Player || !(e.getEntity() instanceof LivingEntity victim) || !(e.getDamager() instanceof Player a)) return;
        if (Combat.inSkill() || TestHits.raw() || e.getCause() != DamageCause.ENTITY_ATTACK || !plugin.worlds().ours(victim.getWorld())) return;
        Swing sw = swingNow(a);
        if (sw == null || !sw.victim().equals(victim.getUniqueId())) return;
        Weapons.Def w = plugin.weapons().of(a.getInventory().getItemInMainHand());
        if (!Stats.isMelee(w)) return;
        double ar = ar(a, w);
        double dealt = DamageCalc.pvpMelee(ar, sw.cooldown(), plugin.cfg().pve.bridgeScale());
        double vanilla = e.getDamage();
        e.setDamage(dealt);
        plugin.test(a, String.format(Locale.ROOT, "PVE_HIT weapon=%s ar=%.1f cd=%.2f vanilla=%.2f dealt=%.2f to=%s t=%d", w.id(), ar,
                sw.cooldown(), vanilla, dealt, victim.getType().key().value(), plugin.ticker().now()));
    }
}
