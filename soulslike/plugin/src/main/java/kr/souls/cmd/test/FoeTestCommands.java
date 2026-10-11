package kr.souls.cmd.test;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.FoeScaling;
import kr.souls.combat.Hit;
import kr.souls.combat.TestHits;
import kr.souls.enemy.EnemyDefs;
import kr.souls.enemy.Foe;
import kr.souls.enemy.Foes;
import kr.souls.enemy.HitResult;
import org.bukkit.Location;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EntityEquipment;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * /soulstest dummy … (M1 P1b): 허수아비. 봇 tools/bots/foes.js 와 P1a 의 attacks.js 가 쓴다. 줄은 모두 ASCII 기계 글.
 * P5a 의 foe spawn|clear|dump 도 이 파일에 더한다 (CombatTestCommands 의 표).
 * <pre>
 *   dummy spawn [toward|away] [hp]   앞 3칸에 허수아비 하나 (enemies.yml dummy, 도장이 다시 세우지 않는 낱개). toward (기본) 는 이 사람을
 *                                    보고, away 는 등을 돌린다. hp 를 주면 난이도 배율 전의 가상 체력을 바꾼다.
 *                                    [T] DUMMY spawn id= eid= uuid= hp= max= def= x= y= z= yaw= baby= equipped= drop= silent= aware=
 *                                    collidable= kbres= persistent= farremove= pickup= tags= reg= vhp= mod=
 *   dummy clear                      허수아비를 모두 지운다 (도장의 것도: 도장은 respawn 틱 뒤 다시 세운다). [T] DUMMY clear n=
 *   dummy dump                       [T] DUMMY dump n= eids= hp= max= dist= vhp= mod= (등록된 허수아비, 가까운 차례)
 *   dummy hit &lt;원피해&gt; [all]         가장 가까운 허수아비 (all 이면 모두) 에 Foes.hit. [T] DUMMY hit n= eid= raw= dealt= hp= killed=
 *   dojo tp &lt;entry|hall&gt;            entry: 시험 방 북쪽 문 앞 (방 안, 북쪽을 본다), hall: 홀 문 안쪽. [T] DOJO tp at= x= y= z=
 *                                    (P5b 가 post·arena·ledge 를 더한다)
 *   dojo build                       도장을 지운 뒤 다시 짓는다 (허수아비도 다시). [T] DOJO build v= blocks= ms=
 *   dojo dump                        [T] DOJO v= built= near= alive= slots=이름:alive|waitN|empty:체력:eid,… center=
 * </pre>
 */
public final class FoeTestCommands {
    public static final String DUMMY = "dummy";

    private FoeTestCommands() {}

    @FunctionalInterface
    private interface PlayerAction {
        void run(Player p);
    }

