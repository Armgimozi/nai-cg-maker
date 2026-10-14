package kr.labyrinth.party;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.suggestion.SuggestionProvider;
import io.papermc.paper.command.brigadier.CommandSourceStack;
import io.papermc.paper.command.brigadier.Commands;
import io.papermc.paper.event.player.AsyncChatEvent;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiConsumer;
import kr.labyrinth.Services;
import kr.labyrinth.command.CommandService;
import kr.labyrinth.core.Text;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.Sound;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerQuitEvent;

/**
 * 파티: 생성·초대(시간 제한)·수락·거절·탈퇴·추방·위임·해산·파티 채팅(토글 또는 한 줄), 최대 인원 config party.max_size.
 * 메모리에만 저장(재시작 시 초기화). 파티장이 접속을 끊으면 접속 중인 다음 파티원에게 자동 위임.
 * 명령: /파티 (party) 생성·초대·수락·거절·탈퇴·추방·위임·해산·채팅·정보 (영문 create·invite·accept·decline·leave·kick·promote·disband·chat·info).
 */
public final class PartyManager implements PartyService, Listener {

    private record Invite(String partyId, UUID from, long expires) {}

    private final Services services;
    private final Map<String, PartyImpl> parties = new ConcurrentHashMap<>();
    private final Map<UUID, PartyImpl> byMember = new ConcurrentHashMap<>();
    /** 초대받은 사람 → (파티 id → 초대). */
    private final Map<UUID, Map<String, Invite>> invites = new ConcurrentHashMap<>();
    private final Set<UUID> chatToggle = ConcurrentHashMap.newKeySet();
    private int seq;

    public PartyManager(Services services) { this.services = services; }

    public void enable() {
        Bukkit.getPluginManager().registerEvents(this, services.plugin());
        registerCommands();
    }

    public void disable() {
        HandlerList.unregisterAll(this);
    }

    // ── PartyService ──────────────────────────────────────────────────────

    @Override
    public Optional<Party> partyOf(Player player) { return Optional.ofNullable(byMember.get(player.getUniqueId())); }

    @Override
    public List<Player> onlineMembers(Player player) {
        PartyImpl p = byMember.get(player.getUniqueId());
        if (p == null) return List.of(player);
        List<Player> out = new ArrayList<>();
        for (UUID u : p.members()) {
            Player m = Bukkit.getPlayer(u);
            if (m != null && m.isOnline()) out.add(m);
        }
        if (!out.contains(player)) out.add(player);
        return out;
    }

    @Override
    public Player leader(Player player) {
        PartyImpl p = byMember.get(player.getUniqueId());
        if (p == null) return player;
        Player l = Bukkit.getPlayer(p.leader());
        return l != null ? l : player;
    }

    // ── 동작 ──────────────────────────────────────────────────────────────

    private int maxSize() { return services.settings().party().maxSize(); }

    private static String name(UUID u) {
        Player p = Bukkit.getPlayer(u);
        if (p != null) return p.getName();
        OfflinePlayer op = Bukkit.getOfflinePlayer(u);
        return op.getName() == null ? u.toString().substring(0, 8) : op.getName();
    }

    private void tell(PartyImpl party, String mm) {
        for (UUID u : party.members()) {
            Player p = Bukkit.getPlayer(u);
            if (p != null) p.sendMessage(Text.mm("<gradient:#7fd8ff:#9cffb0><b>파티</b></gradient> <dark_gray>»</dark_gray> " + mm));
        }
    }

    public void create(Player p) {
        if (byMember.containsKey(p.getUniqueId())) {
            Text.error(p, "이미 파티에 속해 있습니다. <white>/파티 정보</white>");
            return;
        }
        PartyImpl party = new PartyImpl("p" + (++seq), p.getUniqueId());
        parties.put(party.id(), party);
        byMember.put(p.getUniqueId(), party);
        Text.send(p, "<green>파티를 만들었습니다.</green> <gray><white>/파티 초대 <이름></white> 으로 동료를 부르세요. (최대 " + maxSize() + "명)");
    }

