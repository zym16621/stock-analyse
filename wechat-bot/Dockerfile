FROM node:22-alpine

ENV TZ=Asia/Shanghai

WORKDIR /app

# 仅拷贝依赖描述文件，利用 Docker layer cache
COPY package.json ./

# weixin-agent-sdk 部分依赖可能涉及原生编译（如 silk-wasm），添加构建工具
RUN apk add --no-cache python3 make g++ \
    && npm install --omit=dev --no-fund --no-audit \
    && npm install --save-dev tsx typescript @types/node \
    && apk del make g++

# 拷贝源码
COPY tsconfig.json ./
COPY src ./src

# 登录态持久化目录
VOLUME ["/root/.openclaw"]

CMD ["npx", "tsx", "src/index.ts"]
