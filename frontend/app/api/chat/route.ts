import { GoogleGenerativeAI } from "@google/generative-ai";
import { NextResponse } from "next/server";
import {
  buildBusinessContext,
  CHAT_SYSTEM_PROMPT,
} from "@/lib/business-context";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_HISTORY = 12;
const MAX_MESSAGE_LENGTH = 2000;

type ChatRole = "user" | "assistant";

interface ChatMessage {
  role: ChatRole;
  content: string;
}

function getClientErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    if (/API key|GEMINI/i.test(error.message)) {
      return "AI service is not configured. Set GEMINI_API_KEY and restart the dashboard.";
    }
    if (/quota|rate|429/i.test(error.message)) {
      return "The AI service is temporarily rate-limited. Please try again in a moment.";
    }
    return error.message;
  }
  return "Failed to generate a response.";
}

export async function POST(request: Request) {
  try {
    const apiKey = process.env.GEMINI_API_KEY?.trim();
    if (!apiKey) {
      return NextResponse.json(
        {
          error:
            "GEMINI_API_KEY is not set. Add it to your .env and restart the frontend container.",
        },
        { status: 503 }
      );
    }

    const body = (await request.json()) as {
      message?: unknown;
      history?: unknown;
    };

    const message =
      typeof body.message === "string" ? body.message.trim() : "";
    if (!message) {
      return NextResponse.json(
        { error: "Message is required." },
        { status: 400 }
      );
    }
    if (message.length > MAX_MESSAGE_LENGTH) {
      return NextResponse.json(
        { error: `Message must be under ${MAX_MESSAGE_LENGTH} characters.` },
        { status: 400 }
      );
    }

    const history: ChatMessage[] = Array.isArray(body.history)
      ? body.history
          .filter(
            (item): item is ChatMessage =>
              !!item &&
              typeof item === "object" &&
              (item.role === "user" || item.role === "assistant") &&
              typeof item.content === "string" &&
              item.content.trim().length > 0
          )
          .slice(-MAX_HISTORY)
          .map((item) => ({
            role: item.role,
            content: item.content.trim().slice(0, MAX_MESSAGE_LENGTH),
          }))
      : [];

    let businessData: string;
    try {
      businessData = buildBusinessContext();
    } catch (error) {
      return NextResponse.json(
        {
          error:
            error instanceof Error
              ? error.message
              : "Business data files are missing. Run the analytics pipeline first.",
        },
        { status: 503 }
      );
    }

    const modelName =
      process.env.GEMINI_MODEL?.trim() || "gemini-2.5-flash";
    const temperature = Number(process.env.GEMINI_TEMPERATURE ?? "0.3");
    const maxOutputTokens = Number(
      process.env.GEMINI_MAX_OUTPUT_TOKENS ?? "2048"
    );

    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({
      model: modelName,
      systemInstruction: `${CHAT_SYSTEM_PROMPT}\n\nBUSINESS_DATA:\n${businessData}`,
      generationConfig: {
        temperature: Number.isFinite(temperature) ? temperature : 0.3,
        maxOutputTokens: Number.isFinite(maxOutputTokens)
          ? maxOutputTokens
          : 2048,
      },
    });

    const chat = model.startChat({
      history: history.map((item) => ({
        role: item.role === "assistant" ? "model" : "user",
        parts: [{ text: item.content }],
      })),
    });

    const result = await chat.sendMessage(message);
    const reply = result.response.text()?.trim();

    if (!reply) {
      return NextResponse.json(
        { error: "The model returned an empty response. Please try again." },
        { status: 502 }
      );
    }

    return NextResponse.json({
      reply,
      model: modelName,
    });
  } catch (error) {
    console.error("[api/chat]", error);
    return NextResponse.json(
      { error: getClientErrorMessage(error) },
      { status: 500 }
    );
  }
}
