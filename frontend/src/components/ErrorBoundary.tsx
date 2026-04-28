import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error:", error, info);
  }

  reset = () => {
    this.setState({ hasError: false });
    window.location.assign("/");
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background paper-texture px-6 text-center">
        <div className="section-eyebrow mb-3">Error inesperado</div>
        <h1 className="mb-2 text-2xl font-bold text-foreground">Algo salio mal</h1>
        <p className="mb-6 max-w-md text-sm text-muted-foreground">
          Ocurrió un error al renderizar la página. Volvé al inicio e intentá de nuevo.
        </p>
        <button
          type="button"
          onClick={this.reset}
          className="bg-primary px-5 py-3 font-mono text-[11px] uppercase tracking-[0.15em] text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Volver al inicio
        </button>
      </div>
    );
  }
}
