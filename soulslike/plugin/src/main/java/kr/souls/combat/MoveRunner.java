package kr.souls.combat;

import kr.souls.Souls;
import kr.souls.enemy.Foe;
import kr.souls.enemy.HitResult;
import kr.souls.input.InputBuffer;
import kr.souls.item.ItemFactory;
import kr.souls.item.Weapons;
import kr.souls.progression.StatBlock;
import kr.souls.progression.Stats;
import kr.souls.skill.Combat;
import io.papermc.paper.datacomponent.DataComponentTypes;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/**
 * 공격 동작 실행기 (3.6, M1 P1a). 사람마다 상태 하나: 대기 → 준비 → 판정 → 회복 → 대기. 입력은 input/InputRouter 가 Ticker 의 input
 * 자리에서 {@link #input} 으로 넣고, 이 체계는 moves 자리에서 {@link #tick} 으로 돈다 (M1_PLAN 0.6).
 * <ul>
 *   <li>시작할 때 무기를 적어 둔다 (2.3 의 6: 도중에 단축 칸을 바꿔도 시작한 무기의 값으로 끝까지 간다).</li>
 *   <li>틱: 분류의 준비/판정/회복 (content/moves.yml) 을 민첩으로 나눈 것 (MoveTiming). 한 동작은 min-light-cycle (10) 밑으로 가지 않는다.</li>
 *   <li>스태미나는 시작할 때 쓰고, 회복은 동작이 끝나는 틱에서 센다 (Stamina.spend 의 actionEnd). 1 이상이면 시작하고 모자라면 0 에서 멈춘다.</li>
 *   <li>느려짐: 준비·판정 −50%, 회복 −25% (combat/Slow: 걷기 속도라 시야가 좁아지지 않는다, PS 의 S4).</li>
 *   <li>첫 판정 틱에 앞으로 내딛는다 (땅 위에서만).</li>
 *   <li>판정 틱마다 HitQuery (부채꼴·직선) 로 대상을 찾아 Foes.hit (우리 적) 또는 PvP 의 한 대 (Combat.damage, souls 단위 ×
 *       pvp.damage-scale: DamageHook 의 player_skill) 를 넣는다. 한 대상은 한 동작에 한 번, 찌르기는 첫 대상만.</li>
 *   <li>약공격은 1·2·3단으로 잇는다 (입력 기억으로 이은 것, 끝나고 combo-grace 틱 안에 누른 것). 쉬었다 누르면 1단부터. 강공격·달리기
 *       공격 뒤의 약공격은 1단이다.</li>
 *   <li>동작 중의 입력은 끝나기 accept-before 틱 전부터 기억하고 (InputBuffer) 끝나는 틱에 낸다.</li>
 *   <li>준비·판정 중에 마시기·술 (CONSUMABLE 이 있는 것) 을 시작하지 못한다 (InputRouter 가 사용을 막고, 여기서도 끊는다, R17).</li>
 *   <li>서버는 이 동작 때문에 팔을 다시 휘두르지 않는다 (R3): 클라이언트가 누른 순간 이미 휘둘렀다.</li>
 *   <li>구르기 공격 (P1c): 구르기 시작에서 센 {@link #rollAttackWindow} 틱 (가벼운 구르기 9~16, 뒷걸음 7~14) 의 약공격·달리기 공격.
 *       창이 열리기 전 (구르는 중) 의 입력은 창이 열리는 틱까지 기억한다 (accept-before 틱 전부터). 동작 배율 combat.moves.motion.roll,
 *       틱은 약공격 1단, 스태미나는 약공격 × cost.roll. 시작하면 구르기의 대역을 곧바로 거둔다 (Tumble.reveal). 뒤의 약공격은 2단.</li>
 *   <li>구르기 (P1c): 준비·판정 중에는 막히고 (Roll 의 ROLL_DENY why=attack), 회복의 마지막 cancel-at 몫 (rollReadyAt) 부터 동작을
 *       끊고 구른다 (MOVE_CANCEL why=roll).</li>
 * </ul>
 * 시험 줄 (ASCII): MOVE kind= cls= weapon= s= a= r= cycle= mv= ar= raw= stam= st= dex= buf= t=, MOVE_BUF kind= at= until=,
 * MOVE_EARLY kind= at= until=, MOVE_BUF kind= at= until= roll=1 (구르기 공격 창을 기다린다), MOVE_DENY why=weapon|state|stamina kind= …, MOVE_CANCEL why= kind= t=, HIT foe= move= …,
 * HIT_PVP to= move= …, USE_DENY why= item= t=.
 */
