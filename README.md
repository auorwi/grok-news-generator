# Grok 加密货币热点快讯生成器

基于 Grok AI + Web Search 的加密货币实时热点新闻生成工具，支持智能去重、GPT 润色和飞书群推送。

## 功能特性

| 功能 | 说明 |
|------|------|
| 🔍 **实时搜索** | 使用 Grok + Web Search 实时获取加密货币热点 |
| 📊 **智能评分** | 四维度评分系统（重要性/权威性/热度/及时性），满分100分 |
| 🔄 **智能去重** | 基于标题相似度 + 链接去重，避免重复推送 |
| ✨ **GPT 润色** | 对高分新闻（≥75）自动用 GPT 优化标题和内容 |
| 📤 **飞书推送** | 自动推送到飞书群聊，展示原始 vs 优化对比 |
| 💾 **JSON 存储** | 结构化保存所有新闻数据 |

## 安装配置

### 1. 安装依赖

```bash
pip install requests python-dotenv
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# OpenRouter API Key（必需）
open_router_key=your_openrouter_api_key

# 飞书机器人（可选，用于推送）
feishu_webhook_url=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
feishu_webhook_key=your_webhook_secret
```

## 使用方法

### 基础用法

```bash
# 默认运行（获取最近2小时热点，75分以上优化并推送飞书）
python grok_news_generator.py

# 获取最近1小时的热点
python grok_news_generator.py --hours 1

# 调整优化阈值（只优化80分以上）
python grok_news_generator.py --polish-threshold 80
```

### 跳过某些步骤

```bash
# 跳过去重（输出所有新闻）
python grok_news_generator.py --no-dedup

# 跳过 GPT 润色
python grok_news_generator.py --no-polish

# 跳过飞书推送
python grok_news_generator.py --no-feishu

# 不保存文件
python grok_news_generator.py --no-save
```

### 调试模式

```bash
python grok_news_generator.py --debug
```

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--hours` | 2 | 时间窗口（小时） |
| `--max-results` | 20 | Web Search 最大结果数 |
| `--timeout` | 120 | API 请求超时（秒） |
| `--output` | `output/news_YYYYMMDD_HHMM.json` | 输出文件路径 |
| `--polish-threshold` | 75 | GPT 润色阈值（分数） |
| `--dedup-threshold` | 0.7 | 标题相似度阈值（0-1） |
| `--dedup-hours` | 24 | 去重历史窗口（小时） |
| `--feishu-title` | `📰 加密快讯` | 飞书卡片标题 |
| `--no-dedup` | - | 禁用去重 |
| `--no-polish` | - | 禁用 GPT 润色 |
| `--no-feishu` | - | 禁用飞书推送 |
| `--no-save` | - | 不保存文件 |
| `--debug` | - | 调试模式 |

## 评分规则

新闻评分满分 100 分，由四个维度组成：

| 维度 | 满分 | 说明 |
|------|------|------|
| **IMPACT & IMPORTANCE** | 40分 | 事件对市场的影响程度 |
| **SOURCE CREDIBILITY** | 30分 | 信息来源的可信度 |
| **VIRALITY POTENTIAL** | 20分 | 传播潜力和热度 |
| **TIMELINESS** | 10分 | 新闻的时效性 |

### 分数等级

| 等级 | 分数 | 处理方式 |
|------|------|----------|
| 🔥 CRITICAL | 80-100 | GPT 优化 + 飞书推送 |
| ⚡ HIGH | 75-79 | GPT 优化 + 飞书推送 |
| 📢 MEDIUM | 60-74 | 仅保存 |
| 📌 LOW | < 60 | 仅保存 |

## 输出格式

### JSON 文件结构

```json
{
  "generated_at": "2024-12-09 18:30:00 UTC+8",
  "news_count": 5,
  "polished_count": 2,
  "polish_model": "openai/gpt-5.1",
  "news": [
    {
      "title": "原始标题",
      "body": "原始内容",
      "source": "Wu Blockchain",
      "link": "https://x.com/...",
      "publish_time": "2024-12-09 17:30:00 UTC+8",
      "score": {
        "importance": 35,
        "authority": 24,
        "trending": 18,
        "timeliness": 8,
        "total": 85
      },
      "polished": true,
      "gpt_title": "GPT 优化后的标题",
      "gpt_body": "GPT 优化后的内容"
    }
  ]
}
```

## 文件结构

```
grok_news/
├── output/                     # 新闻输出目录
│   └── news_YYYYMMDD_HHMM.json
├── grok_news_generator.py      # 主程序
├── config.py                   # 配置和提示词
├── news_dedup.py               # 去重模块
├── feishu_bot.py               # 飞书推送模块
├── send_news_to_feishu.py      # 独立飞书发送脚本
├── news_history.json           # 去重历史记录
├── hotspot_tracker.py          # 旧版热点追踪器
└── .env                        # 环境变量配置
```

## 信息源

优先监控的信息源：

**新闻媒体**
- @WuBlockchain, @Cointelegraph, @TheBlock__, @CoinDesk, @DecryptMedia

**链上分析**
- @ArkhamIntel, @lookonchain, @PeckShield, @spotonchain

**交易所**
- @binance, @OKX, @coinbase

**KOL**
- @elonmusk, @cz_binance, @VitalikButerin, @saylor

## 工作流程

```
1. 调用 Grok API (Web Search)
   ↓
