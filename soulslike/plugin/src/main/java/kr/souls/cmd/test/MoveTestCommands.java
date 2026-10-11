package kr.souls.cmd.test;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import kr.souls.Lang;
import kr.souls.Souls;
import kr.souls.combat.CombatState;
import kr.souls.combat.MoveRunner;
import kr.souls.combat.MoveTiming;
import kr.souls.combat.Moveset;
import kr.souls.combat.Slow;
import kr.souls.input.InputBuffer;
import kr.souls.item.ItemFactory;
import kr.souls.item.Weapons;
import org.bukkit.attribute.Attribute;
import org.bukkit.attribute.AttributeInstance;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.List;
import java.util.Locale;

/**
 * /soulstest move … (M1 P1a): 공격 동작. 봇 tools/bots/attacks.js 가 읽는다. 줄은 모두 ASCII 기계 글.
 * <pre>
 *   move &lt;light|heavy|running&gt;    입력 하나를 넣은 것과 같다 (입력 기억·막기 규칙 그대로, MoveRunner.input). 줄은 MOVE … / MOVE_BUF / MOVE_DENY
 *   moves                          든 무기 분류의 틱을 이 사람의 민첩으로 (모아 둔 몫 0 에서 한 번).
 *                                  [T] MOVES cls= weapon= dex= aspd= tier= light=s/a/r,… heavy=s/a/r running=s/a/r swing=틱 stab= range=
 *   state                          [T] MOVE_STATE move= phase= start= end= combo= buf= carry= slow= ready= held= fmt= tier= want= swing= aspd=
 *                                  using= main= off= echo=&lt;주손 되돌림 남은 수&gt;/&lt;왼손&gt; (2026-10-11 장부) ping=&lt;서버가 본 핑 ms&gt; t=
 * </pre>
 */
public final class MoveTestCommands {
    private MoveTestCommands() {}

    @FunctionalInterface
    private interface PlayerAction {
        void run(Player p);
    }

    public static LiteralArgumentBuilder<CommandSourceStack> move(Souls plugin) {
        return Commands.literal("move")
                .then(Commands.argument("kind", StringArgumentType.word())
                        .suggests((c, b) -> {
                            for (String x : List.of("light", "heavy", "running")) b.suggest(x);
                            return b.buildFuture();
                        })
                        .executes(ctx -> with(ctx, p -> {
                            String k = StringArgumentType.getString(ctx, "kind").toUpperCase(Locale.ROOT);
                            InputBuffer.Kind kind;
                            try {
                                kind = InputBuffer.Kind.valueOf(k);
                            } catch (IllegalArgumentException e) {
                                plugin.test(p, "MOVE error=bad_kind kind=" + k.toLowerCase(Locale.ROOT));
                                return;
                            }
                            plugin.moves().input(p, kind, null, plugin.ticker().now());
                        })));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> moves(Souls plugin) {
        return Commands.literal("moves").executes(ctx -> with(ctx, p -> {
            MoveRunner mr = plugin.moves();
            Weapons.Def w = plugin.weapons().of(p.getInventory().getItemInMainHand());
            Moveset.Cls c = w == null ? null : mr.moveset().of(w.cls());
            int dex = plugin.stats().of(p).dex();
            if (c == null) {
                plugin.test(p, "MOVES cls=- weapon=" + (w == null ? "-" : w.id()) + " dex=" + dex);
                return;
            }
            StringBuilder light = new StringBuilder();
            for (int i = 0; i < c.combo(); i++) light.append(i == 0 ? "" : ",").append(sar(mr.time(c.light(i), dex, 0)));
            ItemStack fresh = ItemFactory.weapon(w, mr.tier(p));
            var anim = fresh.getData(io.papermc.paper.datacomponent.DataComponentTypes.SWING_ANIMATION);
            plugin.test(p, String.format(Locale.ROOT, "MOVES cls=%s weapon=%s dex=%d aspd=%.4f tier=%d light=%s heavy=%s running=%s swing=%d stab=%s range=%.1f",
                    c.id(), w.id(), dex, mr.speed(dex), mr.tier(p), light, sar(mr.time(c.heavy(), dex, 0)), sar(mr.time(c.running(), dex, 0)),
                    anim == null ? -1 : anim.duration(), c.stab(), c.spec().range()));
        }));
    }

    public static LiteralArgumentBuilder<CommandSourceStack> state(Souls plugin) {
        return Commands.literal("state").executes(ctx -> with(ctx, p -> {
            long now = plugin.ticker().now();
            CombatState st = CombatState.of(p);
            MoveRunner.Run m = st.move;
            InputBuffer.Entry b = st.buffer.peek();
            ItemStack main = p.getInventory().getItemInMainHand();
            var anim = main.getData(io.papermc.paper.datacomponent.DataComponentTypes.SWING_ANIMATION);
            AttributeInstance as = p.getAttribute(Attribute.ATTACK_SPEED);
            Weapons.Def w = plugin.weapons().of(main);
            plugin.test(p, String.format(Locale.ROOT,
                    "MOVE_STATE move=%s phase=%s start=%s end=%s combo=%d buf=%s carry=%.3f slow=%.2f walk=%.3f ready=%s held=%s fmt=%d tier=%d want=%d "
                            + "swing=%s aspd=%.3f using=%s main=%s off=%s echo=%d/%d ping=%d t=%d",
                    m == null ? "-" : m.kind, m == null ? "-" : m.phase(now).name().toLowerCase(Locale.ROOT), m == null ? "-" : m.start,
                    m == null ? "-" : m.end(), st.combo, b == null ? "-" : b.kind().name().toLowerCase(Locale.ROOT) + "@" + b.at(), st.dexCarry,
                    Slow.factor(p), p.getWalkSpeed(), st.rollReadyAt <= CombatState.NEVER ? "-" : st.rollReadyAt, w == null ? "-" : w.id(),
                    ItemFactory.fmtOf(main), ItemFactory.tierOf(main), plugin.moves().tier(p),
                    anim == null ? "-" : anim.type().name().toLowerCase(Locale.ROOT) + "/" + anim.duration(), as == null ? -1 : as.getValue(),
                    p.hasActiveItem() ? p.getActiveItem().getType().getKey().getKey() : "-", main.isEmpty() ? "-" : main.getType().getKey().getKey(),
                    p.getInventory().getItemInOffHand().isEmpty() ? "-" : p.getInventory().getItemInOffHand().getType().getKey().getKey(),
                    st.echoMain.due(now), st.echoOff.due(now), p.getPing(), now));
        }));
    }

    private static String sar(MoveTiming.Timed t) {
        return t.s() + "/" + t.a() + "/" + t.r();
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