    public void invite(Player from, String targetName) {
        Player target = Bukkit.getPlayerExact(targetName);
        if (target == null) {
            Text.error(from, "접속 중인 플레이어가 아닙니다: " + Text.escape(targetName));
            return;
        }
        if (target.equals(from)) {
            Text.error(from, "자기 자신은 초대할 수 없습니다.");
            return;
        }
        PartyImpl party = byMember.get(from.getUniqueId());
        if (party == null) {
            create(from);
            party = byMember.get(from.getUniqueId());
        }
        if (!party.isLeader(from.getUniqueId())) {
            Text.error(from, "파티장만 초대할 수 있습니다.");
            return;
        }
        if (party.contains(target.getUniqueId())) {
            Text.error(from, Text.escape(target.getName()) + " 님은 이미 파티원입니다.");
            return;
        }
        if (byMember.containsKey(target.getUniqueId())) {
            Text.error(from, Text.escape(target.getName()) + " 님은 다른 파티에 속해 있습니다.");
            return;
        }
        if (party.size() >= maxSize()) {
            Text.error(from, "파티가 가득 찼습니다 (최대 " + maxSize() + "명).");
            return;
        }
        int timeout = Math.max(10, services.settings().partyInviteTimeout());
        invites.computeIfAbsent(target.getUniqueId(), k -> new ConcurrentHashMap<>())
                .put(party.id(), new Invite(party.id(), from.getUniqueId(), System.currentTimeMillis() + timeout * 1000L));
        Text.send(from, "<gray><white>" + Text.escape(target.getName()) + "</white> 님을 초대했습니다. (" + timeout + "초)");
        String fromName = Text.escape(from.getName());
        target.sendMessage(Text.mm(Text.PREFIX + "<white>" + fromName + "</white><gray> 님이 파티에 초대했습니다. "
                + "<click:run_command:'/party accept " + fromName + "'><hover:show_text:'<green>파티에 들어갑니다'><green><b>[수락]</b></green></hover></click> "
                + "<click:run_command:'/party decline " + fromName + "'><hover:show_text:'<red>초대를 거절합니다'><red>[거절]</red></hover></click>"));
        target.playSound(target.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 0.7f, 1.4f);
    }

    /** fromName null = 가장 최근 초대. */
    public void accept(Player p, String fromName) {
        Invite inv = findInvite(p, fromName);
        if (inv == null) {
            Text.error(p, "받은 파티 초대가 없거나 만료되었습니다.");
            return;
        }
        invites.getOrDefault(p.getUniqueId(), Map.of()).remove(inv.partyId());
        PartyImpl party = parties.get(inv.partyId());
        if (party == null) {
            Text.error(p, "그 파티는 이미 해산되었습니다.");
            return;
        }
        if (byMember.containsKey(p.getUniqueId())) {
            Text.error(p, "이미 파티에 속해 있습니다. 먼저 <white>/파티 탈퇴</white> 하세요.");
            return;
        }
        if (party.size() >= maxSize()) {
            Text.error(p, "파티가 가득 찼습니다.");
            return;
        }
        party.add(p.getUniqueId());
        byMember.put(p.getUniqueId(), party);
        tell(party, "<white>" + Text.escape(p.getName()) + "</white><green> 님이 파티에 들어왔습니다.</green> <gray>(" + party.size() + "/" + maxSize() + ")");
        for (Player m : onlineMembers(p)) m.playSound(m.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.5f, 1.6f);
    }

    public void decline(Player p, String fromName) {
        Invite inv = findInvite(p, fromName);
        if (inv == null) {
            Text.error(p, "받은 파티 초대가 없습니다.");
            return;
        }
        invites.getOrDefault(p.getUniqueId(), Map.of()).remove(inv.partyId());
        Text.send(p, "<gray>초대를 거절했습니다.");
        Player from = Bukkit.getPlayer(inv.from());
        if (from != null) Text.send(from, "<gray>" + Text.escape(p.getName()) + " 님이 초대를 거절했습니다.");
    }

    private Invite findInvite(Player p, String fromName) {
        Map<String, Invite> map = invites.get(p.getUniqueId());
        if (map == null || map.isEmpty()) return null;
        long now = System.currentTimeMillis();
        map.values().removeIf(i -> i.expires() < now || !parties.containsKey(i.partyId()));
        Invite best = null;
        for (Invite i : map.values()) {
            if (fromName != null && !name(i.from()).equalsIgnoreCase(fromName)) {
                PartyImpl party = parties.get(i.partyId());
                if (party == null || !name(party.leader()).equalsIgnoreCase(fromName)) continue;
            }
            if (best == null || i.expires() > best.expires()) best = i;
        }
        return best;
    }

