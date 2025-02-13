import json

def extract_json(response: str) -> dict:
    """从模型响应中提取 JSON 部分"""
    try:
        # 移除 <think> 标签
        clean_res = response.split('</think>', 1)[-1]
        
        # 找到 JSON 边界（支持嵌套结构）
        start = clean_res.find('{')
        end = clean_res.rfind('}') + 1  # +1 包含结束括号
        
        # 验证边界有效性
        if start == -1 or end == 0 or start >= end:
            raise ValueError("未找到有效的 JSON 边界")
        
        # 提取并清理字符串
        json_str = clean_res[start:end] \
            .replace("'", "\"").replace("\\n", "").strip()  # 去除首尾空格
        
        # 最终解析验证
        return json.loads(json_str)
        
    except json.JSONDecodeError as e:
        print(f"[DEBUG] 原始响应内容:\n{response}")  # 调试日志
        raise ValueError(f"JSON 语法错误：{e.msg}（位置：第 {e.lineno} 行，第 {e.colno} 列）")
    except Exception as e:
        raise ValueError(f"JSON 提取失败：{str(e)}")