public final class MoveRunner {
    /** 땅 위의 미끄럼 (블록 0.6 × 공기 0.91): 내딛는 거리 d 를 첫 속도 d × (1 − 이것) 로 */
    static final double GROUND_DRAG = 0.546;

    public enum Phase { STARTUP, ACTIVE, RECOVERY }

    /** 하는 중인 동작 하나 (시작한 틱의 값으로 굳힌다). */
    public static final class Run {
        public final String kind;
        public final InputBuffer.Kind input;
        /** 약공격의 단 (0 부터), 그 밖은 −1 */
        public final int index;
        public final Weapons.Def weapon;
        public final Moveset.Cls cls;
        public final Moveset.Step step;
        public final long start;
        public final int s, a, r;
        public final double mv, ar, raw, poise, stamina, stepDist;
        public final UUID aim;
        public final boolean buffered;
        final Set<UUID> hit = new HashSet<>();
        /** 찌르기가 첫 대상을 맞혔다 */
        boolean spent;
        int hits;

        Run(String kind, InputBuffer.Kind input, int index, Weapons.Def weapon, Moveset.Cls cls, Moveset.Step step, long start, MoveTiming.Timed t,
            double mv, double ar, double raw, double poise, double stamina, double stepDist, UUID aim, boolean buffered) {
            this.kind = kind;
            this.input = input;
            this.index = index;
            this.weapon = weapon;
            this.cls = cls;
            this.step = step;
            this.start = start;
            this.s = t.s();
            this.a = t.a();
            this.r = t.r();
            this.mv = mv;
            this.ar = ar;
            this.raw = raw;
            this.poise = poise;
            this.stamina = stamina;
            this.stepDist = stepDist;
            this.aim = aim;
            this.buffered = buffered;
        }

        public long activeAt() {
            return start + s;
        }

        public long recoverAt() {
            return start + s + a;
        }

        public long end() {
            return start + s + a + r;
        }

        public int cycle() {
            return s + a + r;
        }

        public int hits() {
            return hits;
        }

        public Phase phase(long now) {
            if (now < activeAt()) return Phase.STARTUP;
            if (now < recoverAt()) return Phase.ACTIVE;
            return Phase.RECOVERY;
        }
    }

    private final Souls plugin;
    private Moveset moveset = Moveset.empty();
    private HitQuery.AimProvider aim = HitQuery.CROSSHAIR;
    /** 동작이 도는 사람 */
    private final Set<UUID> active = new LinkedHashSet<>();
    /** 구르는 중에 누른 입력: 구르기 공격 창이 열리는 틱 (P1c) */
    private final java.util.Map<UUID, Long> rollWait = new java.util.HashMap<>();

    public MoveRunner(Souls plugin) {
        this.plugin = plugin;
        reload();
    }

    private CombatTuning.Moves cfg() {
        return plugin.cfg().tuning.moves;
    }

    private CombatTuning.Input inputCfg() {
        return plugin.cfg().tuning.input;
    }

    /** moves.yml 과 combat.moves 를 다시 읽는다 (켤 때, /souls reload). 무기 아이템의 휘두르기 셈도 새로 끼운다. */
    public void reload() {
        moveset = Moveset.parse(plugin.content().merged("moves.yml"), cfg().vertical());
        if (!moveset.problems().isEmpty()) {
            plugin.getLogger().warning("content/moves.yml 의 틀린 값을 기본값으로 읽었습니다: " + String.join(", ", moveset.problems()));
        }
        if (!plugin.cfg().legacyPve.isEmpty()) {
            plugin.getLogger().warning("config.yml 의 예전 열쇠는 읽지 않는다 (적을 치는 다리와 바닐라 공격 대기는 동작 실행기가 대신한다. 공격의 틱은 "
                    + "content/moves.yml, 공통 값은 combat.moves): " + String.join(", ", plugin.cfg().legacyPve));
        }
        ItemFactory.swings(this::swing);
    }

