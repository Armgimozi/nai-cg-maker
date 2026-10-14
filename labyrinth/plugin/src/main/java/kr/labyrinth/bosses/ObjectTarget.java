package kr.labyrinth.bosses;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.function.BiPredicate;
import java.util.function.Consumer;
import kr.labyrinth.combat.DamageContext;
import kr.labyrinth.combat.DamageType;
import kr.labyrinth.content.BossDef;
import kr.labyrinth.core.Keys;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.InstanceContext;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Display;
import org.bukkit.entity.Husk;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;

/**
 * 부술 수 있는 보스 기믹 오브젝트 (GDD §8.2 {@code ObjectTarget}: 알주머니·고치·인장·서가…).
 * 투명·무음·AI 없는 히트박스(Husk) + fx 모델 디스플레이 + HP 표시. 자체 HP 풀이라 근접·화살·직업/무기 스킬 모두 그대로 맞는다
 * ({@code BossService.byEntity} 가 이 핸들을 돌려주므로 DamageService·TargetFilter 가 적으로 인식).
 * 피해 유형 필터({@link #accept})로 "원거리로만 깰 수 있는 인장" 같은 규칙을 건다. 보스 사망·종료 시 함께 제거.
 */
public final class ObjectTarget implements BossHandle {

    private final Boss owner;
    private final String id;
    private final String name;
    private final Husk hitbox;
    private final ItemDisplay model;
    private final TextDisplay label;
    private final double max;
    private double hp;
    private boolean dead;
    private final Set<DamageType> accepted = EnumSet.allOf(DamageType.class);
    private final List<Consumer<BossHandle>> onDestroyed = new ArrayList<>();
    private String extra = "";
    private final double labelHeight;
    private BiPredicate<ObjectTarget, DamageContext> hitFilter;

    ObjectTarget(Boss owner, String id, String name, Location at, double hp, String fxModel, float modelScale,
                 double hitWidth, double hitHeight) {
        this.owner = owner;
        this.id = id;
        this.name = name;
        this.max = Math.max(1, hp);
        this.hp = this.max;
        Location l = at.clone();
        l.setPitch(0);
        double scale = Math.max(0.3, Math.min(6, Math.max(hitWidth / 0.6, hitHeight / 1.95)));
        this.hitbox = at.getWorld().spawn(l, Husk.class, false, e -> {
            e.setPersistent(false);
            e.setRemoveWhenFarAway(false);
            e.setInvisible(true);
            e.setSilent(true);
            e.setAI(false);
            e.setGravity(false);
            e.setCollidable(false);
            e.setCanPickupItems(false);
            if (e.getEquipment() != null) e.getEquipment().clear();
            e.setAdult();
            attr(e, Attribute.SCALE, scale);
            attr(e, Attribute.KNOCKBACK_RESISTANCE, 1.0);
            attr(e, Attribute.MAX_HEALTH, 100);
            e.setHealth(100);
            Keys.tagTransient(e, Keys.BOSS, owner.id() + ":" + id);
        });
        this.model = fxModel == null ? null : owner.fx().model(fxModel, l, modelScale, Display.Billboard.FIXED);
        this.labelHeight = Math.max(1.2, hitHeight + 0.5);
        this.label = owner.fx().label(l.clone().add(0, labelHeight, 0), "", 0.9f);
        owner.fx().track(hitbox);
        refresh();
    }

    private static void attr(LivingEntity e, Attribute a, double v) {
        AttributeInstance i = e.getAttribute(a);
        if (i != null) i.setBaseValue(v);
    }

    /** 이 유형의 피해만 받는다 (나머지는 "통하지 않음" 표시). */
    public ObjectTarget accept(DamageType... types) {
        accepted.clear();
        accepted.addAll(List.of(types));
        return this;
    }

    public ObjectTarget onDestroyed(Consumer<BossHandle> cb) {
        onDestroyed.add(cb);
        return this;
    }

    /**
     * 피해 직전 가로채기 (유형 필터 통과 후). false 를 돌려주면 피해를 무시한다(HP 그대로).
     * 서열 퍼즐의 "어느 책장을 쳤는가"·먹물 분신의 "누가 때렸는가"처럼 HP 가 아니라 맞은 사실이 중요한 기믹용.
     */
    public ObjectTarget onHit(BiPredicate<ObjectTarget, DamageContext> filter) {
        this.hitFilter = filter;
        return this;
    }

