import re

class NameMatcher:
    @staticmethod
    def normalize_name(name):
        # 去除空格
        name = name.replace(" ", "")
        # 将全角字符转换为半角字符
        name = ''.join(chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char for char in name)
        # 将中文数字转换为阿拉伯数字
        chinese_to_arabic = str.maketrans('零一二三四五六七八九', '0123456789')
        name = name.translate(chinese_to_arabic)
        return name

    @staticmethod
    def match_device_name(dev_name, target_name):
        # 规范化名称
        dev_name = NameMatcher.normalize_name(dev_name)
        target_name = NameMatcher.normalize_name(target_name)
        
        # 完全匹配
        if dev_name == target_name:
            return True
        # 前缀匹配
        if dev_name.startswith(target_name):
            return True
        # 模糊匹配
        if re.search(target_name, dev_name):
            return True
        return False

    @staticmethod
    def find_devices_by_name(nodes, name):
        # 遍历 NodeInfo 实例
        for dev in nodes:
            # 打印设备的名称和类型描述
            print(f"设备名称: {dev.name}, 类型描述: {dev.type_description}")
        
        # 返回匹配的设备
        return [dev for dev in nodes if NameMatcher.match_device_name(dev.name, name)] 