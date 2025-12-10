#!/usr/bin/env python3
"""
Grok Crypto Flash News Generator
Uses OpenRouter API with Grok-4.1-fast model to generate cryptocurrency flash news
"""

import os
import sys
import json
import re
import argparse
import requests
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Import prompt builder from config
from config import build_grok_prompt, GPT_POLISH_PROMPT
from news_dedup import NewsDeduplicator
from feishu_bot import FeishuBot

# API Configuration
OPENROUTER_API = "https://openrouter.ai/api/v1/responses"
OPENROUTER_CHAT_API = "https://openrouter.ai/api/v1/chat/completions"
GROK_MODEL = "x-ai/grok-4.1-fast"
GPT_MODEL = "openai/gpt-5.1"

# Score threshold for GPT polishing
POLISH_SCORE_THRESHOLD = 70

# Default Parameters
DEFAULT_MAX_RESULTS = 20
DEFAULT_TIMEOUT = 120
DEFAULT_HOURS = 2
OUTPUT_DIR = "output"  # 输出目录

# UTC+8 Timezone
UTC_PLUS_8 = timezone(timedelta(hours=8))


def get_api_key() -> str:
    """Get OpenRouter API Key from environment variables"""
    load_dotenv()
    key = os.getenv("open_router_key") or os.getenv("OPENROUTER_API_KEY")
    if not key:
        print("❌ Error: API Key not found", file=sys.stderr)
        print("Please set open_router_key or OPENROUTER_API_KEY in .env file", file=sys.stderr)
        sys.exit(1)
    return key




def convert_to_utc8(time_str: str) -> str:
    """Convert time string to UTC+8 format"""
    if not time_str:
        return datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d %H:%M:%S UTC+8")
    
    try:
        # Try parsing ISO format
        if 'Z' in time_str:
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        elif '+' in time_str or '-' in time_str[-6:]:
            dt = datetime.fromisoformat(time_str)
        else:
            # Assume UTC if no timezone
            dt = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc)
        
        # Convert to UTC+8
        dt_utc8 = dt.astimezone(UTC_PLUS_8)
        return dt_utc8.strftime("%Y-%m-%d %H:%M:%S UTC+8")
    except Exception:
        # Return original if parsing fails
        return time_str


def get_total_score(news: Dict) -> int:
    """Extract total score from news item for sorting"""
    score = news.get('score', {})
    if isinstance(score, dict):
        return score.get('total', 0)
    elif isinstance(score, (int, float)):
        return int(score)
    return 0


