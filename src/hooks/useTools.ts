import { useQuery } from "@tanstack/react-query";
import { fetchTools, fetchToolDetail } from "@/services/api";

export function useTools() {
  return useQuery({
    queryKey: ["tools"],
    queryFn: () => fetchTools(true), // Fetch time-series data for trend calculations
  });
}

export function useToolDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["tool", id],
    queryFn: () => fetchToolDetail(id!),
    enabled: !!id,
  });
}
