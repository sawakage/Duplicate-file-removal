#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
import logging
from collections import defaultdict
import time

# 设置日志
def setup_logging():
    """配置日志系统"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 防止重复添加处理器
    if logger.handlers:
        return logger
    
    # 文件处理器
    file_handler = logging.FileHandler("file_cleanup.log", encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 格式化
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def safe_path_operation(func, path, *args, **kwargs):
    """安全执行路径操作,处理可能的异常"""
    try:
        return func(path, *args, **kwargs)
    except (OSError, PermissionError, UnicodeEncodeError) as e:
        logger.error(f"操作失败: {path} - 错误: {e}")
        return None
    except Exception as e:
        logger.error(f"未知错误: {path} - 错误: {e}")
        return None

def get_file_info(file_path):
    """获取文件的名称和大小信息"""
    try:
        file_path = Path(file_path)
        if not file_path.is_file():
            return None
        
        # 获取文件名和大小
        file_name = file_path.name
        file_size = file_path.stat().st_size
        
        return (file_name, file_size)
    except Exception as e:
        logger.error(f"获取文件信息失败: {file_path} - 错误: {e}")
        return None

def scan_files_efficiently(directory):
    """高效扫描目录中的所有文件,返回文件信息字典"""
    file_dict = defaultdict(list)
    scanned_count = 0
    error_count = 0
    
    logger.info(f"开始扫描目录: {directory}")
    start_time = time.time()
    
    # 使用os.scandir()而不是os.walk(),它更高效
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    # 递归扫描子目录
                    subdir_dict, sub_scanned, sub_errors = scan_files_efficiently(entry.path)
                    for key, paths in subdir_dict.items():
                        file_dict[key].extend(paths)
                    scanned_count += sub_scanned
                    error_count += sub_errors
                elif entry.is_file(follow_symlinks=False):
                    # 处理文件
                    file_path = Path(entry.path)
                    file_info = safe_path_operation(get_file_info, file_path)
                    
                    if file_info:
                        file_dict[file_info].append(file_path)
                        scanned_count += 1
                    else:
                        error_count += 1
    except Exception as e:
        logger.error(f"扫描目录失败: {directory} - 错误: {e}")
        error_count += 1
    
    elapsed_time = time.time() - start_time
    logger.info(f"扫描完成: {directory} - 找到 {scanned_count} 个文件, 遇到 {error_count} 个错误, 耗时: {elapsed_time:.2f}秒")
    
    return file_dict, scanned_count, error_count

def remove_duplicates_and_matches(b_dir, d_dir):
    """高效删除D文件夹中的重复文件和与B文件夹匹配的文件"""
    logger.info("开始处理D文件夹中的重复文件和与B文件夹匹配的文件")
    start_time = time.time()
    
    # 先扫描B文件夹
    logger.info("扫描B文件夹...")
    b_files, b_scanned, b_errors = scan_files_efficiently(b_dir)
    logger.info(f"B文件夹扫描完成: 找到 {b_scanned} 个文件, 遇到 {b_errors} 个错误")
    
    # 扫描D文件夹
    logger.info("扫描D文件夹...")
    d_files, d_scanned, d_errors = scan_files_efficiently(d_dir)
    logger.info(f"D文件夹扫描完成: 找到 {d_scanned} 个文件, 遇到 {d_errors} 个错误")
    
    removed_duplicates = 0
    removed_matches = 0
    
    # 处理D文件夹中的文件
    for file_info, paths in d_files.items():
        if len(paths) > 1:
            # 处理重复文件
            file_name, file_size = file_info
            logger.info(f"找到重复文件: {file_name} (大小: {file_size} 字节), 共 {len(paths)} 个副本")
            
            # 保留第一个文件,删除其余副本
            kept_file = paths[0]
            for file_path in paths[1:]:
                if safe_path_operation(os.remove, file_path):
                    logger.info(f"已删除重复文件: {file_path} (保留: {kept_file})")
                    removed_duplicates += 1
        
        # 检查是否与B文件夹中的文件匹配
        if file_info in b_files:
            file_name, file_size = file_info
            logger.info(f"找到与B文件夹匹配的文件: {file_name} (大小: {file_size} 字节)")
            
            # 删除D中的所有匹配文件
            for file_path in paths:
                if safe_path_operation(os.remove, file_path):
                    logger.info(f"已删除匹配文件: {file_path} (B中存在: {b_files[file_info][0]})")
                    removed_matches += 1
    
    elapsed_time = time.time() - start_time
    logger.info(f"处理完成: 共删除 {removed_duplicates + removed_matches} 个文件, 耗时: {elapsed_time:.2f}秒")
    logger.info(f"- 删除重复文件: {removed_duplicates}")
    logger.info(f"- 删除与B匹配的文件: {removed_matches}")
    
    return removed_duplicates, removed_matches

def main():
    """主函数"""
    # 设置控制台编码为UTF-8
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    # 定义B和D文件夹路径
    b_dir = Path("B")
    d_dir = Path("D")
    
    # 检查文件夹是否存在
    if not b_dir.exists() or not b_dir.is_dir():
        logger.error("B文件夹不存在或不是有效目录")
        return
    
    if not d_dir.exists() or not d_dir.is_dir():
        logger.error("D文件夹不存在或不是有效目录")
        return
    
    logger.info("开始处理任务...")
    total_start_time = time.time()
    
    # 合并处理：删除D文件夹中的重复文件和与B文件夹匹配的文件
    removed_duplicates, removed_matches = remove_duplicates_and_matches(b_dir, d_dir)
    
    total_elapsed_time = time.time() - total_start_time
    logger.info(f"所有任务完成! 共删除 {removed_duplicates + removed_matches} 个文件, 总耗时: {total_elapsed_time:.2f}秒")

if __name__ == "__main__":
    main()