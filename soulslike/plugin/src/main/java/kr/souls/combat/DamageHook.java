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
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
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
 *   <li>원인 물체가 있는 피해: 적이면 원피해 × 난이도 enemy-damage (5.7). 플레이어 (PvP 켬) 면 근접 한 대를 souls 무기의 공격력으로
 *       바꾼다 (M1 의 동작 실행기 전의 다리, 검토 T9: AR × (0.2 + 0.8 × 회복²) × pvp.damage-scale). 그다음 방어:
 *       피해 = 원피해² / (원피해 + 방어). 피해 종류가 술 (souls:magic, 태그 #souls:magic) 이면 마법 저항, 아니면 방어력 (체력).</li>
 * </ul>
 * 시험 피해 (/soulstest hit, rollhit, warn) 는 날 피해를 보는 시험이라 이 고리를 지나지 않는다 (TestHits.raw). def 깃발을 주면 지난다.
 * M1 에서 적의 공격이 DamageCalc 를 먼저 지나면 그 피해에 표시를 달아 여기서 두 번 줄이지 않는다.
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
    /** 근접 공격 직전의 바닐라 공격 대기 (0..1). 피해 이벤트 때는 이미 0 으로 돌아가 있다 */
    private final Map<UUID, Float> cooldowns = new HashMap<>();

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
        cooldowns.put(e.getPlayer().getUniqueId(), e.getPlayer().getAttackCooldown());
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        cooldowns.remove(e.getPlayer().getUniqueId());
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
            from = "player";
            if (e.getDamageSource().getDirectEntity() == a && (dc == DamageCause.ENTITY_ATTACK || dc == DamageCause.ENTITY_SWEEP_ATTACK)) {
                Weapons.Def w = plugin.weapons().of(a.getInventory().getItemInMainHand());
                if (Stats.isMelee(w)) {
                    StatBlock s = plugin.stats().of(a);
                    double ar = DamageCalc.ar(plugin.cfg().stats, Stats.arms(w), s.str(), plugin.stats().twoHanded(a, w));
                    raw = DamageCalc.pvpMelee(ar, cooldowns.getOrDefault(a.getUniqueId(), 1f), plugin.cfg().pvp.damageScale());
                }
            } else {
                // 투사체 같은 바닐라 피해는 바닐라만큼 (최대 HP / 20)
                raw = raw * Combat.maxHealth(p) / 20.0 * plugin.cfg().pvp.damageScale();
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
}
