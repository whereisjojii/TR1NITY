import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useVimShortcuts } from "../src/hooks/useVimShortcuts";

function Harness({
  onJ,
  onShiftG,
  onGG,
  withInput,
}: {
  onJ: () => void;
  onShiftG: () => void;
  onGG: () => void;
  withInput?: boolean;
}) {
  useVimShortcuts([
    { key: "j", description: "next", handler: onJ },
    { key: "G", shift: true, description: "bottom", handler: onShiftG },
    { key: "g", follow: "g", description: "top", handler: onGG },
  ]);
  return withInput ? <input data-testid="input" /> : <div />;
}

describe("useVimShortcuts", () => {
  it("fires single-char bindings", () => {
    const onJ = vi.fn();
    render(<Harness onJ={onJ} onShiftG={() => {}} onGG={() => {}} />);
    fireEvent.keyDown(window, { key: "j" });
    expect(onJ).toHaveBeenCalledTimes(1);
  });

  it("respects shift modifier", () => {
    const onShiftG = vi.fn();
    render(<Harness onJ={() => {}} onShiftG={onShiftG} onGG={() => {}} />);
    fireEvent.keyDown(window, { key: "G", shiftKey: true });
    expect(onShiftG).toHaveBeenCalledTimes(1);
  });

  it("fires two-char gg sequences", () => {
    const onGG = vi.fn();
    render(<Harness onJ={() => {}} onShiftG={() => {}} onGG={onGG} />);
    fireEvent.keyDown(window, { key: "g" });
    fireEvent.keyDown(window, { key: "g" });
    expect(onGG).toHaveBeenCalledTimes(1);
  });

  it("ignores keys when an input is focused", () => {
    const onJ = vi.fn();
    const { getByTestId } = render(
      <Harness onJ={onJ} onShiftG={() => {}} onGG={() => {}} withInput />,
    );
    const input = getByTestId("input");
    input.focus();
    fireEvent.keyDown(input, { key: "j" });
    expect(onJ).not.toHaveBeenCalled();
  });
});
