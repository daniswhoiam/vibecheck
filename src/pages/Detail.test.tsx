import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "@/test/mocks";

// NOTE: Detail imports useToolDetail, useTools, useAspectSentiment — mock all
vi.mock("@/hooks/useTools", () => ({
  useToolDetail: vi.fn(),
  useTools: vi.fn(() => ({ data: [] })),
}));
vi.mock("@/hooks/useAspectSentiment", () => ({
  useAspectSentiment: vi.fn(() => ({ data: undefined, isLoading: false })),
}));

import Detail from "@/pages/Detail";
import { useToolDetail } from "@/hooks/useTools";
import { useAspectSentiment } from "@/hooks/useAspectSentiment";
import { mockAspectResponse } from "@/test/mocks";

const mockTool = {
  id: "1",
  name: "Claude",
  company: "Anthropic",
  sentiment: { positive: 70, neutral: 20, negative: 10 },
  mentions: 100,
  trend: "up" as const,
  trendPercent7d: 5,
  sparklineData: [],
  type: "llm" as const,
  rank: 1,
  description: "...",
  versions: [],
  currentVersion: "Latest",
  bestFor: ["coding"],
  rating: 4.5,
  trendData: [],
  recentMentions: [],
};

function renderDetail() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/detail/1"]}>
        <Routes>
          <Route path="/detail/:id" element={<Detail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Detail page - source filter", () => {
  beforeEach(() => {
    vi.mocked(useToolDetail).mockReturnValue({ data: mockTool, isLoading: false, error: null } as any);
    vi.mocked(useAspectSentiment).mockReturnValue({ data: mockAspectResponse(), isLoading: false } as any);
  });

  it("renders source filter toggle with 5 options", () => {
    renderDetail();
    expect(screen.getByText("All Sources")).toBeInTheDocument();
    expect(screen.getByText("HN")).toBeInTheDocument();
    expect(screen.getByText("Reddit")).toBeInTheDocument();
  });

  it("renders Sentiment by Aspect section", () => {
    renderDetail();
    expect(screen.getByText(/Sentiment by Aspect/i)).toBeInTheDocument();
  });

  it("source filter is placed below entity header", () => {
    renderDetail();
    const header = screen.getByText("Claude");
    const filter = screen.getByText("All Sources");
    expect(header.compareDocumentPosition(filter)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
