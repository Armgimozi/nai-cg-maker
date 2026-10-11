package kr.souls.cmd.test;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.souls.Content;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.CombatReset;
import kr.souls.combat.CombatState;
import kr.souls.combat.Hit;
import kr.souls.combat.Slow;
import kr.souls.combat.Swings;
import kr.souls.enemy.Foe;
import kr.souls.enemy.Foes;
import kr.souls.enemy.HitResult;
import org.bukkit.Location;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.ArmorStand;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * /soulstest contract (M1 P1-0): 계약 점검. 봇 tools/bots/contract.js 가 읽는다. 줄은 모두 ASCII 기계 글.
 * <pre>
 *   contract ticker                  [T] CONTRACT_TICKER order=load,stamina,input,…  (Ticker 의 자리 차례, M1_PLAN 0.6)
 *   contract spawn &lt;종류&gt; [n]        Foes.body 로 n 마리 (기본 1) 를 앞에 세우고 등록한다 (가상 체력 100, 방어 20, 두뇌 끔).
 *                                    [T] CONTRACT_SPAWN type= n= baby= equipped= drop= silent= persistent= farremove= pickup= tags= reg= (R8)
 *   contract spawn-id &lt;id&gt;           Foes.spawn (enemies.yml 의 id). [T] CONTRACT_SPAWN_ID id= ok= type=
 *   contract tp                      첫 적에 표식 (souls_mark 갑옷 거치대) 을 태우고 대조로 깃발 없는 teleport 1칸, 그다음 Foes.teleport
 *                                    1칸. [T] CONTRACT_TP plain= plainkept= plainmoved= ok= kept= moved= (R6)
 *   contract hit &lt;원피해&gt;            첫 적에 Foes.hit. [T] CONTRACT_HIT foe= raw= def= dealt= hp= max= killed= stamped=
 *   contract foes                    [T] CONTRACT_FOES n= near= (이 명령이 세운 적, 눈에서 8칸)
 *   contract clear                   이 명령이 세운 적의 몸을 지운다. [T] CONTRACT_FOES n=0 cleared=
 *   contract slow &lt;배율|root|clear|show&gt;   Slow.set(이 사람, "contract", 배율). [T] CONTRACT_SLOW factor= walk= base= jump= owners=
 *   contract swing main|off          Swings.main / off. [T] CONTRACT_SWING hand= at= since=
 *   contract reset                   [T] CONTRACT_RESET owners= (CombatReset 에 걸린 이름들)
 *   contract content                 [T] CONTRACT_CONTENT files= merged= (Content.FILES, moves.yml·enemies.yml 의 맨 위 열쇠 수)
 * </pre>
 */
public final class ContractTestCommands {
    /** 이 명령이 세운 적의 id (enemies.yml 에 없는 시험 id) */
    public static final String TEST_ID = "contract_probe";
    /**
     * spawn-id 로 세운 적의 표시 태그. foes·clear·hit 는 이 명령이 세운 적 (TEST_ID 또는 이 태그) 만 센다: P1b 부터 도장의 허수아비가
     * 늘 등록부에 있다 (souls_foe·souls_ent 와 함께 켤 때 쓸린다)
     */
    public static final String MINE_TAG = "souls_contract";

    private ContractTestCommands() {}

    @FunctionalInterface
    private interface PlayerAction {
        void run(Player p);
    }

