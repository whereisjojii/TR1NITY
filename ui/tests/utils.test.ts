import { describe, expect, it } from "vitest";
import { fpScoreLabel, severityClass, severityLabel } from "../src/lib/utils";

describe("severityLabel", () => {
  it("maps 0 to INFO and 7 to CRITICAL", () => {
    expect(severityLabel(0)).toBe("INFO");
    expect(severityLabel(2)).toBe("LOW");
    expect(severityLabel(4)).toBe("MEDIUM");
    expect(severityLabel(5)).toBe("HIGH");
    expect(severityLabel(7)).toBe("CRITICAL");
  });
});

describe("severityClass", () => {
  it("clamps out-of-range severities", () => {
    expect(severityClass(-3)).toContain("severity-0");
    expect(severityClass(99)).toContain("severity-7");
  });
});

describe("fpScoreLabel", () => {
  it("classifies the canonical buckets", () => {
    expect(fpScoreLabel(null)).toBe("—");
    expect(fpScoreLabel(0.05)).toBe("likely TP");
    expect(fpScoreLabel(0.3)).toBe("soft TP");
    expect(fpScoreLabel(0.5)).toBe("unmarked");
    expect(fpScoreLabel(0.65)).toBe("soft FP");
    expect(fpScoreLabel(0.95)).toBe("likely FP");
  });
});
