"use client"

import { type FormEvent, type ReactNode, useState } from "react"
import Link from "next/link"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"

const categories = [
  "Electrónica",
  "Electrodomésticos",
  "Informática",
  "Celulares",
  "Otro",
] as const

type Category = (typeof categories)[number]

type AccessRequestFormData = {
  name: string
  email: string
  businessName: string
  websiteOrInstagram: string
  category: Category | ""
}

type AccessRequestPayload = AccessRequestFormData & {
  category: Category
}

type Errors = Partial<Record<keyof AccessRequestFormData, string>>

const initialFormData: AccessRequestFormData = {
  name: "",
  email: "",
  businessName: "",
  websiteOrInstagram: "",
  category: "",
}

async function submitAccessRequest(data: AccessRequestPayload) {
  const response = await fetch("/api/access-request", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    const result = (await response.json().catch(() => null)) as {
      error?: string
    } | null

    throw new Error(
      result?.error ?? "No pudimos enviar la solicitud. Intentá nuevamente.",
    )
  }
}

function validateForm(data: AccessRequestFormData) {
  const nextErrors: Errors = {}
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  if (!data.name.trim()) {
    nextErrors.name = "Ingresá tu nombre."
  }

  if (!data.email.trim()) {
    nextErrors.email = "Ingresá tu email."
  } else if (!emailPattern.test(data.email.trim())) {
    nextErrors.email = "Usá un email válido."
  }

  if (!data.businessName.trim()) {
    nextErrors.businessName = "Ingresá el nombre del negocio."
  }

  if (!data.websiteOrInstagram.trim()) {
    nextErrors.websiteOrInstagram = "Ingresá tu sitio web o Instagram."
  } else if (!isWebsiteOrInstagram(data.websiteOrInstagram)) {
    nextErrors.websiteOrInstagram = "Ingresá una URL válida o un @ de Instagram."
  }

  if (!data.category) {
    nextErrors.category = "Elegí una categoría."
  }

  return nextErrors
}

