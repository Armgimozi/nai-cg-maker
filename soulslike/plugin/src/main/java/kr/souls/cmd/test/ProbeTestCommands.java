package kr.souls.cmd.test;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.TestHits;
import kr.souls.input.InputProbe;
import kr.souls.item.ItemFactory;
import kr.souls.item.Weapons;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Ageable;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.util.Vector;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Consumer;

/**
 * /soulstest probe (M1 PS: 입력 탐침과 스파이크 S1~S13 의 도움, M1_PLAN 2절). 시험 모드에서만 (/soulstest 의 가지).
 * <pre>
 *   probe on | off | status          그 사람의 입력 줄 [T] PROBE ev=... 를 켜고 끈다 (input/InputProbe). [T] PROBE_SET on= cancel= fswing=
 *   probe mark &lt;이름&gt;                기록을 장면마다 나누는 줄 [T] PROBE_MARK label= t= (probe_shots.sh)
 *   probe cancel attack | none       엔터티 공격 (PrePlayerAttackEntityEvent) 을 취소한다 (P1a 흉내, S12)
 *   probe fswing main | off | none   F 를 받으면 서버가 그 손을 휘두른다 (P3 의 패링 몸짓 흉내, S3)
 *   probe move on | off              틱마다 수평 이동량 [T] PROBE ev=move v= (움직일 때만, S12)
 *   probe swing main | off           서버가 지금 그 손을 휘두른다 (swingMainHand / swingOffHand, S3·S13)
 *   probe mob &lt;종류&gt; block | aggr | idle [souls 방패 id | shield]
 *                                    그 몹을 3칸 앞에 (AI 없음, 조용히, 무작위 없이) 세우고 왼손에 방패를 쥐여 startUsingItem(OFF_HAND)
 *                                    (aggr 는 setAggressive 도, idle 은 쥐기만). [T] PROBE_MOB ... using= (1틱 뒤, 20틱 뒤) (S9)
 *   probe mob clear                  세운 몹을 지운다
 *   probe walkspeed &lt;0~1&gt;          Player.setWalkSpeed (기본 0.2): 능력의 걷기 속도와 이동 속도 바탕값을 함께 바꾼다. 시야가 좁아지지
 *                                    않는 느려짐·뿌리인지 본다 (S4). [T] PROBE_WALK walk= base= value=
 *   probe crawl &lt;틱&gt;                 머리 칸 (발 칸 + 1, 3×3) 에 이 사람 화면에만 있는 막힘을 그 틱 동안 깐다 (Roll 의 기어가기 막힘과
 *                                    같은 방식). [T] PROBE_CRAWL placed= ... 와 5틱 뒤 서버가 보는 자세 pose= (S10)
 * </pre>
 * 줄은 모두 ASCII 기계 글 (봇과 tools/client/probe_shots.sh 가 읽는다).
 */
public final class ProbeTestCommands {
    /** 세운 몹의 태그 (지우기용. 켤 때 쓸기는 TestHits.ENT_TAG) */
    public static final String MOB_TAG = "souls_probe";
    /** 화면에만 까는 막힘 (Roll.CEILING 과 같은 블록) */
    private static final Material CEILING = Material.LIME_STAINED_GLASS;

    private ProbeTestCommands() {}

    @FunctionalInterface
    private interface PlayerAction {
        void run(Player p);
    }