    public static LiteralArgumentBuilder<CommandSourceStack> node(Souls plugin) {
        return Commands.literal("contract")
                .then(Commands.literal("ticker").executes(ctx -> with(ctx, p ->
                        plugin.test(p, "CONTRACT_TICKER order=" + String.join(",", plugin.ticker().order())))))
                .then(Commands.literal("spawn")
                        .then(Commands.argument("type", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String x : List.of("zombie", "husk", "skeleton", "vindicator", "pillager", "drowned")) b.suggest(x);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> spawn(plugin, p, StringArgumentType.getString(ctx, "type"), 1)))
                                .then(Commands.argument("n", IntegerArgumentType.integer(1, 64))
                                        .executes(ctx -> with(ctx, p -> spawn(plugin, p, StringArgumentType.getString(ctx, "type"),
                                                IntegerArgumentType.getInteger(ctx, "n")))))))
                .then(Commands.literal("spawn-id")
                        .then(Commands.argument("id", StringArgumentType.word())
                                .executes(ctx -> with(ctx, p -> {
                                    String id = StringArgumentType.getString(ctx, "id");
                                    Mob m = plugin.foes().spawn(id, ahead(p, 3));
                                    if (m != null) m.addScoreboardTag(MINE_TAG);
                                    plugin.test(p, "CONTRACT_SPAWN_ID id=" + id + " ok=" + (m != null) + " type="
                                            + (m == null ? "-" : m.getType().getKey().getKey()));
                                }))))
                .then(Commands.literal("tp").executes(ctx -> with(ctx, p -> tp(plugin, p))))
                .then(Commands.literal("hit")
                        .then(Commands.argument("raw", DoubleArgumentType.doubleArg(0, 100000))
                                .executes(ctx -> with(ctx, p -> hit(plugin, p, DoubleArgumentType.getDouble(ctx, "raw"))))))
                .then(Commands.literal("foes").executes(ctx -> with(ctx, p -> foes(plugin, p, -1))))
                .then(Commands.literal("clear").executes(ctx -> with(ctx, p -> foes(plugin, p, plugin.foes().clear(ContractTestCommands::mine)))))
                .then(Commands.literal("slow")
                        .then(Commands.argument("what", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String x : List.of("0.5", "0.75", "root", "clear", "show")) b.suggest(x);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> slow(plugin, p, StringArgumentType.getString(ctx, "what"))))))
                .then(Commands.literal("swing")
                        .then(Commands.argument("hand", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("main");
                                    b.suggest("off");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> {
                                    long now = plugin.ticker().now();
                                    boolean off = "off".equals(StringArgumentType.getString(ctx, "hand"));
                                    if (off) Swings.off(p, now);
                                    else Swings.main(p, now);
                                    EquipmentSlot hand = off ? EquipmentSlot.OFF_HAND : EquipmentSlot.HAND;
                                    plugin.test(p, "CONTRACT_SWING hand=" + hand + " at=" + Swings.last(p, hand) + " since=" + Swings.since(p, now)
                                            + " t=" + now);
                                }))))
                .then(Commands.literal("reset").executes(ctx -> with(ctx, p ->
                        plugin.test(p, "CONTRACT_RESET owners=" + String.join(",", CombatReset.owners())))))
                .then(Commands.literal("content").executes(ctx -> with(ctx, p -> {
                    List<String> merged = new ArrayList<>();
                    for (String f : Content.MERGED) merged.add(f + ":" + plugin.content().merged(f).getKeys(false).size());
                    plugin.test(p, "CONTRACT_CONTENT files=" + String.join(",", Content.FILES) + " merged=" + String.join(",", merged));
                })));
    }

    private static Location ahead(Player p, double d) {
        Location at = p.getLocation();
        Vector dir = at.getDirection().setY(0);
        if (dir.lengthSquared() < 1e-6) dir = new Vector(0, 0, 1);
        return at.clone().add(dir.normalize().multiply(d));
    }

    /** n 마리를 앞 3칸에 둥글게 세우고 R8 깃발을 센다. */
    private static void spawn(Souls plugin, Player p, String type, int n) {
        Class<? extends Mob> cls = Foes.mobClass(type);
        if (cls == null) {
            plugin.test(p, "CONTRACT_SPAWN type=" + type + " error=not_a_mob");
            return;
        }
        Location base = ahead(p, 3);
        int baby = 0, equipped = 0, loud = 0, persistent = 0, far = 0, pickup = 0, tags = 0, reg = 0, made = 0;
        float drop = 0;
        for (int i = 0; i < n; i++) {
            double a = 2 * Math.PI * i / n;
            Location at = base.clone().add(Math.cos(a) * (n > 1 ? 1.5 : 0), 0, Math.sin(a) * (n > 1 ? 1.5 : 0));
            // 시험이 조용하게: 두뇌를 끈다 (몸의 R8 깃발만 본다)
            Mob m = Foes.body(cls, at, TEST_ID, x -> x.setAware(false));
            if (m == null) continue;
            made++;
            plugin.foes().register(new Foes.Basic(TEST_ID, m, 100, 20));
            if (m instanceof org.bukkit.entity.Ageable ag && !ag.isAdult()) baby++;
            EntityEquipment eq = m.getEquipment();
            boolean any = false;
            for (EquipmentSlot s : EquipmentSlot.values()) {
                try {
                    ItemStack it = eq.getItem(s);
                    if (it != null && !it.getType().isAir()) any = true;
                    drop = Math.max(drop, eq.getDropChance(s));
                } catch (IllegalArgumentException ignored) {
                    // 이 몹에 없는 칸
                }
            }
            if (any) equipped++;
            if (!m.isSilent()) loud++;
            if (m.isPersistent()) persistent++;
            if (m.getRemoveWhenFarAway()) far++;
            if (m.getCanPickupItems()) pickup++;
            if (m.getScoreboardTags().contains(Foes.TAG) && m.getScoreboardTags().contains(kr.souls.combat.TestHits.ENT_TAG)) tags++;
            if (plugin.foes().of(m) != null) reg++;
        }
        plugin.test(p, String.format(Locale.ROOT, "CONTRACT_SPAWN type=%s n=%d baby=%d equipped=%d drop=%.3f silent=%d persistent=%d farremove=%d "
                + "pickup=%d tags=%d reg=%d", type, made, baby, equipped, drop, made - loud, persistent, far, pickup, tags, reg));
    }

    /** 이 명령이 세운 적인가 (도장의 허수아비 같은 다른 적은 세지 않는다). */
    static boolean mine(Foe f) {
        return TEST_ID.equals(f.id()) || f.entity().getScoreboardTags().contains(MINE_TAG);
    }

    private static Foe first(Souls plugin, Player p) {
        Foe best = null;
        double bd = Double.MAX_VALUE;
        for (Foe f : plugin.foes().all()) {
            if (!mine(f) || !f.alive() || f.entity().getWorld() != p.getWorld()) continue;
            double d = f.entity().getLocation().distanceSquared(p.getLocation());
            if (d < bd) {
                bd = d;
                best = f;
            }
        }
        if (best == null) plugin.test(p, "CONTRACT error=no_foe");
        return best;
    }

    /**
     * 표식을 태운 적을 옮긴다 (R6). 먼저 깃발 없는 entity.teleport (대조: 1.21.10 앞의 Paper 는 탑승물이 있으면 말없이 거절했다),
     * 그다음 Foes.teleport. [T] CONTRACT_TP plain= plainkept= plainmoved= ok= kept= moved=
     */
    private static void tp(Souls plugin, Player p) {
        Foe f = first(plugin, p);
        if (f == null) return;
        Mob m = f.entity();
        Location from = m.getLocation();
        ArmorStand mark = m.getWorld().spawn(from, ArmorStand.class, false, a -> {
            a.setMarker(true);
            a.setInvisible(true);
            a.setPersistent(false);
            a.addScoreboardTag(Foes.MARK_TAG);
        });
        m.addPassenger(mark);
        // 사람에게서 멀어지는 쪽으로 1칸, 다시 1칸
        Vector away = from.toVector().subtract(p.getLocation().toVector()).setY(0);
        if (away.lengthSquared() < 1e-6) away = new Vector(0, 0, 1);
        away.normalize();
        boolean plain = m.teleport(from.clone().add(away));
        boolean plainKept = m.getPassengers().contains(mark);
        double plainMoved = m.getLocation().distance(from);
        if (!plainKept) m.addPassenger(mark);
        Location mid = m.getLocation();
        boolean ok = plugin.foes().teleport(f, mid.clone().add(away));
        boolean kept = m.getPassengers().contains(mark);
        double moved = m.getLocation().distance(mid);
        plugin.test(p, String.format(Locale.ROOT, "CONTRACT_TP plain=%s plainkept=%s plainmoved=%.2f ok=%s kept=%s moved=%.2f", plain, plainKept,
                plainMoved, ok, kept, moved));
        mark.remove();
    }

    private static void hit(Souls plugin, Player p, double raw) {
        Foe f = first(plugin, p);
        if (f == null) return;
        long now = plugin.ticker().now();
        Hit h = Hit.builder().moveId("contract").cls("-").raw(raw).attacker(p)
                .dir(f.entity().getLocation().toVector().subtract(p.getLocation().toVector())).build();
        HitResult r = plugin.foes().hit(p, f, h);
        boolean stamped = CombatState.of(p).lastCombatTick == now;
        plugin.test(p, String.format(Locale.ROOT, "CONTRACT_HIT foe=%s raw=%.2f def=%.1f dealt=%.3f hp=%.3f max=%.1f killed=%s landed=%s stamped=%s",
                f.id(), r.raw(), r.def(), r.dealt(), r.hp(), f.max(), r.killed(), r.landed(), stamped));
    }

    private static void foes(Souls plugin, Player p, int cleared) {
        int near = (int) plugin.foes().near(p.getEyeLocation(), 8).stream().filter(ContractTestCommands::mine).count();
        int n = (int) plugin.foes().all().stream().filter(ContractTestCommands::mine).count();
        plugin.test(p, "CONTRACT_FOES n=" + n + " near=" + near + (cleared >= 0 ? " cleared=" + cleared : ""));
    }

    private static void slow(Souls plugin, Player p, String what) {
        switch (what) {
            case "root" -> Slow.root(p, "contract");
            case "clear" -> Slow.clear(p, "contract");
            case "show" -> {
            }
            default -> {
                double f;
                try {
                    f = Double.parseDouble(what);
                } catch (NumberFormatException e) {
                    plugin.test(p, "CONTRACT_SLOW error=bad_value value=" + what);
                    return;
                }
                Slow.set(p, "contract", f);
            }
        }
        AttributeInstance base = p.getAttribute(Attribute.MOVEMENT_SPEED);
        AttributeInstance jump = p.getAttribute(Attribute.JUMP_STRENGTH);
        StringBuilder owners = new StringBuilder();
        for (Map.Entry<String, Double> e : Slow.owners(p).entrySet()) {
            owners.append(owners.length() == 0 ? "" : ",").append(e.getKey()).append(':').append(String.format(Locale.ROOT, "%.2f", e.getValue()));
        }
        plugin.test(p, String.format(Locale.ROOT, "CONTRACT_SLOW factor=%.3f walk=%.4f base=%.4f jump=%.4f owners=%s", Slow.factor(p), p.getWalkSpeed(),
                base == null ? -1 : base.getBaseValue(), jump == null ? -1 : jump.getValue(), owners.length() == 0 ? "-" : owners));
    }

    private static int with(CommandContext<CommandSourceStack> ctx, PlayerAction a) {
        Entity e = ctx.getSource().getExecutor();
        Player p = e instanceof Player x ? x : ctx.getSource().getSender() instanceof Player y ? y : null;
        if (p == null) {
            Lang.tell(ctx.getSource().getSender(), "admin.players-only");
            return 0;
        }
        a.run(p);
        return Command.SINGLE_SUCCESS;
    }
}
