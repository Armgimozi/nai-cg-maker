package kr.souls.cmd;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.tree.LiteralCommandNode;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.Stamina;
import kr.souls.combat.TestHits;
import kr.souls.item.ItemFactory;
import kr.souls.skill.SkillContext;
import kr.souls.skill.SkillDef;
import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.action.DialogAction;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickCallback;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.GameRules;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

import java.time.Duration;
import java.util.List;
import java.util.Locale;

/**
 * /soulstest (config 의 debug.test-mode 가 켜졌을 때만, 권한 souls.test). 봇이 쓰는 시험 훅 (12.11, 13.2).
 * 결과는 "[T] 이름 열쇠=값 ..." 한 줄로 채팅과 서버 기록에 남는다. 봇은 채팅에서 이 줄을 읽는다.
 *
 *   stamina                          [T] STAMINA cur= max= ratio= exhausted= food= sprinting= regenFrom= t=
 *   stamina set <값>                  스태미나를 바꾼다 (탈진 시험)
 *   hit <피해> [type=generic|hit|none] [armor]   막기 성분 + generic 피해 시험. [T] HIT ...
 *   guard <empty|control|bypass|strip>  시험 막기 도구를 손에 쥐어 준다 (우클릭을 누르고 hit). 맞춤 모형 souls:test_guard. strip 은 막기 성분 없음
 *   swing [틱] [공격 속도]            휘두름 시험 도구 (13.4 의 8): swing_animation 길이와 attack_speed (회복 표시기)
 *   rollhit <틱 1~40> [피해]          걸어 둔 뒤 처음 구르는 구르기의 그 틱에 generic 피해. [T] ROLLHIT off= dodged=
 *   warn <틱> [피해]                  "[T] WARN hit_in=<틱>" 을 보내고 그 틱 뒤에 generic 피해 (봇이 자기 화면 기준으로 피하는 시험, 13.3)
 *   roll                             서버에서 곧바로 구르기 (F 패킷 대신)
 *   kill | heal | info | pos | title | skill <id>
 *   dialog                           휴식 창 꼴의 Dialog (13.4 의 4). 단추를 누르면 [T] DIALOG click=<id>, Esc 로 닫으면 [T] DIALOG exit
 */
public final class TestCommands {
    private TestCommands() {}

