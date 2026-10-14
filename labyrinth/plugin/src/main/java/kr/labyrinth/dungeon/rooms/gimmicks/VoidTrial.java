package kr.labyrinth.dungeon.rooms.gimmicks;

import java.util.List;
import kr.labyrinth.core.Text;
import kr.labyrinth.dungeon.FloorState;
import kr.labyrinth.dungeon.gen.BlockList;
import kr.labyrinth.dungeon.gen.FloorLayout;
import kr.labyrinth.dungeon.rooms.GimmickRoom;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Player;

/**
 * 10층 `void_trial`: duration 초 생존. 안전 반경이 radius_start → radius_end 로 줄어든다(방 크기에 맞춰 상한).
 * 밖에 서 있으면 초당 outside_damage. wave_interval 초마다 wave_mobs 웨이브 (인원이 많으면 더 많이).
 */
public final class VoidTrial extends GimmickRoom {

    private long lastDamage;
    private long nextWave;
    private int waves;

    public VoidTrial(FloorState fs, FloorLayout.RoomInfo info) {
        super(fs, info);
    }

    @Override protected String title() { return "심연의 시련"; }

    @Override
    protected String rules() {
        return "<gray>보랏빛 원이 조금씩 숨을 죽여 간다\n"
                + "<gray>심연은 원 바깥부터 삼킨다";
    }

    @Override
    protected List<String> hints() {
        return List.of(
                "보랏빛 원은 좁아질 뿐, 사라지지 않는다.",
                "원 밖에 서 있으면 심연이 살을 갉아먹는다. 무리는 원 가장자리에서 솟아오른다.",
                params.integer("duration", 60) + "초 동안 버티면 성공 — 점점 좁아지는 보랏빛 원 안에 머물며, 가장자리에서 솟는 무리를 처치하라. 원 밖은 초마다 다친다.");
    }

    @Override
    protected int timeLimit() { return 0; }

    @Override
    public void prepare(BlockList list) {
        int cx = fs.ox() + info.centerX(), cz = fs.oz() + info.centerZ();
        list.add(cx, fs.y0(), cz, Material.CRYING_OBSIDIAN.createBlockData());
        for (int k = 0; k < 8; k++) {
            double a = Math.PI * 2 * k / 8;
            list.add(cx + (int) Math.round(Math.cos(a) * 2), fs.y0(), cz + (int) Math.round(Math.sin(a) * 2), Material.OBSIDIAN.createBlockData());
        }
    }

    private double radius() {
        double maxR = Math.min(info.width(), info.depth()) / 2.0 - 0.5;
        double start = Math.min(maxR, params.dbl("radius_start", 10));
        double end = Math.min(start, params.dbl("radius_end", 4));
        double f = Math.min(1, elapsed() / Math.max(1, params.dbl("duration", 60)));
        return start + (end - start) * f;
    }

    @Override
    protected void begin() {
        waves = 0;
        lastDamage = System.currentTimeMillis();
        nextWave = lastDamage + 3000;
    }

    @Override
    protected void update(long t) {
        Location c = center();
        double r = radius();
        if (t % 6 == 0) {
            int points = (int) Math.max(24, r * 8);
            Particle.DustOptions dust = new Particle.DustOptions(Color.fromRGB(0x8A2BE2), 1.4f);
            for (int i = 0; i < points; i++) {
                double a = Math.PI * 2 * i / points;
                Location at = c.clone().add(Math.cos(a) * r, 0.15, Math.sin(a) * r);
                fs.world().spawnParticle(Particle.DUST, at, 1, 0, 0, 0, 0, dust);
            }
            fs.world().spawnParticle(Particle.REVERSE_PORTAL, c.clone().add(0, 0.5, 0), 6, 0.4, 0.3, 0.4, 0.02);
        }
        long now = System.currentTimeMillis();
        if (now - lastDamage >= 1000) {
            lastDamage = now;
            for (Player p : alivePlayersInside()) {
                double dx = p.getLocation().getX() - c.getX(), dz = p.getLocation().getZ() - c.getZ();
                if (dx * dx + dz * dz > r * r) {
                    hurt(p, params.dbl("outside_damage", 0.08), "void_edge");
                    fs.services().hud().actionBar(p, Text.mm("<dark_purple><b>심연이 살을 갉아먹는다!</b></dark_purple>"), 25);
                }
            }
        }
        if (now >= nextWave) {
            nextWave = now + Math.round(params.dbl("wave_interval", 12) * 1000);
            waves++;
            List<String> ids = params.strings("wave_mobs");
            int each = 1 + (partySize() - 1) / 2;
            for (String id : ids.isEmpty() ? List.of(fs.randomFloorMob(rng)) : ids) {
                if (fs.services().content().mob(id) == null) continue;
                for (int i = 0; i < each; i++) {
                    double a = rng.nextDouble() * Math.PI * 2;
                    double rr = Math.max(2, r - 1);
                    spawn(id, c.clone().add(Math.cos(a) * rr, 0, Math.sin(a) * rr));
                }
            }
            fs.sound(c, Sound.ENTITY_WARDEN_SONIC_CHARGE, 0.7f, 1.2f);
            fs.actionBar(fs.allPlayers(), "<dark_purple>심연의 무리 " + waves + "번째 물결!</dark_purple>", 40);
        }
        if (elapsed() >= params.dbl("duration", 60)) {
            fs.sound(c, Sound.BLOCK_BEACON_ACTIVATE, 1.0f, 0.6f);
            succeed();
        }
    }

    @Override
    protected String status() {
        return "생존 " + (int) elapsed() + "/" + params.integer("duration", 60) + "초 · 안전 반경 " + String.format("%.1f", radius());
    }

    @Override
    protected float progress() { return (float) (elapsed() / Math.max(1, params.dbl("duration", 60))); }
}
