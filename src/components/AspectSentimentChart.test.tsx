import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AspectSentimentChart } from "@/components/AspectSentimentChart";
import { mockAspectResponse, mockEmptyAspectResponse } from "@/test/mocks";

const ASPECT_LABELS = ["Performance", "Cost", "Reliability", "UX", "Speed", "Code Quality", "Context Window"];

describe("AspectSentimentChart", () => {
  it("renders all 7 aspect labels", () => {
    const data = mockAspectResponse();
    render(<AspectSentimentChart data={data.aspects} />);
    ASPECT_LABELS.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("shows empty state when all aspects have count=0", () => {
    const emptyData = mockEmptyAspectResponse();
    render(<AspectSentimentChart data={emptyData.aspects} source="discourse" onClearFilter={vi.fn()} />);
    expect(screen.getByText(/No Discourse data indexed yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View All Sources/i })).toBeInTheDocument();
  });

  it("shows insufficient data label for aspects with count=0 amid real data", () => {
    const data = mockAspectResponse();
    // context_window has count=0 in mockAspectResponse
    render(<AspectSentimentChart data={data.aspects} />);
    expect(screen.getByText(/Insufficient data/i)).toBeInTheDocument();
  });

  it("sorts aspects by score descending", () => {
    const data = mockAspectResponse();
    const { container } = render(<AspectSentimentChart data={data.aspects} />);
    // performance (0.65) should appear before cost (-0.30) in DOM order
    const labels = container.querySelectorAll("[data-aspect-label]");
    const labelTexts = Array.from(labels).map((el) => el.textContent);
    const perfIdx = labelTexts.findIndex((t) => t?.includes("Performance"));
    const costIdx = labelTexts.findIndex((t) => t?.includes("Cost"));
    expect(perfIdx).toBeLessThan(costIdx);
  });
});
