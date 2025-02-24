import sqlite3
from dataclasses import asdict,dataclass
from typing import List, Dict
from pydantic import BaseModel
import json

class NodeInfo(BaseModel):
    id: int
    type: int
    type_description: str
    name: str
    device_type: str

class DatabaseManager:
    def __init__(self, db_name='local.db'):
        self.db_name = db_name
        self._initialize_database()

    def _initialize_database(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS node_info (
                    id INTEGER PRIMARY KEY,
                    type INTEGER,
                    type_description TEXT,
                    name TEXT,
                    device_type TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def save_node_info(self, node_info: NodeInfo):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO node_info (id, type, type_description, name, device_type)
                VALUES (:id, :type, :type_description, :name, :device_type)
            ''', asdict(node_info))
            conn.commit()

    def save_node_info_bulk(self, node_info_list):
        # Log the node_info_list to debug
        print("Saving NodeInfo list:", node_info_list)
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            # Convert dictionaries to NodeInfo objects if necessary
            node_info_dicts = []
            for node_info in node_info_list:
                if isinstance(node_info, dict):
                    node_info['id'] = str(node_info['id'])  # Ensure id is a string
                    node_info['device_type'] = str(node_info['device_type']) if node_info['device_type'] is not None else ""
                    node_info = NodeInfo(**node_info)  # Convert dict to NodeInfo
                node_info_dicts.append(node_info.dict())  # Use .dict() for Pydantic models
            
            cursor.executemany('''
                INSERT OR REPLACE INTO node_info (id, type, type_description, name, device_type)
                VALUES (:id, :type, :type_description, :name, :device_type)
            ''', node_info_dicts)
            conn.commit()
        except Exception as e:
            print(f"Error saving node info: {e}")
            conn.rollback()
        finally:
            conn.close()

    def query_nodes(self) -> List[NodeInfo]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, type, type_description, name, device_type FROM node_info ORDER BY timestamp DESC')
            rows = cursor.fetchall()
        
        # 将查询结果转换为 NodeInfo 对象
        return [NodeInfo(id=row[0], type=row[1], type_description=row[2], name=row[3], device_type=row[4]) for row in rows]

def wrap_node_info(node, nt_type_mapping):
    nt_type = node.get("nt")
    return NodeInfo(
        id=int(node.get("id")),  # 确保 id 是整数
        type=nt_type,
        type_description=nt_type_mapping.get(nt_type, "未知类型"),
        name=node.get("n"),
        device_type=str(node.get("type")) if node.get("type") is not None else ""  # 确保 device_type 是字符串
    ) 