    /** 머리 위 이름·HP 표시를 없앤다 (정체를 숨겨야 하는 오브젝트 — 먹물 분신 등). */
    public ObjectTarget hideLabel() {
        owner.fx().discard(label);
        return this;
    }

    /** HP 줄 옆 추가 글자 (카운트다운 등). */
    public void extra(String mm) {
        this.extra = mm == null ? "" : mm;
        refresh();
    }

    public Boss owner() { return owner; }

    public String kind() { return id; }

    public Location at() { return hitbox.getLocation(); }

    public ItemDisplay display() { return model; }

    private void refresh() {
        if (label == null || !label.isValid()) return;
        double ratio = hp / max;
        int segs = 10;
        int full = (int) Math.ceil(ratio * segs);
        String bar = "<#ff6a6a>" + "|".repeat(Math.max(0, full)) + "</#ff6a6a><#3a3a3a>" + "|".repeat(Math.max(0, segs - full)) + "</#3a3a3a>";
        BossFx.text(label, "<white>" + name + "</white>\n<b>" + bar + "</b> <gray>" + Text.num(hp) + "</gray>"
                + (extra.isEmpty() ? "" : "\n" + extra));
    }

    // ── BossHandle / CustomMob / HealthPool ───────────────────────────────

    @Override public BossDef def() { return owner.def(); }
    @Override public int phase() { return owner.phase(); }
    @Override public void onDeath(Consumer<BossHandle> callback) { onDestroyed(callback); }
    @Override public void end() { remove(); }
    @Override public String id() { return owner.id() + ":" + id; }
    @Override public String displayName() { return name; }
    @Override public LivingEntity entity() { return hitbox; }
    @Override public InstanceContext instance() { return owner.instance(); }
    @Override public double damage() { return 0; }
    @Override public void addThreat(Player player, double amount) { }
    @Override public void taunt(Player player, double seconds) { }
    @Override public Player target() { return null; }
    @Override public double health() { return hp; }
    @Override public double maxHealth() { return max; }
    @Override public double defense() { return 0; }
    @Override public boolean invulnerable() { return dead; }
    @Override public boolean isAlive() { return !dead && hp > 0; }

    @Override
    public double applyDamage(double amount, DamageContext ctx) {
        if (dead || amount <= 0) return 0;
        DamageType type = ctx == null ? DamageType.TRUE : ctx.type();
        if (!accepted.contains(type)) {
            BossFx.particle(Particle.SMOKE, at().add(0, 1, 0), 4, 0.2, 0.3, 0.2, 0.01);
            if (ctx != null && ctx.attackerPlayer() != null) {
                owner.services().hud().actionBar(ctx.attackerPlayer(), Text.mm("<gray>" + name + "에는 이 공격이 통하지 않습니다"), 30);
            }
            return 0;
        }
        if (hitFilter != null) {
            boolean pass;
            try {
                pass = hitFilter.test(this, ctx);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("보스 오브젝트 피격 처리 오류", t);
                pass = false;
            }
            if (!pass || dead) return 0;
        }
        double dealt = Math.min(hp, amount);
        hp -= dealt;
        BossFx.dust(at().add(0, 0.9, 0), Color.fromRGB(230, 230, 240), 1.1f, 4, 0.3);
        if (hp <= 0.0001) destroy();
        else refresh();
        return dealt;
    }

    /** 직접 깎기 (웅크리기 연타 등 피해 경로 밖의 기믹). */
    public void chip(double amount) {
        if (dead || amount <= 0) return;
        hp = Math.max(0, hp - amount);
        if (hp <= 0.0001) destroy();
        else refresh();
    }

    @Override
    public double heal(double amount) { return 0; }

    private void destroy() {
        if (dead) return;
        dead = true;
        hp = 0;
        Location at = at();
        BossFx.particle(Particle.POOF, at.clone().add(0, 0.8, 0), 18, 0.4, 0.5, 0.4, 0.05);
        BossFx.sound(at, Sound.BLOCK_WOOL_BREAK, 1f, 0.7f);
        for (Consumer<BossHandle> cb : onDestroyed) {
            try {
                cb.accept(this);
            } catch (Throwable t) {
                kr.labyrinth.core.Log.error("보스 오브젝트 파괴 콜백 오류", t);
            }
        }
        remove();
    }

    @Override
    public void remove() {
        dead = true;
        owner.service().unregisterObject(this);
        owner.fx().discard(hitbox);
        owner.fx().discard(model);
        owner.fx().discard(label);
    }
}
