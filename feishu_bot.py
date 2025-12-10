#!/usr/bin/env python3
"""
飞书机器人 - 加密货币热点推送模块
功能：将热点数据格式化为飞书卡片消息并推送到群聊
"""

import os
import time
import hmac
import hashlib
import base64
import requests
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv


class FeishuBot:
    """飞书消息推送机器人"""

    def __init__(self, webhook_url: str = None, secret: str = None):
        """
        初始化飞书机器人

        Args:
            webhook_url: 飞书机器人 Webhook 地址（可选，会从环境变量读取）
            secret: 签名密钥（可选，从环境变量读取）
        """
        load_dotenv()

        self.webhook_url = webhook_url or os.getenv("feishu_webhook_url")
        self.secret = secret or os.getenv("feishu_webhook_key")

        if not self.webhook_url:
            raise ValueError("未找到飞书 webhook URL，请在 .env 中配置 feishu_webhook_url")

    def _generate_sign(self, timestamp: str) -> Optional[str]:
        """
        生成签名（如果配置了密钥）

        Args:
            timestamp: 时间戳字符串

        Returns:
            签名字符串，如果未配置密钥则返回 None
        """
        if not self.secret:
            return None

        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _get_urgency_emoji(self, urgency: str) -> str:
        """根据紧急程度返回 emoji"""
        emoji_map = {
            "Urgent": "🔥",
            "High": "⚠️",
            "Normal": "📌",
            "Low": "📝"
        }
        return emoji_map.get(urgency, "📰")

    def _get_header_color(self, avg_score: float) -> str:
        """
        根据平均热度评分返回卡片头部颜色

        Args:
            avg_score: 平均热度评分

        Returns:
            颜色名称
        """
        if avg_score >= 90:
            return "red"
        elif avg_score >= 85:
            return "orange"
        elif avg_score >= 80:
            return "wathet"
        else:
            return "blue"

    def _format_tags(self, tags: List[str], max_count: int = 3) -> str:
        """格式化标签"""
        return " ".join([f"`{tag}`" for tag in tags[:max_count]])

    def _truncate_text(self, text: str, max_length: int = 200) -> str:
        """截断文本到指定长度"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def build_hotspot_card(
        self,
        hotspots: List[Dict],
        title: str = "🚀 加密市场热点快讯",
        simple_mode: bool = False
    ) -> Dict:
        """
        构建飞书卡片消息

        Args:
            hotspots: 热点列表
            title: 卡片标题
            simple_mode: 是否使用简洁模式

        Returns:
            飞书卡片消息体
        """
        if simple_mode:
            return self._build_simple_card(hotspots, title)
        else:
            return self._build_detailed_card(hotspots, title)

    def _convert_to_utc8(self, utc_time_str: str) -> str:
        """将 UTC 时间字符串转换为 UTC+8 时间"""
        from datetime import timedelta
        
        try:
            if utc_time_str.endswith("Z"):
                utc_time_str = utc_time_str[:-1]
            utc_time = datetime.fromisoformat(utc_time_str)
            utc8_time = utc_time + timedelta(hours=8)
            return utc8_time.strftime("%m-%d %H:%M")
        except Exception:
            return ""

    def _format_faq(self, faq_list: List[Dict]) -> str:
        """格式化 FAQ 列表为 Markdown 字符串"""
        if not faq_list:
            return ""
        
        lines = []
        for i, faq in enumerate(faq_list, 1):
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            if question and answer:
                lines.append(f"**Q{i}: {question}**")
                lines.append(f"A: {answer}")
                lines.append("")
        
        return "\n".join(lines).strip()

    def _build_detailed_card(self, hotspots: List[Dict], title: str) -> Dict:
        """构建详细版卡片"""
        elements = []

        # 计算平均热度评分
        scores = [h.get("热度评分", {}).get("综合得分", 0) for h in hotspots]
        avg_score = sum(scores) / len(scores) if scores else 0

        # 添加头部时间
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"⏰ 更新时间：{current_time}"
            }
        })

        elements.append({"tag": "hr"})

        # 遍历热点
        for idx, hotspot in enumerate(hotspots, 1):
            # 提取数据
            topic = hotspot.get("主题", "无标题")
            score = hotspot.get("热度评分", {}).get("综合得分", 0)
            urgency = hotspot.get("情报内容", {}).get("metadata", {}).get("urgency", "Normal")
            tags = hotspot.get("相关主体", [])

            # 获取内容
            content = hotspot.get("情报内容", {}).get("content", {})
            brief = content.get("brief", "")
            analysis = content.get("analysis", "")
            faq_list = hotspot.get("情报内容", {}).get("faq_schema", [])

            # 获取原文链接和发布时间
            source_url = ""
            publish_time_str = ""
            tweets = hotspot.get("引用推文", [])
            if tweets:
                source_url = tweets[0].get("推文链接", "")
                utc_time_str = tweets[0].get("发布时间", "")
                if utc_time_str:
                    publish_time_str = self._convert_to_utc8(utc_time_str)

            # 紧急程度 emoji
            emoji = self._get_urgency_emoji(urgency)

            # 标题行
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{emoji} {idx}. {topic}**"
                }
            })

            # 热度 + 发布时间
            time_str = f" ｜ 🕐 {publish_time_str}" if publish_time_str else ""
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"🔥 热度 **{score}**{time_str}"
                }
            })

            # 摘要
            if brief:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📋 **概要**：{brief}"
                    }
                })

            # 分析
            if analysis:
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"📊 **分析**：{analysis}"
                    }
                })

            # FAQ 折叠面板
            if faq_list:
                faq_content = self._format_faq(faq_list)
                elements.append({
                    "tag": "collapsible_panel",
                    "expanded": False,
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": "❓ 点击查看常见问题"
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
                                "content": faq_content
                            }
                        }
                    ]
                })

            # 底部：查看原文按钮 + 标签
            tags_str = "   ".join(tags[:3])
            
            if source_url or tags:
                bottom_columns = []
                
                if source_url:
                    bottom_columns.append({
                        "tag": "column",
                        "width": "auto",
                        "elements": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "📎 查看原文"
                                },
                                "type": "default",
                                "url": source_url
                            }
                        ]
                    })
                
                if tags:
                    bottom_columns.append({
                        "tag": "column",
                        "width": "weighted",
                        "weight": 1,
                        "vertical_align": "center",
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": tags_str
                                }
                            }
                        ]
                    })
                
                elements.append({
                    "tag": "column_set",
                    "flex_mode": "none",
                    "background_style": "default",
                    "horizontal_spacing": "default",
                    "columns": bottom_columns
                })

            # 分隔线（最后一条不加）
            if idx < len(hotspots):
                elements.append({"tag": "hr"})

        # 底部提示
        elements.append({
            "tag": "note",
            "elements": [
                {
                    "tag": "plain_text",
                    "content": "💡 数据来源：链上监控 & 社交媒体 | 仅供参考，不构成投资建议"
                }
            ]
        })

        # 构建完整卡片
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": self._get_header_color(avg_score)
                },
                "elements": elements
            }
        }

        return card

    def _build_simple_card(self, hotspots: List[Dict], title: str) -> Dict:
        """构建简洁版卡片（适合频繁推送）"""
        lines = [f"⏰ {datetime.now().strftime('%H:%M')}\n"]

        for idx, hotspot in enumerate(hotspots, 1):
            topic = hotspot.get("主题", "无标题")
            score = hotspot.get("热度评分", {}).get("综合得分", 0)

            # 获取原文链接
            source_url = ""
            tweets = hotspot.get("引用推文", [])
            if tweets:
                source_url = tweets[0].get("推文链接", "")

            # 根据评分添加火焰
            flames = "🔥" * min(int(score / 30) + 1, 3)

            if source_url:
                lines.append(f"**{idx}. [{topic}]({source_url})** {flames} {score}")
            else:
                lines.append(f"**{idx}. {topic}** {flames} {score}")

        # 计算平均分
        scores = [h.get("热度评分", {}).get("综合得分", 0) for h in hotspots]
        avg_score = sum(scores) / len(scores) if scores else 0

        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": self._get_header_color(avg_score)
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "\n\n".join(lines)
                        }
                    }
                ]
            }
        }

        return card

    def send(self, message: Dict) -> Dict:
        """
        发送消息到飞书

        Args:
            message: 消息体

        Returns:
            飞书 API 响应
        """
        payload = message.copy()

        # 如果配置了签名
        if self.secret:
            timestamp = str(int(time.time()))
            sign = self._generate_sign(timestamp)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"code": -1, "msg": f"发送失败: {str(e)}"}

    def push_hotspots(
        self,
        hotspots: List[Dict],
        max_count: int = 5,
        sort_by_score: bool = True,
        simple_mode: bool = False,
        title: str = "🚀 加密市场热点快讯"
    ) -> Dict:
        """
        推送热点到飞书群

        Args:
            hotspots: 热点列表
            max_count: 最大推送条数（1-10）
            sort_by_score: 是否按热度排序
            simple_mode: 是否使用简洁模式
            title: 卡片标题

        Returns:
            发送结果
        """
        if not hotspots:
            return {"code": -1, "msg": "没有热点可推送"}

        # 限制条数
        max_count = min(max(1, max_count), 10)

        # 按热度排序
        if sort_by_score:
            hotspots = sorted(
                hotspots,
                key=lambda x: x.get("热度评分", {}).get("综合得分", 0),
                reverse=True
            )

        # 取前 N 条
        hotspots_to_send = hotspots[:max_count]

        # 构建消息
        message = self.build_hotspot_card(hotspots_to_send, title, simple_mode)

        # 发送
        return self.send(message)


# ==================== 使用示例 ====================

if __name__ == "__main__":
    import json

    # 从环境变量加载配置
    load_dotenv()

    # 初始化机器人
    bot = FeishuBot()

    # 从 JSON 文件加载热点
    with open("hotspots_20251207_1831.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        hotspots = data.get("热点列表", [])

    # 推送热点（详细模式）
    result = bot.push_hotspots(
        hotspots=hotspots,
        max_count=5,
        sort_by_score=True,
        simple_mode=False,
        title="🚀 加密市场热点快讯"
    )

    print(f"发送结果: {result}")

    # 简洁模式示例
    # result = bot.push_hotspots(
    #     hotspots=hotspots,
    #     max_count=3,
    #     simple_mode=True,
    #     title="📢 快讯"
    # )
