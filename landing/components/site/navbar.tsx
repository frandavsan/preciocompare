import Link from "next/link"

const navLinks = [
  { label: "Producto", href: "/#producto" },
  { label: "Funcionalidades", href: "/#funcionalidades" },
  { label: "Demo", href: "/#demo" },
]

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ??
  (process.env.NODE_ENV === "production"
    ? "https://app.preciocompare.com"
    : "http://localhost:8080")

export function Navbar({ showAccessCta = true }: { showAccessCta?: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 lg:px-10">
        <Link href="/" className="flex items-center">
          <span className="font-serif text-xl tracking-tight text-primary">
            PrecioCompare
          </span>
        </Link>

        <nav className="hidden items-center gap-10 md:flex">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[13px] text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-6">
          <a
            href={APP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:text-primary"
          >
            Ingresar
          </a>
          {showAccessCta ? (
            <Link
              href="/solicitar-acceso"
              className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary transition-colors hover:text-primary/80"
            >
              Solicitar acceso
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  )
}
