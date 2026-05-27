import re


class StringUtil:
    @staticmethod
    def filter_invalid_character(content: str) -> str:
        """过滤无效字符 (简单实现)"""
        if not content:
            return ""
        # 可以在这里去除一些特殊的不可见字符
        return content

    @staticmethod
    def extract_json_object(content: str) -> str:
        """
        从 Markdown 中提取 JSON
        例如: ```json { "a": 1 } ``` -> { "a": 1 }
        """
        if not content:
            return ""
        
        # 1. 尝试去除 Markdown 代码块标记
        pattern = r"```json(.*?)```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        pattern_simple = r"```(.*?)```"
        match_simple = re.search(pattern_simple, content, re.DOTALL)
        if match_simple:
            return match_simple.group(1).strip()

        # 2. 如果没有代码块，尝试寻找第一个 { 和最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            return content[start : end + 1]
            
        return content
    
    @staticmethod
    def _to_half_width(text: str) -> str:
        """全角转半角"""
        res = []
        for char in text:
            code = ord(char)
            if code == 0x3000:  # 全角空格
                code = 0x0020
            elif 0xFF01 <= code <= 0xFF5E:  # 全角字符范围
                code -= 0xFEE0
            res.append(chr(code))
        return "".join(res)

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        if not text:
            return False
        # 中文字符常用范围：\u4E00~\u9FFF
        for c in text:
            if '\u4e00' <= c <= '\u9fff':
                return True
        return False

    @staticmethod
    def _replace_wrong_unicode(source: str, replace_str: str = "") -> str:
        if not source:
            return source        
        # 过滤excel、word中的特殊字符
        pattern = re.compile(r'([\u007f-\u009f]|\u00ad|[\u0483-\u0489]|[\u0559-\u055a]|\u058a|[\u0591-\u05bd]|\u05bf|[\u05c1-\u05c2]|[\u05c4-\u05c7]|[\u0606-\u060a]|[\u063b-\u063f]|\u0674|[\u06e5-\u06e6]|\u070f|[\u076e-\u077f]|\u0a51|\u0a75|\u0b44|[\u0b62-\u0b63]|[\u0c62-\u0c63]|[\u0ce2-\u0ce3]|[\u0d62-\u0d63]|\u135f|[\u200b-\u200f]|[\u2028-\u202e]|\u2044|\u2071|[\uf701-\uf70e]|[\uf710-\uf71a]|\ufb1e|[\ufc5e-\ufc62]|\ufeff|\ufffc|\u00a0)')
        return pattern.sub(replace_str, source)

    @staticmethod
    def format_paragraph(text: str) -> str:
        if not text:
            return text
        t = text[:50] if len(text) > 50 else text
        
        # 检测前50个字符是否含有中文 (全角标点先转为半角后再进行判断)
        if not StringUtil._contains_chinese(StringUtil._to_half_width(t)):
            text = StringUtil._to_half_width(text)
            
        text = StringUtil._replace_wrong_unicode(text, "")
        
        # 过滤多余的空行和首尾空白 (与 Java 版本正则表达式保持一致)
        text = re.sub(r'^(\r?\n)*( *)|(\r?\n)*( *)$', '', text)
        text = re.sub(r'(( *)\r?\n( *))+', '\n\n', text)
        return text
