#!/usr/bin/env python3
"""
News Deduplication Module (SQLite)
Deduplication based on title similarity and link matching
Also stores full news data for historical queries
"""

import os
import sqlite3
import hashlib
import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from contextlib import contextmanager

# Default settings
DEFAULT_DB_FILE = "news_history.db"
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_HISTORY_HOURS = 24


class NewsDeduplicator:
    """News Deduplicator using SQLite"""
    
    def __init__(
        self,
        db_file: str = DEFAULT_DB_FILE,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        history_hours: int = DEFAULT_HISTORY_HOURS
    ):
        """
        Initialize deduplicator
        
        Args:
            db_file: SQLite database file path
            similarity_threshold: Title similarity threshold (0-1)
            history_hours: Hours to keep history for dedup checking
        """
        self.db_file = db_file
        self.similarity_threshold = similarity_threshold
        self.history_hours = history_hours
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Main news table - stores full news data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    title_hash TEXT NOT NULL,
                    body TEXT,
                    link TEXT,
                    source TEXT,
                    publish_time TEXT,
                    score_importance INTEGER DEFAULT 0,
                    score_authority INTEGER DEFAULT 0,
                    score_trending INTEGER DEFAULT 0,
                    score_timeliness INTEGER DEFAULT 0,
                    score_total INTEGER DEFAULT 0,
                    gpt_title TEXT,
                    gpt_body TEXT,
                    polished INTEGER DEFAULT 0,
                    raw_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Index for faster lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_link ON news(link)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_hash ON news(title_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON news(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_score_total ON news(score_total)")
            
            conn.commit()
    
    def _get_title_hash(self, title: str) -> str:
        """Generate hash for title"""
        normalized = title.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _calculate_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        t1 = title1.lower().strip()
        t2 = title2.lower().strip()
        return SequenceMatcher(None, t1, t2).ratio()
    
    def _get_cutoff_time(self) -> str:
        """Get cutoff time for history check"""
        cutoff = datetime.now() - timedelta(hours=self.history_hours)
        return cutoff.isoformat()
    
    def is_duplicate(self, news: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check if news is a duplicate
        
        Args:
            news: News data
        
        Returns:
            (is_duplicate, reason)
        """
        title = news.get("title", "")
        link = news.get("link", "")
        cutoff_time = self._get_cutoff_time()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check link duplicate
            if link:
                cursor.execute(
                    "SELECT id FROM news WHERE link = ? AND created_at > ?",
                    (link, cutoff_time)
                )
                if cursor.fetchone():
                    return True, f"Link duplicate: {link[:50]}..."
            
            # 2. Check title similarity
            cursor.execute(
                "SELECT title FROM news WHERE created_at > ?",
                (cutoff_time,)
            )
            
            for row in cursor.fetchall():
                existing_title = row["title"]
                similarity = self._calculate_similarity(title, existing_title)
                
                if similarity >= self.similarity_threshold:
                    return True, f"Title similar ({similarity:.0%}): {existing_title[:40]}..."
        
        return False, None
    
    def filter_duplicates(self, news_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter duplicate news
        
        Args:
            news_list: List of news
        
        Returns:
            (new_news_list, duplicate_news_list)
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
        Add news to history database
        
        Args:
            news_list: List of news
        """
        current_time = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for news in news_list:
                title = news.get("title", "")
                score = news.get("score", {})
                
                # Extract score components
                if isinstance(score, dict):
                    score_importance = score.get("importance", 0)
                    score_authority = score.get("authority", 0)
                    score_trending = score.get("trending", 0)
                    score_timeliness = score.get("timeliness", 0)
                    score_total = score.get("total", 0)
                else:
                    score_importance = score_authority = score_trending = score_timeliness = 0
                    score_total = score if isinstance(score, int) else 0
                
                cursor.execute("""
                    INSERT INTO news (
                        title, title_hash, body, link, source, publish_time,
                        score_importance, score_authority, score_trending, 
                        score_timeliness, score_total,
                        gpt_title, gpt_body, polished, raw_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title,
                    self._get_title_hash(title),
                    news.get("body", ""),
                    news.get("link", ""),
                    news.get("source", ""),
                    news.get("publish_time", ""),
                    score_importance,
                    score_authority,
                    score_trending,
                    score_timeliness,
                    score_total,
                    news.get("gpt_title", ""),
                    news.get("gpt_body", ""),
                    1 if news.get("polished") else 0,
                    json.dumps(news, ensure_ascii=False),
                    current_time,
                    current_time
                ))
            
            conn.commit()
    
    def cleanup_old_records(self, keep_days: int = 7) -> int:
        """
        Clean up old records (older than keep_days)
        
        Args:
            keep_days: Days to keep records
        
        Returns:
            Number of deleted records
        """
        cutoff = datetime.now() - timedelta(days=keep_days)
        cutoff_str = cutoff.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM news WHERE created_at < ?", (cutoff_str,))
            count = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM news WHERE created_at < ?", (cutoff_str,))
            conn.commit()
            
        return count
    
    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total records
            cursor.execute("SELECT COUNT(*) FROM news")
            total = cursor.fetchone()[0]
            
            # Records within history window
            cutoff = self._get_cutoff_time()
            cursor.execute("SELECT COUNT(*) FROM news WHERE created_at > ?", (cutoff,))
            recent = cursor.fetchone()[0]
            
            # Polished count
            cursor.execute("SELECT COUNT(*) FROM news WHERE polished = 1")
            polished = cursor.fetchone()[0]
            
            # Average score
            cursor.execute("SELECT AVG(score_total) FROM news WHERE score_total > 0")
            avg_score = cursor.fetchone()[0] or 0
            
        return {
            "total_records": total,
            "recent_records": recent,
            "polished_count": polished,
            "average_score": round(avg_score, 1),
            "history_hours": self.history_hours,
            "similarity_threshold": self.similarity_threshold,
            "db_file": self.db_file
        }
    
    def get_news_by_date(self, date: str = None, limit: int = 50) -> List[Dict]:
        """
        Get news by date
        
        Args:
            date: Date string (YYYY-MM-DD), None for today
            limit: Maximum number of records
        
        Returns:
            List of news
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT raw_json FROM news 
                WHERE created_at LIKE ?
                ORDER BY score_total DESC, created_at DESC
                LIMIT ?
            """, (f"{date}%", limit))
            
            results = []
            for row in cursor.fetchall():
                try:
                    results.append(json.loads(row["raw_json"]))
                except:
                    pass
            
            return results
    
    def get_high_score_news(self, min_score: int = 70, days: int = 7) -> List[Dict]:
        """
        Get high-score news from recent days
        
        Args:
            min_score: Minimum score threshold
            days: Number of days to look back
        
        Returns:
            List of news
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT raw_json FROM news 
                WHERE score_total >= ? AND created_at > ?
                ORDER BY score_total DESC, created_at DESC
            """, (min_score, cutoff_str))
            
            results = []
            for row in cursor.fetchall():
                try:
                    results.append(json.loads(row["raw_json"]))
                except:
                    pass
            
            return results
    
    def search_news(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        Search news by keyword in title or body
        
        Args:
            keyword: Search keyword
            limit: Maximum number of results
        
        Returns:
            List of matching news
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{keyword}%"
            cursor.execute("""
                SELECT raw_json FROM news 
                WHERE title LIKE ? OR body LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (search_pattern, search_pattern, limit))
            
            results = []
            for row in cursor.fetchall():
                try:
                    results.append(json.loads(row["raw_json"]))
                except:
                    pass
            
            return results


# Convenience function
def deduplicate_news(
    news_list: List[Dict],
    db_file: str = DEFAULT_DB_FILE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    history_hours: int = DEFAULT_HISTORY_HOURS,
    save_to_history: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Deduplicate news (convenience function)
    
    Args:
        news_list: List of news
        db_file: SQLite database file
        similarity_threshold: Similarity threshold
        history_hours: Hours to keep history
        save_to_history: Whether to save new news to history
    
    Returns:
        (new_news_list, duplicate_news_list)
    """
    dedup = NewsDeduplicator(
        db_file=db_file,
        similarity_threshold=similarity_threshold,
        history_hours=history_hours
    )
    
    new_news, duplicates = dedup.filter_duplicates(news_list)
    
    if save_to_history and new_news:
        dedup.add_to_history(new_news)
    
    return new_news, duplicates


def migrate_json_to_sqlite(json_file: str = "news_history.json", db_file: str = DEFAULT_DB_FILE):
    """
    Migrate existing JSON history to SQLite
    
    Args:
        json_file: Source JSON file
        db_file: Target SQLite database
    """
    if not os.path.exists(json_file):
        print(f"JSON file not found: {json_file}")
        return
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return
    
    dedup = NewsDeduplicator(db_file=db_file)
    
    news_records = data.get("news", [])
    if news_records:
        # Convert old format to new format
        migrated = []
        for record in news_records:
            migrated.append({
                "title": record.get("title", ""),
                "link": record.get("link", ""),
                "body": "",
                "source": "",
                "publish_time": record.get("added_at", ""),
                "score": {"total": 0},
                "polished": False
            })
        
        with dedup._get_connection() as conn:
            cursor = conn.cursor()
            current_time = datetime.now().isoformat()
            
            for news in migrated:
                cursor.execute("""
                    INSERT INTO news (
                        title, title_hash, body, link, source, publish_time,
                        score_importance, score_authority, score_trending, 
                        score_timeliness, score_total,
                        gpt_title, gpt_body, polished, raw_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    news["title"],
                    dedup._get_title_hash(news["title"]),
                    "", "", "", news["publish_time"],
                    0, 0, 0, 0, 0,
                    "", "", 0,
                    json.dumps(news, ensure_ascii=False),
                    news["publish_time"] or current_time,
                    current_time
                ))
            
            conn.commit()
        
        print(f"✅ Migrated {len(migrated)} records from {json_file} to {db_file}")
    else:
        print("No records to migrate")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        # Run migration: python news_dedup.py migrate
        migrate_json_to_sqlite()
    else:
        # Show stats
        dedup = NewsDeduplicator()
        stats = dedup.get_stats()
        print("📊 News Database Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")
