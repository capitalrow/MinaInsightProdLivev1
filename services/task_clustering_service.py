"""
CROWN⁴.5 Semantic Task Clustering Service
Groups related tasks using AI embeddings and clustering algorithms.
"""

import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import json
import os

logger = logging.getLogger(__name__)


class TaskClusteringService:
    """Service for grouping related tasks using semantic similarity."""
    
    def __init__(self):
        """Initialize clustering service with OpenAI for embeddings."""
        self.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info("✅ TaskClusteringService initialized with OpenAI")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
        else:
            logger.warning("⚠️ OPENAI_API_KEY not set - using fallback clustering")
    
    def cluster_tasks(self, tasks: List[Dict], num_clusters: Optional[int] = None) -> Dict:
        """
        Cluster tasks into semantic groups.
        
        Args:
            tasks: List of task dictionaries with 'id', 'title', 'description'
            num_clusters: Number of clusters (auto-detected if None)
            
        Returns:
            Dict with 'clusters' (list of task groups) and 'metadata'
        """
        if not tasks or len(tasks) < 2:
            return self._empty_clustering(tasks)
        
        # Try AI-powered clustering first
        if self.client:
            try:
                return self._cluster_with_ai(tasks, num_clusters)
            except Exception as e:
                logger.warning(f"AI clustering failed, falling back to keyword clustering: {e}")
        
        # Fallback to keyword-based clustering
        return self._cluster_with_keywords(tasks, num_clusters)
    
    def _cluster_with_ai(self, tasks: List[Dict], num_clusters: Optional[int] = None) -> Dict:
        """Cluster using OpenAI embeddings and similarity."""
        # Get embeddings for all tasks
        task_texts = [self._get_task_text(task) for task in tasks]
        embeddings = self._get_embeddings(task_texts)
        
        # Calculate similarity matrix
        similarity_matrix = self._calculate_similarity_matrix(embeddings)
        
        # Determine optimal number of clusters
        if num_clusters is None:
            num_clusters = self._estimate_optimal_clusters(len(tasks))
        
        # Perform clustering using similarity scores
        cluster_assignments = self._assign_clusters(similarity_matrix, num_clusters)
        
        # Group tasks by cluster
        clusters_dict = defaultdict(list)
        for i, task in enumerate(tasks):
            cluster_id = cluster_assignments[i]
            clusters_dict[cluster_id].append(task)
        
        # Generate cluster labels using AI
        clusters = []
        for cluster_id, cluster_tasks in sorted(clusters_dict.items()):
            label = self._generate_cluster_label_ai(cluster_tasks)
            clusters.append({
                'id': cluster_id,
                'label': label,
                'tasks': cluster_tasks,
                'size': len(cluster_tasks)
            })
        
        return {
            'success': True,
            'clusters': clusters,
            'metadata': {
                'method': 'ai_embeddings',
                'num_clusters': len(clusters),
                'total_tasks': len(tasks)
            }
        }
    
    def _cluster_with_keywords(self, tasks: List[Dict], num_clusters: Optional[int] = None) -> Dict:
        """Fallback clustering using keyword extraction and similarity."""
        # Extract keywords from each task
        task_keywords = [self._extract_keywords(self._get_task_text(task)) for task in tasks]
        
        # Calculate keyword-based similarity
        similarity_matrix = []
        for i, keywords_i in enumerate(task_keywords):
            row = []
            for j, keywords_j in enumerate(task_keywords):
                similarity = self._keyword_similarity(keywords_i, keywords_j)
                row.append(similarity)
            similarity_matrix.append(row)
        
        # Determine optimal number of clusters
        if num_clusters is None:
            num_clusters = self._estimate_optimal_clusters(len(tasks))
        
        # Simple greedy clustering
        cluster_assignments = self._assign_clusters(similarity_matrix, num_clusters)
        
        # Group tasks by cluster
        clusters_dict = defaultdict(list)
        for i, task in enumerate(tasks):
            cluster_id = cluster_assignments[i]
            clusters_dict[cluster_id].append(task)
        
        # Generate cluster labels from common keywords
        clusters = []
        for cluster_id, cluster_tasks in sorted(clusters_dict.items()):
            label = self._generate_cluster_label_keywords(cluster_tasks)
            clusters.append({
                'id': cluster_id,
                'label': label,
                'tasks': cluster_tasks,
                'size': len(cluster_tasks)
            })
        
        return {
            'success': True,
            'clusters': clusters,
            'metadata': {
                'method': 'keyword_similarity',
                'num_clusters': len(clusters),
                'total_tasks': len(tasks)
            }
        }
    
    def _get_task_text(self, task: Dict) -> str:
        """Get combined text for task (title + description)."""
        title = task.get('title', '')
        description = task.get('description', '')
        return f"{title}. {description}".strip()
    
    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get OpenAI embeddings for texts."""
        if not self.client:
            raise ValueError("OpenAI client not available")
        
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Failed to get embeddings: {e}")
            raise
    
    def _calculate_similarity_matrix(self, embeddings: List[List[float]]) -> List[List[float]]:
        """Calculate cosine similarity matrix from embeddings."""
        import math
        
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            """Calculate cosine similarity between two vectors."""
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)
        
        n = len(embeddings)
        matrix = []
        for i in range(n):
            row = []
            for j in range(n):
                similarity = cosine_similarity(embeddings[i], embeddings[j])
                row.append(similarity)
            matrix.append(row)
        return matrix
    
    def _estimate_optimal_clusters(self, num_tasks: int) -> int:
        """Estimate optimal number of clusters based on task count."""
        if num_tasks < 5:
            return 1
        elif num_tasks < 10:
            return 2
        elif num_tasks < 20:
            return 3
        elif num_tasks < 50:
            return 4
        else:
            return min(7, max(3, int(num_tasks ** 0.5)))
    
    def _assign_clusters(self, similarity_matrix: List[List[float]], num_clusters: int) -> List[int]:
        """Assign tasks to clusters using similarity matrix (simple greedy approach)."""
        n = len(similarity_matrix)
        if num_clusters >= n:
            return list(range(n))
        
        # Initialize with first k tasks as cluster centers
        cluster_centers = list(range(num_clusters))
        assignments = [-1] * n
        
        # Assign each task to nearest cluster center
        for i in range(n):
            if i in cluster_centers:
                assignments[i] = cluster_centers.index(i)
            else:
                # Find most similar cluster center
                max_similarity = -1
                best_cluster = 0
                for cluster_idx, center_idx in enumerate(cluster_centers):
                    similarity = similarity_matrix[i][center_idx]
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_cluster = cluster_idx
                assignments[i] = best_cluster
        
        return assignments
    
    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text (simple approach)."""
        # Common stop words
        stop_words = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but',
            'in', 'with', 'to', 'for', 'of', 'as', 'by', 'from', 'this', 'that'
        }
        
        # Tokenize and filter
        words = text.lower().split()
        keywords = {
            word.strip('.,!?;:') 
            for word in words 
            if len(word) > 3 and word not in stop_words
        }
        
        return keywords
    
    def _keyword_similarity(self, keywords_a: set, keywords_b: set) -> float:
        """Calculate Jaccard similarity between keyword sets."""
        if not keywords_a or not keywords_b:
            return 0.0
        
        intersection = len(keywords_a & keywords_b)
        union = len(keywords_a | keywords_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _generate_cluster_label_ai(self, tasks: List[Dict]) -> str:
        """Generate cluster label using AI."""
        if not self.client:
            return self._generate_cluster_label_keywords(tasks)
        
        task_titles = [task.get('title', '') for task in tasks[:10]]  # Limit to 10 for API
        titles_text = '\n'.join(f"- {title}" for title in task_titles)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a task organization assistant. Generate a short, descriptive label (2-4 words) that captures the common theme of these tasks."
                    },
                    {
                        "role": "user",
                        "content": f"What's the common theme of these tasks?\n{titles_text}\n\nProvide only the label (2-4 words):"
                    }
                ],
                temperature=0.3,
                max_tokens=20
            )
            
            label = response.choices[0].message.content.strip().strip('"\'')
            return label[:50]  # Limit length
            
        except Exception as e:
            logger.warning(f"Failed to generate AI label: {e}")
            return self._generate_cluster_label_keywords(tasks)
    
    def _generate_cluster_label_keywords(self, tasks: List[Dict]) -> str:
        """Generate cluster label from common keywords."""
        # Extract all keywords from cluster tasks
        all_keywords = defaultdict(int)
        for task in tasks:
            text = self._get_task_text(task)
            keywords = self._extract_keywords(text)
            for keyword in keywords:
                all_keywords[keyword] += 1
        
        # Get most common keywords
        if not all_keywords:
            return f"Tasks ({len(tasks)})"
        
        top_keywords = sorted(all_keywords.items(), key=lambda x: x[1], reverse=True)[:3]
        label = ' '.join(kw[0].capitalize() for kw in top_keywords)
        
        return label if label else f"Tasks ({len(tasks)})"
    
    def _empty_clustering(self, tasks: List[Dict]) -> Dict:
        """Return empty clustering result."""
        if not tasks:
            return {
                'success': True,
                'clusters': [],
                'metadata': {
                    'method': 'none',
                    'num_clusters': 0,
                    'total_tasks': 0
                }
            }
        
        return {
            'success': True,
            'clusters': [{
                'id': 0,
                'label': 'All Tasks',
                'tasks': tasks,
                'size': len(tasks)
            }],
            'metadata': {
                'method': 'single_cluster',
                'num_clusters': 1,
                'total_tasks': len(tasks)
            }
        }


# Singleton instance
task_clustering_service = TaskClusteringService()