    public Moveset moveset() {
        return moveset;
    }

    /** 표적 고정 (P8) 이 조준을 바꾼다. null 이면 십자선. */
    public void aim(HitQuery.AimProvider a) {
        aim = a == null ? HitQuery.CROSSHAIR : a;
    }

    // ── 공격 속도와 아이템의 휘두르기 ──

    /** 민첩 dex 의 공격 속도 배율 a. */
    public double speed(int dex) {
        return DamageCalc.attackSpeed(plugin.cfg().stats, dex);
    }

    /** p 의 민첩 단계 (combat.moves.swing-tiers). */
    public int tier(Player p) {
        return MoveTiming.tier(plugin.stats().of(p).dex(), cfg().swingTiers());
    }

    /** 분류·단계의 아이템 휘두르기 (ItemFactory 가 부른다): 약공격 1단의 준비 + 판정을 그 단계의 첫 민첩으로 나눈 틱. */
    private ItemFactory.SwingSpec swing(String cls, int tier) {
        Moveset.Cls c = moveset.of(cls);
        if (c == null) return null;
        Moveset.Step l1 = c.light(0);
        double a = speed(MoveTiming.tierDex(tier, cfg().swingTiers()));
        return new ItemFactory.SwingSpec(c.stab(), MoveTiming.swingTicks(l1.s(), l1.a(), a, cfg().minStartup()), (float) c.spec().range());
    }

    /** 이 동작의 틱 (모아 둔 몫 carry 로). */
    public MoveTiming.Timed time(Moveset.Step step, int dex, double carry) {
        CombatTuning.Moves m = cfg();
        return MoveTiming.time(step.base(), speed(dex), carry, new MoveTiming.Rules(m.minStartup(), m.minRecovery(), m.minCycle()));
    }

    // ── 상태 ──

    /** 동작 중인가 (회복까지). */
    public boolean busy(Player p) {
        CombatState st = CombatState.peek(p.getUniqueId());
        return st != null && st.move != null;
    }

    /** 준비·판정 중인가 (마시기·술을 막는다, R17. 구르기를 막는다, P1c). */
    public boolean attacking(Player p, long now) {
        CombatState st = CombatState.peek(p.getUniqueId());
        return st != null && st.move != null && now < st.move.recoverAt();
    }

    /** 지금 동작 (없으면 null). */
    public Run current(Player p) {
        CombatState st = CombatState.peek(p.getUniqueId());
        return st == null ? null : st.move;
    }

    /** 공격하지 못하는 몸 상태의 까닭 (되면 null). */
    @SuppressWarnings("deprecation") // isOnGround 는 쓰지 않는다
    static String stateWhy(Player p) {
        if (p.isDead()) return "dead";
        if (p.isInsideVehicle()) return "vehicle";
        if (p.isInWater() || p.isSwimming()) return "water";
        if (p.isClimbing()) return "climbing";
        if (p.isGliding() || p.isFlying()) return "flying";
        return null;
    }

    // ── 입력 ──

    /**
     * 입력 하나 (InputRouter 가 input 자리에서, 시험 명령 /soulstest move). 대기 중이면 곧바로 시작하고, 동작 중이면 기억한다.
     * @param target 겨눈 대상 (조준 힌트, 없으면 null)
     */
    public void input(Player p, InputBuffer.Kind kind, UUID target, long now) {
        CombatState st = CombatState.of(p);
        Run cur = st.move;
        // 구르는 중 (구르기 공격 창 앞) 의 입력은 창이 열리는 틱까지 기억한다 (P1c)
        long open = cur == null ? rollAttackOpensAt(st, now) : CombatState.NEVER;
        if (open > now) {
            CombatTuning.Input in = inputCfg();
            String k = kind.name().toLowerCase(Locale.ROOT);
            if (st.buffer.offer(kind, now, open, in.acceptBefore(), target)) {
                rollWait.put(p.getUniqueId(), open);
                plugin.test(p, "MOVE_BUF kind=" + k + " at=" + now + " until=" + open + " roll=1");
            } else {
                plugin.test(p, "MOVE_EARLY kind=" + k + " at=" + now + " until=" + open + " from=" + (open - in.acceptBefore()) + " roll=1");
            }
            return;
        }
        if (cur != null) {
            CombatTuning.Input in = inputCfg();
            String k = kind.name().toLowerCase(Locale.ROOT);
            if (st.buffer.offer(kind, now, cur.end(), in.acceptBefore(), target)) {
                plugin.test(p, "MOVE_BUF kind=" + k + " at=" + now + " until=" + cur.end());
            } else {
                plugin.test(p, "MOVE_EARLY kind=" + k + " at=" + now + " until=" + cur.end() + " from=" + (cur.end() - in.acceptBefore()));
            }
            return;
        }
        start(p, st, kind, target, now, false);
    }

