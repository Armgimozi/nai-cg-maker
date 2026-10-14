package kr.labyrinth.content;

import java.util.List;

/** fx.yml auras — 전설/신화 무기 아우라. particles 는 각 항목 Params(type, count, radius, height, pattern, …). */
public record AuraDef(String id, String tier, List<Params> particles, String ringModel, double ringSpin,
                      double ringScale, double ringHeight, boolean ringStep, String secondaryModel,
                      double secondarySpin, String secondaryMode, int interval, Params swing, Params raw) {}
