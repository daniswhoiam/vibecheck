import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { SourceFilter } from "@/types/api";

interface SourceFilterToggleProps {
  value: SourceFilter;
  onChange: (value: SourceFilter) => void;
  className?: string;
}

const SOURCES: { id: SourceFilter; label: string }[] = [
  { id: "all", label: "All Sources" },
  { id: "hn", label: "HN" },
  { id: "reddit", label: "Reddit" },
  { id: "discourse", label: "Discourse" },
  { id: "devto", label: "Dev.to" },
];

export function SourceFilterToggle({
  value,
  onChange,
  className,
}: SourceFilterToggleProps) {
  const handleChange = (newValue: string) => {
    // Radix ToggleGroup type="single" sends empty string when deselecting the active item.
    // Treat empty string as "all" to prevent deselecting everything.
    if (!newValue) return;
    onChange(newValue as SourceFilter);
  };

  return (
    <div className={className}>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={handleChange}
        className="flex flex-wrap gap-2"
        aria-label="Filter by data source"
      >
        {SOURCES.map((source) => (
          <ToggleGroupItem
            key={source.id}
            value={source.id}
            className="px-4 py-1.5 rounded-full text-sm font-medium data-[state=on]:bg-foreground data-[state=on]:text-background"
            aria-label={`Filter to ${source.label}`}
          >
            {source.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}
