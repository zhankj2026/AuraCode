---
name: python-standards
description: Python 编码规范和最佳实践
trigger: 当编写或修改 Python 代码时激活
when_to_use: 当编写或修改 Python 代码时主动激活，确保遵循 PEP8 和最佳实践
---

# Python 编码规范

## 命名约定

### 类和异常
- 使用 `PascalCase` (大驼峰)
- 示例: `class UserManager`, `class InvalidInputError`

### 函数和方法
- 使用 `snake_case` (小写下划线)
- 示例: `def get_user_by_id()`, `def calculate_total()`

### 变量和参数
- 使用 `snake_case`
- 避免单字符名称(除了循环变量 i, j, k)
- 示例: `user_name`, `max_retries`

### 常量
- 使用 `UPPER_SNAKE_CASE`
- 示例: `MAX_CONNECTIONS = 10`, `DEFAULT_TIMEOUT = 30`

### 私有成员
- 单下划线前缀表示受保护: `_internal_method()`
- 双下划线前缀触发名称修饰: `__private_attr`

## 导入顺序

按照以下顺序分组,组之间空一行:

1. **标准库**
   ```python
   import os
   import sys
   from typing import List, Dict
   ```

2. **第三方库**
   ```python
   import requests
   from flask import Flask
   ```

3. **本地模块**
   ```python
   from .utils import helper
   from models.user import User
   ```

### 导入规则
- 每行一个导入
- 避免 `from module import *`
- 使用绝对导入优于相对导入
- 按字母顺序排序

## 代码格式

### 缩进
- 使用 4 个空格,不使用 Tab
- 连续行使用括号对齐

### 行长度
- 最大 88 字符(使用 black 格式化)
- 长字符串使用括号换行

### 空行
- 顶层函数和类定义之间: 2 个空行
- 类内方法之间: 1 个空行
- 函数内逻辑块之间: 1 个空行

## 错误处理

### 原则
1. 使用具体异常,避免 bare `except`
2. 优先使用 `with` 语句管理资源
3. 异常消息要清晰有用

### 示例

```python
# ✅ 正确: 具体异常
try:
    with open('file.txt', 'r') as f:
        data = f.read()
except FileNotFoundError:
    logger.error("文件不存在: file.txt")
except PermissionError:
    logger.error("权限不足: file.txt")

# ❌ 错误: bare except
try:
    do_something()
except:  # 不要这样做
    pass
```

### 上下文管理器
```python
# ✅ 使用 with 自动管理资源
with open('file.txt') as f:
    content = f.read()

# ✅ 自定义上下文管理器
from contextlib import contextmanager

@contextmanager
def temp_dir():
    dir_path = tempfile.mkdtemp()
    try:
        yield dir_path
    finally:
        shutil.rmtree(dir_path)
```

## 文档字符串

### 函数文档
```python
def calculate_total(prices: List[float], tax_rate: float = 0.1) -> float:
    """
    计算含税总价
    
    Args:
        prices: 价格列表
        tax_rate: 税率,默认 0.1
    
    Returns:
        含税总价
    
    Raises:
        ValueError: 如果价格为负
    """
    if any(p < 0 for p in prices):
        raise ValueError("价格不能为负")
    
    subtotal = sum(prices)
    return subtotal * (1 + tax_rate)
```

### 类文档
```python
class UserManager:
    """
    用户管理器
    
    负责用户的创建、查询、更新和删除操作。
    
    Attributes:
        db: 数据库连接
        cache: 缓存实例
    """
    pass
```

## 类型提示

### 基本使用
```python
from typing import List, Dict, Optional, Union

def get_user(user_id: int) -> Optional[Dict[str, str]]:
    """查询用户,不存在返回 None"""
    pass

def process_data(data: Union[str, bytes]) -> str:
    """处理字符串或字节数据"""
    pass
```

### 复杂类型
```python
from typing import TypedDict, Literal

class UserDict(TypedDict):
    id: int
    name: str
    email: str

Status = Literal["active", "inactive", "pending"]
```

## 最佳实践

### 1. 列表推导式优于循环
```python
# ✅ 简洁
squares = [x**2 for x in range(10)]

# ❌ 冗长
squares = []
for x in range(10):
    squares.append(x**2)
```

### 2. 使用 enumerate 而非 range(len())
```python
# ✅ Pythonic
for i, item in enumerate(items):
    print(i, item)

# ❌ 不推荐
for i in range(len(items)):
    print(i, items[i])
```

### 3. 使用 get 方法访问字典
```python
# ✅ 安全
name = user.get('name', 'Unknown')

# ❌ 可能抛出 KeyError
name = user['name']
```

### 4. 使用 pathlib 处理路径
```python
from pathlib import Path

# ✅ 现代方式
file_path = Path('data') / 'output.txt'
file_path.parent.mkdir(parents=True, exist_ok=True)

# ❌ 传统方式
import os
file_path = os.path.join('data', 'output.txt')
```

## 测试规范

- 测试文件命名: `test_<module>.py`
- 测试函数命名: `test_<functionality>()`
- 使用 pytest 框架
- 每个测试只测试一个功能点
- 使用 fixture 管理测试数据