    public void leave(Player p) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null) {
            Text.error(p, "파티에 속해 있지 않습니다.");
            return;
        }
        removeMember(party, p.getUniqueId(), "<gray>" + Text.escape(p.getName()) + " 님이 파티를 떠났습니다.");
        Text.send(p, "<gray>파티를 떠났습니다.");
    }

    private void removeMember(PartyImpl party, UUID u, String message) {
        party.remove(u);
        byMember.remove(u);
        chatToggle.remove(u);
        if (party.members().isEmpty()) {
            parties.remove(party.id());
            return;
        }
        tell(party, message);
        if (party.leader().equals(u)) {
            UUID next = nextLeader(party);
            party.leader(next);
            tell(party, "<yellow>" + Text.escape(name(next)) + "</yellow><gray> 님이 새 파티장이 되었습니다.");
        }
        if (party.members().size() == 1) {
            tell(party, "<gray>파티원이 혼자 남았습니다. (/파티 초대 로 다시 모으거나 /파티 해산)");
        }
    }

    private UUID nextLeader(PartyImpl party) {
        for (UUID m : party.members()) if (Bukkit.getPlayer(m) != null) return m;
        return party.members().get(0);
    }

    public void kick(Player p, String targetName) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null || !party.isLeader(p.getUniqueId())) {
            Text.error(p, "파티장만 추방할 수 있습니다.");
            return;
        }
        UUID target = null;
        for (UUID m : party.members()) if (name(m).equalsIgnoreCase(targetName)) target = m;
        if (target == null || target.equals(p.getUniqueId())) {
            Text.error(p, "그런 파티원이 없습니다: " + Text.escape(targetName));
            return;
        }
        removeMember(party, target, "<gray>" + Text.escape(name(target)) + " 님이 파티에서 추방되었습니다.");
        Player t = Bukkit.getPlayer(target);
        if (t != null) Text.send(t, "<red>파티에서 추방되었습니다.");
    }

    public void promote(Player p, String targetName) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null || !party.isLeader(p.getUniqueId())) {
            Text.error(p, "파티장만 위임할 수 있습니다.");
            return;
        }
        UUID target = null;
        for (UUID m : party.members()) if (name(m).equalsIgnoreCase(targetName)) target = m;
        if (target == null || target.equals(p.getUniqueId())) {
            Text.error(p, "그런 파티원이 없습니다: " + Text.escape(targetName));
            return;
        }
        party.leader(target);
        tell(party, "<yellow>" + Text.escape(name(target)) + "</yellow><gray> 님이 새 파티장이 되었습니다.");
    }

    public void disband(Player p) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null || !party.isLeader(p.getUniqueId())) {
            Text.error(p, "파티장만 해산할 수 있습니다.");
            return;
        }
        tell(party, "<red>파티가 해산되었습니다.");
        for (UUID u : party.members()) {
            byMember.remove(u);
            chatToggle.remove(u);
        }
        parties.remove(party.id());
    }

    public void toggleChat(Player p) {
        if (!byMember.containsKey(p.getUniqueId())) {
            Text.error(p, "파티에 속해 있지 않습니다.");
            return;
        }
        if (chatToggle.remove(p.getUniqueId())) Text.send(p, "<gray>파티 채팅 <red>끔</red> — 일반 채팅으로 말합니다.");
        else {
            chatToggle.add(p.getUniqueId());
            Text.send(p, "<gray>파티 채팅 <green>켬</green> — 채팅이 파티원에게만 보입니다. (다시 /파티 채팅 으로 끔)");
        }
    }

    public void partyChat(Player p, String message) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null) {
            Text.error(p, "파티에 속해 있지 않습니다.");
            return;
        }
        sendPartyChat(party, p, Component.text(message));
    }

    private void sendPartyChat(PartyImpl party, Player from, Component message) {
        Component line = Text.mm("<gradient:#7fd8ff:#9cffb0>[파티]</gradient> " + (party.isLeader(from.getUniqueId()) ? "<yellow>★</yellow>" : "")
                + "<white>" + Text.escape(from.getName()) + "</white><dark_gray>:</dark_gray> ").append(message.colorIfAbsent(net.kyori.adventure.text.format.NamedTextColor.AQUA));
        for (UUID u : party.members()) {
            Player m = Bukkit.getPlayer(u);
            if (m != null) m.sendMessage(line);
        }
        Bukkit.getConsoleSender().sendMessage(line);
    }

    public void info(Player p) {
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null) {
            Text.send(p, "<gray>파티에 속해 있지 않습니다. <white>/파티 생성</white> 또는 <white>/파티 초대 <이름></white>");
            Map<String, Invite> map = invites.get(p.getUniqueId());
            if (map != null && !map.isEmpty()) Text.send(p, "<gray>받은 초대 " + map.size() + "개 — <white>/파티 수락</white>");
            return;
        }
        Text.send(p, "<gradient:#7fd8ff:#9cffb0><b>파티</b></gradient> <gray>(" + party.size() + "/" + maxSize() + ") · 난이도 배율: 몹 HP ×"
                + String.format("%.2f", services.settings().party().hp(party.size())) + ", 피해 ×"
                + String.format("%.2f", services.settings().party().damage(party.size())));
        for (UUID u : party.members()) {
            Player m = Bukkit.getPlayer(u);
            String status;
            if (m == null) status = "<dark_gray>오프라인";
            else {
                var d = services.data().get(m);
                var cls = services.classes().classOf(m);
                status = "<gray>Lv." + d.level() + " " + (cls == null ? "무직" : Text.strip(cls.name())) + " · 해금 " + d.unlockedFloor() + "층"
                        + (services.dungeon().isInLabyrinth(m) ? " · <light_purple>미궁 안" : "");
            }
            p.sendMessage(Text.mm(" " + (party.isLeader(u) ? "<yellow>★ " : "<gray>· ") + "<white>" + Text.escape(name(u)) + "</white> " + status));
        }
    }

    // ── 이벤트 ────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.LOW, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        Player p = e.getPlayer();
        if (!chatToggle.contains(p.getUniqueId())) return;
        PartyImpl party = byMember.get(p.getUniqueId());
        if (party == null) {
            chatToggle.remove(p.getUniqueId());
            return;
        }
        e.setCancelled(true);
        sendPartyChat(party, p, e.message());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        invites.remove(u);
        PartyImpl party = byMember.get(u);
        if (party == null || !party.isLeader(u)) return;
        Bukkit.getScheduler().runTask(services.plugin(), () -> {
            if (!party.isLeader(u) || Bukkit.getPlayer(u) != null) return;
            for (UUID m : party.members()) {
                if (!m.equals(u) && Bukkit.getPlayer(m) != null) {
                    party.leader(m);
                    tell(party, "<gray>파티장이 접속을 끊어 <yellow>" + Text.escape(name(m)) + "</yellow> 님이 파티장이 되었습니다.");
                    return;
                }
            }
        });
    }

    // ── 명령 ──────────────────────────────────────────────────────────────

    private static int run(CommandContext<CommandSourceStack> ctx, Runnable r) {
        CommandService.safeRun(ctx, r);
        return Command.SINGLE_SUCCESS;
    }

    private SuggestionProvider<CommandSourceStack> onlinePlayers() {
        return (c, b) -> {
            String rem = b.getRemainingLowerCase();
            for (Player p : Bukkit.getOnlinePlayers()) if (p.getName().toLowerCase(Locale.ROOT).startsWith(rem)) b.suggest(p.getName());
            return b.buildFuture();
        };
    }

    private SuggestionProvider<CommandSourceStack> partyMembers() {
        return (c, b) -> {
            if (CommandService.sender(c) instanceof Player p) {
                PartyImpl party = byMember.get(p.getUniqueId());
                if (party != null) for (UUID u : party.members()) if (!u.equals(p.getUniqueId())) b.suggest(name(u));
            }
            return b.buildFuture();
        };
    }

    private void simple(String en, String ko, java.util.function.Consumer<Player> action) {
        for (String n : new String[] {en, ko}) {
            services.commands().addSubcommand("party", Commands.literal(n).executes(ctx -> run(ctx,
                    () -> CommandService.withPlayer(CommandService.sender(ctx), action))));
        }
    }

    private void withName(String en, String ko, SuggestionProvider<CommandSourceStack> sugg, boolean optional, BiConsumer<Player, String> action) {
        for (String n : new String[] {en, ko}) {
            LiteralArgumentBuilder<CommandSourceStack> lit = Commands.literal(n);
            if (optional) lit.executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), p -> action.accept(p, null))));
            lit.then(Commands.argument("player", StringArgumentType.word()).suggests(sugg)
                    .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                            p -> action.accept(p, StringArgumentType.getString(ctx, "player"))))));
            services.commands().addSubcommand("party", lit);
        }
    }

    private void registerCommands() {
        simple("create", "생성", this::create);
        withName("invite", "초대", onlinePlayers(), false, this::invite);
        withName("accept", "수락", onlinePlayers(), true, this::accept);
        withName("decline", "거절", onlinePlayers(), true, this::decline);
        simple("leave", "탈퇴", this::leave);
        withName("kick", "추방", partyMembers(), false, this::kick);
        withName("promote", "위임", partyMembers(), false, this::promote);
        simple("disband", "해산", this::disband);
        simple("info", "정보", this::info);
        simple("list", "목록", this::info);
        for (String n : new String[] {"chat", "채팅"}) {
            services.commands().addSubcommand("party", Commands.literal(n)
                    .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx), this::toggleChat)))
                    .then(Commands.argument("message", StringArgumentType.greedyString())
                            .executes(ctx -> run(ctx, () -> CommandService.withPlayer(CommandService.sender(ctx),
                                    p -> partyChat(p, StringArgumentType.getString(ctx, "message")))))));
        }
    }
}
