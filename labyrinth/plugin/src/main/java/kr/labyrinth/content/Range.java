package kr.labyrinth.content;

import java.util.random.RandomGenerator;

/** 실수 닫힌 구간 [min, max] — 아이템 스탯 굴림 등. */
public record Range(double min, double max) {
    /** t ∈ [0,1] 위치의 값. */
    public double lerp(double t) { return min + (max - min) * Math.max(0, Math.min(1, t)); }

    public double roll(RandomGenerator rng) { return lerp(rng.nextDouble()); }
}