2. 生成新闻列表 + 评分
   ↓
3. 去重过滤（与历史记录比对）
   ↓
4. GPT 润色（≥75分）
   ↓
5. 保存 JSON 文件
   ↓
6. 推送飞书（≥75分）
```

## 示例输出

```
🚀 Starting Grok Flash News Generator
   Time window: 2 hours
   Dedup: Enabled (threshold: 0.7)
   GPT Polish: Enabled (>= 75)
   Feishu: Enabled (only >= 75)

📊 Generated 5 news items
🔄 Deduplicating...
   ✅ New: 4 | Duplicates: 1

✨ Polishing 2 high-score news (>= 75) with GPT...
   ✅ Successfully polished: 2/2

📤 Sending 2 news to Feishu...
✅ 飞书发送成功!

==================================================
📋 Summary
==================================================
   Generated: 5
   Duplicates removed: 1
   New news: 4
   GPT polished: 2
   Sent to Feishu: 2
==================================================
```

## n8n 工作流

项目包含一个 n8n 工作流文件 `n8n_workflow.json`，可以直接导入 n8n 使用。

### 工作流节点

```
[每2小时触发] → [构建提示词] → [调用 Grok API] → [解析新闻列表]
                                                    ↓
                    ┌───────────────────────────────┴───────────────────────────────┐
                    ↓                                                               ↓
            [筛选高分 ≥75]                                                    [低分 <75]
                    ↓                                                               ↓
              [GPT 润色]                                                            │
                    ↓                                                               │
            [解析润色结果]                                                          │
                    └───────────────────────┬───────────────────────────────────────┘
                                            ↓
                                      [合并新闻]
                                            ↓
                                    [构建飞书卡片]
                                            ↓
                                     [发送到飞书]
```

### 导入步骤

1. 打开 n8n 编辑器
2. 点击右上角 **...** → **Import from File**
3. 选择 `n8n_workflow.json`
4. 配置凭证：
   - 创建 **HTTP Header Auth** 凭证，命名为 `OpenRouter API`
   - Header Name: `Authorization`
   - Header Value: `Bearer your_openrouter_api_key`
5. 设置环境变量：
   - `FEISHU_WEBHOOK_URL`: 飞书机器人 Webhook 地址
   - `FEISHU_WEBHOOK_SECRET`: 飞书机器人签名密钥（可选，如果启用了签名验证）

### 触发方式

- **定时触发**: 默认每 2 小时执行一次
- **手动触发**: 在 n8n 编辑器中点击 Execute Workflow

## License

MIT