def polish_with_gpt(
    api_key: str,
    title: str,
    body: str,
    timeout: int = 60,
    debug: bool = False
) -> Optional[Dict[str, str]]:
    """
    Use GPT-4.1 to polish title and body
    Only sends title and body to the API, returns polished version
    """
    # Build prompt with only title and body
    prompt = GPT_POLISH_PROMPT.format(title=title, body=body)
    
    payload = {
        "model": GPT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        resp = requests.post(
            OPENROUTER_CHAT_API,
            headers=headers,
            data=json.dumps(payload),
            timeout=timeout
        )
        resp.raise_for_status()
        response = resp.json()
        
        # Extract content
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        if debug:
            print(f"🐛 GPT Response: {content[:200]}...")
        
        # Parse JSON response
        result = parse_gpt_polish_response(content)
        return result
        
    except Exception as e:
        if debug:
            print(f"🐛 GPT polish error: {str(e)}")
        return None


def parse_gpt_polish_response(text: str) -> Optional[Dict[str, str]]:
    """Parse GPT polish response to extract title and body"""
    if not text:
        return None
    
    # Try direct JSON parse
    try:
        result = json.loads(text)
        if 'title' in result and 'body' in result:
            return result
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            result = json.loads(text[start:end+1])
            if 'title' in result and 'body' in result:
                return result
        except json.JSONDecodeError:
            pass
    
    return None


def polish_high_score_news(
    api_key: str,
    news_list: List[Dict],
    threshold: int = POLISH_SCORE_THRESHOLD,
    debug: bool = False
) -> Tuple[List[Dict], int]:
    """
    Polish news items with score >= threshold using GPT-4.1
    Preserves original content and adds polished version
    """
    polished_count = 0
    
    for news in news_list:
        total_score = get_total_score(news)
        
        if total_score >= threshold:
            title = news.get('title', '')
            body = news.get('body', '')
            
            if title and body:
                print(f"   ✨ Polishing: {title[:50]}... (Score: {total_score})")
                
                # Call GPT to polish
                polished = polish_with_gpt(
                    api_key=api_key,
                    title=title,
                    body=body,
                    debug=debug
                )
                
                if polished:
                    # Keep original title/body, add gpt_title/gpt_body
                    news['gpt_title'] = polished.get('title', '')
                    news['gpt_body'] = polished.get('body', '')
                    news['polished'] = True
                    polished_count += 1
                    print(f"      ✅ Polished successfully")
                else:
                    news['gpt_title'] = ""
                    news['gpt_body'] = ""
                    news['polished'] = False
                    print(f"      ⚠️ Polish failed, keeping original")
        else:
            # Below threshold: no GPT optimization
            news['polished'] = False
            news['gpt_title'] = ""
            news['gpt_body'] = ""
    
    return news_list, polished_count


def process_news_list(news_list: List[Dict]) -> List[Dict]:
    """Process news list: convert times to UTC+8 and sort by score"""
    for news in news_list:
        if 'publish_time' in news:
            news['publish_time'] = convert_to_utc8(news['publish_time'])
    
    # Sort by total score (highest first)
    news_list.sort(key=get_total_score, reverse=True)
    return news_list


def generate_news(
    api_key: str,
    prompt: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout: int = DEFAULT_TIMEOUT,
    debug: bool = False
) -> Optional[List[Dict[str, Any]]]:
    """Call Grok API to generate flash news"""
    
    print("=" * 60)
    print("📰 Grok Crypto Flash News Generator")
    print("=" * 60)
    print(f"   Model: {GROK_MODEL}")
    print(f"   Web Search Results: {max_results}")
    print(f"   Timeout: {timeout}s")
    print("-" * 60)
    
    # Build request
    payload = {
        "model": GROK_MODEL,
        "input": prompt,
        "max_output_tokens": 6000,
        "plugins": [{"id": "web", "max_results": max_results}]
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    print("📡 Calling Grok API (with Web Search)...")
    
    try:
        resp = requests.post(
            OPENROUTER_API,
            headers=headers,
            data=json.dumps(payload),
            timeout=timeout
        )
        resp.raise_for_status()
        response = resp.json()
        
        # Debug mode: save response
        if debug:
            debug_file = f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(response, f, indent=2, ensure_ascii=False)
            print(f"🐛 Debug: Response saved to {debug_file}")
        
        # Extract text content
        text = extract_text_from_response(response, debug)
        if not text:
            return None
        
        # Parse JSON
        result = parse_json_response(text, debug)
        
        # Print token stats
        usage = response.get("usage", {})
        if usage:
            print(f"📊 Tokens: Input {usage.get('input_tokens', 'N/A')} | "
                  f"Output {usage.get('output_tokens', 'N/A')} | "
                  f"Total {usage.get('total_tokens', 'N/A')}")
        
        return result
        
    except requests.HTTPError as e:
        print(f"❌ HTTP Error: {e.response.status_code}", file=sys.stderr)
        print(f"   Response: {e.response.text[:500]}", file=sys.stderr)
        return None
    except requests.Timeout:
        print(f"❌ Request timeout ({timeout}s)", file=sys.stderr)
        return None
    except requests.RequestException as e:
        print(f"❌ Network error: {str(e)}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Unknown error: {str(e)}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc()
        return None


def extract_text_from_response(response: Dict, debug: bool = False) -> Optional[str]:
    """Extract text content from API response"""
    msg = next(
        (o for o in response.get("output", []) if o.get("type") == "message"),
        None
    )
    if not msg:
        print("❌ Error: Message content not found", file=sys.stderr)
        return None
    
    out = next(
        (c for c in msg.get("content", []) if c.get("type") == "output_text"),
        None
    )
    if not out:
        print("❌ Error: Output text not found", file=sys.stderr)
        return None
    
    text = out.get("text", "")
    
    if debug:
        print(f"🐛 Text length: {len(text)} chars")
        print(f"🐛 Preview: {text[:300]}...")
    
    return text


def parse_json_response(text: str, debug: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Parse JSON from text response"""
    if not text:
        return None
    
    # Method 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return [result] if isinstance(result, dict) else None
    except json.JSONDecodeError:
        pass
    
    # Method 2: Extract ```json code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end != -1:
            json_text = text[start:end].strip()
            try:
                result = json.loads(json_text)
                if isinstance(result, list):
                    return result
                return [result] if isinstance(result, dict) else None
            except json.JSONDecodeError:
                if debug:
                    print("🐛 Code block parse failed")
    
    # Method 3: Find JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        json_text = text[start:end+1]
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            # Clean trailing commas
            cleaned = re.sub(r',(\s*[}\]])', r'\1', json_text)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
    
    # Method 4: Find JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_text = text[start:end+1]
        try:
            result = json.loads(json_text)
            return [result] if isinstance(result, dict) else None
        except json.JSONDecodeError:
            cleaned = re.sub(r',(\s*[}\]])', r'\1', json_text)
            try:
                result = json.loads(cleaned)
                return [result] if isinstance(result, dict) else None
            except json.JSONDecodeError:
                if debug:
                    print(f"🐛 JSON parse failed, text length: {len(json_text)}")
    
    print("❌ Unable to parse JSON response", file=sys.stderr)
    if debug:
        print(f"🐛 Raw text:\n{text[:500]}...", file=sys.stderr)
    return None


def format_score(score: Any) -> str:
    """Format score for display"""
    if isinstance(score, dict):
        total = score.get('total', 'N/A')
        return f"{total}/100"
    elif isinstance(score, (int, float)):
        return f"{score}/100"
    else:
        return str(score)


def format_score_details(score: Any) -> str:
    """Format detailed score breakdown"""
    if not isinstance(score, dict):
        return ""
    
    parts = []
    if 'importance' in score:
        parts.append(f"Importance:{score['importance']}/30")
    if 'authority' in score:
        parts.append(f"Authority:{score['authority']}/25")
    if 'trending' in score:
        parts.append(f"Trending:{score['trending']}/25")
    if 'timeliness' in score:
        parts.append(f"Timeliness:{score['timeliness']}/20")
    
    return " | ".join(parts)


def get_score_level(score: Any) -> str:
    """Get score level emoji and label"""
    total = 0
    if isinstance(score, dict):
        total = score.get('total', 0)
    elif isinstance(score, (int, float)):
        total = score
    
    if total >= 80:
        return "🔥 CRITICAL"
    elif total >= 60:
        return "⚡ HIGH"
    elif total >= 40:
        return "📢 MEDIUM"
    else:
        return "📌 LOW"


def print_news_summary(news_list: List[Dict[str, Any]]):
    """Print news summary"""
    print("\n" + "=" * 70)
    print("📰 Flash News Summary")
    print("=" * 70)
    
    current_time = datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d %H:%M:%S UTC+8")
    print(f"⏰ Generated at: {current_time}")
    
    polished_count = sum(1 for n in news_list if n.get('polished'))
    print(f"\n🔥 Total: {len(news_list)} news items ({polished_count} polished)\n")
    
    for i, news in enumerate(news_list, 1):
        score = news.get('score', {})
        score_level = get_score_level(score)
        is_polished = news.get('polished', False)
        
        print("-" * 70)
        polish_tag = " ✨[POLISHED]" if is_polished else ""
        print(f"【{i}】{news.get('title', 'N/A')}{polish_tag}")
        print(f"    {score_level} | Score: {format_score(score)} | "
              f"Source: {news.get('source', 'N/A')}")
        print(f"    Time: {news.get('publish_time', 'N/A')}")
        
        # Score breakdown
        score_details = format_score_details(score)
        if score_details:
            print(f"    📊 {score_details}")
        
        # Show original body
        body = news.get('body', '')
        if body:
            display_body = body[:200] + "..." if len(body) > 200 else body
            print(f"\n    📝 {display_body}")
        
        # Show GPT polished version if available
        if is_polished and news.get('gpt_title'):
            print(f"\n    ✨ [GPT Title]: {news.get('gpt_title', '')}")
            gpt_body = news.get('gpt_body', '')
            if gpt_body:
                display_gpt = gpt_body[:150] + "..." if len(gpt_body) > 150 else gpt_body
                print(f"    ✨ [GPT Body]: {display_gpt}")
        
        link = news.get('link', '')
        if link:
            print(f"\n    🔗 {link}")
        print()
    
    print("=" * 70)


def save_news(news_list: List[Dict[str, Any]], output_file: str):
    """Save news to file with both original and polished content"""
    polished_count = sum(1 for n in news_list if n.get('polished'))
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_data = {
        "generated_at": datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d %H:%M:%S UTC+8"),
        "news_count": len(news_list),
        "polished_count": polished_count,
        "polish_model": GPT_MODEL if polished_count > 0 else None,
        "news": news_list
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved to: {output_file}")
    
    # Summary of what's saved
    if polished_count > 0:
        print(f"   📦 Contains: {polished_count} polished items (with gpt_title & gpt_body)")


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


def build_feishu_card(news_list: List[Dict], title: str = "📰 Crypto Flash News", polish_threshold: int = 75) -> Dict:
    """
    Build Feishu card message (Original vs GPT comparison)
    
    Args:
        news_list: News list
        title: Card title
        polish_threshold: Score threshold for GPT polishing
    
    Returns:
        Feishu card message body
    """
    elements = []
    
    # Sort news by score (highest first)
    sorted_news = sorted(news_list, key=lambda x: x.get("score", {}).get("total", 0) if isinstance(x.get("score"), dict) else 0, reverse=True)
    
    # Header time
    current_time = datetime.now(UTC_PLUS_8).strftime("%Y-%m-%d %H:%M")
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"⏰ Generated: {current_time} (UTC+8)"
        }
    })
    elements.append({"tag": "hr"})
    
    # Iterate news
    for idx, news in enumerate(sorted_news, 1):
        score = news.get("score", {})
        total_score = score.get("total", 0) if isinstance(score, dict) else 0
        is_polished = news.get("polished", False)
        
        emoji = get_score_emoji(total_score)
        source = news.get("source", "Unknown")
        link = news.get("link", "")
        publish_time = news.get("publish_time", "")
        
        # Original content
        original_title = news.get("title", "")
        original_body = news.get("body", "")
        
        # GPT polished content
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
        
        # Publish time
        if publish_time:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"🕐 {publish_time}"
                }
            })
        
        # ========== Check if polished ==========
        if is_polished and gpt_title and gpt_body:
            # Has GPT polished version - show original in collapsible panel
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
            
            # GPT Polished Version
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
            # No GPT version - show original directly (no collapsible)
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⚠️ *Score below {polish_threshold}, generated by Grok directly*"
                }
            })
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Title**: {original_title}"
                }
            })
            # Truncate long content
            display_body = original_body[:500] + "..." if len(original_body) > 500 else original_body
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**Content**: {display_body}"
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
    polished_count = sum(1 for n in news_list if n.get('polished'))
    elements.append({
        "tag": "note",
        "elements": [
            {
                "tag": "plain_text",
                "content": f"💡 Total: {len(news_list)} | GPT Polished: {polished_count} | For reference only"
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


def send_to_feishu(news_list: List[Dict], title: str = "📰 Crypto Flash News", max_retries: int = 3, polish_threshold: int = 75) -> bool:
    """
    Send news to Feishu with retry mechanism
    
    Args:
        news_list: News list
        title: Card title
        max_retries: Maximum retry attempts (default: 3)
        polish_threshold: Score threshold for GPT polishing display
    
    Returns:
        Whether send was successful
    """
    if not news_list:
        print("⚠️ No news to send")
        return False
    
    bot = FeishuBot()
    card = build_feishu_card(news_list, title, polish_threshold)
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   Attempt {attempt}/{max_retries}...")
            result = bot.send(card)
            
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print("✅ Feishu send successful!")
                return True
            else:
                print(f"   ❌ Attempt {attempt} failed: {result}")
                if attempt < max_retries:
                    import time
                    time.sleep(2)  # Wait 2 seconds before retry
        except Exception as e:
            print(f"   ❌ Attempt {attempt} error: {str(e)}")
            if attempt < max_retries:
                import time
                time.sleep(2)
    
    print(f"❌ Feishu send failed after {max_retries} attempts")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Grok Crypto Flash News Generator - AI-powered cryptocurrency news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (with dedup + feishu)
  python %(prog)s
  
  # Get news from last 1 hour
  python %(prog)s --hours 1
  
  # Skip deduplication
  python %(prog)s --no-dedup
  
  # Skip GPT polishing
  python %(prog)s --no-polish
  
  # Skip Feishu notification
  python %(prog)s --no-feishu
  
  # Custom polish threshold (default: 75)
  python %(prog)s --polish-threshold 80
  
  # Debug mode
  python %(prog)s --debug
        """
    )
    
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS,
                       help=f"Time window in hours (default: {DEFAULT_HOURS})")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS,
                       help=f"Max web search results (default: {DEFAULT_MAX_RESULTS})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                       help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--output", 
                       default=f"{OUTPUT_DIR}/news_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                       help="Output file path")
    parser.add_argument("--debug", action="store_true",
                       help="Debug mode")
    parser.add_argument("--no-save", action="store_true",
                       help="Don't save to file, only print")
    
    # GPT Polish options
    parser.add_argument("--no-polish", action="store_true",
                       help="Skip GPT polishing for high-score news")
    parser.add_argument("--polish-threshold", type=int, default=POLISH_SCORE_THRESHOLD,
                       help=f"Score threshold for GPT polishing (default: {POLISH_SCORE_THRESHOLD})")
    
    # Dedup options
    parser.add_argument("--no-dedup", action="store_true",
                       help="Skip deduplication")
    parser.add_argument("--dedup-threshold", type=float, default=0.7,
                       help="Title similarity threshold for dedup (default: 0.7)")
    parser.add_argument("--dedup-hours", type=int, default=24,
                       help="History window for dedup in hours (default: 24)")
    
    # Feishu options
    parser.add_argument("--no-feishu", action="store_true",
                       help="Skip sending to Feishu")
    parser.add_argument("--feishu-title", default="📰 Crypto Flash News",
                       help="Feishu card title")
    
    args = parser.parse_args()
    
    print(f"\n🚀 Starting Grok Flash News Generator")
    print(f"   Time window: {args.hours} hours")
    print(f"   Output timezone: UTC+8")
    print(f"   Dedup: {'Disabled' if args.no_dedup else f'Enabled (threshold: {args.dedup_threshold})'}")
    print(f"   GPT Polish: {'Disabled' if args.no_polish else f'Enabled (>= {args.polish_threshold})'}")
    print(f"   Feishu: {'Disabled' if args.no_feishu else f'Enabled (only >= {args.polish_threshold})'}")
    print()
    
    # Get API Key
    api_key = get_api_key()
    
    # Build prompt (imported from config.py)
    prompt = build_grok_prompt(hours=args.hours)
    
    # Generate news
    news_list = generate_news(
        api_key=api_key,
        prompt=prompt,
        max_results=args.max_results,
        timeout=args.timeout,
        debug=args.debug
    )
    
    if not news_list:
        print("❌ Generation failed", file=sys.stderr)
        sys.exit(1)
    
    # Process: convert times to UTC+8 and sort by score
    news_list = process_news_list(news_list)
    print(f"\n📊 Generated {len(news_list)} news items")
    
    # ========== Deduplication ==========
    duplicate_count = 0
    if not args.no_dedup:
        print(f"\n🔄 Deduplicating (similarity >= {args.dedup_threshold}, history: {args.dedup_hours}h)...")
        
        dedup = NewsDeduplicator(
            history_file="news_history.json",
            similarity_threshold=args.dedup_threshold,
            history_hours=args.dedup_hours
        )
        
        new_news, duplicates = dedup.filter_duplicates(news_list)
        duplicate_count = len(duplicates)
        
        print(f"   ✅ New: {len(new_news)} | Duplicates: {duplicate_count}")
        
        if duplicates:
            print("   ⏭️ Skipped duplicates:")
            for dup in duplicates[:3]:  # Show max 3
                reason = dup.get("reason", "Unknown")
                title = dup.get("news", {}).get("title", "N/A")[:40]
                print(f"      • {title}... ({reason})")
        
        # Add new news to history
        if new_news:
            dedup.add_to_history(new_news)
        
        news_list = new_news
    
    if not news_list:
        print("\n⚠️ No new news after deduplication")
        sys.exit(0)
    
    # ========== GPT Polish ==========
    polished_count = 0
    if not args.no_polish:
        high_score_count = sum(1 for n in news_list if get_total_score(n) >= args.polish_threshold)
        if high_score_count > 0:
            print(f"\n✨ Polishing {high_score_count} high-score news (>= {args.polish_threshold}) with GPT...")
            news_list, polished_count = polish_high_score_news(
                api_key=api_key,
                news_list=news_list,
                threshold=args.polish_threshold,
                debug=args.debug
            )
            print(f"   ✅ Successfully polished: {polished_count}/{high_score_count}")
    
    # ========== Print Summary ==========
    print_news_summary(news_list)
    
    # ========== Save Result ==========
    if not args.no_save:
        save_news(news_list, args.output)
    
    # ========== Send to Feishu ==========
    # Send ALL news to Feishu (sorted by score, highest first)
    # High-score news shows GPT polished version, low-score shows original with notice
    if not args.no_feishu:
        if news_list:
            polished_in_list = sum(1 for n in news_list if n.get('polished'))
            unpolished_in_list = len(news_list) - polished_in_list
            print(f"\n📤 Sending {len(news_list)} news to Feishu...")
            print(f"   ✨ {polished_in_list} GPT polished (>= {args.polish_threshold})")
            print(f"   📝 {unpolished_in_list} Grok original (< {args.polish_threshold})")
            send_to_feishu(news_list, args.feishu_title, polish_threshold=args.polish_threshold)
        else:
            print("\n⚠️ No news to send to Feishu")
    
    # ========== Final Summary ==========
    feishu_sent = len(news_list) if not args.no_feishu and news_list else 0
    print("\n" + "=" * 50)
    print("📋 Summary")
    print("=" * 50)
    print(f"   Generated: {len(news_list) + duplicate_count}")
    print(f"   Duplicates removed: {duplicate_count}")
    print(f"   New news: {len(news_list)}")
    print(f"   GPT polished: {polished_count}")
    print(f"   Sent to Feishu: {feishu_sent} (all news, sorted by score)")
    print("=" * 50)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
