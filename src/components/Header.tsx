import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import SearchDropdown from "./SearchDropdown";

const Header = () => {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 10);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled
          ? "glass-effect shadow-sm"
          : "bg-transparent"
      }`}
    >
      <div className="container mx-auto px-6 h-16 flex items-center gap-6">
        <Link to="/" className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-primary-foreground text-sm font-semibold">V</span>
          </div>
          <span className="text-lg font-semibold tracking-tight">Vibecheck</span>
        </Link>
        
        {/* Search - hidden on mobile, shown in main content instead */}
        <div className="hidden md:block flex-1">
          <SearchDropdown />
        </div>
      </div>
    </header>
  );
};

export default Header;
