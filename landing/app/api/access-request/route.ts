import { NextResponse } from "next/server"

const categories = [
  "Electrónica",
  "Electrodomésticos",
  "Informática",
  "Celulares",
  "Otro",
] as const

type Category = (typeof categories)[number]

type AccessRequestPayload = {
  name: string
  email: string
  businessName: string
  websiteOrInstagram: string
  category: Category
}

const maxLengths: Record<keyof AccessRequestPayload, number> = {
  name: 120,
  email: 180,
  businessName: 160,
  websiteOrInstagram: 220,
  category: 40,
}

export const runtime = "nodejs"

export async function POST(request: Request) {
  let body: unknown

  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { error: "No pudimos leer la solicitud." },
      { status: 400 },
    )
  }

  const parsed = parseAccessRequest(body)

  if (!parsed.ok) {
    return NextResponse.json({ error: parsed.error }, { status: 400 })
  }

  try {
    await sendTelegramSignupMessage({
      ...parsed.data,
      createdAt: new Date().toISOString(),
    })

    return NextResponse.json({ ok: true })
  } catch (error) {
    console.error("Failed to send access request to Telegram", error)

    return NextResponse.json(
      { error: "No pudimos enviar la solicitud. Intentá nuevamente." },
      { status: 502 },
    )
  }
}

function parseAccessRequest(value: unknown) {
  if (!value || typeof value !== "object") {
    return { ok: false as const, error: "Completá todos los campos." }
  }

  const source = value as Partial<Record<keyof AccessRequestPayload, unknown>>
  const data = {
    name: normalizeField(source.name, maxLengths.name),
    email: normalizeField(source.email, maxLengths.email),
    businessName: normalizeField(
      source.businessName,
      maxLengths.businessName,
    ),
    websiteOrInstagram: normalizeField(
      source.websiteOrInstagram,
      maxLengths.websiteOrInstagram,
    ),
    category: normalizeField(source.category, maxLengths.category),
  }

  if (
    !data.name ||
    !data.email ||
    !data.businessName ||
    !data.websiteOrInstagram ||
    !data.category
  ) {
    return { ok: false as const, error: "Completá todos los campos." }
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) {
    return { ok: false as const, error: "Usá un email válido." }
  }

  if (!isWebsiteOrInstagram(data.websiteOrInstagram)) {
    return {
      ok: false as const,
      error: "Ingresá una URL válida o un @ de Instagram.",
    }
  }

  if (!categories.includes(data.category as Category)) {
    return { ok: false as const, error: "Elegí una categoría válida." }
  }

  return {
    ok: true as const,
    data: {
      ...data,
      category: data.category as Category,
    },
  }
}

function normalizeField(value: unknown, maxLength: number) {
  return typeof value === "string" ? value.trim().slice(0, maxLength) : ""
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

async function sendTelegramSignupMessage(
  data: AccessRequestPayload & { createdAt: string },
) {
  const botToken = process.env.TELEGRAM_BOT_TOKEN
  const chatId = process.env.TELEGRAM_CHAT_ID
  const messageThreadId = process.env.TELEGRAM_MESSAGE_THREAD_ID

  if (!botToken || !chatId) {
    throw new Error(
      "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variable",
    )
  }

  const text = [
    "New signup!",
    "",
    `Nombre: ${data.name}`,
    `Email: ${data.email}`,
    `Negocio: ${data.businessName}`,
    `Sitio web o Instagram: ${data.websiteOrInstagram}`,
    `Categoría principal: ${data.category}`,
    `Fecha: ${data.createdAt}`,
  ].join("\n")

  const response = await fetch(
    `https://api.telegram.org/bot${botToken}/sendMessage`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chat_id: chatId,
        text,
        ...(messageThreadId
          ? { message_thread_id: Number(messageThreadId) }
          : {}),
      }),
    },
  )

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Telegram API error: ${response.status} ${errorText}`)
  }
}
