import { login, start, type Agent } from "weixin-agent-sdk";

const PY_BASE = process.env.STOCK_ANALYSE_URL ?? "http://stock-analyse:8168";
const TOKEN = process.env.DISPATCH_TOKEN ?? "";

if (!TOKEN) {
  console.error("[wechat-bot] DISPATCH_TOKEN env is required");
  process.exit(1);
}

const agent: Agent = {
  async chat(req) {
    if (!req.text) {
      return { text: "(暂仅支持文本指令，发 /help 查看帮助)" };
    }

    try {
      const r = await fetch(`${PY_BASE}/api/v1/wechat/dispatch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Dispatch-Token": TOKEN,
        },
        body: JSON.stringify({
          conversation_id: req.conversationId,
          text: req.text,
        }),
        signal: AbortSignal.timeout(30_000),
      });

      if (!r.ok) {
        console.error(`[wechat-bot] dispatch HTTP ${r.status}`);
        return { text: `服务暂不可用 (HTTP ${r.status})` };
      }

      const json = (await r.json()) as { data?: { text?: string } };
      return { text: json?.data?.text ?? "(空响应)" };
    } catch (e) {
      console.error("[wechat-bot] dispatch error:", e);
      return { text: "服务繁忙，请稍后再试" };
    }
  },
};

await login();
const bot = start(agent);
console.log("[wechat-bot] started, waiting for messages...");
await bot.wait();
