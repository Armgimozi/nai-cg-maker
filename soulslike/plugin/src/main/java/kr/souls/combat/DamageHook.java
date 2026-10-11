package kr.souls.combat;

import kr.souls.Keys;
import kr.souls.Souls;
import kr.souls.progression.StatBlock;
import kr.souls.skill.Combat;
import net.kyori.adventure.key.Key;
import org.bukkit.Bukkit;
import org.bukkit.Tag;
import org.bukkit.damage.DamageType;
import org.bukkit.tag.DamageTypeTags;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDamageEvent.DamageCause;

import java.util.EnumSet;
import java.util.Locale;
import java.util.Set;

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
 *         <li>근접 공격은 동작 실행기 (combat/MoveRunner, M1 P1a) 가 Combat.damage 로 넣으므로 위의 player_skill 이다 (souls 단위의 공격력
 *             × 동작 배율 × pvp.damage-scale). 바닐라 근접 공격은 InputRouter 가 늘 취소한다. 그래도 바닐라 근접 피해가 오면 (다른
 *             플러그인) 바닐라 × 최대 HP / 20 × pvp.damage-scale (player_vanilla).</li>
 *         <li>나머지 모두 (투사체: 화살·눈덩이·투척 물약 player_projectile, 잔류 구름·가시·번개·TNT 같은 간접 피해 player_indirect):
 *             바닐라 × 최대 HP / 20 × pvp.damage-scale.</li>
 *       </ul>
 *       그다음 방어: 피해 = 원피해² / (원피해 + 방어). 피해 종류가 술 (souls:magic, 태그 #souls:magic) 이면 마법 저항, 아니면 방어력 (체력).</li>
 * </ul>
 * 시험 피해 (/soulstest hit, rollhit, warn) 는 날 피해를 보는 시험이라 이 고리를 지나지 않는다 (TestHits.raw). def 깃발을 주면 지난다.
 * M1 에서 적의 공격이 DamageCalc 를 먼저 지나면 그 피해에 표시를 달아 여기서 두 번 줄이지 않는다.
 * <p>
 * 적을 치는 피해는 이 고리를 지나지 않는다: 동작 실행기가 우리 적 (enemy/Foes, 가상 체력) 에 Foes.hit 으로 넣는다 (M1 P1a. M1 전의
 * 공격력 다리 onHitFoe 와 pve.bridge-scale 은 없앴다).
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
        if (cause instanceof Player) {
            Entity direct = e.getDamageSource().getDirectEntity();
            double scale = Combat.maxHealth(p) / 20.0 * plugin.cfg().pvp.damageScale();
            if (Combat.inSkill()) {
                // 플러그인 술·스킬, 동작 실행기의 근접 한 대 (M1 P1a), 시험 pvphit: 이미 HP 단위
                from = "player_skill";
            } else if (direct == cause && (dc == DamageCause.ENTITY_ATTACK || dc == DamageCause.ENTITY_SWEEP_ATTACK)) {
                // 바닐라 근접 (InputRouter 가 늘 취소하므로 다른 플러그인이 넣은 것뿐): 바닐라 단위. 때린 이가 몸소 친 것만 (잔류 구름의
                // 즉시 피해도 원인이 사람이고 ENTITY_ATTACK 으로 올 수 있다: 그것은 아래 player_indirect)
                from = "player_vanilla";
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
}
