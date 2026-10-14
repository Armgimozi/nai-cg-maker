package kr.labyrinth.ui;

import kr.labyrinth.Services;
import kr.labyrinth.content.ClassDef;
import kr.labyrinth.content.FloorDef;
import kr.labyrinth.core.Difficulty;
import kr.labyrinth.core.Text;
import kr.labyrinth.data.PlayerData;
import kr.labyrinth.stats.DerivedStats;
import kr.labyrinth.stats.Stat;
import org.bukkit.entity.Player;

/**
 * 기본 메뉴 구현: GUI 대신 클릭 가능한 채팅 메시지. ui 담당의 GUI 가 붙기 전에도 게임이 진행되게 한다.
 */
public class ChatMenuService implements MenuService {

    protected final Services services;

    public ChatMenuService(Services services) { this.services = services; }

    private static String button(String label, String command, String hover) {
        return "<click:run_command:'" + command + "'><hover:show_text:'" + hover + "'>" + label + "</hover></click>";
    }

    @Override
    public void openMain(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>━━━━ 미궁 라비린스 ━━━━</b></gradient>"));
        p.sendMessage(Text.mm("<gray>Lv.<white>" + d.level() + "</white>  골드 <gold>" + Text.num(d.gold())
                + "</gold>  해금 <aqua>지하 " + d.unlockedFloor() + "층</aqua>"));
        p.sendMessage(Text.mm(button("<green>[입장]</green>", "/lab enter", "층 선택") + "  "
                + button("<yellow>[스탯]</yellow>", "/stats", "스탯 분배") + "  "
                + button("<aqua>[직업]</aqua>", "/class", "직업") + "  "
                + button("<light_purple>[칭호]</light_purple>", "/title", "칭호") + "  "
                + button("<white>[파티]</white>", "/party", "파티")));
    }

    @Override
    public void openStats(Player p) {
        PlayerData d = services.data().get(p);
        DerivedStats s = services.stats().get(p);
        p.sendMessage(Text.mm("<gradient:#ffd84f:#ff9f43><b>━━━━ 스탯 ━━━━</b></gradient>  <gray>남은 포인트 <yellow>"
                + d.statPoints() + "</yellow>"));
        for (Stat st : Stat.values()) {
            String plus = d.statPoints() > 0
                    ? " " + button("<green>[+1]</green>", "/stats add " + st.name() + " 1", st.displayName() + " +1")
                    + " " + button("<dark_green>[+5]</dark_green>", "/stats add " + st.name() + " 5", st.displayName() + " +5")
                    : "";
            p.sendMessage(Text.mm("<" + st.color() + ">" + st.displayName() + " <gray>(" + st.name() + ")</gray> <white>"
                    + s.stat(st) + "</white> <dark_gray>(투자 " + d.allocated(st) + ")</dark_gray>" + plus));
        }
        p.sendMessage(Text.mm("<gray>공격력 <white>" + Text.num(s.attackPower()) + "</white> · 최대 HP <white>"
                + Text.num(s.maxHp()) + "</white> · 최대 MP <white>" + Text.num(s.maxMp()) + "</white> · 방어 <white>"
                + Text.num(s.defense()) + "</white>"));
        p.sendMessage(Text.mm("<gray>치명타 <white>" + Text.pct(s.critChance()) + "</white> ×" + String.format("%.2f", s.critDamage())
                + " · 회피 <white>" + Text.pct(s.evasion()) + "</white> · 피해감소 <white>" + Text.pct(s.damageReduction())
                + "</white> · 재사용감소 <white>" + Text.pct(s.cooldownReduction()) + "</white>"));
    }

    @Override
    public void openClass(Player p) {
        ClassDef cur = services.classes().classOf(p);
        p.sendMessage(Text.mm("<aqua><b>━━━━ 직업 ━━━━</b></aqua>  <gray>현재: " + (cur == null ? "없음"
                : "<" + cur.color() + ">" + cur.name())));
        for (ClassDef c : services.content().classes().values()) {
            p.sendMessage(Text.mm("<" + c.color() + ">● " + c.name() + "</" + c.color() + "> <dark_gray>(" + c.role() + ")</dark_gray> ")
                    .append(Text.mm(c.description())));
        }
    }

    @Override
    public void openParty(Player p) {
        p.performCommand("party info");
    }

    @Override
    public void openTitles(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<light_purple><b>━━━━ 칭호 ━━━━</b></light_purple>  <gray>달성 " + d.achievements().size()
                + " / " + services.content().achievements().size()));
        d.achievements().keySet().forEach(id -> {
            var def = services.content().achievements().get(id);
            if (def != null) p.sendMessage(Text.mm(" " + def.title() + " <dark_gray>— " + Text.escape(def.description())));
        });
    }

    @Override
    public void openEntrance(Player p) {
        PlayerData d = services.data().get(p);
        p.sendMessage(Text.mm("<green><b>━━━━ 미궁 입장 ━━━━</b></green>"));
        for (FloorDef f : services.content().floors().values()) {
            boolean open = f.number() <= d.unlockedFloor();
            String label = (open ? "<green>" : "<dark_gray>") + "[지하 " + f.number() + "층] " + Text.strip(f.name());
            p.sendMessage(Text.mm(open ? button(label, "/lab enter " + f.number(), "입장") : label + " <red>잠김"));
        }
    }

    @Override
    public void openSetup(Player p) {
        p.sendMessage(Text.mm("<gradient:#c9a2ff:#7fd8ff><b>━━━━ 미궁 라비린스 초기 설정 ━━━━</b></gradient>"));
        p.sendMessage(Text.mm("<gray>서버 난이도를 골라 주세요. 나중에 <white>/미궁 난이도</white> 로 바꿀 수 있습니다."));
        StringBuilder sb = new StringBuilder();
        for (Difficulty d : services.settings().difficulties().values()) {
            sb.append(button("<yellow>[" + d.name() + "]</yellow>", "/lab difficulty " + d.id(),
                    "몹 HP ×" + d.hp() + " · 피해 ×" + d.damage() + " · 드롭 ×" + d.drop())).append("  ");
        }
        p.sendMessage(Text.mm(sb.toString()));
    }

    @Override
    public void openAccessories(Player p) {
        Text.send(p, "<gray>장신구 칸은 <white>/미궁 장신구</white> 메뉴에서 관리합니다.");
    }
}