    /** /soulstest 밑에 붙일 probe 가지. */
    public static LiteralArgumentBuilder<CommandSourceStack> node(Souls plugin) {
        InputProbe probe = plugin.probe();
        return Commands.literal("probe")
                .then(Commands.literal("on").executes(ctx -> with(ctx, p -> {
                    probe.enable(p, true);
                    plugin.test(p, probe.state(p));
                })))
                .then(Commands.literal("off").executes(ctx -> with(ctx, p -> {
                    probe.enable(p, false);
                    plugin.test(p, probe.state(p));
                })))
                .then(Commands.literal("status").executes(ctx -> with(ctx, p -> plugin.test(p, probe.state(p)))))
                .then(Commands.literal("mark")
                        .then(Commands.argument("label", StringArgumentType.word())
                                .executes(ctx -> with(ctx, p -> plugin.test(p, "PROBE_MARK label=" + StringArgumentType.getString(ctx, "label") // lang-machine
                                        + " t=" + plugin.ticker().now())))))
                .then(Commands.literal("cancel")
                        .then(Commands.argument("what", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("attack");
                                    b.suggest("none");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> {
                                    boolean ok = probe.cancelAttack(p, "attack".equals(StringArgumentType.getString(ctx, "what")));
                                    plugin.test(p, ok ? probe.state(p) : "PROBE_SET error=off"); // lang-machine: 시험 줄
                                }))))
                .then(Commands.literal("fswing")
                        .then(Commands.argument("hand", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String x : List.of("main", "off", "none")) b.suggest(x);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> {
                                    boolean ok = probe.fSwing(p, slot(StringArgumentType.getString(ctx, "hand")));
                                    plugin.test(p, ok ? probe.state(p) : "PROBE_SET error=off"); // lang-machine: 시험 줄
                                }))))
                .then(Commands.literal("move")
                        .then(Commands.argument("onoff", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("on");
                                    b.suggest("off");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> {
                                    boolean ok = probe.move(p, "on".equals(StringArgumentType.getString(ctx, "onoff")));
                                    plugin.test(p, ok ? probe.state(p) : "PROBE_SET error=off"); // lang-machine: 시험 줄
                                }))))
                .then(Commands.literal("swing")
                        .then(Commands.argument("hand", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("main");
                                    b.suggest("off");
                                    return b.buildFuture();
                                })
                                .executes(ctx -> with(ctx, p -> {
                                    EquipmentSlot s = slot(StringArgumentType.getString(ctx, "hand"));
                                    probe.serverSwing(p, s == null ? EquipmentSlot.HAND : s, "cmd");
                                }))))
                .then(Commands.literal("mob")
                        .then(Commands.literal("clear").executes(ctx -> with(ctx, p -> {
                            int n = clearMobs();
                            plugin.test(p, "PROBE_MOB cleared=" + n + " t=" + plugin.ticker().now()); // lang-machine: 시험 줄
                        })))
                        .then(Commands.argument("type", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String x : List.of("husk", "zombie", "skeleton", "piglin", "wither_skeleton", "drowned")) b.suggest(x);
                                    return b.buildFuture();
                                })
                                .then(Commands.argument("mode", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            for (String x : List.of("block", "aggr", "idle")) b.suggest(x);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> with(ctx, p -> mob(plugin, p, StringArgumentType.getString(ctx, "type"),
                                                StringArgumentType.getString(ctx, "mode"), "redin_guard_shield")))
                                        .then(Commands.argument("item", StringArgumentType.word())
                                                .suggests((c, b) -> {
                                                    b.suggest("shield");
                                                    for (Weapons.Def d : plugin.weapons().all().values())
                                                        if (Weapons.BLOCK.equals(d.use())) b.suggest(d.id());
                                                    return b.buildFuture();
                                                })
                                                .executes(ctx -> with(ctx, p -> mob(plugin, p, StringArgumentType.getString(ctx, "type"),
                                                        StringArgumentType.getString(ctx, "mode"), StringArgumentType.getString(ctx, "item"))))))))
                .then(Commands.literal("walkspeed")
                        .then(Commands.argument("value", com.mojang.brigadier.arguments.FloatArgumentType.floatArg(0f, 1f))
                                .executes(ctx -> with(ctx, p -> {
                                    // 능력의 걷기 속도 (기본 0.2) 와 이동 속도 속성의 바탕값 (그 반) 을 함께 바꾼다: 클라이언트 시야 (FOV) 는 속성 ÷ 걷기
                                    // 속도로 셈하므로 이 길로 느리게 하면 시야가 좁아지지 않는다 (S4). 0 이면 걷기 속도 0 이라 시야 셈을 건너뛴다
                                    p.setWalkSpeed(com.mojang.brigadier.arguments.FloatArgumentType.getFloat(ctx, "value"));
                                    var a = p.getAttribute(org.bukkit.attribute.Attribute.MOVEMENT_SPEED);
                                    plugin.test(p, String.format(Locale.ROOT, "PROBE_WALK walk=%.3f base=%.4f value=%.4f t=%d", p.getWalkSpeed(), // lang-machine
                                            a == null ? -1 : a.getBaseValue(), a == null ? -1 : a.getValue(), plugin.ticker().now()));
                                }))))
                .then(Commands.literal("crawl")
                        .then(Commands.argument("ticks", IntegerArgumentType.integer(1, 1200))
                                .executes(ctx -> with(ctx, p -> crawl(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"))))));
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

    private static EquipmentSlot slot(String s) {
        return switch (s) {
            case "main" -> EquipmentSlot.HAND;
            case "off" -> EquipmentSlot.OFF_HAND;
            default -> null;
        };
    }

    // ------------------------------------------------------------------ S9: 몹의 방패 자세

    private static void mob(Souls plugin, Player p, String typeName, String mode, String item) {
        EntityType type = EntityType.fromName(typeName.toLowerCase(Locale.ROOT));
        if (type == null || !type.isSpawnable() || type.getEntityClass() == null || !LivingEntity.class.isAssignableFrom(type.getEntityClass())) {
            plugin.test(p, "PROBE_MOB error=type type=" + typeName); // lang-machine: 시험 줄
            return;
        }
        ItemStack shield;
        if ("shield".equals(item)) {
            shield = ItemStack.of(Material.SHIELD);
        } else {
            Weapons.Def d = plugin.weapons().get(item);
            if (d == null) {
                plugin.test(p, "PROBE_MOB error=item item=" + item); // lang-machine: 시험 줄
                return;
            }
            shield = ItemFactory.weapon(d);
        }
        Location eye = p.getLocation();
        Vector f = eye.getDirection().setY(0);
        if (f.lengthSquared() < 1e-6) f = new Vector(0, 0, 1);
        Location at = eye.clone().add(f.normalize().multiply(3));
        at.setDirection(eye.toVector().subtract(at.toVector()));
        LivingEntity le = (LivingEntity) spawnRaw(p.getWorld(), at, type.getEntityClass(), e -> {
            e.setSilent(true);
            e.setPersistent(false);
            e.addScoreboardTag(MOB_TAG);
            e.addScoreboardTag(TestHits.ENT_TAG);
            if (e instanceof Ageable a) a.setAdult();
            if (e instanceof Mob m) {
                m.setAI(false);
                m.setRemoveWhenFarAway(false);
                if (m.getEquipment() != null) {
                    m.getEquipment().clear();
                    for (EquipmentSlot s : EquipmentSlot.values()) {
                        try {
                            m.getEquipment().setDropChance(s, 0f);
                        } catch (IllegalArgumentException ignored) {
                            // 몸 칸 (BODY·SADDLE) 은 이 몹에 없다
                        }
                    }
                }
            }
            if (e instanceof org.bukkit.entity.Zombie z) z.setShouldBurnInDay(false);
            if (e instanceof org.bukkit.entity.AbstractSkeleton s) s.setShouldBurnInDay(false);
        });
        if (le.getEquipment() != null) le.getEquipment().setItemInOffHand(shield);
        if ("aggr".equals(mode) && le instanceof Mob m) m.setAggressive(true);
        if (!"idle".equals(mode)) le.startUsingItem(EquipmentSlot.OFF_HAND);
        plugin.test(p, mobLine(plugin, le, mode, "0")); // lang-machine
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (le.isValid()) plugin.test(p, mobLine(plugin, le, mode, "1"));
        }, 1L);
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (le.isValid()) plugin.test(p, mobLine(plugin, le, mode, "20"));
        }, 20L);
    }

    private static String mobLine(Souls plugin, LivingEntity le, String mode, String after) {
        return String.format(Locale.ROOT, "PROBE_MOB type=%s mode=%s after=%s using=%s hand=%s raised=%s aggressive=%s off=%s t=%d", // lang-machine
                le.getType().getKey().getKey(), mode, after, le.hasActiveItem(), le.hasActiveItem() ? le.getActiveItemHand() : "-",
                le.isHandRaised(), le instanceof Mob m && m.isAggressive(),
                le.getEquipment() == null ? "-" : le.getEquipment().getItemInOffHand().getType().getKey().getKey(), plugin.ticker().now());
    }

    @SuppressWarnings("unchecked")
    private static <T extends Entity> T spawnRaw(World w, Location at, Class<? extends Entity> cls, Consumer<Entity> init) {
        Class<T> c = (Class<T>) cls;
        return w.spawn(at, c, false, init::accept);
    }

    private static int clearMobs() {
        int n = 0;
        for (World w : Bukkit.getWorlds()) {
            for (Entity e : w.getEntities()) {
                if (e.getScoreboardTags().contains(MOB_TAG)) {
                    e.remove();
                    n++;
                }
            }
        }
        return n;
    }

    // ------------------------------------------------------------------ S10: 화면에만 있는 막힘으로 눕기

    private static void crawl(Souls plugin, Player p, int ticks) {
        Location l = p.getLocation();
        World w = p.getWorld();
        int bx = l.getBlockX(), by = l.getBlockY() + 1, bz = l.getBlockZ();
        List<Block> placed = new ArrayList<>();
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                Block b = w.getBlockAt(bx + dx, by, bz + dz);
                if (!b.isPassable()) continue;
                p.sendBlockChange(b.getLocation(), CEILING.createBlockData());
                placed.add(b);
            }
        }
        plugin.test(p, String.format(Locale.ROOT, "PROBE_CRAWL placed=%d y=%d feet=%.3f pose=%s until=%d t=%d", placed.size(), by, l.getY(), // lang-machine
                p.getPose(), plugin.ticker().now() + ticks, plugin.ticker().now()));
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (p.isOnline()) plugin.test(p, "PROBE_CRAWL check pose=" + p.getPose() + " swimming=" + p.isSwimming() // lang-machine
                    + " t=" + plugin.ticker().now());
        }, 5L);
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            for (Block b : placed) p.sendBlockChange(b.getLocation(), b.getBlockData());
            plugin.test(p, "PROBE_CRAWL off pose=" + p.getPose() + " t=" + plugin.ticker().now()); // lang-machine
        }, ticks);
    }
}