    /** 동작을 시작한다. 시작했으면 true (못 하면 MOVE_DENY). */
    private boolean start(Player p, CombatState st, InputBuffer.Kind kind, UUID target, long now, boolean buffered) {
        // 구르기 공격 창 안의 약공격·달리기 공격은 구르기 공격이다 (P1c)
        if ((kind == InputBuffer.Kind.LIGHT || kind == InputBuffer.Kind.RUNNING) && inRollAttackWindow(st, now)) kind = InputBuffer.Kind.ROLL;
        String k = kind.name().toLowerCase(Locale.ROOT);
        ItemStack main = p.getInventory().getItemInMainHand();
        Weapons.Def w = plugin.weapons().of(main);
        Moveset.Cls c = Stats.isMelee(w) ? moveset.of(w.cls()) : null;
        if (c == null) {
            plugin.test(p, "MOVE_DENY why=weapon kind=" + k + " weapon=" + (w == null ? (main.isEmpty() ? "-" : main.getType().getKey().getKey()) : w.id())
                    + " t=" + now);
            return false;
        }
        String why = stateWhy(p);
        if (why != null) {
            plugin.test(p, "MOVE_DENY why=state state=" + why + " kind=" + k + " t=" + now);
            return false;
        }
        CombatTuning.Moves m = cfg();
        Moveset.Step step;
        String name;
        int index = -1;
        double mv, cost, poise, stepDist;
        switch (kind) {
            case HEAVY -> {
                step = c.heavy();
                name = "heavy";
                mv = m.heavy();
                cost = c.staminaHeavy();
                poise = c.poiseHeavy();
                stepDist = c.stepHeavy();
            }
            case RUNNING -> {
                step = c.running();
                name = "running";
                mv = m.running();
                cost = c.staminaLight() * m.costRunning();
                poise = c.poiseLight();
                stepDist = c.stepRunning();
            }
            case ROLL -> {
                // 구르기 공격 (P1c): 틱은 약공격 1단
                step = c.light(0);
                name = "roll";
                mv = m.roll();
                cost = c.staminaLight() * m.costRoll();
                poise = c.poiseLight();
                stepDist = c.stepLight();
            }
            default -> {
                // 약공격. 끝난 지 combo-grace 틱 안이면 다음 단, 아니면 1단
                index = now <= st.moveEnd + m.comboGrace() ? Math.floorMod(st.combo, c.combo()) : 0;
                step = c.light(index);
                name = "light" + (index + 1);
                mv = m.lightMv(index);
                cost = c.staminaLight();
                poise = c.poiseLight();
                stepDist = c.stepLight();
            }
        }
        StatBlock sb = plugin.stats().of(p);
        MoveTiming.Timed t = time(step, sb.dex(), st.dexCarry);
        long end = now + t.cycle();
        double before = st.stamina.cur();
        if (!plugin.stamina().spend(p, cost, end)) {
            plugin.test(p, String.format(Locale.ROOT, "MOVE_DENY why=stamina kind=%s st=%.1f cost=%.1f t=%d", k, before, cost, now));
            return false;
        }
        st.dexCarry = t.carry();
        double ar = DamageCalc.ar(plugin.cfg().stats, Stats.arms(w), sb.str(), plugin.stats().twoHanded(p, w));
        double raw = DamageCalc.hit(ar, mv, 1, 1);
        Run run = new Run(name, kind, index, w, c, step, now, t, mv, ar, raw, poise, cost, stepDist, target, buffered);
        st.move = run;
        st.rollReadyAt = run.end() - Math.round(run.r * m.cancelAt());
        // 약공격은 다음 단으로, 구르기 공격 뒤의 약공격은 2단 (다크 소울처럼), 강공격·달리기 공격 뒤는 1단
        st.combo = kind == InputBuffer.Kind.LIGHT ? index + 1 : kind == InputBuffer.Kind.ROLL ? 1 : 0;
        Slow.set(p, "move", 1 - m.slowStartup());
        active.add(p.getUniqueId());
        plugin.test(p, String.format(Locale.ROOT,
                "MOVE kind=%s cls=%s weapon=%s s=%d a=%d r=%d cycle=%d mv=%.0f ar=%.1f raw=%.1f stam=%.1f st=%.1f dex=%d aspd=%.4f carry=%.3f "
                        + "shape=%s range=%.1f buf=%s aim=%s t=%d",
                name, c.id(), w.id(), run.s, run.a, run.r, run.cycle(), mv, ar, raw, cost, st.stamina.cur(), sb.dex(), speed(sb.dex()), t.carry(),
                step.spec().shape().name().toLowerCase(Locale.ROOT), step.spec().range(), buffered, target == null ? "-" : target, now));
        if (kind == InputBuffer.Kind.ROLL) {
            // 구르기의 대역을 곧바로 거두고 진짜 몸으로 친다 (reveal 틱을 기다리면 대역이 일어서는 동안 공격이 보이지 않는다)
            plugin.test(p, "ROLL_ATTACK roll=" + st.roll.id() + " at=" + (now - st.rollStart) + " revealed=" + plugin.roll().tumble().reveal(p) + " t=" + now);
        }
        return true;
    }

