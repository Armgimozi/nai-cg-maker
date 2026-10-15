package kr.labyrinth.classes;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import io.papermc.paper.command.brigadier.Commands;
import kr.labyrinth.Services;
import kr.labyrinth.classes.skills.SkillFx;
import kr.labyrinth.classes.skills.SkillTask;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.core.Log;
import kr.labyrinth.core.Module;
import kr.labyrinth.core.Text;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

/**
 * classes 담당 모듈 진입점. 이 파일과 이 패키지는 classes 담당 소유 — 다른 작업자는 수정하지 않는다.
 * <p>
 * 등록: {@link LabyrinthClassService}(직업·마나·쿨다운·스킬 입력), {@link LabyrinthStatusEffectService}(상태이상·버프·보호막),
 * {@link ClassPassives}(직업 패시브·맹세 분담), {@link SkillInputListener}(F/Q 키). 명령: /직업 선택|정보|스킬,
 * 관리자 /labadmin setclass &lt;플레이어&gt; &lt;직업|none&gt; (직업 변경 제한 {@link ClassChangeGate} 를 거치지 않음).
 */
public final class ClassesModule implements Module, Listener {

    private final Services services;
    private LabyrinthClassService classService;
    private LabyrinthStatusEffectService effectService;
    private ClassPassives passives;
    private SkillInputListener input;

    public ClassesModule(Services services) { this.services = services; }

    @Override
    public String name() { return "classes"; }

    @Override
    public void enable() {
        effectService = new LabyrinthStatusEffectService(services);
        services.setEffects(effectService);
        effectService.start();

        classService = new LabyrinthClassService(services);
        services.setClasses(classService);
        classService.start();

        passives = new ClassPassives(services);
        passives.start();

        input = new SkillInputListener(services, classService);
        Bukkit.getPluginManager().registerEvents(input, services.plugin());
        Bukkit.getPluginManager().registerEvents(this, services.plugin());

        registerCommands();
        validateSkills();
    }

    @Override
    public void disable() {
        SkillTask.cancelAll();
        SkillFx.removeAll();
        if (input != null) HandlerList.unregisterAll(input);
        HandlerList.unregisterAll(this);
        if (passives != null) passives.stop();
        if (classService != null) classService.stop();
        if (effectService != null) effectService.stop();
    }

    @Override
    public void reload() { validateSkills(); }

    /** classes.yml 의 모든 스킬에 구현이 있는지 확인 (없으면 경고). */
    private void validateSkills() {
        int missing = 0;
        for (ClassDef c : services.content().classes().values()) {
            for (ClassDef.SkillDef s : c.skills()) {
                if (classService.registry().get(s.id()) == null) {
                    Log.warn("[직업] '" + c.id() + "' 의 스킬 '" + s.id() + "' 구현이 없습니다 (classes/skills/*)");
                    missing++;
                }
            }
        }
        if (missing == 0) Log.info("[직업] 직업 " + services.content().classes().size() + "종 · 스킬 구현 " + classService.registry().all().size() + "개 준비");
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(services.plugin(), () -> {
            if (p.isOnline()) classService.ensureStarterWeapon(p);
        }, 40L);
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent e) {
        classService.forget(e.getPlayer());
        passives.forget(e.getPlayer());
    }

    // ── 명령: /직업 선택 <직업> · /직업 정보 · /직업 스킬 ─────────────────

