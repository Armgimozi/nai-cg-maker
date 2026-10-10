package kr.souls.cmd;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.DoubleArgumentType;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.LongArgumentType;
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
import kr.souls.combat.Tumble;
import kr.souls.data.Profile;
import kr.souls.progression.StatBlock;
import kr.souls.hud.Glyphs;
import kr.souls.item.ItemFactory;
import kr.souls.skill.SkillContext;
import kr.souls.skill.SkillDef;
import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.action.DialogAction;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import net.kyori.adventure.text.event.ClickCallback;
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
 *   tumble [자세 번호] [side|front|back] [seen|own|both]
 *                                    구르기 대역을 그 열쇠 자세로 멈춰 세운다 (10초, 3칸 앞). 번호가 없거나 -1 이면 열쇠 자세를 모두 한 줄로.
 *                                    side: 구르는 쪽이 보는 사람의 오른쪽 (옆모습), front: 보는 사람 쪽으로 (앞모습), back: 멀어지는 쪽 (등).
 *                                    seen (기본): 남에게 보이는 벌 (바닐라 머리), own: 그 사람 화면의 벌 (표시 알파, 픽셀 머리),
 *                                    both: 둘을 나란히 (own 이 오른쪽 1.2칸. 픽셀 머리와 바닐라 머리를 견준다)
 *   kill | heal | info | pos | title | skill <id>
 *   hud                              [T] HUD mode=glyph|text bossbar= hp=채움/길이 trail= fp= st= souls= blank= (보낸 HUD 막대 값, 픽셀, 10.2)
 *   dialog                           휴식 창 꼴의 Dialog (13.4 의 4). 단추를 누르면 [T] DIALOG click=<id>, Esc 로 닫으면 [T] DIALOG exit
 *   give <id|all> [inv|main|off]     무기·방패·촉매 (content/weapons.yml) 를 아이템으로. inv 는 인벤토리 (기본), main 은 든 칸,
 *                                    off 는 왼손. all 은 스물을 단축 슬롯부터 차례로 (든 칸은 그대로 둔다). [T] GIVE id= n= to=
 *
 * 1.3판 (5.7~5.10, 13.2). 봇은 창 단추를 진짜 패킷 (custom_click_action, lib.clickDialog) 으로도 누르고, 여기 명령은 같은 처리기를 부른다:
 *   souls <n>                        자기 소울을 n 으로. [T] SOULS n=
 *   settings <난이도> <on|off>        세계 설정 창의 난이도 단추를 그 PvP 값으로 누른 것과 같다 (via=dialog). [T] SETTINGS ...
 *   settings esc | clear | show      창을 닫은 것과 같다 (via=esc) / 세계 설정을 지운다 (새 세계처럼, 다음 접속에 창) / 지금 값
 *   origin <id> | esc | show         출신 확인 창의 "이 출신으로" / 출신 창을 닫은 것 / 출신 창을 띄운다. [T] ORIGIN ...
 *   levelup open | <vig|mnd|end|str|dex|int> [n] | undo | confirm | cancel   레벨 올리기 창의 단추. [T] LEVELUP ...
 *   stats                            [T] STATS ... (5.9)
 *   stat <id> <값>                    능력치 하나를 바로 정한다 (시험용, 레벨이 따라 바뀐다)
 *   rest                             시험 방 화톳불에서 쉰 것과 같다 (HP·스태미나를 채우고 휴식 창). [T] REST shown
 *   load                             [T] LOAD ... (5.8)
 *   pvphit <이름> [피해]              그 사람을 원인이 나인 generic 피해로 때린다 (PvP 길, 스킬 피해처럼 HP 단위). [T] PVPHIT dealt= ...
 *   pvpshoot <이름> <arrow|snowball|potion|cloud|harm>   그 사람에게 쏜 사람이 나인 투사체·구름 (harm: 즉시 피해 잔류 구름). [T] PVPSHOOT kind=
 *   foehp spawn|check|hurt|clear     시험 좀비 (움직이지 않는다) 를 2칸 앞에 / 지금 값 / 체력 절반으로 / 지운다. [T] FOEHP n= hp=체력/최대,… mult=
 *   effect <효과> <틱>                 나에게 해로운 효과 (지능의 상태 이상 저항 시험). [T] AILMENT ... 와 EFFECT have=
 *   burn <틱>                         나에게 불붙음 (불붙이는 이벤트를 지나 저항으로 줄인다). [T] BURN fire=
 *   tap                              마지막 짧은 누름 판정 ([T] ROLL_TAP ... / ROLL_TAP_SKIP ...)
 *   press <창> <단추>                 열린 우리 창의 단추를 누른 것과 같다 (창 이름: settings, origin, origin_confirm, levelup, stats, rest)
 *   ui                               [T] UI open=<창>
 *   attr                             [T] ATTRS max_health=<값>[수정자 열쇠:값,…] movement_speed=… attack_speed=… (서버 쪽 속성과 수정자.
 *                                    클라이언트는 하트 배율 때문에 max_health 를 20 으로 받으므로 수정자가 쌓이지 않았는지는 여기서 본다)
 *   opens <자물쇠 id>                 Keys.opens (만능 열쇠·문 열쇠, 9.5): [T] OPENS lock= result= master= (이야기로 막힌 문은 늘 false)
 *
 * 반지 (9.4, item/RingSlots):
 *   ring give <id>                   반지를 인벤토리에 (시험 반지는 이것으로만 얻는다). [T] RING_GIVE id= ok=
 *   ring show                        [T] RINGS r1= r2= (프로필) s0..s4= (2×2 칸: 사본은 id*, 결과 칸 s0, 반지 칸 s1·s3) inv=<칸:id,…>
 *                                    cursor= strays= (칸 밖의 사본) ground= (32칸 안의 반지 물체) near=<종류:수,…> (8칸 안의 반지가
 *                                    아닌 물체) regen= poise= parry= guard=
 *   ring equip <1|2> <id|none>       반지 칸에 바로 낀다 / 뺀다 (아이템을 쓰거나 주지 않는다. 찍기 준비). [T] RING_SET ok=
 *   ring chest                       빈 상자 창 (세 줄) 을 연다 (다른 창이 열린 동안 죽거나 나갈 때 2×2 사본이 새지 않는지). [T] RING_CHEST open=
 * 반지 칸의 누르기는 [T] RING act=put|take|swap|unequip|hotbar|offhand|equip, 거절은 RING_DENY slot= why=, 같은 반지 둘은 RING_SAME,
 * 칸 밖 사본 지우기는 RING_SWEEP, 2×2 에 들어온 다른 것을 돌려주면 RING_STRAY.
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
                                            for (String s : List.of("type=generic", "type=hit", "type=magic", "type=none", "armor", "def",
                                                    "type=magic def", "type=generic armor"))
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
                .then(Commands.literal("tumble")
                        .executes(ctx -> withPlayer(ctx, p -> tumble(plugin, p, -1, "side", "seen")))
                        .then(Commands.argument("frame", IntegerArgumentType.integer(-1, 63))
                                .executes(ctx -> withPlayer(ctx, p -> tumble(plugin, p, IntegerArgumentType.getInteger(ctx, "frame"), "side", "seen")))
                                .then(Commands.argument("facing", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            for (String x : List.of("side", "front", "back")) b.suggest(x);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> tumble(plugin, p, IntegerArgumentType.getInteger(ctx, "frame"),
                                                StringArgumentType.getString(ctx, "facing"), "seen")))
                                        .then(Commands.argument("which", StringArgumentType.word())
                                                .suggests((c, b) -> {
                                                    for (String x : List.of("seen", "own", "both")) b.suggest(x);
                                                    return b.buildFuture();
                                                })
                                                .executes(ctx -> withPlayer(ctx, p -> tumble(plugin, p, IntegerArgumentType.getInteger(ctx, "frame"),
                                                        StringArgumentType.getString(ctx, "facing"), StringArgumentType.getString(ctx, "which"))))))))
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
                .then(Commands.literal("hud").executes(ctx -> withPlayer(ctx, p -> plugin.test(p, plugin.hud().testLine(p)))))
                .then(Commands.literal("boss")
                        .then(Commands.literal("off").executes(ctx -> withPlayer(ctx, p -> {
                            plugin.hud().bossOff(p, "test");
                            plugin.test(p, "BOSS off t=" + plugin.ticker().now());
                        })))
                        .then(Commands.argument("hp", DoubleArgumentType.doubleArg(0, 100))
                                .executes(ctx -> withPlayer(ctx, p -> boss(plugin, p, DoubleArgumentType.getDouble(ctx, "hp"), 100)))
                                .then(Commands.argument("posture", DoubleArgumentType.doubleArg(0, 100))
                                        .executes(ctx -> withPlayer(ctx, p -> boss(plugin, p, DoubleArgumentType.getDouble(ctx, "hp"),
                                                DoubleArgumentType.getDouble(ctx, "posture")))))))
                .then(Commands.literal("pos").executes(ctx -> withPlayer(ctx, p -> {
                    Location l = p.getLocation();
                    plugin.test(p, String.format(Locale.ROOT, "POS x=%.3f y=%.3f z=%.3f yaw=%.1f ground=%s t=%d",
                            l.getX(), l.getY(), l.getZ(), l.getYaw(), p.isOnGround(), plugin.ticker().now()));
                })))
                .then(Commands.literal("title").executes(ctx -> withPlayer(ctx, p -> plugin.death().showTitle(p, true))))
                .then(Commands.literal("dialog").executes(ctx -> withPlayer(ctx, p -> dialog(plugin, p))))
                .then(Commands.literal("give")
                        .then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    b.suggest("all");
                                    for (String id : plugin.weapons().all().keySet()) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> give(plugin, p, StringArgumentType.getString(ctx, "id"), "inv")))
                                .then(Commands.argument("to", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            for (String x : List.of("inv", "main", "off")) b.suggest(x);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> give(plugin, p, StringArgumentType.getString(ctx, "id"),
                                                StringArgumentType.getString(ctx, "to")))))))
                .then(Commands.literal("skill")
                        .then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : plugin.skills().all().keySet()) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> skill(plugin, p, StringArgumentType.getString(ctx, "id"))))))
                .then(Commands.literal("souls").then(Commands.argument("n", LongArgumentType.longArg(0, Profile.SOULS_MAX))
                        .executes(ctx -> withPlayer(ctx, p -> {
                            plugin.purse().set(p, LongArgumentType.getLong(ctx, "n"));
                            plugin.profiles().save(p, false);
                            plugin.test(p, "SOULS n=" + plugin.purse().get(p) + " t=" + plugin.ticker().now());
                        }))))
                .then(Commands.literal("settings")
                        .then(Commands.literal("esc").executes(ctx -> withPlayer(ctx, p -> plugin.start().settingsLater(p))))
                        .then(Commands.literal("show").executes(ctx -> withPlayer(ctx, p -> {
                            var st = plugin.worldState().get();
                            plugin.test(p, "SETTINGS " + (st == null ? "none" : st.line()) + " gamerule_pvp=" + p.getWorld().getGameRuleValue(GameRules.PVP));
                        })))
                        .then(Commands.literal("clear").executes(ctx -> withPlayer(ctx, p -> {
                            plugin.worldState().clear(plugin.worlds().world());
                            plugin.worlds().applyPvp();
                            plugin.test(p, "SETTINGS cleared");
                        })))
                        .then(Commands.argument("difficulty", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : plugin.cfg().difficulties.keySet()) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .then(Commands.argument("pvp", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            b.suggest("on");
                                            b.suggest("off");
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> plugin.start().chooseSettings(p, StringArgumentType.getString(ctx, "difficulty"),
                                                "on".equalsIgnoreCase(StringArgumentType.getString(ctx, "pvp")), "dialog"))))))
                .then(Commands.literal("origin")
                        .then(Commands.literal("esc").executes(ctx -> withPlayer(ctx, p -> plugin.start().originLater(p))))
                        .then(Commands.literal("show").executes(ctx -> withPlayer(ctx, p -> kr.souls.ui.OriginDialog.show(plugin, p))))
                        .then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (var o : plugin.origins().all()) b.suggest(o.id());
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> plugin.start().chooseOrigin(p, StringArgumentType.getString(ctx, "id"), "dialog")))))
                .then(Commands.literal("levelup")
                        .then(Commands.literal("open").executes(ctx -> withPlayer(ctx, p -> plugin.levelUp().open(p))))
                        .then(Commands.literal("undo").executes(ctx -> withPlayer(ctx, p -> plugin.levelUp().add(p, "vig", -1))))
                        .then(Commands.literal("confirm").executes(ctx -> withPlayer(ctx, p -> plugin.levelUp().confirm(p))))
                        .then(Commands.literal("cancel").executes(ctx -> withPlayer(ctx, p -> plugin.levelUp().cancel(p))))
                        .then(Commands.argument("stat", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : StatBlock.IDS) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> levelAdd(plugin, p, StringArgumentType.getString(ctx, "stat"), 1)))
                                .then(Commands.argument("n", IntegerArgumentType.integer(-98, 98))
                                        .executes(ctx -> withPlayer(ctx, p -> levelAdd(plugin, p, StringArgumentType.getString(ctx, "stat"),
                                                IntegerArgumentType.getInteger(ctx, "n")))))))
                .then(Commands.literal("stats").executes(ctx -> withPlayer(ctx, p -> plugin.test(p, plugin.stats().line(p)))))
                .then(Commands.literal("stat")
                        .then(Commands.argument("id", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : StatBlock.IDS) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .then(Commands.argument("value", IntegerArgumentType.integer(1, 99))
                                        .executes(ctx -> withPlayer(ctx, p -> setStat(plugin, p, StringArgumentType.getString(ctx, "id"),
                                                IntegerArgumentType.getInteger(ctx, "value")))))))
                .then(Commands.literal("rest").executes(ctx -> withPlayer(ctx, p -> plugin.testBonfire().rest(p))))
                .then(Commands.literal("load").executes(ctx -> withPlayer(ctx, p -> {
                    var t = plugin.load().refresh(p);
                    plugin.test(p, String.format(Locale.ROOT, "LOAD weight=%.1f cap=%.1f tier=%s roll=%s t=%d", plugin.load().weight(p),
                            plugin.cfg().stats.equipLoad.at(plugin.stats().of(p).str()), t.id(), t.roll(), plugin.ticker().now()));
                })))
                .then(Commands.literal("pvphit")
                        .then(Commands.argument("name", StringArgumentType.word())
                                .executes(ctx -> withPlayer(ctx, p -> pvpHit(plugin, p, StringArgumentType.getString(ctx, "name"), 40)))
                                .then(Commands.argument("amount", DoubleArgumentType.doubleArg(0, 10000))
                                        .executes(ctx -> withPlayer(ctx, p -> pvpHit(plugin, p, StringArgumentType.getString(ctx, "name"),
                                                DoubleArgumentType.getDouble(ctx, "amount")))))))
                .then(Commands.literal("pvpshoot")
                        .then(Commands.argument("name", StringArgumentType.word())
                                .then(Commands.argument("kind", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            for (String x : List.of("arrow", "snowball", "potion", "cloud", "harm")) b.suggest(x);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> pvpShoot(plugin, p, StringArgumentType.getString(ctx, "name"),
                                                StringArgumentType.getString(ctx, "kind")))))))
                .then(Commands.literal("effect")
                        .then(Commands.argument("type", StringArgumentType.word())
                                .then(Commands.argument("ticks", IntegerArgumentType.integer(1, 20000))
                                        .executes(ctx -> withPlayer(ctx, p -> effect(plugin, p, StringArgumentType.getString(ctx, "type"),
                                                IntegerArgumentType.getInteger(ctx, "ticks")))))))
                .then(Commands.literal("burn")
                        .then(Commands.argument("ticks", IntegerArgumentType.integer(1, 2000))
                                .executes(ctx -> withPlayer(ctx, p -> burn(plugin, p, IntegerArgumentType.getInteger(ctx, "ticks"))))))
                .then(Commands.literal("tap").executes(ctx -> withPlayer(ctx, p -> plugin.test(p, plugin.sneakTap().lastLine(p)))))
                .then(Commands.literal("press")
                        .then(Commands.argument("dialog", StringArgumentType.word())
                                .then(Commands.argument("button", StringArgumentType.word())
                                        .executes(ctx -> withPlayer(ctx, p -> {
                                            boolean ok = plugin.ui().press(p, StringArgumentType.getString(ctx, "dialog"), StringArgumentType.getString(ctx, "button"));
                                            if (!ok) plugin.test(p, "PRESS error=not_open open=" + plugin.ui().openDialog(p));
                                        })))))
                .then(Commands.literal("ui").executes(ctx -> withPlayer(ctx, p -> plugin.test(p, "UI open=" + plugin.ui().openDialog(p)))))
                .then(Commands.literal("attr").executes(ctx -> withPlayer(ctx, p -> attrs(plugin, p))))
                .then(Commands.literal("foehp")
                        .then(Commands.literal("spawn").executes(ctx -> withPlayer(ctx, p -> foeHp(plugin, p, "spawn"))))
                        .then(Commands.literal("check").executes(ctx -> withPlayer(ctx, p -> foeHp(plugin, p, "check"))))
                        .then(Commands.literal("hurt").executes(ctx -> withPlayer(ctx, p -> foeHp(plugin, p, "hurt"))))
                        .then(Commands.literal("clear").executes(ctx -> withPlayer(ctx, p -> foeHp(plugin, p, "clear")))))
                .then(Commands.literal("opens")
                        .then(Commands.argument("lock", StringArgumentType.word())
                                .suggests((c, b) -> {
                                    for (String id : kr.souls.item.MasterKey.KEY_DOORS.keySet()) b.suggest(id);
                                    for (String id : kr.souls.item.MasterKey.STORY_DOORS) b.suggest(id);
                                    return b.buildFuture();
                                })
                                .executes(ctx -> withPlayer(ctx, p -> {
                                    String lock = StringArgumentType.getString(ctx, "lock");
                                    boolean master = java.util.Arrays.stream(p.getInventory().getContents()).anyMatch(kr.souls.item.MasterKey::is);
                                    plugin.test(p, "OPENS lock=" + lock + " result=" + kr.souls.Keys.opens(p, lock) + " master=" + master);
                                }))))
                .then(Commands.literal("ring")
                        .then(Commands.literal("give")
                                .then(Commands.argument("id", StringArgumentType.word())
                                        .suggests((c, b) -> {
                                            for (String id : plugin.rings().all().keySet()) b.suggest(id);
                                            return b.buildFuture();
                                        })
                                        .executes(ctx -> withPlayer(ctx, p -> ringGive(plugin, p, StringArgumentType.getString(ctx, "id"))))))
                        .then(Commands.literal("show").executes(ctx -> withPlayer(ctx, p -> plugin.test(p, plugin.ringSlots().line(p)))))
                        .then(Commands.literal("chest").executes(ctx -> withPlayer(ctx, p -> {
                            // 다른 창 (세 줄 상자 꼴, 바닐라 제목) 을 연다: 그 창이 열린 동안의 죽음·나가기에서 2×2 사본이 새지 않는지 본다.
                            // 깔때기·셜커 상자 꼴은 쓰지 않는다: 그 창의 칸 하나가 GUI 의 지운 칸 자리와 겹쳐 가리킴 테가 지워진다 (9.4 알려진 한계)
                            p.openInventory(org.bukkit.Bukkit.createInventory(null, 27));
                            plugin.test(p, "RING_CHEST open=" + p.getOpenInventory().getTopInventory().getType());
                        })))
                        .then(Commands.literal("equip")
                                .then(Commands.argument("slot", IntegerArgumentType.integer(1, kr.souls.data.Profile.RING_SLOTS))
                                        .then(Commands.argument("id", StringArgumentType.word())
                                                .suggests((c, b) -> {
                                                    b.suggest("none");
                                                    for (String id : plugin.rings().all().keySet()) b.suggest(id);
                                                    return b.buildFuture();
                                                })
                                                .executes(ctx -> withPlayer(ctx, p -> {
                                                    int slot = IntegerArgumentType.getInteger(ctx, "slot");
                                                    String id = StringArgumentType.getString(ctx, "id");
                                                    boolean ok = plugin.ringSlots().set(p, slot - 1, "none".equals(id) ? null : id);
                                                    plugin.test(p, "RING_SET slot=" + slot + " id=" + id + " ok=" + ok);
                                                }))))))
                .build();
        reg.register(root, "Soulslike test hooks (debug.test-mode)", List.of());
    }

    /** 시험 보스 막대 (화면 아래 가운데, 10.2): 수문장 흐롤프의 이름으로 체력·자세 % (M2 의 보스가 쓰는 Hud.boss 그대로). */
    private static void boss(Souls plugin, Player p, double hp, double posture) {
        plugin.hud().boss(p, "test", "boss.hrolf.name", hp, 100, posture, 100);
        plugin.test(p, String.format(Locale.ROOT, "BOSS hp=%.0f posture=%.0f t=%d", hp, posture, plugin.ticker().now()));
    }

    /**
     * 구르기 대역을 그 열쇠 자세로 멈춰 세운다 (10초). 보는 쪽 3칸 앞. facing: side 는 구르는 쪽이 보는 사람의 오른쪽 (옆에서 본다),
     * front 는 보는 사람 쪽 (앞모습), back 은 멀어지는 쪽 (등). frame 이 -1 이면 열쇠 자세를 모두, 오른쪽으로 1.3칸 간격.
     * which: seen (남에게 보이는 벌), own (그 사람 화면의 벌: 표시 알파, 픽셀 머리), both (own 을 오른쪽 1.2칸에 나란히).
     */
    private static void tumble(Souls plugin, Player p, int frame, String facing, String which) {
        Tumble t = plugin.roll().tumble();
        Location eye = p.getLocation();
        double yaw = Math.toRadians(eye.getYaw());
        org.bukkit.util.Vector fwd = new org.bukkit.util.Vector(-Math.sin(yaw), 0, Math.cos(yaw));
        org.bukkit.util.Vector right = new org.bukkit.util.Vector(-Math.cos(yaw), 0, -Math.sin(yaw));
        org.bukkit.util.Vector dir = switch (facing) {
            case "front" -> fwd.clone().multiply(-1);
            case "back" -> fwd.clone();
            default -> right.clone();
        };
        Location base = eye.clone().add(fwd.clone().multiply(3));
        int n = t.frames();
        boolean both = which.equals("both");
        boolean own = which.equals("own");
        for (int k = 0; k < (both ? 2 : 1); k++) {
            boolean o = both ? k == 1 : own;
            Location b = both ? base.clone().add(right.clone().multiply(k == 1 ? 0.6 : -0.6)) : base;
            if (frame >= 0) {
                t.pose(p, b, dir, frame, 200, o);
            } else {
                for (int i = 0; i < n; i++) t.pose(p, b.clone().add(right.clone().multiply((i - (n - 1) / 2.0) * (both ? 2.6 : 1.3))), dir, i, 200, o);
            }
        }
        plugin.test(p, String.format(Locale.ROOT, "TUMBLE frame=%s of=%d facing=%s which=%s t=%d", frame < 0 ? "row" : String.valueOf(frame), n,
                facing, which, plugin.ticker().now()));
    }

    private interface PlayerAction {
        void run(Player p);
    }

    private static int withPlayer(CommandContext<CommandSourceStack> ctx, PlayerAction a) {
        Entity e = SoulsCommands.target(ctx);
        if (!(e instanceof Player p)) {
            Lang.tell(ctx.getSource().getSender(), "admin.players-only");
            return 0;
        }
        a.run(p);
        return Command.SINGLE_SUCCESS;
    }

    private static void stamina(Souls plugin, Player p) {
        CombatState st = CombatState.of(p);
        // rate: 지금 틱당 회복 (Stamina.tick 의 셈: 기본 × 기력 × 장비 무게 × 반지, 막는 중 배율은 빼고)
        double rate = plugin.cfg().stamina.regenPerTick() * plugin.cfg().stats.regenScale.at(plugin.stamina().endurance(p))
                * plugin.load().regen(p) * plugin.ringSlots().staminaRegen(p);
        plugin.test(p, String.format(Locale.ROOT, "STAMINA cur=%.2f max=%.1f ratio=%.4f exhausted=%s food=%d sprinting=%s regenFrom=%d t=%d rate=%.4f",
                st.stamina.cur(), st.stamina.max(), st.stamina.ratio(), st.exhausted, p.getFoodLevel(), p.isSprinting(),
                st.stamina.regenFrom(), plugin.ticker().now(), rate));
    }

    /** 시험 반지를 인벤토리에 (9.4: 시험 반지는 이 명령으로만 얻는다). [T] RING_GIVE id= ok= */
    private static void ringGive(Souls plugin, Player p, String id) {
        kr.souls.item.Rings.Def d = plugin.rings().get(id);
        if (d == null) {
            plugin.test(p, "RING_GIVE id=" + id + " ok=false why=unknown");
            return;
        }
        // 가방 (안쪽 27칸) 부터: 단축 슬롯을 채우지 않게
        org.bukkit.inventory.ItemStack it = plugin.rings().make(d);
        if (!kr.souls.util.Items.putBackpackFirst(p.getInventory(), it)) kr.souls.util.Items.give(p, it);
        plugin.test(p, "RING_GIVE id=" + id + " ok=true test=" + d.test());
    }

    private static void hit(Souls plugin, Player p, double amount, String flags) {
        String type = "generic";
        boolean armor = false, def = false;
        for (String f : flags.trim().split("\\s+")) {
            if (f.startsWith("type=")) type = f.substring(5).toLowerCase(Locale.ROOT);
            else if (f.equals("armor")) armor = true;
            else if (f.equals("def")) def = true;
        }
        if (!List.of("generic", "hit", "magic", "none").contains(type)) {
            plugin.test(p, "HIT error=unknown_type type=" + type);
            return;
        }
        TestHits.Result r = plugin.testHits().hit(p, amount, type, armor, def);
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

    /**
     * 무기·방패·촉매 주기 (content/weapons.yml, ItemFactory.weapon). all 은 스물을 등록 차례로 인벤토리에 (단축 슬롯부터 빈 칸에).
     * main 은 든 칸을 바꾸고, off 는 왼손을 바꾼다. 주손 무기의 막기 성분은 WeaponGuard 가 왼손을 보고 다시 맞춘다 (2.3 의 3).
     */
    private static void give(Souls plugin, Player p, String id, String to) {
        List<String> ids = "all".equals(id) ? List.copyOf(plugin.weapons().all().keySet()) : List.of(id);
        int n = 0;
        for (String w : ids) {
            kr.souls.item.Weapons.Def d = plugin.weapons().get(w);
            if (d == null) {
                plugin.test(p, "GIVE error=unknown id=" + w);
                continue;
            }
            org.bukkit.inventory.ItemStack it = ItemFactory.weapon(d);
            switch (to) {
                case "main" -> p.getInventory().setItemInMainHand(it);
                case "off" -> p.getInventory().setItemInOffHand(it);
                // 시험 도구라 바닐라처럼 단축 슬롯부터 (Items.give 는 souls 무기를 가방부터 넣는다, 5.8)
                default -> p.getInventory().addItem(it);
            }
            n++;
        }
        org.bukkit.Bukkit.getScheduler().runTask(plugin, () -> {
            if (p.isOnline()) new kr.souls.item.WeaponGuard(plugin).refresh(p);
        });
        plugin.test(p, "GIVE id=" + id + " n=" + n + " to=" + to);
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
                "INFO world=%s mode=%s difficulty=%s biome=%s x=%.2f y=%.2f z=%.2f hp=%.1f maxhp=%.0f scale=%.0f food=%d xpLevel=%d stamina=%.1f/%.0f "
                        + "keep_inventory=%s immediate_respawn=%s locator_bar=%s natural_regen=%s pvp=%s test_mode=%s pack=%s t=%d",
                w.getName(), p.getGameMode(), w.getDifficulty(), w.getBiome(l.getBlockX(), l.getBlockY(), l.getBlockZ()).getKey(),
                l.getX(), l.getY(), l.getZ(), p.getHealth(), kr.souls.skill.Combat.maxHealth(p), p.isHealthScaled() ? p.getHealthScale() : 0,
                p.getFoodLevel(), p.getLevel(), st.stamina.cur(), st.stamina.max(),
                w.getGameRuleValue(GameRules.KEEP_INVENTORY), w.getGameRuleValue(GameRules.IMMEDIATE_RESPAWN),
                w.getGameRuleValue(GameRules.LOCATOR_BAR), w.getGameRuleValue(GameRules.NATURAL_HEALTH_REGENERATION),
                w.getGameRuleValue(GameRules.PVP), plugin.cfg().testMode, plugin.pack().sha1(), plugin.ticker().now()));
        // 창작·관전 모드는 스태미나가 닳지 않는다
        if (!Stamina.fighting(p)) plugin.test(p, "INFO note=not_fighting mode=" + p.getGameMode());
    }

    /**
     * Dialog 창 점검 (10.4, 13.4 의 4). 휴식 창과 같은 꼴: 제목은 화톳불 이름, 본문 한 줄, 단추 한 열, 나가기 동작.
     * 단추와 나가기 동작은 서버 콜백으로 받는다. Esc 로 닫을 때 나가기 동작이 오는지를 실제 클라이언트로 본다.
     */
    private static void dialog(Souls plugin, Player p) {
        ClickCallback.Options once = ClickCallback.Options.builder().uses(1).lifetime(Duration.ofMinutes(5)).build();
        // 글은 모두 번역 열쇠 (lang/ko.yml, en.yml, 대체 글은 p 의 언어). 단추는 양피지색 (바닐라 흰 글씨는 화면에서 가장 밝아 제목보다 튄다)
        List<ActionButton> buttons = List.of(
                ActionButton.builder(Lang.c(p, "bonfire.rest")).width(160)
                        .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG click=rest t=" + plugin.ticker().now()), once)).build(),
                ActionButton.builder(Lang.c(p, "bonfire.warp")).width(160)
                        .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG click=warp t=" + plugin.ticker().now()), once)).build());
        ActionButton exit = ActionButton.builder(Lang.c(p, "bonfire.leave")).width(160)
                .action(DialogAction.customClick((r, a) -> plugin.test(p, "DIALOG exit t=" + plugin.ticker().now()), once)).build();
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(Glyphs.dialogTitle(Lang.c(p, "bonfire.test-name")))
                        .canCloseWithEscape(true).pause(false).afterAction(DialogBase.DialogAfterAction.CLOSE)
                        .body(List.of(DialogBody.plainMessage(Lang.c(p, "bonfire.status", "souls", "0", "level", "1", "next", "320"))))
                        .build())
                .type(DialogType.multiAction(buttons).exitAction(exit).columns(1).build()));
        p.showDialog(d);
        plugin.test(p, "DIALOG shown t=" + plugin.ticker().now());
    }

    /** 서버 쪽 속성 값과 수정자 (열쇠:값). 같은 열쇠가 둘이면 쌓인 것이다. */
    private static void attrs(Souls plugin, Player p) {
        StringBuilder sb = new StringBuilder("ATTRS");
        for (org.bukkit.attribute.Attribute a : List.of(org.bukkit.attribute.Attribute.MAX_HEALTH, org.bukkit.attribute.Attribute.MOVEMENT_SPEED,
                org.bukkit.attribute.Attribute.ATTACK_SPEED)) {
            org.bukkit.attribute.AttributeInstance in = p.getAttribute(a);
            if (in == null) continue;
            StringBuilder m = new StringBuilder();
            for (org.bukkit.attribute.AttributeModifier mod : in.getModifiers()) {
                if (!m.isEmpty()) m.append(',');
                m.append(mod.getKey().asString()).append(':').append(String.format(Locale.ROOT, "%.4f", mod.getAmount()));
            }
            sb.append(' ').append(a.getKey().getKey()).append('=').append(String.format(Locale.ROOT, "%.4f", in.getValue()))
                    .append(" ").append(a.getKey().getKey()).append("_mods=").append(m.isEmpty() ? "-" : m);
        }
        plugin.test(p, sb.toString());
    }

    private static void levelAdd(Souls plugin, Player p, String stat, int n) {
        if (!StatBlock.known(stat)) {
            plugin.test(p, "LEVELUP error=unknown stat=" + stat);
            return;
        }
        if (!plugin.levelUp().active(p)) plugin.levelUp().open(p);
        plugin.levelUp().add(p, stat.toLowerCase(Locale.ROOT), n);
    }

    private static void setStat(Souls plugin, Player p, String id, int v) {
        if (!StatBlock.known(id)) {
            plugin.test(p, "STAT error=unknown id=" + id);
            return;
        }
        double before = plugin.stamina().max(p);
        var pr = plugin.profiles().of(p);
        pr.setStats(pr.stats().with(id, v));
        plugin.attributes().apply(p);
        plugin.load().refresh(p);
        plugin.stamina().grow(p, before);
        plugin.profiles().save(p, false);
        plugin.test(p, "STAT " + id + "=" + v + " level=" + pr.stats().level());
    }

    private static Player other(Souls plugin, Player p, String name) {
        Player t = org.bukkit.Bukkit.getPlayerExact(name);
        if (t == null) plugin.test(p, "PVP error=no_player name=" + name);
        return t;
    }

    /** 원인이 나인 generic 피해 (PvP 끔이면 바닐라가 이벤트 없이 버린다, 켬이면 방어로 줄어 들어간다). */
    private static void pvpHit(Souls plugin, Player p, String name, double amount) {
        Player t = other(plugin, p, name);
        if (t == null) return;
        double before = t.getHealth();
        t.setNoDamageTicks(0);
        // 플러그인 스킬 피해와 같은 길 (이미 HP 단위, DEF from=player_skill). PvP 확인은 바닐라 규칙과 PvpGuard 가 한다
        kr.souls.skill.Combat.asSkill(() -> t.damage(amount, kr.souls.skill.Combat.source(org.bukkit.damage.DamageType.GENERIC, p)));
        double dealt = Math.max(0, before - (t.isDead() ? 0 : t.getHealth()));
        plugin.test(p, String.format(Locale.ROOT, "PVPHIT to=%s amount=%.1f dealt=%.2f pvp=%s why=%s t=%d", t.getName(), amount, dealt,
                plugin.pvp().enabled(), plugin.pvp().protectedWhy(t), plugin.ticker().now()));
    }

    /** 시험 적 (난이도 체력, 5.7): 머리줄 [T] FOEHP n= max= health= mult= (적마다 max/health 를 쉼표로). */
    private static void foeHp(Souls plugin, Player p, String what) {
        String tag = "souls_test_foe";
        List<org.bukkit.entity.LivingEntity> foes = new java.util.ArrayList<>();
        for (org.bukkit.entity.LivingEntity le : p.getWorld().getLivingEntities()) if (le.getScoreboardTags().contains(tag)) foes.add(le);
        switch (what) {
            case "spawn" -> {
                org.bukkit.Location at = p.getLocation().add(p.getLocation().getDirection().setY(0).normalize().multiply(2));
                foes.add(p.getWorld().spawn(at, org.bukkit.entity.Zombie.class, z -> {
                    z.setAI(false);
                    z.setSilent(true);
                    z.setPersistent(false);
                    z.setShouldBurnInDay(false);
                    z.addScoreboardTag(tag);
                    z.addScoreboardTag(TestHits.ENT_TAG);
                }));
            }
            case "hurt" -> foes.forEach(le -> le.setHealth(Math.max(1, le.getHealth() / 2)));
            case "clear" -> {
                foes.forEach(org.bukkit.entity.Entity::remove);
                foes.clear();
            }
            default -> {
            }
        }
        StringBuilder hp = new StringBuilder();
        for (org.bukkit.entity.LivingEntity le : foes) {
            if (hp.length() > 0) hp.append(',');
            hp.append(String.format(Locale.ROOT, "%.2f/%.2f", le.getHealth(), kr.souls.skill.Combat.maxHealth(le)));
        }
        plugin.test(p, String.format(Locale.ROOT, "FOEHP what=%s n=%d hp=%s mult=%.2f difficulty=%s", what, foes.size(),
                hp.length() == 0 ? "-" : hp, plugin.difficulty().enemyHealth(), plugin.difficulty().id()));
    }

    /** 그 사람에게 쏜 사람이 나인 투사체·구름 (PvP 막기의 길마다). */
    private static void pvpShoot(Souls plugin, Player p, String name, String kind) {
        Player t = other(plugin, p, name);
        if (t == null) return;
        org.bukkit.Location from = p.getEyeLocation();
        org.bukkit.Location aim = t.getLocation().add(0, 1.0, 0);
        org.bukkit.util.Vector dir = aim.toVector().subtract(from.toVector()).normalize();
        // 맞는 사람 1.3칸 앞에서 그를 겨눠 띄운다 (쏜 사람의 몸에 걸리거나 빗나가지 않게). 쏜 사람은 나다
        org.bukkit.Location at = aim.clone().subtract(dir.clone().multiply(1.3));
        at.setDirection(dir);
        switch (kind) {
            case "arrow" -> {
                org.bukkit.entity.Arrow ar = t.getWorld().spawnArrow(at, dir, 1.6f, 0f);
                ar.setShooter(p);
                // 화살이 어디로 갔나 (봇 시험의 진단 줄): 5틱 뒤
                org.bukkit.Bukkit.getScheduler().runTaskLater(plugin, () -> plugin.test(p, String.format(Locale.ROOT,
                        "PVPSHOOT_TRACE kind=arrow valid=%s ground=%s at=%.2f,%.2f,%.2f from=%.2f,%.2f,%.2f target=%.2f,%.2f,%.2f",
                        ar.isValid(), ar.isInBlock(), ar.getLocation().getX(), ar.getLocation().getY(), ar.getLocation().getZ(),
                        at.getX(), at.getY(), at.getZ(), aim.getX(), aim.getY(), aim.getZ())), 5);
            }
            case "snowball" -> t.getWorld().spawn(at, org.bukkit.entity.Snowball.class, sb -> {
                sb.setShooter(p);
                sb.setVelocity(dir.clone().multiply(1.2));
            });
            case "potion" -> {
                org.bukkit.entity.ThrownPotion tp = p.launchProjectile(org.bukkit.entity.ThrownPotion.class, dir.multiply(0.8));
                org.bukkit.inventory.ItemStack it = org.bukkit.inventory.ItemStack.of(org.bukkit.Material.SPLASH_POTION);
                it.editMeta(org.bukkit.inventory.meta.PotionMeta.class, m -> m.setBasePotionType(org.bukkit.potion.PotionType.POISON));
                tp.setItem(it);
            }
            // 해치는 잔류 구름 (즉시 피해): 맞는 이의 피해 원인은 나, 바로 친 것은 구름 (간접 피해 player_indirect, 검토 pvp-indirect-unscaled)
            case "harm" -> t.getWorld().spawn(t.getLocation(), org.bukkit.entity.AreaEffectCloud.class, c -> {
                c.setSource(p);
                c.setRadius(2.0f);
                c.setDuration(30);
                c.setWaitTime(0);
                c.setReapplicationDelay(40);
                c.addCustomEffect(new org.bukkit.potion.PotionEffect(org.bukkit.potion.PotionEffectType.INSTANT_DAMAGE, 1, 0), true);
            });
            case "cloud" -> t.getWorld().spawn(t.getLocation(), org.bukkit.entity.AreaEffectCloud.class, c -> {
                c.setSource(p);
                c.setRadius(2.0f);
                c.setDuration(60);
                c.setWaitTime(0);
                c.setReapplicationDelay(5);
                c.addCustomEffect(new org.bukkit.potion.PotionEffect(org.bukkit.potion.PotionEffectType.POISON, 100, 0), true);
            });
            default -> {
                plugin.test(p, "PVPSHOOT error=unknown kind=" + kind);
                return;
            }
        }
        plugin.test(p, "PVPSHOOT kind=" + kind + " to=" + t.getName() + " t=" + plugin.ticker().now());
    }

    private static void effect(Souls plugin, Player p, String type, int ticks) {
        org.bukkit.potion.PotionEffectType t = org.bukkit.Registry.EFFECT.get(org.bukkit.NamespacedKey.minecraft(type.toLowerCase(Locale.ROOT)));
        if (t == null) {
            plugin.test(p, "EFFECT error=unknown type=" + type);
            return;
        }
        p.removePotionEffect(t);
        p.addPotionEffect(new org.bukkit.potion.PotionEffect(t, ticks, 0));
        org.bukkit.potion.PotionEffect have = p.getPotionEffect(t);
        plugin.test(p, "EFFECT type=" + type + " asked=" + ticks + " have=" + (have == null ? 0 : have.getDuration()));
    }

    private static void burn(Souls plugin, Player p, int ticks) {
        org.bukkit.event.entity.EntityCombustEvent ev = new org.bukkit.event.entity.EntityCombustEvent(p, ticks / 20f);
        org.bukkit.Bukkit.getPluginManager().callEvent(ev);
        int fire = ev.isCancelled() ? 0 : Math.round(ev.getDuration() * 20);
        if (fire > 0) p.setFireTicks(fire);
        plugin.test(p, "BURN asked=" + ticks + " fire=" + fire);
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