    // ── 구르기 공격 (P1c) ──

    /** 구르기 공격 창 (구르기 시작에서 센 틱) [next + roll-attack.from, next + roll-attack.to]. 구른 적이 없으면 null. */
    public long[] rollAttackWindow(Player p) {
        CombatState st = CombatState.peek(p.getUniqueId());
        return st == null ? null : rollAttackWindow(st);
    }

    private long[] rollAttackWindow(CombatState st) {
        if (st.roll == null) return null;
        CombatTuning.Moves m = cfg();
        return window(st.roll.next(), m.rollFrom(), m.rollTo());
    }

    /** 구르기의 next 와 창 (from, to) 의 구르기 시작에서 센 틱 [시작, 끝]. */
    public static long[] window(int next, int from, int to) {
        return new long[]{next + from, next + to};
    }

    /** now 가 마지막 구르기의 구르기 공격 창 안인가. */
    boolean inRollAttackWindow(CombatState st, long now) {
        long[] w = rollAttackWindow(st);
        if (w == null) return false;
        long t = now - st.rollStart;
        return t >= w[0] && t <= w[1];
    }

    /** 구르는 중이고 창이 아직 열리지 않았으면 창이 열리는 틱, 아니면 NEVER. */
    long rollAttackOpensAt(CombatState st, long now) {
        long[] w = rollAttackWindow(st);
        if (w == null || !st.rolling(now)) return CombatState.NEVER;
        long open = st.rollStart + w[0];
        return now < open ? open : CombatState.NEVER;
    }

    // ── 틱 ──

    /** Ticker 의 moves 자리. */
    public void tick(long now) {
        if (!rollWait.isEmpty()) waitRolls(now);
        if (active.isEmpty()) return;
        for (UUID id : List.copyOf(active)) {
            Player p = Bukkit.getPlayer(id);
            CombatState st = CombatState.peek(id);
            if (p == null || st == null || st.move == null) {
                active.remove(id);
                continue;
            }
            Run m = st.move;
            if (!p.isValid() || p.isDead()) {
                cancel(p, st, "dead", now);
                continue;
            }
            CombatTuning.Moves cfg = cfg();
            // 준비·판정 중에 시작한 마시기·술은 끊는다 (R17. 쓰지 않았으니 횟수·마나는 그대로)
            if (now < m.recoverAt() && p.hasActiveItem() && consumable(p.getActiveItem())) {
                String item = p.getActiveItem().getType().getKey().getKey();
                p.clearActiveItem();
                plugin.test(p, "USE_DENY why=attack where=tick item=" + item + " t=" + now);
            }
            if (now == m.activeAt()) {
                Slow.set(p, "move", 1 - cfg.slowActive());
                step(p, m, now);
            }
            if (now >= m.activeAt() && now < m.recoverAt()) hits(p, m, now);
            if (now == m.recoverAt()) Slow.set(p, "move", 1 - cfg.slowRecovery());
            if (now >= m.end()) {
                finish(p, st, m);
                InputBuffer.Entry e = st.buffer.take(now, inputCfg().buffer());
                if (e == null || !start(p, st, e.kind(), e.aim(), now, true)) active.remove(id);
            }
        }
    }

