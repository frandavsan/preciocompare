import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import TopNav from "@/components/TopNav";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/contexts/AuthContext";

type LocationState = {
  from?: { pathname?: string; search?: string; hash?: string };
} | null;

// ProtectedRoute hands us the full Location object; reassemble pathname +
// search + hash so deep links like /producto?q=...&selected=... survive a
// re-auth round-trip instead of dropping the query string.
const buildReturnPath = (state: LocationState): string => {
  const from = state?.from;
  if (!from?.pathname) return "/";
  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`;
};

const SignIn = () => {
  const { session, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isLoading && session) {
    return <Navigate to={buildReturnPath(location.state as LocationState)} replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (signInError) {
      setError(
        signInError.message === "Invalid login credentials"
          ? "Credenciales invalidas"
          : signInError.message
      );
      setIsSubmitting(false);
      return;
    }

    navigate(buildReturnPath(location.state as LocationState), { replace: true });
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#fbf9f5] text-[#1b1c1a]">
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-[16%] -top-[24%] h-[42rem] w-[42rem] rounded-full bg-[radial-gradient(circle_at_58%_42%,hsl(272_81%_74%_/_0.5),hsl(262_90%_38%_/_0.22)_52%,transparent_74%)] blur-[132px]" />
        <div className="absolute -right-[14%] -top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle_at_38%_42%,hsl(252_78%_80%_/_0.22),hsl(262_90%_38%_/_0.1)_58%,transparent_76%)] blur-[120px]" />
        <div className="absolute -bottom-[22%] -right-[12%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle_at_38%_38%,hsl(177_62%_72%_/_0.4),hsl(179_98%_21%_/_0.16)_56%,transparent_76%)] blur-[128px]" />
      </div>

      <TopNav activeSection="access" />

      <main className="relative z-10 flex min-h-[calc(100vh-9rem)] flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-md rounded-[0.6rem] bg-white p-10 shadow-[0_20px_40px_rgba(74,68,82,0.04)] md:p-12">
          <header className="mb-10 text-center">
            <h1 className="text-4xl font-semibold tracking-tight text-[#1b1c1a]">
              Acceso al Portal
            </h1>
          </header>

          <form className="space-y-6" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <label htmlFor="signin-email" className="ml-1 block font-mono text-[11px] uppercase tracking-[0.22em] text-[#4a4452]">
                Email
              </label>
              <input
                id="signin-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                placeholder="nombre@compania.com"
                className="w-full rounded-[0.6rem] border-b-2 border-transparent bg-[#eae8e4] px-4 py-4 text-[#1b1c1a] outline-none transition-all duration-300 placeholder:text-[#7c7484]/70 focus:border-[#46078d] focus:bg-white disabled:opacity-60"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="signin-password" className="ml-1 block font-mono text-[11px] uppercase tracking-[0.22em] text-[#4a4452]">
                Contrasena
              </label>
              <input
                id="signin-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                placeholder="••••••••"
                className="w-full rounded-[0.6rem] border-b-2 border-transparent bg-[#eae8e4] px-4 py-4 text-[#1b1c1a] outline-none transition-all duration-300 placeholder:text-[#7c7484]/70 focus:border-[#46078d] focus:bg-white disabled:opacity-60"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-[0.5rem] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {error}
              </div>
            )}

            <div className="pt-4">
              <button
                type="submit"
                disabled={isSubmitting || !email || !password}
                className="flex w-full items-center justify-center gap-2 rounded-[0.6rem] bg-[#46078d] py-4 font-mono text-[11px] font-bold tracking-[0.22em] text-white transition-all duration-300 hover:opacity-90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "INGRESANDO..." : "INGRESAR"}
                {!isSubmitting && <ArrowRight className="h-4 w-4" />}
              </button>
            </div>
          </form>

          <div className="mt-10 border-t border-[#4a4452]/10 pt-7 text-center">
            <p className="text-sm leading-relaxed text-[#4a4452]/70">
              No tiene cuenta? Contactese con{" "}
              <a
                href="mailto:fs@preciocompare.com"
                className="font-semibold text-[#3f1476] transition-colors hover:text-[#016a68]"
              >
                fs@preciocompare.com
              </a>{" "}
              para consultar precios
            </p>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-4 font-mono text-[10px] uppercase tracking-[0.3em] text-[#7c7484]/60">
          <span>Market Analytics</span>
          <span className="h-1 w-1 rounded-full bg-[#7c7484]/60" />
          <span>Real-time Pricing</span>
          <span className="h-1 w-1 rounded-full bg-[#7c7484]/60" />
          <span>Global Coverage</span>
        </div>
      </main>

      <footer className="relative z-10 flex flex-col items-center justify-between gap-4 px-6 py-5 text-center md:flex-row md:px-8 md:text-left">
        <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#3f1476]/60">
          © 2024 PrecioCompare. Editorial Intelligence for Enterprise.
        </div>
        <div className="flex flex-wrap items-center justify-center gap-6 font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
          <button className="transition-colors hover:text-[#3f1476]">Privacy Policy</button>
          <button className="transition-colors hover:text-[#3f1476]">Terms of Service</button>
          <button className="transition-colors hover:text-[#3f1476]">Contact Support</button>
        </div>
      </footer>
    </div>
  );
};

export default SignIn;
