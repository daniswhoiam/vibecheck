interface TabFilterProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const TABS = [
  { id: "all", label: "All" },
  { id: "llms", label: "LLMs" },
  { id: "tools", label: "Tools" },
];

export default function TabFilter({ activeTab, onTabChange }: TabFilterProps) {
  return (
    <div className="flex gap-2">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            activeTab === tab.id
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