    /** 구르는 중에 기억한 입력을 창이 열리는 틱에 낸다 (구르기를 끊었거나 죽었으면 버린다). */
    private void waitRolls(long now) {
        for (java.util.Map.Entry<UUID, Long> en : List.copyOf(rollWait.entrySet())) {
            if (now < en.getValue()) continue;
            rollWait.remove(en.getKey());
            Player p = Bukkit.getPlayer(en.getKey());
            CombatState st = CombatState.peek(en.getKey());
            if (p == null || st == null || st.move != null || p.isDead()) continue;
            // 그사이 새로 굴렀으면 그 구르기의 창까지 다시 기다린다
            long open = rollAttackOpensAt(st, now);
            if (open > now) {
                rollWait.put(en.getKey(), open);
                continue;
            }
            InputBuffer.Entry e = st.buffer.take(now, inputCfg().buffer());
            if (e != null && start(p, st, e.kind(), e.aim(), now, true)) active.add(p.getUniqueId());
        }
    }

    /** 이 아이템이 먹고 마시는 것 (CONSUMABLE 성분: 물약, 에스트 M3, 촉매의 술 M5). */
    @SuppressWarnings("UnstableApiUsage")
    public static boolean consumable(ItemStack it) {
        return it != null && !it.isEmpty() && it.hasData(DataComponentTypes.CONSUMABLE);
    }

    private void finish(Player p, CombatState st, Run m) {
        st.move = null;
        st.moveEnd = m.end();
        st.rollReadyAt = CombatState.NEVER;
        Slow.clear(p, "move");
    }

    /** 첫 판정 틱에 앞으로 내딛는다 (땅 위에서만, 조준 쪽으로). */
    @SuppressWarnings("deprecation") // isOnGround: 클라이언트가 알려 준 값을 믿는다 (혼자 하는 서버)
    private void step(Player p, Run m, long now) {
        if (m.stepDist <= 0 || !p.isOnGround()) return;
        Vector d = aim.aim(p, now).clone().setY(0);
        if (d.lengthSquared() < 1e-9) return;
        d.normalize().multiply(m.stepDist * (1 - GROUND_DRAG));
        p.setVelocity(d.setY(0));
    }

    /** 판정 한 틱: 대상을 모아 HitQuery 의 차례로 맞힌다. */
    private void hits(Player p, Run m, long now) {
        HitQuery.Spec sp = m.step.spec();
        if (sp.thrust() && m.spent) return;
        Location eye = p.getEyeLocation();
        Vector dir = aim.aim(p, now);
        List<Object> who = new ArrayList<>();
        List<BoundingBox> boxes = new ArrayList<>();
        for (Foe f : plugin.foes().near(eye, sp.range())) {
            if (m.hit.contains(f.entity().getUniqueId())) continue;
            who.add(f);
            boxes.add(f.entity().getBoundingBox());
        }
        for (Player v : p.getWorld().getPlayers()) {
            if (v == p || m.hit.contains(v.getUniqueId()) || !Stamina.fighting(v)) continue;
            BoundingBox b = v.getBoundingBox();
            if (HitQuery.distToBox(b, eye.getX(), eye.getY(), eye.getZ()) > sp.range()) continue;
            who.add(v);
            boxes.add(b);
        }
        if (who.isEmpty()) return;
        List<Integer> order = new ArrayList<>(HitQuery.order(eye, dir, sp, boxes));
        if (order.isEmpty()) return;
        // 찌르기는 겨눈 대상 (바닐라가 고른 것) 이 판정 안이면 그것부터
        if (sp.thrust() && m.aim != null) {
            for (int i = 0; i < order.size(); i++) {
                Object o = who.get(order.get(i));
                UUID u = o instanceof Foe f ? f.entity().getUniqueId() : ((Player) o).getUniqueId();
                if (u.equals(m.aim)) {
                    order.add(0, order.remove(i));
                    break;
                }
            }
        }
        for (int i : order) {
            Object o = who.get(i);
            if (o instanceof Foe f) {
                hitFoe(p, m, f, now);
            } else if (!hitPlayer(p, m, (Player) o, now)) {
                continue;
            }
            if (sp.thrust()) {
                m.spent = true;
                break;
            }
        }
    }

