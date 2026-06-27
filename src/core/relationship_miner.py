"""منقب العلاقات المخفية بين الملفات"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class RelationshipMiner:
    """كشف العلاقات المخفية بين الملفات وبناء رسم بياني"""

    def __init__(self):
        self.graph = None

    def find_relationships(self, file_paths: List[str]) -> List[Dict]:
        """كشف العلاقات بين مجموعة ملفات"""
        relationships = []

        # 1. الملفات المكررة
        duplicates = self.detect_duplicates(file_paths)
        for group in duplicates:
            for dup in group[1:]:
                relationships.append({
                    "type": "duplicate",
                    "source": group[0],
                    "target": dup,
                    "weight": 0.95,
                })

        # 2. تشابه الأسماء
        name_map = defaultdict(list)
        for fp in file_paths:
            name = Path(fp).stem.lower()
            name_map[name].append(fp)

        for name, paths in name_map.items():
            if len(paths) > 1:
                for i in range(len(paths)):
                    for j in range(i + 1, len(paths)):
                        relationships.append({
                            "type": "similar_name",
                            "source": paths[i],
                            "target": paths[j],
                            "weight": 0.8,
                        })

        # 3. الملفات في نفس المجلد
        dir_map = defaultdict(list)
        for fp in file_paths:
            parent = str(Path(fp).parent)
            dir_map[parent].append(fp)

        for directory, paths in dir_map.items():
            if len(paths) > 1:
                for i in range(len(paths)):
                    for j in range(i + 1, len(paths)):
                        relationships.append({
                            "type": "same_directory",
                            "source": paths[i],
                            "target": paths[j],
                            "weight": 0.3,
                        })

        # 4. امتدادات متشابهة
        ext_map = defaultdict(list)
        for fp in file_paths:
            ext = Path(fp).suffix.lower()
            ext_map[ext].append(fp)

        ext_groups = {
            ".jpg": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
            ".mp4": [".mp4", ".avi", ".mkv", ".mov", ".webm"],
            ".zip": [".zip", ".rar", ".7z", ".tar.gz"],
            ".py": [".py", ".js", ".ts", ".java", ".cpp"],
            ".xls": [".xls", ".xlsx", ".csv"],
        }
        for base_exts, related in ext_groups.items():
            all_exts = set(related)
            for ext in list(all_exts):
                for fp in ext_map.get(ext, []):
                    related_files = []
                    for rext in all_exts - {ext}:
                        for rfp in ext_map.get(rext, []):
                            # نفس المجلد واسم مشابه
                            if Path(fp).parent == Path(rfp).parent:
                                stem_fp = Path(fp).stem.lower()
                                stem_rf = Path(rfp).stem.lower()
                                if stem_fp == stem_rf:
                                    related_files.append(rfp)
                    for rf in related_files:
                        relationships.append({
                            "type": "related_format",
                            "source": fp,
                            "target": rf,
                            "weight": 0.6,
                        })

        return relationships

    def detect_duplicates(self, file_paths: List[str]) -> List[List[str]]:
        """كشف المجموعات المكررة"""
        from src.utils.helpers import compute_file_hash

        hash_map = defaultdict(list)
        for fp in file_paths:
            path = Path(fp)
            if path.is_file():
                try:
                    h = compute_file_hash(str(path))
                    hash_map[h].append(str(path))
                except Exception:
                    continue

        return [group for group in hash_map.values() if len(group) > 1]

    def build_graph(self, file_paths: List[str]) -> dict:
        """بناء رسم بياني كامل للعلاقات"""
        import networkx as nx

        self.graph = nx.Graph()
        for fp in file_paths:
            path = Path(fp)
            self.graph.add_node(str(path), name=path.name,
                              extension=path.suffix,
                              size=path.stat().st_size if path.exists() else 0)

        relationships = self.find_relationships(file_paths)
        for rel in relationships:
            self.graph.add_edge(
                rel["source"], rel["target"],
                relationship=rel["type"],
                weight=rel["weight"],
            )

        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "relationships": len(relationships),
        }

    def export_graph(self, output_path: str) -> bool:
        """تصدير الرسم البياني كـ GEXF"""
        if self.graph is None:
            return False
        try:
            import networkx as nx
            nx.write_gexf(self.graph, output_path)
            logger.info(f"تم تصدير الرسم البياني: {output_path}")
            return True
        except Exception as e:
            logger.error(f"خطأ في التصدير: {e}")
            return False

    def export_graph_json(self, output_path: str) -> bool:
        """تصدير الرسم البياني كـ JSON"""
        if self.graph is None:
            return False
        try:
            from networkx import node_link_data
            data = node_link_data(self.graph)
            import json
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"خطأ في التصدير: {e}")
            return False
