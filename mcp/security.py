#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 zhankj
#
# This source code is licensed under the [ Apache-2.0] license.
# For the full license text, please refer to the LICENSE file in the root directory.
#
# Author: zhankj <creating2018@aliyun.com>
# Project Homepage: http://www.auracode.top
#

"""
MCP Security Policy - MCP 服务器安全策略

参考标准实现 src/services/mcp/config.ts 中的安全策略实现：
1. 允许列表 (Allowlist) - 只允许配置的服务器
2. 拒绝列表 (Denylist) - 禁止特定服务器
3. 命令精确匹配 - stdio 服务器的命令数组匹配
4. URL 模式匹配 - 远程服务器的 URL 通配符匹配

配置示例 (config.yaml):
    mcp:
      security:
        allowlist:
          - server_name: "postgres"
          - server_command: ["npx", "-y", "@modelcontextprotocol/server-filesystem"]
          - server_url: "https://*.example.com/*"
        denylist:
          - server_name: "dangerous-server"
          - server_command: ["rm", "-rf"]
"""
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AllowedMcpServerEntry:
    """允许列表条目（三种匹配方式互斥）"""
    server_name: Optional[str] = None
    server_command: Optional[List[str]] = None
    server_url: Optional[str] = None
    
    def validate(self) -> List[str]:
        """验证条目有效性"""
        errors = []
        defined_count = sum([
            self.server_name is not None,
            self.server_command is not None,
            self.server_url is not None,
        ])
        
        if defined_count == 0:
            errors.append("Entry must have at least one of: server_name, server_command, server_url")
        elif defined_count > 1:
            errors.append("Entry must have exactly one of: server_name, server_command, server_url")
        
        if self.server_command and len(self.server_command) == 0:
            errors.append("server_command must have at least one element (the command)")
        
        if self.server_name and not self._is_valid_name(self.server_name):
            errors.append(f"Invalid server_name: {self.server_name}")
        
        return errors
    
    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """验证服务器名称格式"""
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))


@dataclass
class DeniedMcpServerEntry:
    """拒绝列表条目"""
    server_name: Optional[str] = None
    server_command: Optional[List[str]] = None
    server_url: Optional[str] = None


