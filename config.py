# Grok News Generator Configuration

# ============================================================
# 信息源列表
# ============================================================
NEWS_SOURCES = """
News Media
 @WatcherGuru
 @WuBlockchain
 @Cointelegraph
 @TheBlock__
 @BitcoinNewsCom
 @DecryptMedia
 @BanklessHQ
 @beincrypto
 @Blockworks_
 @Utoday_en
 @CoinGapeMedia
 @BitcoinMagazine
 @CoinDesk
On-chain Analytics
 @ArkhamIntel
 @lookonchain
 @WhaleChart
 @peckshield
 @spotonchain
Exchanges
 @binance
 @OKX
 @BingXOfficial
 @coinbase
Projects / Protocols
 @ethereum
 @solana
 @Uniswap
 @AaveAave
High-Influence KOLs
 @elonmusk
 @cz_binance
 @VitalikButerin
 @saylor
 @APompliano
 @justinsuntron
 @CryptoHayes
"""

# ============================================================
# 新闻写作规则
# ============================================================
NEWS_WRITING_RULES = """
Search and provide short flash news updates on the latest developments in Web3, cryptocurrencies, exchanges, and blockchain published in past 2 hours
Each flash must:
• Start with a concise headline describing the event itself
 • Do not include the source name or media outlet in the headline
Write the body in hard-news style:
• First sentence: state the event, followed by source attribution (e.g., “according to Cointelegraph”, “Wu Blockchain reported”, “data from Spot On Chain shows”)
 • Do not use Twitter handles in attribution — use the source name instead of @handle (e.g., “Wu Blockchain”, not “@WuBlockchain”)
The tone must remain news-neutral:
• No hype, no predictions, no emotional language, no financial advice
 • Use factual attribution language (“data shows”, “analysts noted”, “regulators said”)
Each flash must include the original source link from X (Twitter) or an official article at the end of the update.
 If no meaningful historical context exists, report the news factually and do not add speculation.

"""

# ============================================================
# 评分规则 (1-100分)
# ============================================================
SCORING_RULES = """
## SCORING SYSTEM (1-100 points)

### 1. IMPACT & IMPORTANCE (0-40 points) [WEIGHT INCREASED]
Evaluate the potential impact on price and volatility.
* **Crucial Context**: Adjust score based on Asset Market Cap Tier. (BTC/ETH events > Low Cap events).
* **35-40**: Systemic Shock (ETF Approval, Regulation Ban, Exchange Insolvency, Binace/Coinbase Listing).
* **25-34**: Major Catalyst (Mainnet Launch, >$100M Hack, Partnership with Google/Apple/Visa).
* **10-24**: Moderate Catalyst (Standard Partnership, Features, Local Exchange Listing).
* **0-9**: Noise (Routine maintenance, AMA announcements, opinions).

### 2. SOURCE CREDIBILITY (0-30 points) [REFINED]
* **25-30**: Primary Sources (Official Twitter/Blog of Tier-1 Projects, SEC/Fed Official Statements).
* **20-24**: Top Tier Media/Data (Bloomberg, Wu Blockchain, PeckShield, ZachXBT).
* **10-19**: Standard Crypto Media (CoinDesk, Cointelegraph) or Tier-2 Official Accounts.
* **0-9**: Unverified/Rumors/KOL Opinions without on-chain proof.
* **PENALTY**: If the source is known for FUD or Fake News, score MUST be 0.

### 3. VIRALITY POTENTIAL (0-20 points) [AI ESTIMATION]
*Since real-time metrics might be missing, estimate the POTENTIAL for this news to go viral.*
* **16-20**: High Meme Potential / Emotional Trigger (e.g., "Founder Arrested", "All Time High", "Rug Pull").
* **8-15**: Standard Industry Discussion.
* **0-7**: Boring/Technical/Niche.

### 4. TIMELINESS (0-10 points) [REDUCED WEIGHT]
* **10**: < 15 mins (Breaking)
* **7**: 15 - 60 mins
* **3**: 1 - 4 hours
* **0**: > 4 hours
"""

# ============================================================
# JSON 输出格式
# ============================================================
JSON_OUTPUT_FORMAT = """
You MUST return ONLY this JSON format, don't add any other things:
[
  {
    "title": "Concise headline describing the event",
    "body": "Full news body with source attribution, historical context, and impact analysis",
    "source": "Source name (e.g., Wu Blockchain, Cointelegraph)",
    "link": "Direct URL to the original post/article (must be a real clickable link)",
    "publish_time": "Original publish time in ISO format (will be converted to UTC+8)",
    "score": {
      "importance": 25,
      "authority": 20,
      "trending": 18,
      "timeliness": 15,
      "total": 78
    }
  }
]

IMPORTANT:
- Output 3-5 flash news items, sorted by total score (highest first)
- All content must be in English
- The "link" field MUST contain a real, working URL to the source
- The "publish_time" should be in ISO format like "2024-12-09T15:30:00Z"
- Each dimension score must be an integer within its range
- Total score = importance + authority + trending + timeliness (max 100)
"""


def build_grok_prompt(hours: int = 2) -> str:
    """
    构建完整的 Grok 提示词
    
    Args:
        hours: 时间窗口（小时）
    
    Returns:
        完整的提示词字符串
    """
    return f"""You are a crypto news copywriter.

After **{hours} hours**, provide short flash news updates on the latest developments in **Web3, cryptocurrencies, exchanges, and blockchain**. Each flash must:

{NEWS_WRITING_RULES}

Prioritize reliable information from these verified X accounts:
{NEWS_SOURCES}

Your goal is to deliver clear, authoritative flash news that explains:  
**what happened, what came before, and why it matters — with source attribution in the body using source names instead of Twitter handles.**

---

{SCORING_RULES}

---

{JSON_OUTPUT_FORMAT}
"""



GPT_POLISH_PROMPT = """
Polish the following flash news into a clear, neutral, and professional update. Keep only verified key facts, remove hype, and ensure attribution is accurate. Maintain a hard-news tone, correct grammar, and present the event, actions taken, and financial details in a logical order. Do not add speculation.

## Input
Title: {title}
Body: {body}

## Output Format
Return ONLY this JSON format:
{{{{
  "title": "Clear, neutral headline (max 12 words)",
  "body": "Professional news paragraph with verified facts and proper attribution"
}}}}
"""