import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SourceFilterToggle } from "@/components/SourceFilterToggle";

describe("SourceFilterToggle", () => {
  it("renders all 5 source options", () => {
    render(<SourceFilterToggle value="all" onChange={vi.fn()} />);
    expect(screen.getByText("All Sources")).toBeInTheDocument();
    expect(screen.getByText("HN")).toBeInTheDocument();
    expect(screen.getByText("Reddit")).toBeInTheDocument();
    expect(screen.getByText("Discourse")).toBeInTheDocument();
    expect(screen.getByText("Dev.to")).toBeInTheDocument();
  });

  it("calls onChange when a source is selected", () => {
    const onChange = vi.fn();
    render(<SourceFilterToggle value="all" onChange={onChange} />);
    fireEvent.click(screen.getByText("Reddit"));
    expect(onChange).toHaveBeenCalledWith("reddit");
  });

  it("reflects the active source via aria-pressed or data-state", () => {
    render(<SourceFilterToggle value="hn" onChange={vi.fn()} />);
    const hnButton = screen.getByText("HN").closest("button");
    expect(hnButton).toHaveAttribute("data-state", "on");
  });
});