function isWebsiteOrInstagram(value: string) {
  const normalizedValue = value.trim()
  const instagramPattern = /^@[a-zA-Z0-9._]{1,30}$/
  const websitePattern =
    /^(https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(\/[^\s]*)?$/

  return (
    instagramPattern.test(normalizedValue) ||
    websitePattern.test(normalizedValue)
  )
}

export function AccessRequestForm() {
  const [formData, setFormData] = useState(initialFormData)
  const [errors, setErrors] = useState<Errors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)
  const [submitError, setSubmitError] = useState("")

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitError("")

    const nextErrors = validateForm(formData)
    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0 || !formData.category) {
      return
    }

    try {
      setIsSubmitting(true)

      await submitAccessRequest({
        ...formData,
        name: formData.name.trim(),
        email: formData.email.trim(),
        businessName: formData.businessName.trim(),
        websiteOrInstagram: formData.websiteOrInstagram.trim(),
        category: formData.category,
      })

      setIsSubmitted(true)
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : "No pudimos enviar la solicitud. Intentá nuevamente.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSubmitted) {
    return (
      <div className="flex min-h-[31rem] flex-col justify-center rounded-md border border-border bg-card p-7 shadow-[0_30px_80px_-55px_#32077E55] sm:p-8">
        <span className="label-mono-primary">Solicitud recibida</span>
        <h2 className="mt-5 font-serif text-3xl leading-tight tracking-tight text-foreground">
          Gracias. Revisamos tu solicitud manualmente.
        </h2>
        <span className="mt-3 block h-px w-12 bg-primary" />
        <p className="mt-6 text-[15px] leading-relaxed text-muted-foreground">
          Te vamos a escribir para revisar el registro y coordinar el acceso a PrecioCompare.
        </p>
        <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">
          También podés contactarnos en{" "}
          <a
            href="mailto:fs@preciocompare.com"
            className="text-primary transition-colors hover:text-primary/80"
          >
            fs@preciocompare.com
          </a>
          .
        </p>
        <Link
          href="/"
          className="mt-8 inline-flex h-10 w-fit items-center justify-center rounded-sm border border-border bg-card px-5 font-mono text-[10px] uppercase tracking-[0.18em] text-foreground transition-colors hover:border-primary/40 hover:text-primary"
        >
          Volver al inicio
        </Link>
      </div>
    )
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      className="rounded-md border border-border bg-card p-7 shadow-[0_30px_80px_-55px_#32077E55] sm:p-8"
    >
      <div className="flex items-center justify-between gap-4 border-b border-border pb-5">
        <span className="label-mono-primary">Datos de contacto</span>
        <span className="label-mono">Acceso manual</span>
      </div>

      <div className="mt-7 grid gap-5">
        <Field id="name" label="Nombre" error={errors.name}>
          <Input
            id="name"
            required
            value={formData.name}
            onChange={(event) =>
              setFormData((current) => ({
                ...current,
                name: event.target.value,
              }))
            }
            aria-invalid={Boolean(errors.name)}
            placeholder="Tu nombre"
            className="h-11 rounded-sm bg-background/70"
          />
        </Field>

        <Field id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            required
            value={formData.email}
            onChange={(event) =>
              setFormData((current) => ({
                ...current,
                email: event.target.value,
              }))
            }
            aria-invalid={Boolean(errors.email)}
            placeholder="nombre@compania.com"
            className="h-11 rounded-sm bg-background/70"
          />
        </Field>

        <Field id="businessName" label="Negocio" error={errors.businessName}>
          <Input
            id="businessName"
            required
            value={formData.businessName}
            onChange={(event) =>
              setFormData((current) => ({
                ...current,
                businessName: event.target.value,
              }))
            }
            aria-invalid={Boolean(errors.businessName)}
            placeholder="Nombre de tu negocio"
            className="h-11 rounded-sm bg-background/70"
          />
        </Field>

        <Field
          id="websiteOrInstagram"
          label="Sitio web o Instagram"
          error={errors.websiteOrInstagram}
        >
          <Input
            id="websiteOrInstagram"
            required
            value={formData.websiteOrInstagram}
            onChange={(event) =>
              setFormData((current) => ({
                ...current,
                websiteOrInstagram: event.target.value,
              }))
            }
            placeholder="https://... o @usuario"
            className="h-11 rounded-sm bg-background/70"
          />
        </Field>

        <Field id="category" label="Categoría principal" error={errors.category}>
          <Select
            value={formData.category}
            onValueChange={(value) =>
              setFormData((current) => ({
                ...current,
                category: value as Category,
              }))
            }
          >
            <SelectTrigger
              id="category"
              aria-required="true"
              aria-invalid={Boolean(errors.category)}
              className="h-11 w-full rounded-sm bg-background/70"
            >
              <SelectValue placeholder="Elegí una categoría" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((category) => (
                <SelectItem key={category} value={category}>
                  {category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      {submitError ? (
        <p className="mt-5 rounded-sm border border-destructive/20 bg-destructive/5 px-4 py-3 text-[12px] leading-relaxed text-destructive/80">
          {submitError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-7 inline-flex h-11 w-full items-center justify-center rounded-sm bg-primary px-6 font-mono text-[11px] uppercase tracking-[0.18em] text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "Enviando..." : "ENVIAR SOLICITUD"}
      </button>

      <p className="mt-4 text-center text-[12px] leading-relaxed text-muted-foreground">
        Te vamos a contactar por email para coordinar el acceso.
      </p>
    </form>
  )
}

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-foreground/70">
          {label}
        </span>
        {hint ? (
          <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">
            {hint}
          </span>
        ) : null}
      </label>
      {children}
      <span
        className={cn(
          "min-h-4 text-[11px] leading-none text-destructive/80",
          !error && "invisible",
        )}
      >
        {error ?? "Sin error"}
      </span>
    </div>
  )
}
