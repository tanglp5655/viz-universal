# -*- coding: utf-8 -*-
"""统一退出码与中文提示前缀（P0 工程化）。

退出码约定（脚本 main() 返回值，调用方/CI 据此判断）：
  EXIT_OK      0  成功
  EXIT_USAGE   1  用户输入/参数错误（缺参数、文件不存在、密码缺失）
  EXIT_CONFIG  2  配置/环境错误（依赖缺失、行业预置缺失、主题库缺失）
  EXIT_RUNTIME 3  运行时错误（数据为空、读取失败、处理异常）
"""

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_CONFIG = 2
EXIT_RUNTIME = 3


def err(msg):
    print('[错误] ' + msg)


def warn(msg):
    print('[警告] ' + msg)


def info(msg):
    print('[信息] ' + msg)
