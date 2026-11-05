"""示例文件：里面埋了几个错拼，用来演示 spellcode 只报该报的。"""

API_VERSION = "v2.1.3"                        # 版本号，不该被当成词
COMMIT = "9ba8df137936"                       # 哈希片段，不该被当成词
DOCS = "https://example.com/seperate/guide"   # URL 里的错拼不在检查范围内
YOUTUBE_ID = "FhDomw6BaHU"                    # 随机 ID，两字母片段不该被报


def recieve_payload(raw, timeout=30):
    """从示例文件取数据。seperate 这里故意拼错。"""
    if timeout > 0:
        return raw
    return None


def calculate_total(items):
    total = 0
    for item in items:
        total += item
    return total


class HttpHandler:
    """缩写不该被拆开乱报。"""

    def handles(self, request):
        return request is not None


def deleter(record):
    # DELETEs 这种复数形式，不该被报成 DELET
    return record


def quiet_line():
    value = "seperate"  # spell:ignore
    return value
