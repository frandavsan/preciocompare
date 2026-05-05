"use client"

import { type CSSProperties, useEffect, useRef } from "react"

export function BackgroundBlobs() {
  const backgroundRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handlePointerMove(event: PointerEvent) {
      backgroundRef.current?.style.setProperty(
        "--page-glow-x",
        `${(event.clientX / window.innerWidth) * 100}%`,
      )
      backgroundRef.current?.style.setProperty(
        "--page-glow-y",
        `${(event.clientY / window.innerHeight) * 100}%`,
      )
    }

    window.addEventListener("pointermove", handlePointerMove, { passive: true })

    return () => {
      window.removeEventListener("pointermove", handlePointerMove)
    }
  }, [])

  return (
    <div
      ref={backgroundRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
      style={
        {
          "--page-glow-x": "50%",
          "--page-glow-y": "38%",
        } as CSSProperties
      }
    >
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at var(--page-glow-x) var(--page-glow-y), oklch(0.94 0.05 292 / 0.54), oklch(0.93 0.035 205 / 0.2) 18rem, transparent 36rem)",
        }}
      />
      <div
        className="absolute inset-y-0 left-[-4vw] w-[44vw] opacity-80 blur-3xl"
        style={{
          background:
            "linear-gradient(90deg, oklch(0.84 0.12 300 / 0.58), oklch(0.92 0.04 292 / 0.28) 48%, transparent 100%)",
        }}
      />
      <div
        className="absolute inset-y-0 right-[-4vw] w-[36vw] opacity-55 blur-3xl"
        style={{
          background:
            "linear-gradient(270deg, oklch(0.88 0.07 295 / 0.42), oklch(0.94 0.025 285 / 0.22) 48%, transparent 100%)",
        }}
      />
      <div
        className="absolute right-[-8vw] bottom-[-10vh] h-[70vh] w-[58vw] opacity-75 blur-3xl"
        style={{
          background:
            "radial-gradient(ellipse at bottom right, oklch(0.88 0.08 178 / 0.55), oklch(0.93 0.03 205 / 0.3) 44%, transparent 72%)",
        }}
      />
      <div
        className="absolute left-[-10vw] bottom-[-12vh] h-[55vh] w-[42vw] opacity-50 blur-3xl"
        style={{
          background:
            "radial-gradient(ellipse at bottom left, oklch(0.87 0.09 300 / 0.48), transparent 70%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.2]"
        style={{
          backgroundImage:
            "linear-gradient(to right, oklch(0.74 0.02 260 / 0.16) 1px, transparent 1px), linear-gradient(to bottom, oklch(0.74 0.02 260 / 0.12) 1px, transparent 1px)",
          backgroundSize: "4.5rem 4.5rem",
          maskImage:
            "linear-gradient(to bottom, transparent, black 8%, black 82%, transparent)",
        }}
      />
      <div
        className="absolute inset-x-0 top-0 h-28 opacity-55"
        style={{
          background:
            "linear-gradient(180deg, oklch(1 0 0 / 0.68), transparent)",
        }}
      />
    </div>
  )
}
