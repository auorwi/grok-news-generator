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


def build_comparison_card(news_list: list, title: str = "📰 加密快讯对比") -> dict:
    """
    构建原始 vs GPT 优化版本的对比卡片
    
    Args:
        news_list: 新闻列表
        title: 卡片标题
    
    Returns:
        飞书卡片消息体
    """
    elements = []
    
    # 头部时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"⏰ 生成时间：{current_time}"
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
        
        # ========== 新闻标题栏 ==========
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**{emoji} 快讯 {idx}** ｜ 评分: **{total_score}/100** ｜ 来源: {source}"
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
        
        # ========== 原始版本（折叠面板）==========
        original_content = f"**标题**：{original_title}\n\n**内容**：{original_body}"
        elements.append({
            "tag": "collapsible_panel",
            "expanded": False,
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "📄 原始版本（点击展开）"
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
        
        # ========== GPT 优化版本 ==========
        if is_polished and gpt_title and gpt_body:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "✨ **GPT 优化版本**"
                }
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**标题**：{gpt_title}"
                }
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**内容**：{gpt_body}"
                }
            })
        else:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "⚠️ 未优化（分数未达阈值或优化失败）"
                }
            })
        
        # 原文链接按钮
        if link:
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "🔗 查看原文"
                        },
                        "type": "default",
                        "url": link
                    }
                ]
            })
        
        # 分隔线
        if idx < len(news_list):
            elements.append({"tag": "hr"})
    
    # 底部说明
    elements.append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": "💡 原始版本由 Grok 生成 | GPT 优化版本由 GPT-4.1 润色 | 仅供参考"
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
    parser = argparse.ArgumentParser(description="发送新闻到飞书群（原始 vs GPT 对比）")
    parser.add_argument("--file", "-f", required=True, help="新闻 JSON 文件路径")
    parser.add_argument("--threshold", "-t", type=int, default=70, help="分数阈值（默认: 70）")
    parser.add_argument("--title", default="📰 加密快讯对比（原始 vs GPT）", help="卡片标题")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际发送")
    
    args = parser.parse_args()
    
    # 加载新闻
    print(f"📂 加载文件: {args.file}")
    data = load_news(args.file)
    news_list = data.get("news", [])
    
    if not news_list:
        print("❌ 没有找到新闻数据")
        sys.exit(1)
    
    print(f"📊 总共 {len(news_list)} 条新闻")
    
    # 筛选分数 > threshold 的新闻
    filtered_news = []
    for news in news_list:
        score = news.get("score", {})
        total = score.get("total", 0) if isinstance(score, dict) else 0
        if total >= args.threshold:
            filtered_news.append(news)
    
    print(f"✅ 筛选出 {len(filtered_news)} 条分数 >= {args.threshold} 的新闻")
    
    if not filtered_news:
        print("⚠️ 没有符合条件的新闻")
        sys.exit(0)
    
    # 构建卡片
    card = build_comparison_card(filtered_news, args.title)
    
    if args.dry_run:
        print("\n📋 预览模式（不发送）:")
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return
    
    # 发送到飞书
    print("\n📤 发送到飞书...")
    try:
        bot = FeishuBot()
        result = bot.send(card)
        
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            print("✅ 发送成功!")
        else:
            print(f"❌ 发送失败: {result}")
    except Exception as e:
        print(f"❌ 发送出错: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

