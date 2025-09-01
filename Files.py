#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import hashlib
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_processing.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

def calculate_file_hash(file_path, chunk_size=8192):
    """
    计算文件的MD5哈希值
    """
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path} - {str(e)}")
        return None

def get_regular_files(folder_path):
    """
    获取文件夹中的普通文件（非压缩文件、非文件夹）
    返回{文件名: 文件信息}字典
    """
    regular_files = {}
    
    # 确保文件夹存在
    if not os.path.exists(folder_path):
        logger.error(f"文件夹不存在: {folder_path}")
        return regular_files
    
    # 压缩文件扩展名列表
    archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}
    
    # 遍历文件夹中的所有条目
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        
        # 只处理文件,跳过文件夹
        if os.path.isfile(full_path):
            # 获取文件扩展名
            _, ext = os.path.splitext(entry)
            
            # 跳过压缩文件
            if ext.lower() in archive_extensions:
                continue
                
            try:
                # 获取文件大小
                file_size = os.path.getsize(full_path)
                
                regular_files[entry] = {
                    'size': file_size,
                    'path': full_path,
                    # 哈希值暂时不计算,等需要时再计算
                    'hash': None
                }
                logger.info(f"已扫描文件: {entry} (大小: {file_size} 字节)")
                    
            except (OSError, PermissionError) as e:
                logger.error(f"无法访问文件 {full_path}: {str(e)}")
                continue
    
    return regular_files

def safe_delete_file(file_path, log_file, reason):
    """安全删除文件并记录"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            log_file.write(f"删除: {file_path} ({reason})\n")
            logger.info(f"已删除: {file_path} ({reason})")
            return True
        return False
    except Exception as e:
        logger.error(f"删除文件失败: {file_path} - {str(e)}")
        log_file.write(f"删除失败: {file_path} - {str(e)}\n")
        return False

def process_regular_files(folder_a, folder_c):
    """
    主处理函数：比较A和C文件夹中的普通文件
    """
    # 扫描普通文件
    logger.info("开始扫描文件夹A中的普通文件...")
    files_a = get_regular_files(folder_a)
    logger.info(f"文件夹A中找到 {len(files_a)} 个普通文件")
    
    logger.info("开始扫描文件夹C中的普通文件...")
    files_c = get_regular_files(folder_c)
    logger.info(f"文件夹C中找到 {len(files_c)} 个普通文件")
    
    # 创建日志文件
    with open("file_processing_report.txt", "w", encoding="utf-8") as log_file:
        log_file.write("普通文件处理报告\n\n")
        
        # 处理C中与A重复的文件
        logger.info("检查C中与A重复的普通文件...")
        to_delete = []
        
        # 构建A文件的查找字典,键为(文件名, 文件大小)
        a_file_map = {}
        for name, info in files_a.items():
            key = (name, info['size'])
            a_file_map[key] = info['path']
        
        # 检查C中的每个文件是否在A中存在同名且同大小的文件
        for name, info in files_c.items():
            key = (name, info['size'])
            if key in a_file_map:
                # 文件名和大小相同,需要比较哈希值
                logger.info(f"发现同名同大小文件: {name}, 开始计算哈希值...")
                
                # 计算C文件的哈希值
                c_hash = calculate_file_hash(info['path'])
                if c_hash is None:
                    logger.warning(f"无法计算C文件哈希值,跳过: {name}")
                    continue
                
                # 计算A文件的哈希值
                a_file_path = a_file_map[key]
                a_hash = calculate_file_hash(a_file_path)
                if a_hash is None:
                    logger.warning(f"无法计算A文件哈希值,跳过: {name}")
                    continue
                
                # 比较哈希值
                if c_hash == a_hash:
                    to_delete.append(info['path'])
                    log_file.write(f"删除: C {name} (与A中文件内容完全相同,A中路径: {a_file_path})\n")
                    logger.info(f"文件内容相同,将删除C中的文件: {name}")
                else:
                    logger.info(f"文件内容不同,保留C中的文件: {name}")
        
        # 执行删除
        deleted_count = 0
        for path in to_delete:
            if safe_delete_file(path, log_file, "与A中文件内容重复"):
                deleted_count += 1
        
        log_file.write(f"\n总计删除 {deleted_count} 个文件\n")
    
    logger.info(f"普通文件处理完成! 删除了 {deleted_count} 个文件")
    return True

if __name__ == "__main__":
    # 设置实际的文件夹路径 - 用户需要修改这些路径
    FOLDER_A = r"A"  # 替换为实际的A文件夹路径
    FOLDER_C = r"C"     # 替换为实际的C文件夹路径
    
    # 检查文件夹是否存在
    if not os.path.exists(FOLDER_A):
        logger.error(f"文件夹 {FOLDER_A} 不存在！")
        sys.exit(1)
    
    if not os.path.exists(FOLDER_C):
        logger.error(f"文件夹 {FOLDER_C} 不存在！")
        sys.exit(1)
    
    # 运行主处理
    logger.info(f"开始处理文件夹 A: {FOLDER_A}")
    logger.info(f"开始处理文件夹 C: {FOLDER_C}")
    
    success = process_regular_files(FOLDER_A, FOLDER_C)
    
    if not success:
        logger.error("处理过程中遇到错误")
        sys.exit(1)
    else:
        logger.info("操作成功完成")
        sys.exit(0)