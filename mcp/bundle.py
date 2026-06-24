"""
MCPB (MCP Bundle) 文件格式支持

对标 Claude Code 的 .mcpb bundle 格式，支持打包分发 MCP 服务器配置。

.mcpb 文件是一个 JSON 格式的配置文件，包含：
- 包元数据（名称、版本、描述）
- 多个 MCP 服务器配置
- 环境变量模板
- 依赖关系声明

使用场景：
1. 打包分发一组相关的 MCP 服务器配置
2. 项目级 MCP 配置模板
3. 企业级 MCP 服务器集合
4. Skill 依赖的 MCP 服务器自动安装

参考：Claude Code 的 .mcpb 文件格式
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class McpbServerConfig:
    """MCPB 中的单个服务器配置"""
    name: str
    type: str = "stdio"  # stdio, sse, http, websocket
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    disabled: bool = False
    auto_approve: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "type": self.type,
            "disabled": self.disabled,
        }
        
        if self.type == "stdio":
            if self.command:
                result["command"] = self.command
            if self.args:
                result["args"] = self.args
            if self.env:
                result["env"] = self.env
        elif self.type in ("sse", "http", "websocket"):
            if self.url:
                result["url"] = self.url
            if self.headers:
                result["headers"] = self.headers
        
        if self.auto_approve:
            result["auto_approve"] = self.auto_approve
        
        return result
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "McpbServerConfig":
        """从字典创建"""
        server_type = data.get("type", "stdio")
        
        if server_type == "stdio":
            return cls(
                name=name,
                type=server_type,
                command=data.get("command"),
                args=data.get("args", []),
                env=data.get("env", {}),
                disabled=data.get("disabled", False),
                auto_approve=data.get("auto_approve", []),
            )
        else:
            return cls(
                name=name,
                type=server_type,
                url=data.get("url"),
                headers=data.get("headers", {}),
                disabled=data.get("disabled", False),
                auto_approve=data.get("auto_approve", []),
            )
    
    def validate(self) -> List[str]:
        """验证配置有效性"""
        errors = []
        
        if not self.name:
            errors.append("Server name is required")
        
        if self.type not in ("stdio", "sse", "http", "websocket"):
            errors.append(f"Invalid server type: {self.type}")
        
        if self.type == "stdio":
            if not self.command:
                errors.append("Command is required for stdio servers")
        elif self.type in ("sse", "http", "websocket"):
            if not self.url:
                errors.append("URL is required for remote servers")
        
        return errors


@dataclass
class McpbMetadata:
    """MCPB 包元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "name": self.name,
            "version": self.version,
        }
        
        if self.description:
            result["description"] = self.description
        if self.author:
            result["author"] = self.author
        if self.license:
            result["license"] = self.license
        if self.homepage:
            result["homepage"] = self.homepage
        if self.keywords:
            result["keywords"] = self.keywords
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "McpbMetadata":
        """从字典创建"""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author"),
            license=data.get("license"),
            homepage=data.get("homepage"),
            keywords=data.get("keywords", []),
        )
    
    def validate(self) -> List[str]:
        """验证元数据有效性"""
        errors = []
        
        if not self.name:
            errors.append("Package name is required")
        
        if not self.version:
            errors.append("Package version is required")
        
        return errors


