#!/usr/bin/env python3
"""
新闻去重模块
基于标题相似度和链接进行去重
"""

import os
import json
import hashlib
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# 默认去重数据文件
DEFAULT_DEDUP_FILE = "news_history.json"
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_HISTORY_HOURS = 24


class NewsDeduplicator:
    """新闻去重器"""
    
    def __init__(
        self,
        history_file: str = DEFAULT_DEDUP_FILE,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        history_hours: int = DEFAULT_HISTORY_HOURS
    ):
        """
        初始化去重器
        
        Args:
            history_file: 历史记录文件路径
            similarity_threshold: 标题相似度阈值 (0-1)
            history_hours: 历史记录保留时间（小时）
        """
        self.history_file = history_file
        self.similarity_threshold = similarity_threshold
        self.history_hours = history_hours
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """加载历史记录"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"news": [], "links": set()}
        return {"news": [], "links": []}
    
    def _save_history(self):
        """保存历史记录"""
        # 清理过期记录
        self._cleanup_old_records()
        
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def _cleanup_old_records(self):
        """清理过期的历史记录"""
        cutoff_time = datetime.now() - timedelta(hours=self.history_hours)
        cutoff_str = cutoff_time.isoformat()
        
        # 过滤保留未过期的记录
        self.history["news"] = [
            n for n in self.history.get("news", [])
            if n.get("added_at", "") > cutoff_str
        ]
        
        # 重建链接集合
        self.history["links"] = [
            n.get("link", "") for n in self.history["news"]
            if n.get("link")
        ]
    
    def _get_title_hash(self, title: str) -> str:
        """生成标题的 hash"""
        normalized = title.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """计算两个标题的相似度"""
        # 规范化
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        
        # 使用 SequenceMatcher 计算相似度
        return SequenceMatcher(None, t1, t2).ratio()
    
    def is_duplicate(self, news: Dict) -> Tuple[bool, Optional[str]]:
        """
        检查新闻是否重复
        
        Args:
            news: 新闻数据
        
        Returns:
            (是否重复, 重复原因)
        """
        title = news.get("title", "")
        link = news.get("link", "")
        
        # 1. 检查链接是否重复
        if link and link in self.history.get("links", []):
            return True, f"链接重复: {link[:50]}..."
        
        # 2. 检查标题相似度
        for existing in self.history.get("news", []):
            existing_title = existing.get("title", "")
            similarity = self._calculate_similarity(title, existing_title)
            
            if similarity >= self.similarity_threshold:
                return True, f"标题相似({similarity:.0%}): {existing_title[:40]}..."
        
        return False, None
    
    def filter_duplicates(self, news_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤重复新闻
        
        Args:
            news_list: 新闻列表
        
        Returns:
            (新新闻列表, 重复新闻列表)
        """
        new_news = []
        duplicate_news = []
        
        for news in news_list:
            is_dup, reason = self.is_duplicate(news)
            
            if is_dup:
                duplicate_news.append({
                    "news": news,
                    "reason": reason
                })
            else:
                new_news.append(news)
        
        return new_news, duplicate_news
    
    def add_to_history(self, news_list: List[Dict]):
        """
        将新闻添加到历史记录
        
        Args:
            news_list: 新闻列表
        """
        current_time = datetime.now().isoformat()
        
        for news in news_list:
            title = news.get("title", "")
            link = news.get("link", "")
            
            record = {
                "title": title,
                "title_hash": self._get_title_hash(title),
                "link": link,
                "added_at": current_time
            }
            
            self.history["news"].append(record)
            
            if link:
                if "links" not in self.history:
                    self.history["links"] = []
                self.history["links"].append(link)
        
        self._save_history()
    
    def get_stats(self) -> Dict:
        """获取去重统计信息"""
        return {
            "total_history": len(self.history.get("news", [])),
            "history_hours": self.history_hours,
            "similarity_threshold": self.similarity_threshold
        }


# 便捷函数
def deduplicate_news(
    news_list: List[Dict],
    history_file: str = DEFAULT_DEDUP_FILE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    history_hours: int = DEFAULT_HISTORY_HOURS,
    save_to_history: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    去重新闻的便捷函数
    
    Args:
        news_list: 新闻列表
        history_file: 历史记录文件
        similarity_threshold: 相似度阈值
        history_hours: 历史保留时间
        save_to_history: 是否将新新闻保存到历史
    
    Returns:
        (新新闻列表, 重复新闻列表)
    """
    dedup = NewsDeduplicator(
        history_file=history_file,
        similarity_threshold=similarity_threshold,
        history_hours=history_hours
    )
    
    new_news, duplicates = dedup.filter_duplicates(news_list)
    
    if save_to_history and new_news:
        dedup.add_to_history(new_news)
    
    return new_news, duplicates