    private void registerCommands() {
        var choose = Commands.argument("직업", StringArgumentType.word())
                .suggests((ctx, b) -> {
                    String rem = b.getRemainingLowerCase();
                    for (ClassDef c : services.content().classes().values()) {
                        if (c.id().startsWith(rem) || c.name().startsWith(b.getRemaining())) b.suggest(c.id());
                    }
                    return b.buildFuture();
                })
                .executes(ctx -> {
                    CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), p -> {
                        String arg = StringArgumentType.getString(ctx, "직업");
                        ClassDef def = byIdOrName(arg);
                        if (def == null) {
                            Text.error(p, "알 수 없는 직업: " + Text.escape(arg) + " <gray>(" + classList() + ")");
                            return;
                        }
                        services.classes().changeClass(p, def.id());
                    }));
                    return Command.SINGLE_SUCCESS;
                });
        services.commands().addSubcommand("class", Commands.literal("choose").then(choose));
        services.commands().addSubcommand("class", Commands.literal("선택").then(choose));

        var info = Commands.literal("info").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), this::sendInfo));
            return Command.SINGLE_SUCCESS;
        });
        services.commands().addSubcommand("class", info);
        services.commands().addSubcommand("class", Commands.literal("정보").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), this::sendInfo));
            return Command.SINGLE_SUCCESS;
        }));
        services.commands().addSubcommand("class", Commands.literal("skills").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), classService::showSkillBar));
            return Command.SINGLE_SUCCESS;
        }));
        services.commands().addSubcommand("class", Commands.literal("스킬").executes(ctx -> {
            CommandService.safeRun(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), classService::showSkillBar));
            return Command.SINGLE_SUCCESS;
        }));

        // 관리자: /labadmin setclass <플레이어> <직업|none> — 두루마리·대기 시간·미궁 공략 중 제한 없이 (변경 시각 기록도 그대로)
        var target = Commands.argument("player", StringArgumentType.word())
                .suggests((ctx, b) -> {
                    String rem = b.getRemainingLowerCase();
                    for (Player o : Bukkit.getOnlinePlayers()) if (o.getName().toLowerCase(java.util.Locale.ROOT).startsWith(rem)) b.suggest(o.getName());
                    return b.buildFuture();
                })
                .then(Commands.argument("class", StringArgumentType.word())
                        .suggests((ctx, b) -> {
                            String rem = b.getRemainingLowerCase();
                            for (ClassDef c : services.content().classes().values()) if (c.id().startsWith(rem)) b.suggest(c.id());
                            if ("none".startsWith(rem)) b.suggest("none");
                            return b.buildFuture();
                        })
                        .executes(ctx -> {
                            CommandService.safeRun(ctx, () -> adminSetClass(ctx.getSource().getSender(),
                                    StringArgumentType.getString(ctx, "player"), StringArgumentType.getString(ctx, "class")));
                            return Command.SINGLE_SUCCESS;
                        }));
        services.commands().addSubcommand("labadmin", Commands.literal("setclass").then(target));
    }

    private void adminSetClass(org.bukkit.command.CommandSender s, String playerName, String arg) {
        Player t = Bukkit.getPlayerExact(playerName);
        if (t == null) {
            Text.error(s, "접속 중인 플레이어가 아닙니다.");
            return;
        }
        boolean none = arg.equalsIgnoreCase("none") || arg.equals("없음");
        ClassDef def = none ? null : byIdOrName(arg);
        if (!none && def == null) {
            Text.error(s, "알 수 없는 직업: " + Text.escape(arg) + " <gray>(" + classList() + ", none)");
            return;
        }
        ClassDef before = services.classes().classOf(t);
        if (!classService.adminSetClass(t, def == null ? null : def.id())) {
            Text.error(s, "<white>" + Text.escape(t.getName()) + "</white> 님은 이미 " + (def == null ? "직업이 없습니다." : def.name() + " 입니다."));
            return;
        }
        Text.send(s, "<white>" + Text.escape(t.getName()) + "</white> <gray>직업: " + (before == null ? "없음" : before.name()) + " → <white>"
                + (def == null ? "없음" : def.name()) + "</white> <dark_gray>(관리자 — 두루마리·대기 시간 제한 없음)");
    }

    private ClassDef byIdOrName(String arg) {
        ClassDef d = services.content().classDef(arg.toLowerCase(java.util.Locale.ROOT));
        if (d != null) return d;
        for (ClassDef c : services.content().classes().values()) if (Text.strip(c.name()).equals(arg)) return c;
        return null;
    }

    private String classList() {
        return String.join(", ", services.content().classes().values().stream().map(c -> c.id() + "=" + Text.strip(c.name())).toList());
    }

    private void sendInfo(Player p) {
        ClassDef c = services.classes().classOf(p);
        if (c == null) {
            Text.send(p, "<gray>직업이 없습니다. <white>/직업 선택 <직업></white> <gray>(" + classList() + ")");
            return;
        }
        String col = c.color();
        int level = services.data().get(p).level();
        p.sendMessage(Text.mm("<" + col + "><b>━━━━ " + c.name() + " ━━━━</b></" + col + ">  <gray>MP <#6fc3ff>"
                + Text.num(services.classes().mana(p)) + "</#6fc3ff>/" + Text.num(services.classes().maxMana(p))));
        p.sendMessage(Text.mm(c.description()));
        p.sendMessage(Text.mm("<gray>주로 쓰는 능력치 " + LabyrinthClassService.mainStatsText(c)));
        if (c.passive() != null) {
            p.sendMessage(Text.mm("<gold>패시브</gold> <" + col + ">" + c.passive().name() + "</" + col + "> <gray>— "
                    + Text.escape(c.passive().description())));
        }
        for (ClassDef.SkillDef s : c.skills()) {
            boolean locked = level < s.unlockLevel();
            double cd = services.classes().cooldownRemaining(p, s.id());
            p.sendMessage(Text.mm((locked ? "<dark_gray>" : "<white>") + LabyrinthClassService.keyLabel(s.input()) + " "
                    + (locked ? s.name() + " 🔒Lv." + s.unlockLevel() + "</dark_gray>"
                    : "<" + col + ">" + s.name() + "</" + col + "></white> <gray>MP " + Text.num(s.mana()) + " · "
                    + LabyrinthClassService.fmt(s.cooldown()) + "초" + (cd > 0 ? " <red>(" + LabyrinthClassService.fmt(cd) + "초 남음)" : ""))));
            p.sendMessage(Text.mm("   <gray>").append(Text.mm("<gray>" + s.description())));
        }
        p.sendMessage(Text.mm("<dark_gray>무엇을 들었든 " + kr.labyrinth.core.InputKeys.CLASS_KEYS
                + " · 버리기·손 바꾸기는 인벤토리 창에서"));
        p.sendMessage(Text.mm("<gray>직업 변경: " + changeStatus(p, c)));
    }

    /** "/직업 정보" 의 직업 변경 한 줄 — 남은 대기 시간 · 필요한 두루마리 (관문 {@link ClassChangeGate} 와 같은 판정). */
    private String changeStatus(Player p, ClassDef c) {
        ClassChangeGate g = classService.gate();
        ClassChangeRule.Verdict v = g.check(p, c.id(), null);
        String when = v.block() == ClassChangeRule.Block.IN_RUN ? "<#ff8a8a>미궁 공략 중에는 불가</#ff8a8a>"
                : v.cooldownLeftMs() > 0 ? "<#ff8a8a>다음 변경까지 " + ClassChangeRule.duration(v.cooldownLeftMs()) + "</#ff8a8a>"
                : "<#7fe07f>지금 바꿀 수 있음</#7fe07f>";
        if (!v.needsItem()) return when;
        return when + " <dark_gray>·</dark_gray> 바꿀 때 <white>" + g.itemName() + "</white> 1장 <dark_gray>(가진 수 " + g.scrolls(p)
                + (g.shopHint().isEmpty() ? "" : " · " + g.shopHint()) + ")";
    }
}