@dataclass
class McpSecurityPolicy:
    """MCP 安全策略配置"""
    allowlist: Optional[List[AllowedMcpServerEntry]] = None  # None = 无限制，[] = 全部拒绝
    denylist: List[DeniedMcpServerEntry] = field(default_factory=list)
    enabled: bool = True
    
    def is_server_allowed(self, server_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        检查服务器是否被允许
        
        优先级:
        1. 拒绝列表优先（绝对拒绝）
        2. 允许列表检查（如果有配置）
        3. 无允许列表 = 全部允许
        
        Args:
            server_name: 服务器名称
            config: 服务器配置（用于命令/URL 匹配）
        
        Returns:
            True 如果允许，False 如果拒绝
        """
        if not self.enabled:
            return True
        
        # 1. 拒绝列表优先
        if self._is_server_denied(server_name, config):
            logger.warning(f"MCP server '{server_name}' denied by denylist")
            return False
        
        # 2. 允许列表检查
        # allowlist is None = 无限制 = 全部允许
        if self.allowlist is None:
            return True
        
        # 空允许列表 = 全部拒绝
        if len(self.allowlist) == 0:
            logger.warning(f"MCP server '{server_name}' denied: empty allowlist")
            return False
        
        # 检查是否有显式的允许条目（至少有一个条目定义了具体内容）
        has_explicit_entries = any([
            e.server_name is not None or 
            e.server_command is not None or 
            e.server_url is not None 
            for e in self.allowlist
        ])
        
        if not has_explicit_entries:
            # 所有条目都是空的 = 全部拒绝
            logger.warning(f"MCP server '{server_name}' denied: empty allowlist entries")
            return False
        
        # 3. 检查是否包含命令或 URL 条目
        has_command_entries = any(e.server_command for e in self.allowlist)
        has_url_entries = any(e.server_url for e in self.allowlist)
        
        if config:
            server_command = self._get_command_array(config)
            server_url = self._get_server_url(config)
            
            if server_command:
                # stdio 服务器
                if has_command_entries:
                    # 如果有命令条目，必须匹配其中一个
                    for entry in self.allowlist:
                        if entry.server_command and self._command_arrays_match(
                            entry.server_command, server_command
                        ):
                            return True
                    logger.warning(
                        f"MCP server '{server_name}' denied: command not in allowlist"
                    )
                    return False
                else:
                    # 无命令条目，检查名称匹配
                    for entry in self.allowlist:
                        if entry.server_name == server_name:
                            return True
                    logger.warning(
                        f"MCP server '{server_name}' denied: name not in allowlist"
                    )
                    return False
            
            elif server_url:
                # 远程服务器（SSE/HTTP/WS）
                if has_url_entries:
                    # 如果有 URL 条目，必须匹配其中一个
                    for entry in self.allowlist:
                        if entry.server_url and self._url_matches_pattern(
                            server_url, entry.server_url
                        ):
                            return True
                    logger.warning(
                        f"MCP server '{server_name}' denied: URL not in allowlist"
                    )
                    return False
                else:
                    # 无 URL 条目，检查名称匹配
                    for entry in self.allowlist:
                        if entry.server_name == server_name:
                            return True
                    logger.warning(
                        f"MCP server '{server_name}' denied: name not in allowlist"
                    )
                    return False
            else:
                # 未知类型，仅检查名称
                for entry in self.allowlist:
                    if entry.server_name == server_name:
                        return True
                logger.warning(
                    f"MCP server '{server_name}' denied: name not in allowlist"
                )
                return False
        
        # 无配置，仅检查名称
        for entry in self.allowlist:
            if entry.server_name == server_name:
                return True
        
        logger.warning(
            f"MCP server '{server_name}' denied: name not in allowlist"
        )
        return False
    
    def _is_server_denied(self, server_name: str, config: Optional[Dict]) -> bool:
        """检查服务器是否在拒绝列表中"""
        for entry in self.denylist:
            if entry.server_name and entry.server_name == server_name:
                return True
            
            if config:
                server_command = self._get_command_array(config)
                if entry.server_command and server_command:
                    if self._command_arrays_match(entry.server_command, server_command):
                        return True
                
                server_url = self._get_server_url(config)
                if entry.server_url and server_url:
                    if self._url_matches_pattern(server_url, entry.server_url):
                        return True
        
        return False
    
    def _get_command_array(self, config: Dict) -> Optional[List[str]]:
        """从配置中提取命令数组"""
        if config.get("type") == "stdio" or "command" in config:
            command = config.get("command", "")
            args = config.get("args", [])
            if command:
                return [command] + (args if isinstance(args, list) else [])
        return None
    
    def _get_server_url(self, config: Dict) -> Optional[str]:
        """从配置中提取服务器 URL"""
        if config.get("type") in ("sse", "http", "ws") or "url" in config:
            return config.get("url")
        return None
    
    def _command_arrays_match(self, allowed: List[str], actual: List[str]) -> bool:
        """
        精确匹配命令数组
        
        要求:
        - 长度相同
        - 每个元素完全匹配
        """
        if len(allowed) != len(actual):
            return False
        
        return all(a == b for a, b in zip(allowed, actual))
    
    def _url_matches_pattern(self, url: str, pattern: str) -> bool:
        """
        URL 模式匹配（支持通配符）
        
        支持:
        - *: 匹配任意字符（除 / 外）
        - **: 匹配任意字符（包括 /）
        - ?: 匹配单个字符
        
        示例:
        - "https://*.example.com/*" 匹配 "https://api.example.com/mcp"
        - "http://localhost:*" 匹配 "http://localhost:3000"
        """
        # 将 URL 模式转换为 fnmatch 模式
        # fnmatch 支持 *, ?, [seq], [!seq]
        return fnmatch.fnmatch(url, pattern)
    
    def validate(self) -> List[str]:
        """验证安全策略配置"""
        errors = []
        
        for i, entry in enumerate(self.allowlist):
            entry_errors = entry.validate()
            if entry_errors:
                errors.append(f"Allowlist entry {i}: {'; '.join(entry_errors)}")
            
            # 额外检查空命令数组
            if entry.server_command is not None and len(entry.server_command) == 0:
                errors.append(f"Allowlist entry {i}: server_command must have at least one element")
        
        for i, entry in enumerate(self.denylist):
            # 拒绝列表同样需要验证
            defined_count = sum([
                entry.server_name is not None,
                entry.server_command is not None,
                entry.server_url is not None,
            ])
            if defined_count == 0:
                errors.append(f"Denylist entry {i}: must have at least one field")
            elif defined_count > 1:
                errors.append(f"Denylist entry {i}: must have exactly one field")
            
            # 额外检查空命令数组
            if entry.server_command is not None and len(entry.server_command) == 0:
                errors.append(f"Denylist entry {i}: server_command must have at least one element")
        
        return errors


def load_security_policy(config: Dict[str, Any]) -> McpSecurityPolicy:
    """
    从配置字典加载安全策略
    
    Args:
        config: 配置字典（通常来自 config.yaml 的 mcp.security 部分）
    
    Returns:
        McpSecurityPolicy 实例
    """
    policy = McpSecurityPolicy(allowlist=[])  # 初始化为空列表
    
    security_config = config.get("mcp", {}).get("security", {})
    if not security_config:
        return policy
    
    # 加载启用状态
    policy.enabled = security_config.get("enabled", True)
    
    # 加载允许列表
    allowlist_config = security_config.get("allowlist", [])
    for entry_config in allowlist_config:
        if isinstance(entry_config, dict):
            entry = AllowedMcpServerEntry(
                server_name=entry_config.get("server_name"),
                server_command=entry_config.get("server_command"),
                server_url=entry_config.get("server_url"),
            )
            policy.allowlist.append(entry)
        elif isinstance(entry_config, str):
            # 简单字符串作为服务器名称
            policy.allowlist.append(AllowedMcpServerEntry(server_name=entry_config))
    
    # 加载拒绝列表
    denylist_config = security_config.get("denylist", [])
    for entry_config in denylist_config:
        if isinstance(entry_config, dict):
            entry = DeniedMcpServerEntry(
                server_name=entry_config.get("server_name"),
                server_command=entry_config.get("server_command"),
                server_url=entry_config.get("server_url"),
            )
            policy.denylist.append(entry)
        elif isinstance(entry_config, str):
            policy.denylist.append(DeniedMcpServerEntry(server_name=entry_config))
    
    # 验证配置
    errors = policy.validate()
    if errors:
        logger.warning(f"MCP security policy validation errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return policy


# 全局安全策略实例
_global_security_policy: Optional[McpSecurityPolicy] = None


def get_security_policy() -> McpSecurityPolicy:
    """获取全局安全策略实例"""
    global _global_security_policy
    if _global_security_policy is None:
        _global_security_policy = McpSecurityPolicy()
    return _global_security_policy


def set_security_policy(policy: McpSecurityPolicy) -> None:
    """设置全局安全策略实例"""
    global _global_security_policy
    _global_security_policy = policy
    logger.info(f"MCP security policy updated (enabled={policy.enabled}, "
                f"allowlist={len(policy.allowlist)}, denylist={len(policy.denylist)})")


def initialize_security_policy(config: Dict[str, Any]) -> None:
    """从配置初始化全局安全策略"""
    policy = load_security_policy(config)
    set_security_policy(policy)


def is_mcp_server_allowed(
    server_name: str,
    config: Optional[Dict[str, Any]] = None
) -> bool:
    """
    便捷函数：检查 MCP 服务器是否被允许
    
    Args:
        server_name: 服务器名称
        config: 服务器配置
    
    Returns:
        True 如果允许，False 如果拒绝
    """
    policy = get_security_policy()
    return policy.is_server_allowed(server_name, config)
