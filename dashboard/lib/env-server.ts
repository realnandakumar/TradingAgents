import fs from "fs";
import path from "path";

import { repoRootFromDashboard } from "@/lib/desk-cli-server";

const PROVIDER_API_KEY_ENV: Record<string, string | null> = {
  openai: "OPENAI_API_KEY",
  anthropic: "ANTHROPIC_API_KEY",
  google: "GOOGLE_API_KEY",
  azure: "AZURE_OPENAI_API_KEY",
  xai: "XAI_API_KEY",
  deepseek: "DEEPSEEK_API_KEY",
  qwen: "DASHSCOPE_API_KEY",
  "qwen-cn": "DASHSCOPE_CN_API_KEY",
  glm: "ZHIPU_API_KEY",
  "glm-cn": "ZHIPU_CN_API_KEY",
  minimax: "MINIMAX_API_KEY",
  "minimax-cn": "MINIMAX_CN_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
  ollama: null,
};

function parseDotEnv(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function loadRootEnv(): Record<string, string> {
  const envPath = path.join(repoRootFromDashboard(), ".env");
  try {
    if (!fs.existsSync(envPath)) return {};
    return parseDotEnv(fs.readFileSync(envPath, "utf-8"));
  } catch {
    return {};
  }
}

export function envValue(key: string): string | undefined {
  return process.env[key] ?? loadRootEnv()[key];
}

export function llmProvider(): string {
  return (
    envValue("TRADINGAGENTS_LLM_PROVIDER") ??
    envValue("LLM_PROVIDER") ??
    "openai"
  ).toLowerCase();
}

export function rootEnvForSpawn(): Record<string, string> {
  return loadRootEnv();
}

export function checkLlmApiKey(): {
  configured: boolean;
  provider: string;
  envVar: string | null;
  message: string;
} {
  const provider = llmProvider();
  const envVar = PROVIDER_API_KEY_ENV[provider] ?? null;
  if (envVar === null) {
    return {
      configured: true,
      provider,
      envVar: null,
      message: `Provider "${provider}" does not require an API key.`,
    };
  }
  const value = envValue(envVar);
  const configured = Boolean(value?.trim());
  return {
    configured,
    provider,
    envVar,
    message: configured
      ? `${envVar} is set for ${provider}.`
      : `Set ${envVar} in the repo root .env before running AI commands.`,
  };
}
