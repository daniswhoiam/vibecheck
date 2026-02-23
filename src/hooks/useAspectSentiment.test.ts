import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAspectSentiment } from "@/hooks/useAspectSentiment";
import { mockAspectResponse, createQueryClient } from "@/test/mocks";

describe("useAspectSentiment", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches aspect data when entityId is provided", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAspectResponse(),
    }));
    const queryClient = createQueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    const { result } = renderHook(() => useAspectSentiment("1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.aspects.performance.mean).toBe(0.65);
  });

  it("does not fetch when entityId is undefined", () => {
    const queryClient = createQueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    const { result } = renderHook(() => useAspectSentiment(undefined), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("includes source param when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockAspectResponse(),
    });
    vi.stubGlobal("fetch", fetchMock);
    const queryClient = createQueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
    renderHook(() => useAspectSentiment("1", "7d", "reddit"), { wrapper });
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0][0]).toContain("source=reddit");
  });
});
