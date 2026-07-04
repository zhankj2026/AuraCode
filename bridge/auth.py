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
Bridge 简单 Bearer Token 认证
"""

import secrets
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


_bearer_scheme = HTTPBearer(auto_error=False)


class SimpleTokenAuth:
    """简单 Bearer Token 认证"""

    def __init__(self, token: Optional[str] = None):
        self.token: str = token or secrets.token_urlsafe(32)

    def verify(
        self, credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
    ) -> bool:
        if not credentials or credentials.credentials != self.token:
            raise HTTPException(status_code=401, detail="Invalid or missing token")
        return True

    def get_token(self) -> str:
        return self.token