    private void hitFoe(Player p, Run m, Foe f, long now) {
        m.hit.add(f.entity().getUniqueId());
        Vector push = f.entity().getLocation().toVector().subtract(p.getLocation().toVector()).setY(0);
        Hit h = Hit.builder().moveId(m.kind).cls(m.cls.id()).raw(m.raw).poise(m.poise).type(m.step.type()).dir(push).attacker(p).build();
        HitResult r = plugin.foes().hit(p, f, h);
        if (!r.landed()) return;
        m.hits++;
        plugin.test(p, String.format(Locale.ROOT,
                "HIT foe=%s move=%s cls=%s weapon=%s type=%s mv=%.0f ar=%.1f raw=%.1f def=%.1f dealt=%.2f hp=%.2f killed=%s n=%d tick=%d t=%d",
                f.id(), m.kind, m.cls.id(), m.weapon.id(), m.step.type().name().toLowerCase(Locale.ROOT), m.mv, m.ar, r.raw(), r.def(), r.dealt(), r.hp(),
                r.killed(), m.hits, now - m.start, now));
    }

    /** PvP 한 대 (M1: 곧바로 Combat.damage, 구르기 무적만 먹는다. 대기열·막기·패링은 M6). 맞히지 않았으면 false. */
    private boolean hitPlayer(Player p, Run m, Player v, long now) {
        if (!plugin.pvp().allowed(p, v)) return false;
        m.hit.add(v.getUniqueId());
        double amount = m.raw * plugin.cfg().pvp.damageScale();
        double dealt = Combat.damage(p, v, amount, false, null);
        CombatState.of(p).lastCombatTick = now;
        m.hits++;
        plugin.test(p, String.format(Locale.ROOT, "HIT_PVP to=%s move=%s cls=%s weapon=%s mv=%.0f ar=%.1f raw=%.1f dealt=%.2f hp=%.1f n=%d tick=%d t=%d",
                v.getName(), m.kind, m.cls.id(), m.weapon.id(), m.mv, m.ar, amount, dealt, v.getHealth(), m.hits, now - m.start, now));
        return true;
    }

    // ── 끊기·거두기 ──

    /** 지금 동작을 끊는다 (기억한 입력도 버린다). 끊었으면 true. P1c 의 구르기가 부른다 (MOVE_CANCEL why=roll). */
    public boolean cancel(Player p, String why, long now) {
        CombatState st = CombatState.peek(p.getUniqueId());
        return st != null && cancel(p, st, why, now);
    }

    private boolean cancel(Player p, CombatState st, String why, long now) {
        Run m = st.move;
        st.buffer.clear();
        active.remove(p.getUniqueId());
        rollWait.remove(p.getUniqueId());
        if (m == null) return false;
        st.move = null;
        st.moveEnd = now;
        st.rollReadyAt = CombatState.NEVER;
        Slow.clear(p, "move");
        plugin.test(p, "MOVE_CANCEL why=" + why + " kind=" + m.kind + " at=" + (now - m.start) + " t=" + now);
        return true;
    }

    /** CombatReset (죽음·나가기·다른 세계·끄기·접속): 동작·입력 기억·단·모아 둔 몫을 거둔다. */
    public void reset(Player p, CombatReset.Why why) {
        CombatState st = CombatState.peek(p.getUniqueId());
        if (st == null) {
            active.remove(p.getUniqueId());
            rollWait.remove(p.getUniqueId());
            return;
        }
        cancel(p, st, why.name().toLowerCase(Locale.ROOT), plugin.ticker().now());
        st.combo = 0;
        st.dexCarry = 0;
        st.moveEnd = CombatState.NEVER;
    }
}
