package kr.augsky.vfx;

import org.bukkit.Location;
import org.bukkit.SoundCategory;

/** 겹쳐 쓰는 소리. 한 시전이 한 틱에 6개까지만 (소리 폭탄 방지) */
final class Sfx {
    private Sfx() {}

    static void play(CastFx fx, Location at, String key, double vol, double pitch) {
        if (at == null || at.getWorld() == null || key == null) return;
        if (!fx.soundSlot()) return;
        at.getWorld().playSound(at, key, SoundCategory.PLAYERS, (float) vol, (float) Math.max(0.5, Math.min(2.0, pitch)));
    }

    static void layers(CastFx fx, Location at, Palette.Snd[] list, int n, double volMul) {
        if (list == null) return;
        for (int i = 0; i < list.length && i < n; i++) {
            Palette.Snd s = list[i];
            play(fx, at, s.key(), s.vol() * volMul, s.pitch());
        }
    }

    /** 프리즘 궁극기 전용: 맑은 종소리 오름차순 */
    static void arpeggio(CastFx fx, Location at, double base) {
        double[] steps = {1.0, 1.26, 1.5, 2.0};
        for (int i = 0; i < steps.length; i++) {
            double p = base * steps[i];
            fx.vfx.after(i * 2, () -> play(fx, at, "block.note_block.chime", 0.6, p));
        }
    }
}
