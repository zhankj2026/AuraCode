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
配置管理模块

提供统一的配置管理接口，支持：
- 配置加载（YAML/JSON）
- 配置验证
- 配置热更新
- 配置持久化
"""

from .manager import ConfigManager, config_manager
from .schema import ConfigSchema

__all__ = ['ConfigManager', 'ConfigSchema', 'config_manager']