    /** /soulstest dummy … */
    public static LiteralArgumentBuilder<CommandSourceStack> dummy(Souls plugin) {
        return Commands.literal("dummy")
                .then(Commands.literal("spawn")
                        .executes(ctx -> with(ctx, p -> spawn(plugin, p, "toward", -1)))
                        .then(Commands.argument("facing", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("toward");
                                    b.suggest("away");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> spawn(plugin, p, StringArgumentType.getString(ctx, "facing"), -1)))
                                .then(Commands.argument("hp", DoubleArgumentType.doubleArg(1, 1e9))
                                        .executes(ctx -> with(ctx, p -> spawn(plugin, p, StringArgumentType.getString(ctx, "facing"),
                                                DoubleArgumentType.getDouble(ctx, "hp")))))))
                .then(Commands.literal("clear").executes(ctx -> with(ctx, p ->
                        plugin.test(p, "DUMMY clear n=" + plugin.foes().clear(f -> DUMMY.equals(f.id()))))))
                .then(Commands.literal("dump").executes(ctx -> with(ctx, p -> dump(plugin, p))))
                .then(Commands.literal("hit")
                        .then(Commands.argument("raw", DoubleArgumentType.doubleArg(0, 1e9))
                                .executes(ctx -> with(ctx, p -> hit(plugin, p, DoubleArgumentType.getDouble(ctx, "raw"), false)))
                                .then(Commands.literal("all")
                                        .executes(ctx -> with(ctx, p -> hit(plugin, p, DoubleArgumentType.getDouble(ctx, "raw"), true))))));
    }

    /** /soulstest dojo … */
    public static LiteralArgumentBuilder<CommandSourceStack> dojo(Souls plugin) {
        return Commands.literal("dojo")
                .then(Commands.literal("tp")
                        .then(Commands.argument("where", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("entry");
                                    b.suggest("hall");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> tp(plugin, p, StringArgumentType.getString(ctx, "where"))))))
                .then(Commands.literal("build").executes(ctx -> with(ctx, p -> plugin.worlds().buildDojo(p))))
                .then(Commands.literal("dump").executes(ctx -> with(ctx, p -> plugin.test(p, plugin.dojo().dump()))));
    }

    private static void tp(Souls plugin, Player p, String where) {
        org.bukkit.World w = plugin.worlds().world();
        Location to = w == null ? null : switch (where) {
            case "entry" -> plugin.dojo().entry(w);
            case "hall" -> plugin.dojo().hall(w);
            default -> null;
        };
        if (to == null) {
            plugin.test(p, "DOJO tp error=no_anchor at=" + where);
            return;
        }
        // 구르는 중이면 대역 (탑승물) 을 먼저 내린다 (/souls tp 와 같다)
        plugin.roll().release(p);
        p.teleport(to);
        plugin.test(p, String.format(Locale.ROOT, "DOJO tp at=%s x=%.2f y=%.2f z=%.2f", where, to.getX(), to.getY(), to.getZ()));
    }

    private static Location ahead(Player p, double d) {
        Location at = p.getLocation();
        Vector dir = at.getDirection().setY(0);
        if (dir.lengthSquared() < 1e-6) dir = new Vector(0, 0, 1);
        return at.clone().add(dir.normalize().multiply(d));
    }

    private static void spawn(Souls plugin, Player p, String facing, double hp) {
        EnemyDefs.Def d = plugin.foes().defs().get(DUMMY);
        if (d == null) {
            plugin.test(p, "DUMMY spawn error=no_def");
            return;
        }
        Location at = ahead(p, 3);
        Vector toPlayer = p.getLocation().toVector().subtract(at.toVector()).setY(0);
        float yaw = toPlayer.lengthSquared() < 1e-6 ? p.getLocation().getYaw() + 180f
                : (float) Math.toDegrees(Math.atan2(-toPlayer.getX(), toPlayer.getZ()));
        if ("away".equalsIgnoreCase(facing)) yaw += 180f;
        at.setYaw(wrap(yaw));
        at.setPitch(0);
        Foes.Live f = plugin.foes().spawn(d, at, hp > 0 ? hp : d.hp(), "cmd", null);
        if (f == null) {
            plugin.test(p, "DUMMY spawn error=spawn_failed body=" + d.body());
            return;
        }
        Mob m = f.entity();
        boolean baby = m instanceof Ageable a && !a.isAdult();
        boolean equipped = false;
        float drop = 0;
        EntityEquipment eq = m.getEquipment();
        for (EquipmentSlot s : EquipmentSlot.values()) {
            try {
                ItemStack it = eq.getItem(s);
                if (it != null && !it.getType().isAir()) equipped = true;
                drop = Math.max(drop, eq.getDropChance(s));
            } catch (IllegalArgumentException ignored) {
                // 이 몹에 없는 칸
            }
        }
        AttributeInstance kb = m.getAttribute(Attribute.KNOCKBACK_RESISTANCE);
        Location l = m.getLocation();
        boolean tags = m.getScoreboardTags().contains(Foes.TAG) && m.getScoreboardTags().contains(TestHits.ENT_TAG);
        plugin.test(p, String.format(Locale.ROOT, "DUMMY spawn id=%s eid=%d uuid=%s hp=%.1f max=%.1f def=%.1f x=%.2f y=%.2f z=%.2f yaw=%.0f baby=%d "
                        + "equipped=%d drop=%.3f silent=%s aware=%s collidable=%s kbres=%.2f persistent=%s farremove=%s pickup=%s tags=%s reg=%s vhp=%.1f mod=%d",
                f.id(), m.getEntityId(), m.getUniqueId(), f.hp(), f.max(), f.def(), l.getX(), l.getY(), l.getZ(), l.getYaw(), baby ? 1 : 0,
                equipped ? 1 : 0, drop, m.isSilent(), m.isAware(), m.isCollidable(), kb == null ? -1 : kb.getValue(), m.isPersistent(),
                m.getRemoveWhenFarAway(), m.getCanPickupItems(), tags, plugin.foes().of(m) != null, m.getHealth(), mod(m)));
    }

    /** 난이도 체력 수정자 (FoeScaling, 우리 적에는 붙지 않는다) 가 붙었으면 1. */
    private static int mod(Mob m) {
        AttributeInstance a = m.getAttribute(Attribute.MAX_HEALTH);
        return a != null && a.getModifier(FoeScaling.MOD) != null ? 1 : 0;
    }

    private static List<Foe> dummies(Souls plugin, Player p) {
        List<Foe> out = new ArrayList<>();
        for (Foe f : plugin.foes().all()) if (DUMMY.equals(f.id()) && f.alive() && f.entity().getWorld() == p.getWorld()) out.add(f);
        out.sort(Comparator.comparingDouble(f -> f.entity().getLocation().distanceSquared(p.getLocation())));
        return out;
    }

    private static void dump(Souls plugin, Player p) {
        List<Foe> ds = dummies(plugin, p);
        List<String> eids = new ArrayList<>(), hp = new ArrayList<>(), max = new ArrayList<>(), dist = new ArrayList<>(), vhp = new ArrayList<>();
        int mods = 0;
        for (Foe f : ds) {
            Mob m = f.entity();
            eids.add(String.valueOf(m.getEntityId()));
            hp.add(String.format(Locale.ROOT, "%.1f", f.hp()));
            max.add(String.format(Locale.ROOT, "%.1f", f.max()));
            dist.add(String.format(Locale.ROOT, "%.1f", m.getLocation().distance(p.getLocation())));
            vhp.add(String.format(Locale.ROOT, "%.1f", m.getHealth()));
            mods += mod(m);
        }
        plugin.test(p, "DUMMY dump n=" + ds.size() + " eids=" + join(eids) + " hp=" + join(hp) + " max=" + join(max) + " dist=" + join(dist)
                + " vhp=" + join(vhp) + " mod=" + mods);
    }

    private static void hit(Souls plugin, Player p, double raw, boolean all) {
        List<Foe> ds = dummies(plugin, p);
        if (ds.isEmpty()) {
            plugin.test(p, "DUMMY hit n=0 error=no_dummy");
            return;
        }
        List<Foe> targets = all ? ds : ds.subList(0, 1);
        List<String> eids = new ArrayList<>(), dealt = new ArrayList<>(), hp = new ArrayList<>(), killed = new ArrayList<>();
        for (Foe f : List.copyOf(targets)) {
            Hit h = Hit.builder().moveId("test").cls("-").raw(raw).attacker(p)
                    .dir(f.entity().getLocation().toVector().subtract(p.getLocation().toVector()).setY(0)).build();
            int eid = f.entity().getEntityId();
            HitResult r = plugin.foes().hit(p, f, h);
            eids.add(String.valueOf(eid));
            dealt.add(String.format(Locale.ROOT, "%.3f", r.dealt()));
            hp.add(String.format(Locale.ROOT, "%.3f", r.hp()));
            killed.add(String.valueOf(r.killed()));
        }
        plugin.test(p, String.format(Locale.ROOT, "DUMMY hit n=%d raw=%.2f eid=%s dealt=%s hp=%s killed=%s", targets.size(), raw, join(eids), join(dealt),
                join(hp), join(killed)));
    }

    private static String join(List<String> xs) {
        return xs.isEmpty() ? "-" : String.join(",", xs);
    }

    static float wrap(float yaw) {
        float y = yaw % 360f;
        if (y >= 180f) y -= 360f;
        if (y < -180f) y += 360f;
        return y;
    }

    static int with(CommandContext<CommandSourceStack> ctx, PlayerAction a) {
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
