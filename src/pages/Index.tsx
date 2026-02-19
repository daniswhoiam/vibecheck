import { useState } from "react";
import Header from "@/components/Header";
import TabFilter from "@/components/TabFilter";
import ToolCard from "@/components/ToolCard";
import ToolCardSkeleton from "@/components/ToolCardSkeleton";
import SearchDropdown from "@/components/SearchDropdown";
import { useTools } from "@/hooks/useTools";
import { useLanguage } from "@/hooks/useLanguage";

const Index = () => {
  const [activeTab, setActiveTab] = useState("all");
  const { data: tools, isLoading, error } = useTools();
  const { t } = useLanguage();

  const filteredTools = tools?.filter((tool) => {
    if (activeTab === "all") return true;
    if (activeTab === "llms") return tool.type === "llm";
    if (activeTab === "tools") return tool.type === "tool";
    return true;
  }) ?? [];

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-6 pt-24 pb-12">
        {/* Mobile Search - above tabs */}
        <div className="md:hidden mb-4">
          <SearchDropdown />
        </div>

        {/* Tabs */}
        <div className="mb-8">
          <TabFilter activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        {/* Error State */}
        {error && (
          <div className="text-center py-12">
            <p className="text-destructive">{t("errorLoading")}</p>
          </div>
        )}

        {/* Card Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => <ToolCardSkeleton key={i} />)
            : filteredTools.map((tool) => <ToolCard key={tool.id} tool={tool} />)
          }
        </div>
      </main>
    </div>
  );
};

export default Index;
