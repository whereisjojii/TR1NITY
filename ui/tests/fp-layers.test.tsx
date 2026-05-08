import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FPLayerBadge } from "../src/components/FPLayerBadge";

describe("FPLayerBadge", () => {
  it("renders an empty-state message when no layers are passed", () => {
    render(<FPLayerBadge layers={[]} />);
    expect(screen.getByText(/No FP layer fired/i)).toBeInTheDocument();
  });

  it("renders a badge for every contributing layer", () => {
    render(
      <FPLayerBadge
        layers={[
          {
            layer: "L1",
            score: 0.9,
            detail: { rule: "Authorized scanner" },
          },
          {
            layer: "L3",
            score: 0.95,
            detail: { suppression_id: "s-1" },
          },
        ]}
      />,
    );
    expect(screen.getByText(/Whitelist/i)).toBeInTheDocument();
    expect(screen.getByText(/Suppression/i)).toBeInTheDocument();
    expect(screen.getByText(/0\.90/)).toBeInTheDocument();
    expect(screen.getByText(/0\.95/)).toBeInTheDocument();
  });
});
