from langchain_core.runnables import RunnablePassthrough, RunnableLambda, RunnableParallel
from langchain.prompts import PromptTemplate
from prompts_test import template  # Import the prompt variable from prompts.py
from typing import List, Dict
from utils import extract_json  # 确保 utils.py 中的 extract_json 是普通函数
import os
from gateway import bulid_command, NodeType, DeviceType  # 新增导入
import gc

import json

class LangChainIntegrationTest:


    

    def __init__(self):
        # 从 app.py 复制的核心组件
        from ollama_api import initialize_llm
        from database_manager import DatabaseManager
        os.environ['OLLAMA_MODEL_NAME'] = os.getenv('OLLAMA_MODEL_NAME', 'deepseek-r1:7b')  # 默认值
        os.environ['OLLAMA_IP_PORT'] = os.getenv('OLLAMA_IP_PORT', 'http://192.168.3.73:11434')  # 默认值 
        
        self.llm = initialize_llm()
        self.db_manager = DatabaseManager()
        self._init_chain()
        
    def _init_chain(self):
        """重构处理链结构"""
        self.prompt_template = PromptTemplate(
            template=template,
            input_variables=["user_input", "device_list", "room_list", "scene_list"]
        )
        
        # 使用RunnableParallel确保参数正确合并
        self.chain = (
            RunnableParallel({
                "user_input": RunnablePassthrough(),
                "device_list": RunnablePassthrough(),
                "room_list": RunnablePassthrough(),
                "scene_list": RunnablePassthrough()
            })
            | self.prompt_template 
            | self.llm
        )

    def test_scenario(self, user_input: str):
        """修改后的测试方法"""
        self._init_chain()  # 每次测试重新初始化
        
        print(f"\n=== 测试输入：'{user_input}' ===")
        
        try:
            # 生成模拟数据
            room_list, device_list, scene_list = self._generate_mock_data()
            
            # 构建节点信息字符串
            node_info_str = self._format_node_info(room_list, device_list, scene_list)
            
            # 执行处理链
            full_response = []
            input_variables = {"user_input": user_input, "device_list": device_list, "room_list": room_list, "scene_list": scene_list}
            prompt = self.prompt_template.format(**input_variables)
            print(prompt)
            for chunk in self.chain.stream(prompt):  
                full_response.append(chunk)
            
            # 合并响应为字符串再解析
            combined_response = ''.join(full_response)
            command = extract_json(combined_response)
            
            # 打印完整处理流程
            print(f"[处理结果]: {json.dumps(command, ensure_ascii=False)}")
            
            control_result = self._simulate_control(command) 
            print(f"[控制结果]: {control_result}")
        except Exception as e:
            print(f"\n[处理失败] 错误类型：{type(e).__name__}, 详情：{str(e)}")

        # 在测试方法结束时
        gc.collect()

    def _simulate_control(self, command: Dict):
        """模拟设备控制逻辑"""
        result = bulid_command(command, None)
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)

    def _generate_mock_data(self):
        """生成完整的模拟测试数据"""
        from collections import namedtuple
        Node = namedtuple('Node', ['id', 'type', 'type_description', 'name', 'device_type'])
        
        rooms = [
            "客厅", "餐厅", "厨房", "阳台", 
            "主卧", "南次卧", "北书房", "主卫", "客卫"
        ]
        
        devices = [
            "客厅灯带", "餐厅灯带", "餐厅吊灯", "背景墙射灯2",
            "背景墙射灯1", "餐厅射灯3", "餐厅射灯4", "泛光灯4",
            "泛光灯5", "泛光灯6", "泛光灯1", "泛光灯2",
            "泛光灯3", "泛光灯6", "格栅灯1", "沙发射灯2",
            "沙发射灯3", "茶几射灯1", "茶几射灯2", "茶几射灯3",
            "阳台灯2", "阳台灯1", "餐厅射灯1", "餐厅射灯2",
            "主卧射灯1", "主卧射灯2", "主卧吸顶顶灯", "过道灯4",
            "过道灯1", "过道灯3", "过道灯2"
        ]
        
        scenes = [
            "日常模式", "睡前模式", "观影模式", "欢迎模式",
            "主卧全关", "主卧全开", "夜灯模式", "阅读模式",
            "全关", "全开"
        ]
        
        return rooms, devices, scenes

    def _format_node_info(self, room_list: List[str], device_list: List[str], scene_list: List[str]) -> str:
        """格式化节点信息字符串"""
        result_strings = []
        node_groups = {}
        
        # 处理房间信息
        for room in room_list:
            if room not in node_groups:
                node_groups[room] = []
            node_groups[room].append(room)
        
        # 处理设备信息
        for device in device_list:
            if device not in node_groups:
                node_groups[device] = []
            node_groups[device].append(device)
        
        # 处理情景模式信息
        for scene in scene_list:
            if scene not in node_groups:
                node_groups[scene] = []
            node_groups[scene].append(scene)
        
        # 处理分组信息
        for node_description, nodes in node_groups.items():
            result_strings.append(f" '{node_description}'数据包含:")
            for node in nodes:
                device_type_str = self._infer_device_type(node)
                device_type_description = self._get_device_type_description(device_type_str)
                
                # 优化点1：合并重复的条件判断
                # 优化点2：添加设备类型描述信息增强可读性
                node_info = (
                    f"- {node}" 
                    if device_type_description != "未知设备类型"
                    else f"- {node}"
                )
                result_strings.append(node_info)
        
        return '\n'.join(result_strings)  # 将列表转为字符串

    def _infer_device_type(self, node: str) -> str:
        """智能推断设备类型（返回DeviceType枚举名称）"""
        keyword_mapping = {
            "射灯": DeviceType.LIGHT_SWITCH.name,
            "灯带": DeviceType.LIGHT_SWITCH.name,
            "吸顶": DeviceType.DIMMABLE_LIGHT.name,
            "吊灯": DeviceType.DIMMABLE_LIGHT.name,
            "窗帘": DeviceType.CURTAIN_MOTOR.name,
            "开关": DeviceType.SWITCH_CONTROLLER.name,
            "传感器": DeviceType.HUMAN_SENSOR.name,
            "门磁": DeviceType.DOOR_MAGNETIC.name,
            "旋钮": DeviceType.KNOB.name,
            "光感": DeviceType.HUMAN_LIGHT_SENSOR.name,
            "亮度": DeviceType.BRIGHTNESS_SENSOR.name,
            "温湿度": DeviceType.TEMPERATURE_HUMIDITY_SENSOR.name
        }
        for keyword, device_type in keyword_mapping.items():
            if keyword in node:
                return device_type
        return DeviceType.LIGHT_SWITCH.name  # 默认类型

    def _get_device_type_description(self, device_type_str: str) -> str:
        """设备类型到中文描述的映射"""
        return {
            DeviceType.LIGHT_SWITCH.name: "可开关灯具",
            DeviceType.DIMMABLE_LIGHT.name: "亮度可调灯具",
            DeviceType.COLOR_TEMPERATURE_LIGHT.name: "色温可调灯具",
            DeviceType.COLOR_LIGHT.name: "色彩可调灯具",
            DeviceType.CURTAIN_MOTOR.name: "窗帘电机",
            DeviceType.SWITCH_CONTROLLER.name: "双路开关控制器",
            DeviceType.AC_GATEWAY.name: "空调网关",
            DeviceType.MULTI_SWITCH_PANEL.name: "多路开关面板",
            DeviceType.DIGITAL_FOCUS_LIGHT.name: "数字调焦色温灯",
            DeviceType.AC_CONTROLLER.name: "空调控制器",
            DeviceType.CONTROL_PANEL.name: "控制面板",
            DeviceType.HUMAN_SENSOR.name: "人体传感器",
            DeviceType.DOOR_MAGNETIC.name: "门磁",
            DeviceType.KNOB.name: "旋钮",
            DeviceType.HUMAN_LIGHT_SENSOR.name: "人体光感传感器",
            DeviceType.BRIGHTNESS_SENSOR.name: "亮度传感器",
            DeviceType.TEMPERATURE_HUMIDITY_SENSOR.name: "温湿度传感器",
            DeviceType.MIRAI_HUMAN_SENSOR.name: "迈睿人体传感器"
        }.get(device_type_str, "未知设备类型")

if __name__ == '__main__':
    tester = LangChainIntegrationTest()
    
    # 测试案例集
    test_cases = [
        "打开客厅所有的灯",
        "请打开客厅灯带",
        "打开阳台灯",
        "执行观影模式",
        "执行全开模式",
        "打开全开模式",
        "关闭背景墙灯",
        "关闭书房灯",
        "关闭书房吸顶灯",
        # "打开小麦岛的灯",
        # "关闭所有灯光"
    ]
    
    for case in test_cases:
        tester.test_scenario(case)
        print("\n" + "="*50 + "\n") 