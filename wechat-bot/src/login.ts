// 仅用于首次扫码登录，登录态会持久化到 ~/.openclaw/
import { login } from "weixin-agent-sdk";

await login();
console.log("[wechat-bot] login completed, you can now run `pnpm start`");
