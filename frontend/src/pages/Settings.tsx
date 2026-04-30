import { useEffect, useMemo, useState } from "react";
import { Check, Lock, Mail, Pencil, Store } from "lucide-react";
import TopNav from "@/components/TopNav";
import { useAuth } from "@/contexts/AuthContext";

const DEFAULT_COMMERCE_NAME = "Mi comercio";

const Settings = () => {
  const { session } = useAuth();
  const email = session?.user.email ?? "Sin email";
  const storageKey = useMemo(
    () => `preciocompare:commerce-name:${email.toLowerCase()}`,
    [email],
  );
  const [commerceName, setCommerceName] = useState(DEFAULT_COMMERCE_NAME);
  const [draftCommerceName, setDraftCommerceName] = useState(DEFAULT_COMMERCE_NAME);
  const [isEditingCommerce, setIsEditingCommerce] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(storageKey);
    const next = stored?.trim() || DEFAULT_COMMERCE_NAME;
    setCommerceName(next);
    setDraftCommerceName(next);
  }, [storageKey]);

  const handleStartEditing = () => {
    setDraftCommerceName(commerceName);
    setIsEditingCommerce(true);
  };

  const handleSaveCommerceName = () => {
    const next = draftCommerceName.trim() || DEFAULT_COMMERCE_NAME;
    window.localStorage.setItem(storageKey, next);
    setCommerceName(next);
    setDraftCommerceName(next);
    setIsEditingCommerce(false);
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background paper-texture text-foreground isolate">
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
        <div className="absolute -left-[16%] -top-[24%] h-[42rem] w-[42rem] rounded-full bg-[radial-gradient(circle_at_58%_42%,hsl(272_81%_74%_/_0.5),hsl(262_90%_38%_/_0.22)_52%,transparent_74%)] blur-[132px]" />
        <div className="absolute -right-[14%] -top-[8%] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle_at_38%_42%,hsl(252_78%_80%_/_0.22),hsl(262_90%_38%_/_0.1)_58%,transparent_76%)] blur-[120px]" />
        <div className="absolute -bottom-[22%] -right-[12%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle_at_38%_38%,hsl(177_62%_72%_/_0.4),hsl(179_98%_21%_/_0.16)_56%,transparent_76%)] blur-[128px]" />
      </div>

      <TopNav activeSection="settings" />

      <main className="relative z-10 mx-auto flex min-h-[calc(100vh-9rem)] w-full max-w-4xl flex-col items-center justify-center px-6 pb-28 pt-8">
        <div className="w-full max-w-2xl">
          <div className="section-eyebrow mb-4">Configuracion</div>
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-foreground sm:text-4xl">
            Datos de cuenta
          </h1>
          <div className="primary-rule mb-6 mt-3" />
          <p className="mb-10 max-w-xl text-[15px] leading-[1.7] text-muted-foreground">
            Administra la identidad del comercio asociada a esta sesion.
          </p>
        </div>

        <section className="w-full max-w-2xl">
          <div className="space-y-6">
            <div className="grid gap-2 border-b border-border/80 pb-5 sm:grid-cols-[225px_minmax(0,1fr)] sm:items-center">
              <div className="inline-flex items-center gap-2 editorial-label">
                <Mail className="h-3.5 w-3.5 text-primary" />
                Email
              </div>
              <div className="min-w-0 font-mono text-sm text-foreground">
                <span className="block truncate">{email}</span>
              </div>
            </div>

            <div className="grid gap-2 border-b border-border/80 pb-5 sm:grid-cols-[225px_minmax(0,1fr)] sm:items-center">
              <div className="inline-flex items-center gap-2 editorial-label">
                <Lock className="h-3.5 w-3.5 text-primary" />
                Contraseña
              </div>
              <div className="min-w-0 font-mono text-sm tracking-[0.18em] text-muted-foreground">
                ************
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-[225px_minmax(0,1fr)] sm:items-center">
              <div className="flex items-start gap-2">
                <Store className="mt-[1px] h-3.5 w-3.5 shrink-0 text-primary" />
                <div>
                  <div className="editorial-label">Nombre del comercio</div>
                </div>
              </div>
              <div className="flex min-w-0 items-center gap-2">
                {isEditingCommerce ? (
                  <input
                    type="text"
                    value={draftCommerceName}
                    onChange={(e) => setDraftCommerceName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveCommerceName();
                      if (e.key === "Escape") setIsEditingCommerce(false);
                    }}
                    autoFocus
                    className="min-w-0 flex-1 border-b-2 border-primary bg-transparent py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground"
                    placeholder="Nombre del comercio"
                  />
                ) : (
                  <div className="min-w-0 flex-1 py-2 text-sm font-medium text-foreground">
                    <span className="block truncate">{commerceName}</span>
                  </div>
                )}

                {isEditingCommerce ? (
                  <button
                    type="button"
                    onClick={handleSaveCommerceName}
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center text-secondary transition-colors hover:text-secondary/75"
                    aria-label="Guardar nombre del comercio"
                  >
                    <Check className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStartEditing}
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center text-primary transition-colors hover:text-primary/75"
                    aria-label="Editar nombre del comercio"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Settings;
