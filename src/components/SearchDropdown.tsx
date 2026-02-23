// Minimal SearchDropdown component stub
const SearchDropdown = () => {
  return (
    <div className="relative w-full max-w-md">
      <input
        type="search"
        placeholder="Search tools..."
        className="w-full px-4 py-2 rounded-xl bg-secondary/50 border border-border/30 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  );
};

export default SearchDropdown;