@dataclass
class McpbBundle:
    """
    MCPB 包（MCP Bundle）
    
    对标 Claude Code 的 .mcpb 文件格式，用于打包分发 MCP 服务器配置。
    
    文件结构：
    ```json
    {
      "name": "database-tools",
      "version": "1.0.0",
      "description": "Database MCP servers bundle",
      "servers": {
        "postgres": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-postgres"],
          "env": {
            "DATABASE_URL": "${user:DATABASE_URL}"
          }
        },
        "redis": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-redis"],
          "env": {
            "REDIS_URL": "${user:REDIS_URL}"
          }
        }
      }
    }
    ```
    """
    metadata: McpbMetadata
    servers: Dict[str, McpbServerConfig] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        result = {
            **self.metadata.to_dict(),
        }
        
        if self.servers:
            result["servers"] = {
                name: config.to_dict()
                for name, config in self.servers.items()
            }
        
        if self.variables:
            result["variables"] = self.variables
        
        if self.dependencies:
            result["dependencies"] = self.dependencies
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "McpbBundle":
        """从字典创建（用于反序列化）"""
        metadata = McpbMetadata.from_dict(data)
        
        servers = {}
        if "servers" in data:
            for name, server_data in data["servers"].items():
                servers[name] = McpbServerConfig.from_dict(name, server_data)
        
        return cls(
            metadata=metadata,
            servers=servers,
            variables=data.get("variables", {}),
            dependencies=data.get("dependencies", []),
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> "McpbBundle":
        """从 .mcpb 文件加载"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"MCPB file not found: {file_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        bundle = cls.from_dict(data)
        logger.info(f"Loaded MCPB bundle from {file_path}: {bundle.metadata.name} v{bundle.metadata.version}")
        
        return bundle
    
    def to_file(self, file_path: str, pretty: bool = True) -> None:
        """保存到 .mcpb 文件"""
        path = Path(file_path)
        
        # 确保扩展名为 .mcpb
        if path.suffix != ".mcpb":
            path = path.with_suffix(".mcpb")
        
        data = self.to_dict()
        
        with open(path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        
        logger.info(f"Saved MCPB bundle to {path}: {self.metadata.name} v{self.metadata.version}")
    
    def validate(self) -> List[str]:
        """验证包完整性"""
        errors = []
        
        # 验证元数据
        errors.extend(self.metadata.validate())
        
        # 验证所有服务器配置
        for name, server in self.servers.items():
            server_errors = server.validate()
            if server_errors:
                errors.append(f"Server '{name}': {'; '.join(server_errors)}")
        
        return errors
    
    def get_enabled_servers(self) -> Dict[str, McpbServerConfig]:
        """获取所有启用的服务器"""
        return {
            name: config
            for name, config in self.servers.items()
            if not config.disabled
        }
    
    def get_disabled_servers(self) -> Dict[str, McpbServerConfig]:
        """获取所有禁用的服务器"""
        return {
            name: config
            for name, config in self.servers.items()
            if config.disabled
        }
    
    def add_server(self, config: McpbServerConfig) -> None:
        """添加服务器配置"""
        self.servers[config.name] = config
    
    def remove_server(self, name: str) -> bool:
        """移除服务器配置"""
        if name in self.servers:
            del self.servers[name]
            return True
        return False
    
    def get_server(self, name: str) -> Optional[McpbServerConfig]:
        """获取服务器配置"""
        return self.servers.get(name)
    
    def resolve_variables(self, user_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        解析环境变量
        
        支持语法：
        - ${user:VAR_NAME}: 从用户变量中获取
        - ${bundle:VAR_NAME}: 从包变量中获取
        - ${VAR_NAME}: 从环境变量中获取
        
        Args:
            user_vars: 用户提供的环境变量
        
        Returns:
            解析后的环境变量字典
        """
        import os
        import re
        
        resolved = {}
        
        # 收集所有需要解析的变量
        for server in self.servers.values():
            for key, value in server.env.items():
                # 匹配 ${...} 语法
                matches = re.findall(r'\$\{([^}]+)\}', value)
                for match in matches:
                    if match.startswith("user:"):
                        var_name = match[5:]
                        if user_vars and var_name in user_vars:
                            resolved[var_name] = user_vars[var_name]
                        else:
                            resolved[var_name] = os.environ.get(var_name, "")
                    elif match.startswith("bundle:"):
                        var_name = match[7:]
                        resolved[var_name] = self.variables.get(var_name, "")
                    else:
                        resolved[match] = os.environ.get(match, "")
        
        return resolved
    
    def get_server_count(self) -> int:
        """获取服务器总数"""
        return len(self.servers)
    
    def get_enabled_count(self) -> int:
        """获取启用的服务器数量"""
        return len(self.get_enabled_servers())


class McpbManager:
    """
    MCPB 包管理器
    
    负责：
    1. 加载和验证 .mcpb 文件
    2. 安装包中的 MCP 服务器到 McpManager
    3. 卸载包中的 MCP 服务器
    4. 包缓存和管理
    """
    
    def __init__(self):
        self._bundles: Dict[str, McpbBundle] = {}
        self._bundle_dir: Optional[Path] = None
    
    def set_bundle_dir(self, dir_path: str) -> None:
        """设置包存储目录"""
        self._bundle_dir = Path(dir_path)
        self._bundle_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Set MCPB bundle directory: {dir_path}")
    
    def load_bundle(self, file_path: str) -> McpbBundle:
        """
        加载 MCPB 包
        
        Args:
            file_path: .mcpb 文件路径
        
        Returns:
            加载的包对象
        """
        bundle = McpbBundle.from_file(file_path)
        
        # 验证包
        errors = bundle.validate()
        if errors:
            error_msg = f"Invalid MCPB bundle: {'; '.join(errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 缓存包
        self._bundles[bundle.metadata.name] = bundle
        
        return bundle
    
    def install_bundle(
        self,
        file_path: str,
        mcp_manager: Any,  # McpManager 实例
        user_vars: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """
        安装 MCPB 包
        
        Args:
            file_path: .mcpb 文件路径
            mcp_manager: McpManager 实例
            user_vars: 用户提供的环境变量
        
        Returns:
            成功安装的服务器名称列表
        """
        # 加载包
        bundle = self.load_bundle(file_path)
        
        installed_servers = []
        
        # 安装所有启用的服务器
        for name, server_config in bundle.get_enabled_servers().items():
            try:
                # 解析环境变量
                from mcp.config import McpStdioServerConfig, McpSSEServerConfig
                
                if server_config.type == "stdio":
                    # 解析环境变量
                    env = {}
                    for key, value in server_config.env.items():
                        import re
                        matches = re.findall(r'\$\{([^}]+)\}', value)
                        if matches:
                            resolved_vars = bundle.resolve_variables(user_vars)
                            resolved_value = value
                            for var_name in matches:
                                if var_name in resolved_vars:
                                    resolved_value = resolved_value.replace(
                                        f"${{{var_name}}}", resolved_vars[var_name]
                                    )
                            env[key] = resolved_value
                        else:
                            env[key] = value
                    
                    config = McpStdioServerConfig(
                        command=server_config.command,
                        args=server_config.args,
                        env=env if env else None,
                    )
                else:
                    config = McpSSEServerConfig(
                        url=server_config.url,
                        headers=server_config.headers if server_config.headers else None,
                    )
                
                # 添加到 McpManager
                import asyncio
                loop = asyncio.get_event_loop()
                state = loop.run_until_complete(mcp_manager.add_server(name, config))
                
                if not state.error:
                    installed_servers.append(name)
                    logger.info(f"Installed server '{name}' from bundle '{bundle.metadata.name}'")
                else:
                    logger.warning(f"Failed to install server '{name}': {state.error}")
            
            except Exception as e:
                logger.error(f"Error installing server '{name}': {e}")
        
        return installed_servers
    
    def uninstall_bundle(
        self,
        bundle_name: str,
        mcp_manager: Any,
    ) -> List[str]:
        """
        卸载 MCPB 包
        
        Args:
            bundle_name: 包名称
            mcp_manager: McpManager 实例
        
        Returns:
            成功卸载的服务器名称列表
        """
        if bundle_name not in self._bundles:
            raise ValueError(f"Bundle not found: {bundle_name}")
        
        bundle = self._bundles[bundle_name]
        uninstalled_servers = []
        
        # 卸载所有服务器
        for name in bundle.servers.keys():
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(mcp_manager.remove_server(name))
                uninstalled_servers.append(name)
                logger.info(f"Uninstalled server '{name}' from bundle '{bundle_name}'")
            except Exception as e:
                logger.error(f"Error uninstalling server '{name}': {e}")
        
        # 从缓存中移除
        del self._bundles[bundle_name]
        
        return uninstalled_servers
    
    def list_bundles(self) -> Dict[str, McpbBundle]:
        """列出所有已加载的包"""
        return self._bundles.copy()
    
    def get_bundle(self, name: str) -> Optional[McpbBundle]:
        """获取包"""
        return self._bundles.get(name)
    
    def scan_directory(self, dir_path: Optional[str] = None) -> List[str]:
        """
        扫描目录中的 .mcpb 文件
        
        Args:
            dir_path: 目录路径（默认使用 bundle_dir）
        
        Returns:
            发现的 .mcpb 文件路径列表
        """
        target_dir = Path(dir_path) if dir_path else self._bundle_dir
        
        if not target_dir or not target_dir.exists():
            return []
        
        mcpb_files = []
        for file_path in target_dir.glob("*.mcpb"):
            mcpb_files.append(str(file_path))
        
        logger.info(f"Found {len(mcpb_files)} MCPB files in {target_dir}")
        return mcpb_files


# 全局 MCPB 管理器实例
_mcpb_manager: Optional[McpbManager] = None


def get_mcpb_manager() -> McpbManager:
    """获取全局 MCPB 管理器"""
    global _mcpb_manager
    if _mcpb_manager is None:
        _mcpb_manager = McpbManager()
    return _mcpb_manager


def initialize_mcpb(bundle_dir: Optional[str] = None) -> McpbManager:
    """
    初始化 MCPB 管理器
    
    Args:
        bundle_dir: 包存储目录
    
    Returns:
        MCPB 管理器实例
    """
    manager = get_mcpb_manager()
    
    if bundle_dir:
        manager.set_bundle_dir(bundle_dir)
    
    return manager
