import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

type TopNavSection = "intelligence" | "market-data" | "settings" | "access";

interface TopNavProps {
  activeSection: TopNavSection;
}

const baseNavItems: Array<{
  key: TopNavSection;
  label: string;
  to: string;
}> = [
  { key: "intelligence", label: "Buscar", to: "/" },
  { key: "market-data", label: "Resultados", to: "/producto" },
  { key: "settings", label: "Configuración", to: "/configuracion" },
];

const LAST_RESULTS_PATH_KEY = "preciocompare:last-results-path";

const TopNav = ({ activeSection }: TopNavProps) => {
  const { session, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate("/signin", { replace: true });
  };

  const handleResultsClick = () => {
    const lastResultsPath = window.sessionStorage.getItem(LAST_RESULTS_PATH_KEY);
    if (!lastResultsPath) {
      toast.warning("Primero debes realizar una búsqueda");
      return;
    }
    navigate(lastResultsPath);
  };

  return (
    <nav className="relative z-10 flex items-center justify-between px-6 py-6 lg:px-8">
      <Link
        to="/"
        className="text-[1.28rem] font-semibold tracking-[-0.02em] text-[#3f1476] transition-opacity hover:opacity-75"
        style={{ fontFamily: "'IBM Plex Sans', 'Inter', sans-serif" }}
      >
        PrecioCompare
      </Link>
      <div className="hidden items-center gap-8 text-sm text-slate-600 md:flex">
        {baseNavItems.map((item) =>
          item.key === activeSection ? (
            <span key={item.key} className="border-b-2 border-[#3f1476] pb-1 font-semibold text-[#3f1476]">
              {item.label}
            </span>
          ) : item.key === "market-data" ? (
            <button
              key={item.key}
              type="button"
              onClick={handleResultsClick}
              className="transition-opacity hover:opacity-70"
            >
              {item.label}
            </button>
          ) : (
            <Link key={item.key} to={item.to} className="transition-opacity hover:opacity-70">
              {item.label}
            </Link>
          ),
        )}
        {session ? (
          <button
            type="button"
            onClick={handleSignOut}
            className="transition-opacity hover:opacity-70"
          >
            Salir
          </button>
        ) : activeSection === "access" ? (
          <span className="border-b-2 border-[#3f1476] pb-1 font-semibold text-[#3f1476]">
            Entrar
          </span>
        ) : (
          <Link to="/signin" className="transition-opacity hover:opacity-70">
            Entrar
          </Link>
        )}
      </div>
    </nav>
  );
};

export default TopNav;
