package kr.augsky.cmd;

import kr.augsky.AugSky;
import kr.augsky.augment.AugmentDef;
import kr.augsky.augment.PlayerData;
import kr.augsky.augment.Tier;
import kr.augsky.map.MapBuilder;
import kr.augsky.util.Items;
import kr.augsky.util.Text;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/** /증강, /스폰, /무기도감, /증강관리 */
public final class Commands implements TabExecutor {
    private final AugSky plugin;
    private final Map<UUID, Long> spawnCd = new HashMap<>();

    public Commands(AugSky plugin) {
        this.plugin = plugin;
    }

    private static void msg(CommandSender s, String mm) {
        s.sendMessage(Text.mm(mm));
    }

    @Override
    public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        switch (cmd.getName()) {
            case "augment" -> augment(s, a);
            case "augspawn" -> spawn(s);
            case "weapons" -> {
                if (s instanceof Player p) plugin.menus().openWeapons(p, 0);
            }
            case "augadmin" -> admin(s, a);
            default -> {
                return false;
            }
        }
        return true;
    }

    // ------------------------------------------------------------------ /증강

    private void augment(CommandSender s, String[] a) {
        if (!(s instanceof Player p)) {
            msg(s, "게임 안에서 쓰는 명령어입니다.");
            return;
        }
        String sub = a.length == 0 ? "" : a[0];
        switch (sub) {
            case "", "목록", "list" -> plugin.menus().openMine(p);
            case "도감", "codex" -> plugin.menus().openCodex(p, a.length > 1 && Tier.parse(a[1]) != null ? Tier.parse(a[1]) : Tier.SILVER);
            case "선택", "choose" -> plugin.menus().openChoice(p);
            case "제단", "위치", "where" -> places(p);
            case "책", "book" -> Items.give(p, plugin.items().guideBook());
            default -> help(p);
        }
    }

    private void help(Player p) {
        msg(p, "<#ffcc55>━━━━ 증강 스카이블럭 ━━━━");
        msg(p, "<white>/증강 <gray>내 증강 보기");
        msg(p, "<white>/증강 도감 <gray>모든 증강 보기");
        msg(p, "<white>/증강 선택 <gray>고르다 만 증강 선택지 다시 열기");
        msg(p, "<white>/증강 제단 <gray>제단과 균열 위치");
        msg(p, "<white>/증강 책 <gray>안내서 다시 받기");
        msg(p, "<white>/무기도감 <gray>모든 무기 보기");
        msg(p, "<white>/스폰 <gray>시작의 섬으로 이동");
    }

    private void places(Player p) {
        msg(p, "<#ffcc55>━━━━ 주요 장소 ━━━━");
        Location l = p.getLocation();
        for (MapBuilder.Place pl : MapBuilder.PLACES) {
            int dx = pl.x() - l.getBlockX(), dz = pl.z() - l.getBlockZ();
            int dist = (int) Math.round(Math.hypot(dx, dz));
            msg(p, "<white>" + pl.name() + " <dark_gray>(" + pl.x() + ", " + pl.y() + ", " + pl.z() + ") <gray>"
                    + MapBuilder.dir(dx, dz) + " " + dist + "m");
        }
    }

    private void spawn(CommandSender s) {
        if (!(s instanceof Player p)) return;
        long now = System.currentTimeMillis();
        Long last = spawnCd.get(p.getUniqueId());
        if (last != null && now - last < 10_000 && !p.hasPermission("augsky.admin")) {
            msg(p, "<gray>잠시 뒤에 다시 쓰세요.");
            return;
        }
        spawnCd.put(p.getUniqueId(), now);
        p.teleport(plugin.spawnLocation());
        p.setFallDistance(0);
        msg(p, "<gray>시작의 섬으로 이동했습니다.");
    }

    // ------------------------------------------------------------------ /증강관리

    private void admin(CommandSender s, String[] a) {
        if (!s.hasPermission("augsky.admin")) {
            msg(s, "<#ff7070>권한이 없습니다.");
            return;
        }
        if (a.length == 0) {
            adminHelp(s);
            return;
        }
        String sub = a[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "무기", "weapon" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 무기 <id> [플레이어]");
                    return;
                }
                Player t = target(s, a, 2);
                ItemStack it = plugin.weapons().create(a[1]);
                if (t == null || it == null) {
                    msg(s, "<#ff7070>무기나 플레이어를 찾을 수 없습니다.");
                    return;
                }
                Items.give(t, it);
                msg(s, "<gray>" + t.getName() + "에게 무기 " + a[1] + " 지급");
            }
            case "아이템", "item" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 아이템 <id> [개수] [플레이어]");
                    return;
                }
                int n = a.length > 2 ? parseInt(a[2], 1) : 1;
                Player t = target(s, a, 3);
                ItemStack it = plugin.items().spec(a[1], n);
                if (t == null || it == null) {
                    msg(s, "<#ff7070>아이템이나 플레이어를 찾을 수 없습니다.");
                    return;
                }
                if (plugin.items().def(a[1]) != null) it.setAmount(Math.min(n, it.getMaxStackSize()));
                int left = n;
                while (left > 0) {
                    ItemStack one = it.clone();
                    one.setAmount(Math.min(left, it.getMaxStackSize()));
                    left -= one.getAmount();
                    Items.give(t, one);
                }
                msg(s, "<gray>" + t.getName() + "에게 " + a[1] + " ×" + n + " 지급");
            }
            case "증강", "augment" -> adminAugment(s, a);
            case "선택지", "offer" -> {
                if (a.length < 3) {
                    msg(s, "/증강관리 선택지 <플레이어> <실버|골드|프리즘>");
                    return;
                }
                Player t = Bukkit.getPlayerExact(a[1]);
                Tier tier = Tier.parse(a[2]);
                if (t == null || tier == null) {
                    msg(s, "<#ff7070>플레이어나 등급을 찾을 수 없습니다.");
                    return;
                }
                if (plugin.augments().startOffer(t, tier)) plugin.menus().openChoice(t);
                else msg(s, "<gray>더 줄 수 있는 증강이 없습니다.");
            }
            case "소환", "spawn" -> {
                if (a.length < 2) {
                    msg(s, "/증강관리 소환 <몬스터id> [플레이어 | x y z]");
                    return;
                }
                Location at = null;
                if (a.length >= 5) {
                    World w = s instanceof Player p ? p.getWorld() : Bukkit.getWorlds().get(0);
                    at = new Location(w, parseD(a[2]), parseD(a[3]), parseD(a[4]));
                } else {
                    Player t = target(s, a, 2);
                    if (t != null) at = t.getLocation().add(t.getLocation().getDirection().setY(0).normalize().multiply(4));
                }
                if (at == null) {
                    msg(s, "<#ff7070>위치를 알 수 없습니다.");
                    return;
                }
                LivingEntity le = plugin.mobs().spawn(a[1], at, false);
                msg(s, le == null ? "<#ff7070>몬스터 id 를 확인하세요." : "<gray>" + a[1] + " 소환");
            }
            case "맵생성", "buildmap" -> {
                World w = a.length > 1 ? Bukkit.getWorld(a[1]) : (s instanceof Player p ? p.getWorld() : Bukkit.getWorlds().get(0));
                if (w == null) {
                    msg(s, "<#ff7070>월드를 찾을 수 없습니다.");
                    return;
                }
                msg(s, "<gray>맵을 짓는 중... (" + w.getName() + ")");
                plugin.mapBuilder().buildAll(w);
                msg(s, "<#7cff8c>맵 생성 완료.");
            }
            case "제단", "altar" -> {
                if (!(s instanceof Player p) || a.length < 2 || Tier.parse(a[1]) == null) {
                    msg(s, "/증강관리 제단 <실버|골드|프리즘>  (서 있는 자리에 제단을 세웁니다)");
                    return;
                }
                Location l = p.getLocation();
                plugin.mapBuilder().altarStructure(p.getWorld(), l.getBlockX(), l.getBlockY() - 1, l.getBlockZ(), Tier.parse(a[1]));
                p.teleport(l.clone().add(0, 3, 5));
                msg(s, "<gray>제단을 세웠습니다.");
            }
            case "균열", "rift" -> {
                if (!(s instanceof Player p) || a.length < 2 || !plugin.mobs().registry().rifts().containsKey(a[1])) {
                    msg(s, "/증강관리 균열 <" + String.join("|", plugin.mobs().registry().rifts().keySet()) + ">");
                    return;
                }
                plugin.mapBuilder().riftMarker(p.getWorld(), p.getLocation().getBlock().getLocation().add(0.5, 0, 0.5), a[1]);
                msg(s, "<gray>균열 표식을 세웠습니다. 동쪽 3칸에 보스 소환대가 있습니다.");
            }
            case "리로드", "reload" -> {
                plugin.reloadContent();
                msg(s, "<#7cff8c>설정과 증강/무기/스킬/몬스터를 다시 불러왔습니다.");
            }
            case "리소스팩", "pack" -> {
                for (Player p : Bukkit.getOnlinePlayers()) plugin.pack().send(p);
                msg(s, "<gray>리소스팩을 다시 보냈습니다.");
            }
            case "정보", "info" -> {
                msg(s, "<gray>증강 " + plugin.augments().registry().all().size() + "개, 무기 " + plugin.weapons().all().size()
                        + "종, 스킬 " + plugin.skills().all().size() + "개, 몬스터 " + plugin.mobs().registry().all().size()
                        + "종, 활성 몬스터 " + plugin.mobs().activeCount());
            }
            default -> adminHelp(s);
        }
    }

    private void adminAugment(CommandSender s, String[] a) {
        if (a.length < 3) {
            msg(s, "/증강관리 증강 <추가|제거|초기화|목록> <플레이어> [증강id]");
            return;
        }
        Player t = Bukkit.getPlayerExact(a[2]);
        if (t == null) {
            msg(s, "<#ff7070>플레이어를 찾을 수 없습니다.");
            return;
        }
        switch (a[1]) {
            case "추가", "add" -> {
                if (a.length < 4) return;
                if (a[3].equals("*") || a[3].equals("전부")) {
                    int n = 0;
                    for (String id : plugin.augments().registry().all().keySet()) if (plugin.augments().grant(t, id, false)) n++;
                    msg(s, "<gray>증강 " + n + "개 추가");
                    return;
                }
                msg(s, plugin.augments().grant(t, a[3], true) ? "<gray>추가했습니다." : "<#ff7070>없는 증강이거나 최대 중첩입니다.");
            }
            case "제거", "remove" -> {
                if (a.length < 4) return;
                msg(s, plugin.augments().remove(t, a[3]) ? "<gray>제거했습니다." : "<#ff7070>갖고 있지 않습니다.");
            }
            case "초기화", "reset" -> {
                plugin.augments().reset(t);
                msg(s, "<gray>" + t.getName() + "의 증강을 모두 지웠습니다.");
            }
            case "목록", "list" -> {
                PlayerData d = plugin.augments().data(t);
                List<String> names = new ArrayList<>();
                for (var en : d.augments.entrySet()) {
                    AugmentDef def = plugin.augments().registry().get(en.getKey());
                    names.add((def == null ? en.getKey() : def.tier().wrap(def.name())) + (en.getValue() > 1 ? "×" + en.getValue() : ""));
                }
                msg(s, "<gray>" + t.getName() + ": " + (names.isEmpty() ? "없음" : String.join("<gray>, ", names)));
            }
            default -> msg(s, "/증강관리 증강 <추가|제거|초기화|목록> <플레이어> [증강id]");
        }
    }

    private void adminHelp(CommandSender s) {
        msg(s, "<#ffcc55>━━━━ 증강관리 ━━━━");
        msg(s, "<white>무기 <id> [플레이어]  <gray>무기 지급 (/무기도감 에서 클릭해도 됨)");
        msg(s, "<white>아이템 <id> [개수] [플레이어]  <gray>shard, prism_crystal, ticket_silver ...");
        msg(s, "<white>증강 <추가|제거|초기화|목록> <플레이어> [id]");
        msg(s, "<white>선택지 <플레이어> <등급>  <gray>제물 없이 선택창 열기");
        msg(s, "<white>소환 <몬스터id> [플레이어|x y z]");
        msg(s, "<white>제단 <등급> / 균열 <id>  <gray>지금 위치에 세우기");
        msg(s, "<white>맵생성 [월드]  <gray>빈 공허 월드에 맵 전체 짓기");
        msg(s, "<white>리로드, 리소스팩, 정보");
    }

    private Player target(CommandSender s, String[] a, int idx) {
        if (a.length > idx) return Bukkit.getPlayerExact(a[idx]);
        return s instanceof Player p ? p : null;
    }

    private static int parseInt(String s, int def) {
        try {
            return Integer.parseInt(s);
        } catch (NumberFormatException e) {
            return def;
        }
    }

    private static double parseD(String s) {
        try {
            return Double.parseDouble(s);
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    // ------------------------------------------------------------------ 탭 완성

    @Override
    public List<String> onTabComplete(CommandSender s, Command cmd, String label, String[] a) {
        List<String> out = new ArrayList<>();
        switch (cmd.getName()) {
            case "augment" -> {
                if (a.length == 1) out.addAll(List.of("도감", "선택", "제단", "책", "도움"));
                else if (a.length == 2 && a[0].equals("도감")) out.addAll(List.of("실버", "골드", "프리즘"));
            }
            case "augadmin" -> {
                if (!s.hasPermission("augsky.admin")) return out;
                if (a.length == 1) {
                    out.addAll(List.of("무기", "아이템", "증강", "선택지", "소환", "제단", "균열", "맵생성", "리로드", "리소스팩", "정보"));
                } else {
                    switch (a[0]) {
                        case "무기", "weapon" -> {
                            if (a.length == 2) out.addAll(plugin.weapons().all().keySet());
                            if (a.length == 3) players(out);
                        }
                        case "아이템", "item" -> {
                            if (a.length == 2) out.addAll(plugin.items().all().keySet());
                            if (a.length == 4) players(out);
                        }
                        case "증강", "augment" -> {
                            if (a.length == 2) out.addAll(List.of("추가", "제거", "초기화", "목록"));
                            if (a.length == 3) players(out);
                            if (a.length == 4) out.addAll(plugin.augments().registry().all().keySet());
                        }
                        case "선택지", "offer" -> {
                            if (a.length == 2) players(out);
                            if (a.length == 3) out.addAll(List.of("실버", "골드", "프리즘"));
                        }
                        case "소환", "spawn" -> {
                            if (a.length == 2) out.addAll(plugin.mobs().registry().all().keySet());
                            if (a.length == 3) players(out);
                        }
                        case "제단", "altar" -> out.addAll(List.of("실버", "골드", "프리즘"));
                        case "균열", "rift" -> out.addAll(plugin.mobs().registry().rifts().keySet());
                        default -> {
                        }
                    }
                }
            }
            default -> {
            }
        }
        String last = a.length == 0 ? "" : a[a.length - 1].toLowerCase(Locale.ROOT);
        out.removeIf(x -> !x.toLowerCase(Locale.ROOT).startsWith(last));
        return out;
    }

    private static void players(List<String> out) {
        for (Player p : Bukkit.getOnlinePlayers()) out.add(p.getName());
    }

}
