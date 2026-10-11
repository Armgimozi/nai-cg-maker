package kr.augsky.augment;

import org.bukkit.Material;

import java.util.Locale;

/** 증강 등급. 롤토체스처럼 실버 < 골드 < 프리즘. */
public enum Tier {
    SILVER("실버", "<#cfdbe6>", "</#cfdbe6>", Material.LIGHT_GRAY_STAINED_GLASS_PANE, "block.amethyst_block.chime"),
    GOLD("골드", "<#ffcf40>", "</#ffcf40>", Material.YELLOW_STAINED_GLASS_PANE, "entity.player.levelup"),
    PRISM("프리즘", "<gradient:#ff6b9d:#ffd36b:#6bffb0:#6bc8ff:#c86bff>", "</gradient>", Material.MAGENTA_STAINED_GLASS_PANE, "ui.toast.challenge_complete");

    public final String korean, open, close, sound;
    public final Material pane;

    Tier(String korean, String open, String close, Material pane, String sound) {
        this.korean = korean;
        this.open = open;
        this.close = close;
        this.pane = pane;
        this.sound = sound;
    }

    public String wrap(String s) {
        return open + s + close;
    }

    public String label() {
        return wrap("[" + korean + "]");
    }

    public static Tier parse(String s) {
        if (s == null) return null;
        String k = s.trim().toUpperCase(Locale.ROOT);
        for (Tier t : values()) if (t.name().equals(k) || t.korean.equals(s.trim())) return t;
        return switch (k) {
            case "실버", "S" -> SILVER;
            case "골드", "G" -> GOLD;
            case "프리즘", "P", "PRISMATIC" -> PRISM;
            default -> null;
        };
    }
}
