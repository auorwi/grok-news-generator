#!/usr/bin/env python3
"""
发送新闻到飞书群 - 支持原始版本与 GPT 优化版本对比
"""

import json
import sys
import argparse
from datetime import datetime
from feishu_bot import FeishuBot


def load_news(file_path: str) -> dict:
    """加载新闻 JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_score_emoji(total: int) -> str:
    """根据分数返回 emoji"""
    if total >= 80:
        return "🔥"
    elif total >= 70:
        return "⚡"
    elif total >= 60:
        return "📢"
    else:
        return "📌"


def build_comparison_card(news_list: list, title: str = "📰 Crypto Flash News") -> dict:
    """
    Build Original vs GPT comparison card
    
    Args:
        news_list: News list
        title: Card title
    
    Returns:
        Feishu card message body
    """
    elements = []
    
    # Header time
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"⏰ Generated: {current_time}"
        }
    })
    elements.append({"tag": "hr"})
    
    # 遍历新闻
    for idx, news in enumerate(news_list, 1):
        score = news.get("score", {})
        total_score = score.get("total", 0) if isinstance(score, dict) else score
        is_polished = news.get("polished", False)
        
        emoji = get_score_emoji(total_score)
        source = news.get("source", "Unknown")
        link = news.get("link", "")
        publish_time = news.get("publish_time", "")
        
        # 原始内容
        original_title = news.get("title", "")
        original_body = news.get("body", "")
        
        # GPT 优化内容
        gpt_title = news.get("gpt_title", "")
        gpt_body = news.get("gpt_body", "")
        
        # ========== News header ==========
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{emoji} Flash {idx}** | Score: **{total_score}/100** | Source: {source}"
            }
        })
        
        # 发布时间
        if publish_time:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"🕐 {publish_time}"
                }
            })
        
        # ========== Original version (collapsible) ==========
        original_content = f"**Title**: {original_title}\n\n**Content**: {original_body}"
        elements.append({
            "tag": "collapsible_panel",
            "expanded": False,
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📄 Original Version (Click to expand)"
                }
            },
            "border": {
                "color": "grey"
            },
            "vertical_spacing": "8px",
            "padding": "8px 8px 8px 8px",
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": original_content
                    }
                }
            ]
        })
        
        # ========== GPT Polished Version ==========
        if is_polished and gpt_title and gpt_body:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "✨ **GPT Polished Version**"
                }
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Title**: {gpt_title}"
                }
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Content**: {gpt_body}"
                }
            })
        else:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "⚠️ Not polished (Below threshold or polish failed)"
                }
            })
        
        # Source link button
        if link:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "🔗 View Source"
                        },
                        "type": "default",
                        "url": link
                    }
                ]
            })
        
        # Divider
        if idx < len(news_list):
            elements.append({"tag": "hr"})
    
    # Footer note
    elements.append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": "💡 Original by Grok | Polished by GPT | For reference only"
            }
        ]
    })
    
    # 计算平均分决定颜色
    scores = [n.get("score", {}).get("total", 0) if isinstance(n.get("score"), dict) else 0 for n in news_list]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    if avg_score >= 80:
        color = "red"
    elif avg_score >= 70:
        color = "orange"
    else:
        color = "blue"
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": color
            },
            "elements": elements
        }
    }
    
    return card


def main():
    parser = argparse.ArgumentParser(description="Send news to Feishu (Original vs GPT comparison)")
    parser.add_argument("--file", "-f", required=True, help="News JSON file path")
    parser.add_argument("--threshold", "-t", type=int, default=70, help="Score threshold (default: 70)")
    parser.add_argument("--title", default="📰 Crypto Flash News", help="Card title")
    parser.add_argument("--retries", "-r", type=int, default=3, help="Max retry attempts (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't send")
    
    args = parser.parse_args()
    
    # Load news
    print(f"📂 Loading file: {args.file}")
    data = load_news(args.file)
    news_list = data.get("news", [])
    
    if not news_list:
        print("❌ No news data found")
        sys.exit(1)
    
    print(f"📊 Total: {len(news_list)} news items")
    
    # Filter by score threshold
    filtered_news = []
    for news in news_list:
        score = news.get("score", {})
        total = score.get("total", 0) if isinstance(score, dict) else 0
        if total >= args.threshold:
            filtered_news.append(news)
    
    print(f"✅ Filtered: {len(filtered_news)} news with score >= {args.threshold}")
    
    if not filtered_news:
        print("⚠️ No news meets the threshold")
        sys.exit(0)
    
    # Build card
    card = build_comparison_card(filtered_news, args.title)
    
    if args.dry_run:
        print("\n📋 Preview mode (not sending):")
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return
    
    # Send to Feishu with retry
    print(f"\n📤 Sending to Feishu (max {args.retries} attempts)...")
    bot = FeishuBot()
    
    for attempt in range(1, args.retries + 1):
        try:
            print(f"   Attempt {attempt}/{args.retries}...")
            result = bot.send(card)
            
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("✅ Send successful!")
                return
            else:
                print(f"   ❌ Attempt {attempt} failed: {result}")
                if attempt < args.retries:
                    import time
                    time.sleep(2)
        except Exception as e:
            print(f"   ❌ Attempt {attempt} error: {str(e)}")
            if attempt < args.retries:
                import time
                time.sleep(2)
    
    print(f"❌ Send failed after {args.retries} attempts")
    sys.exit(1)


if __name__ == "__main__":
    main()