    @SuppressWarnings("deprecation") // isOnGround: 클라이언트가 알려 준 값을 그대로 보인다
    public static void register(Souls plugin, Commands reg) {
        LiteralCommandNode<CommandSourceStack> root = Commands.literal("soulstest")
                .requires(s -> plugin.cfg().testMode && s.getSender().hasPermission("souls.test"))
                .then(Commands.literal("stamina")
                        .executes(ctx -> withPlayer(ctx, p -> stamina(plugin, p)))
                        .then(Commands.literal("set").then(Commands.argument("value", DoubleArgumentType.doubleArg(0))
                                .executes(ctx -> withPlayer(ctx, p -> {
                                    CombatState st = CombatState.of(p);
                                    st.stamina.set(DoubleArgumentType.getDouble(ctx, "value"));
                                    // 0 이면 진짜 탈진처럼 회복 지연도 탈진 값 (3.2: 24틱)
                                    boolean zero = st.stamina.cur() <= 0;
                                    var sc = plugin.cfg().stamina;
                                    st.stamina.holdUntil(plugin.ticker().now() + (zero ? sc.exhaustedDelay() : sc.regenDelay()));
                                    if (zero) st.exhausted = true;
                                    stamina(plugin, p);
                                })))))
                .then(Commands.literal("hit")
                        .then(Commands.argument("amount", DoubleArgumentType.doubleArg(0, 10000))
                                .executes(ctx -> withPlayer(ctx, p -> hit(plugin, p, DoubleArgumentType.getDouble(ctx, "amount"), "")))
                                .then(Commands.argument("flags", StringArgumentType.greedyString())
                                        .suggests((c, b) -> {
                                            for (String s : List.of("type=generic", "type=hit", "type=none", "armor", "type=generic armor"))
                                                b.suggest(s);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> hit(plugin, p, DoubleArgumentType.getDouble(ctx, "amount"),
                                                StringArgumentType.getString(ctx, "flags")))))))
                .then(Commands.literal("guard")
                        .then(Commands.argument("kind", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (ItemFactory.GuardTest g : ItemFactory.GuardTest.values()) b.suggest(g.name().toLowerCase(Locale.ROOT));
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> guard(plugin, p, StringArgumentType.getString(ctx, "kind"))))))
                .then(Commands.literal("swing")
                        .executes(ctx -> withPlayer(ctx, p -> swing(plugin, p, 12, 1.0)))
                        .then(Commands.argument("ticks", IntegerArgumentType.integer(1, 100))
                                .executes(ctx -> withPlayer(ctx, p -> swing(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"), 1.0)))
                                .then(Commands.argument("speed", DoubleArgumentType.doubleArg(0.1, 4))
                                        .executes(ctx -> withPlayer(ctx, p -> swing(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"),
                                                DoubleArgumentType.getDouble(ctx, "speed")))))))
                .then(Commands.literal("warn")
                        .then(Commands.argument("ticks", IntegerArgumentType.integer(1, 100))
                                .executes(ctx -> withPlayer(ctx, p -> warn(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"), 2)))
                                .then(Commands.argument("amount", DoubleArgumentType.doubleArg(0, 10000))
                                        .executes(ctx -> withPlayer(ctx, p -> warn(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"),
                                                DoubleArgumentType.getDouble(ctx, "amount")))))))
                .then(Commands.literal("rollhit")
                        .then(Commands.argument("offset", IntegerArgumentType.integer(1, 40))
                                .executes(ctx -> withPlayer(ctx, p -> armRoll(plugin, p, IntegerArgumentType.getInteger(ctx, "offset"), 4)))
                                .then(Commands.argument("amount", DoubleArgumentType.doubleArg(0, 10000))
                                        .executes(ctx -> withPlayer(ctx, p -> armRoll(plugin, p, IntegerArgumentType.getInteger(ctx, "offset"),
                                                DoubleArgumentType.getDouble(ctx, "amount")))))))
                .then(Commands.literal("roll").executes(ctx -> withPlayer(ctx, p -> plugin.roll().tryRoll(p))))
                .then(Commands.literal("kill").executes(ctx -> withPlayer(ctx, p -> {
                    plugin.test(p, "KILL t=" + plugin.ticker().now());
                    p.setHealth(0);
                })))
                .then(Commands.literal("heal").executes(ctx -> withPlayer(ctx, p -> {
                    p.setHealth(kr.souls.skill.Combat.maxHealth(p));
                    plugin.stamina().refill(p);
                    plugin.test(p, String.format(Locale.ROOT, "HEAL hp=%.1f", p.getHealth()));
                })))
                .then(Commands.literal("info").executes(ctx -> withPlayer(ctx, p -> info(plugin, p))))
                .then(Commands.literal("pos").executes(ctx -> withPlayer(ctx, p -> {
                    Location l = p.getLocation();
                    plugin.test(p, String.format(Locale.ROOT, "POS x=%.3f y=%.3f z=%.3f yaw=%.1f ground=%s t=%d",
                            l.getX(), l.getY(), l.getZ(), l.getYaw(), p.isOnGround(), plugin.ticker().now()));
                })))
                .then(Commands.literal("title").executes(ctx -> withPlayer(ctx, p -> plugin.death().showTitle(p, true))))
                .then(Commands.literal("dialog").executes(ctx -> withPlayer(ctx, p -> dialog(plugin, p))))
                .then(Commands.literal("skill")
                        .then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : plugin.skills().all().keySet()) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> skill(plugin, p, StringArgumentType.getString(ctx, "id"))))))
                .build();
        reg.register(root, "식은 가마 시험 명령어 (debug.test-mode)", List.of());
    }

    private interface PlayerAction {
        void run(Player p);
    }

    private static int withPlayer(CommandContext<CommandSourceStack> ctx, PlayerAction a) {
        Entity e = SoulsCommands.target(ctx);
        if (!(e instanceof Player p)) {
            ctx.getSource().getSender().sendMessage(Component.text("플레이어가 쳐야 한다 (또는 /execute as).", NamedTextColor.GRAY));
            return 0;
        }
        a.run(p);
        return Command.SINGLE_SUCCESS;
    }

    private static void stamina(Souls plugin, Player p) {
        CombatState st = CombatState.of(p);
        plugin.test(p, String.format(Locale.ROOT, "STAMINA cur=%.2f max=%.1f ratio=%.4f exhausted=%s food=%d sprinting=%s regenFrom=%d t=%d",
                st.stamina.cur(), st.stamina.max(), st.stamina.ratio(), st.exhausted, p.getFoodLevel(), p.isSprinting(),
                st.stamina.regenFrom(), plugin.ticker().now()));
    }

    private static void hit(Souls plugin, Player p, double amount, String flags) {
        String type = "generic";
        boolean armor = false;
        for (String f : flags.trim().split("\\s+")) {
            if (f.startsWith("type=")) type = f.substring(5).toLowerCase(Locale.ROOT);
            else if (f.equals("armor")) armor = true;
        }
        if (!List.of("generic", "hit", "none").contains(type)) {
            plugin.test(p, "HIT error=unknown_type type=" + type);
            return;
        }
        TestHits.Result r = plugin.testHits().hit(p, amount, type, armor);
        plugin.test(p, "HIT " + r.line() + " t=" + plugin.ticker().now());
    }

    private static void guard(Souls plugin, Player p, String kind) {
        ItemFactory.GuardTest g = ItemFactory.GuardTest.parse(kind);
        if (g == null) {
            plugin.test(p, "GUARD error=unknown_kind kind=" + kind);
            return;
        }
        int slot = p.getInventory().getHeldItemSlot();
        p.getInventory().setItem(slot, ItemFactory.testGuard(g));
        plugin.test(p, "GUARD kind=" + g.name().toLowerCase(Locale.ROOT) + " slot=" + slot + " item=" + ItemFactory.SHELL.getKey().getKey());
    }

    /** 휘두름 시험 도구 (13.4 의 8). 시험 막기 도구와 같은 껍데기·모형에 휘두름 길이와 공격 속도만 단다. */
    private static void swing(Souls plugin, Player p, int ticks, double speed) {
        int slot = p.getInventory().getHeldItemSlot();
        p.getInventory().setItem(slot, ItemFactory.testSwing(ticks, speed));
        plugin.test(p, String.format(Locale.ROOT, "SWING ticks=%d speed=%.2f slot=%d", ticks, speed, slot));
    }

    /**
     * 예고한 뒤 때리기 (13.3). 지금 틱에 "[T] WARN" 줄을 보내고 ticks 틱 뒤에 원인 있는 generic 피해를 넣는다.
     * 봇은 이 줄을 받은 때(자기 화면 기준)에 F 를 누르므로, 왕복 지연이 길수록 무적 창 안에 들기 어렵다.
     * 지금은 피격 대기열(3.9, M1)이 없어 서버 틱 그대로 판정한다. 지연별 피한 비율은 대기열이 생긴 뒤의 견줄 기준선이다.
     */
    private static void warn(Souls plugin, Player p, int ticks, double amount) {
        long warned = plugin.ticker().now();
        plugin.test(p, "WARN hit_in=" + ticks + " at=" + (warned + ticks) + " t=" + warned);
        org.bukkit.Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline() || p.isDead()) return;
            CombatState st = CombatState.of(p);
            long now = plugin.ticker().now();
            // 예고 뒤에 시작한 구르기만 센다 (F 가 피해보다 늦게 닿았으면 -1)
            long since = st.roll == null || st.rollStart < warned ? -1 : now - st.rollStart;
            TestHits.Result r = plugin.testHits().hit(p, amount, "generic", false);
            plugin.test(p, String.format(Locale.ROOT, "WARNHIT roll_t=%d iframes=%d dodged=%s %s t=%d", since,
                    st.roll == null ? 0 : st.roll.iframes(), r.dealt() <= 1e-6, r.line(), now));
        }, ticks);
    }

    private static void armRoll(Souls plugin, Player p, int offset, double amount) {
        CombatState st = CombatState.of(p);
        st.armedRollHit = offset;
        st.armedRollHitAmount = amount;
        st.armedRollStart = Long.MIN_VALUE;
        plugin.test(p, String.format(Locale.ROOT, "ROLLHIT armed off=%d amount=%.2f", offset, amount));
    }

    private static void info(Souls plugin, Player p) {
        Location l = p.getLocation();
        var w = p.getWorld();
        CombatState st = CombatState.of(p);
        plugin.test(p, String.format(Locale.ROOT,
                "INFO world=%s mode=%s difficulty=%s biome=%s x=%.2f y=%.2f z=%.2f hp=%.1f food=%d xpLevel=%d stamina=%.1f/%.0f "
                        + "keep_inventory=%s immediate_respawn=%s locator_bar=%s natural_regen=%s pvp=%s test_mode=%s pack=%s t=%d",
                w.getName(), p.getGameMode(), w.getDifficulty(), w.getBiome(l.getBlockX(), l.getBlockY(), l.getBlockZ()).getKey(),
                l.getX(), l.getY(), l.getZ(), p.getHealth(), p.getFoodLevel(), p.getLevel(), st.stamina.cur(), st.stamina.max(),
                w.getGameRuleValue(GameRules.KEEP_INVENTORY), w.getGameRuleValue(GameRules.IMMEDIATE_RESPAWN),
                w.getGameRuleValue(GameRules.LOCATOR_BAR), w.getGameRuleValue(GameRules.NATURAL_HEALTH_REGENERATION),
                w.getGameRuleValue(GameRules.PVP), plugin.cfg().testMode, plugin.pack().sha1(), plugin.ticker().now()));
        if (!Stamina.fighting(p)) plugin.test(p, "INFO note=not_fighting (창작·관전 모드는 스태미나가 닳지 않는다)");
    }

    /**
     * Dialog 창 점검 (10.4, 13.4 의 4). 휴식 창과 같은 꼴: 제목은 화톳불 이름, 본문 한 줄, 단추 한 열, 나가기 동작.
     * 단추와 나가기 동작은 서버 콜백으로 받는다. Esc 로 닫을 때 나가기 동작이 오는지를 실제 클라이언트로 본다.
     */
    private static void dialog(Souls plugin, Player p) {
        ClickCallback.Options once = ClickCallback.Options.builder().uses(1).lifetime(Duration.ofMinutes(5)).build();
        // 글은 모두 lang/ko.yml (단추는 양피지색. 바닐라 흰 글씨는 화면에서 가장 밝아 제목보다 튄다)
        List<ActionButton> buttons = List.of(
                ActionButton.builder(Lang.c("bonfire.rest")).width(160)
                        .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG click=rest t=" + plugin.ticker().now()), once)).build(),
                ActionButton.builder(Lang.c("bonfire.warp")).width(160)
                        .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG click=warp t=" + plugin.ticker().now()), once)).build());
        ActionButton exit = ActionButton.builder(Lang.c("bonfire.leave")).width(160)
                .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG exit t=" + plugin.ticker().now()), once)).build();
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Lang.c("bonfire.test-name"))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.CLOSE)
                        .body(List.of(DialogBody.plainMessage(Lang.c("bonfire.status", "souls", "0", "level", "1"))))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(exit).columns(1).build()));
        p.showDialog(d);
        plugin.test(p, "DIALOG shown t=" + plugin.ticker().now());
    }

    private static void skill(Souls plugin, Player p, String id) {
        SkillDef def = plugin.skills().get(id);
        if (def == null) {
            plugin.test(p, "SKILL error=unknown id=" + id);
            return;
        }
        def.cast(new SkillContext(plugin, p, null, 1.0));
        plugin.test(p, "SKILL cast id=" + id + " mechanics=" + def.mechanics().size());
    }
}
