#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import logging
import subprocess
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Tuple, Set, Any
import winreg

# 1. 初始化设置
# 设置UTF-8编码环境
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deduplication.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定义路径
E_DIR = Path("E")
F_DIR = Path("F")

# 支持的压缩文件扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}

# 7-Zip路径 (根据实际情况修改)
def find_7zip_path():
    """从注册表或环境变量中查找7-Zip安装路径"""
    # 尝试从注册表获取7-Zip路径
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\7-Zip")
        path, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)
        seven_zip_exe = Path(path) / "7z.exe"
        if seven_zip_exe.exists():
            return str(seven_zip_exe)
    except Exception:
        pass
    
    # 尝试从常见安装路径查找
    common_paths = [
        "C:\\Program Files\\7-Zip\\7z.exe",
        "C:\\Program Files (x86)\\7-Zip\\7z.exe",
        os.environ.get('ProgramFiles', '') + "\\7-Zip\\7z.exe",
        os.environ.get('ProgramFiles(x86)', '') + "\\7-Zip\\7z.exe"
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    # 尝试从PATH环境变量中查找
    for path_dir in os.environ.get('PATH', '').split(';'):
        potential_path = Path(path_dir) / "7z.exe"
        if potential_path.exists():
            return str(potential_path)
    
    return None

def setup_directories():
    """创建必要的目录结构"""
    if not E_DIR.exists():
        logger.error(f"源目录 {E_DIR} 不存在")
        raise FileNotFoundError(f"源目录 {E_DIR} 不存在")
    
    # 创建目标目录F（如果不存在）
    F_DIR.mkdir(exist_ok=True)
    logger.info(f"目录 {F_DIR} 已创建或已存在")

def run_7z_command(command: List[str]) -> Tuple[int, str, str]:
    """运行7-Zip命令并返回结果"""
    # 获取7-Zip路径
    seven_zip_path = find_7zip_path()
    if not seven_zip_path:
        logger.error("无法找到7-Zip安装路径")
        return -1, "", "7-Zip not found"
    
    try:
        result = subprocess.run(
            [seven_zip_path] + command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        logger.error(f"运行7-Zip命令失败: {e}")
        return -1, "", str(e)

def get_archive_contents(archive_path: Path) -> List[Tuple[str, int]]:
    """
    使用7-Zip读取压缩包内容,返回文件列表和大小
    处理嵌套压缩包和文件夹
    """
    contents = []
    
    try:
        # 使用7-Zip列出压缩包内容
        returncode, stdout, stderr = run_7z_command(['l', '-slt', str(archive_path)])
        
        if returncode != 0:
            logger.error(f"无法读取压缩包 {archive_path}: {stderr}")
            return contents
        
        # 解析7-Zip输出
        current_file = {}
        for line in stdout.split('\n'):
            line = line.strip()
            if line == '':
                if current_file:
                    # 处理文件信息
                    if 'Path' in current_file and 'Size' in current_file:
                        file_path = current_file['Path']
                        file_size = int(current_file['Size'])
                        
                        # 跳过目录
                        if not file_path.endswith('/'):
                            # 处理嵌套压缩包
                            if Path(file_path).suffix.lower() in ARCHIVE_EXTENSIONS:
                                # 提取嵌套压缩包到临时文件
                                with tempfile.TemporaryDirectory() as temp_dir:
                                    temp_archive = Path(temp_dir) / Path(file_path).name
                                    
                                    # 提取嵌套压缩包
                                    extract_cmd = ['e', str(archive_path), file_path, f'-o{temp_dir}', '-y']
                                    returncode, _, stderr = run_7z_command(extract_cmd)
                                    
                                    if returncode == 0 and temp_archive.exists():
                                        # 递归处理嵌套压缩包
                                        nested_contents = get_archive_contents(temp_archive)
                                        for nested_file, nested_size in nested_contents:
                                            contents.append((f"{file_path}/{nested_file}", nested_size))
                                    else:
                                        logger.warning(f"无法提取嵌套压缩包 {file_path}: {stderr}")
                            else:
                                contents.append((file_path, file_size))
                    
                    current_file = {}
            else:
                # 解析键值对
                if ' = ' in line:
                    key, value = line.split(' = ', 1)
                    current_file[key] = value
    
    except Exception as e:
        logger.error(f"处理压缩包 {archive_path} 时出错: {e}")
    
    return contents

def get_directory_contents(dir_path: Path, base_path: Path = None) -> List[Tuple[str, int]]:
    """
    递归获取目录内容,包括子目录中的文件
    返回格式：[(相对路径, 文件大小), ...]
    """
    if base_path is None:
        base_path = dir_path
    
    contents = []
    
    try:
        for item in dir_path.iterdir():
            if item.is_file():
                try:
                    # 计算相对路径
                    rel_path = str(item.relative_to(base_path))
                    contents.append((rel_path, item.stat().st_size))
                except OSError as e:
                    logger.warning(f"无法读取文件 {item}: {e}")
            
            elif item.is_dir():
                # 递归处理子目录
                sub_contents = get_directory_contents(item, base_path)
                contents.extend(sub_contents)
    
    except Exception as e:
        logger.error(f"处理目录 {dir_path} 时出错: {e}")
    
    return contents

def compare_archives():
    """
    比较压缩包,找出完全相同的压缩包
    将重复的移动到F目录
    """
    logger.info("开始比较压缩包...")
    
    # 获取所有压缩文件
    archive_files = [f for f in E_DIR.iterdir() if f.is_file() and f.suffix.lower() in ARCHIVE_EXTENSIONS]
    logger.info(f"找到 {len(archive_files)} 个压缩文件")
    
    # 存储每个压缩包的内容
    archive_contents = {}
    for archive in archive_files:
        logger.info(f"分析压缩包: {archive.name}")
        contents = get_archive_contents(archive)
        # 排序以确保比较的一致性
        contents.sort()
        archive_contents[archive] = contents
    
    # 找出完全相同的压缩包
    duplicates = {}
    processed = set()
    
    for archive1, contents1 in archive_contents.items():
        if archive1 in processed:
            continue
            
        duplicates[archive1] = []
        
        for archive2, contents2 in archive_contents.items():
            if archive1 == archive2 or archive2 in processed:
                continue
                
            # 比较内容是否完全相同
            if contents1 == contents2:
                duplicates[archive1].append(archive2)
                processed.add(archive2)
    
    # 移动重复的压缩包到F目录
    for keep_archive, duplicate_archives in duplicates.items():
        if duplicate_archives:
            logger.info(f"保留: {keep_archive.name}")
            
            for duplicate in duplicate_archives:
                try:
                    target_path = F_DIR / duplicate.name
                    shutil.move(str(duplicate), str(target_path))
                    logger.info(f"移动: {duplicate.name} -> F/{duplicate.name}")
                except Exception as e:
                    logger.error(f"移动文件 {duplicate} 失败: {e}")

def find_archive_containment():
    """
    找出压缩包之间的包含关系
    将被包含的压缩包移动到F目录
    """
    logger.info("开始查找压缩包包含关系...")
    
    # 获取所有压缩文件
    archive_files = [f for f in E_DIR.iterdir() if f.is_file() and f.suffix.lower() in ARCHIVE_EXTENSIONS]
    
    # 存储每个压缩包的内容
    archive_contents = {}
    for archive in archive_files:
        logger.info(f"分析压缩包: {archive.name}")
        contents = get_archive_contents(archive)
        # 转换为集合以便比较
        content_set = set(contents)
        archive_contents[archive] = content_set
    
    # 找出包含关系
    contained_archives = set()
    containment_relations = {}
    
    for archive1, content_set1 in archive_contents.items():
        if archive1 in contained_archives:
            continue
            
        for archive2, content_set2 in archive_contents.items():
            if archive1 == archive2 or archive2 in contained_archives:
                continue
                
            # 检查是否包含关系
            if content_set1.issubset(content_set2):
                # archive1 被 archive2 包含
                if archive2 not in containment_relations:
                    containment_relations[archive2] = []
                containment_relations[archive2].append(archive1)
                contained_archives.add(archive1)
                logger.info(f"{archive1.name} 被 {archive2.name} 包含")
            
            elif content_set2.issubset(content_set1):
                # archive2 被 archive1 包含
                if archive1 not in containment_relations:
                    containment_relations[archive1] = []
                containment_relations[archive1].append(archive2)
                contained_archives.add(archive2)
                logger.info(f"{archive2.name} 被 {archive1.name} 包含")
    
    # 移动被包含的压缩包到F目录
    for keep_archive, contained_list in containment_relations.items():
        logger.info(f"保留: {keep_archive.name} (包含 {len(contained_list)} 个其他压缩包)")
        
        for contained in contained_list:
            try:
                target_path = F_DIR / contained.name
                shutil.move(str(contained), str(target_path))
                logger.info(f"移动: {contained.name} -> F/{contained.name}")
            except Exception as e:
                logger.error(f"移动文件 {contained} 失败: {e}")

def compare_directories():
    """
    比较文件夹,找出完全相同的文件夹
    将重复的移动到F目录
    """
    logger.info("开始比较文件夹...")
    
    # 获取所有一级子目录
    directories = [d for d in E_DIR.iterdir() if d.is_dir() and d != F_DIR]
    logger.info(f"找到 {len(directories)} 个目录")
    
    # 存储每个目录的内容
    dir_contents = {}
    for directory in directories:
        logger.info(f"分析目录: {directory.name}")
        contents = get_directory_contents(directory)
        # 排序以确保比较的一致性
        contents.sort()
        dir_contents[directory] = contents
    
    # 找出完全相同的目录
    duplicates = {}
    processed = set()
    
    for dir1, contents1 in dir_contents.items():
        if dir1 in processed:
            continue
            
        duplicates[dir1] = []
        
        for dir2, contents2 in dir_contents.items():
            if dir1 == dir2 or dir2 in processed:
                continue
                
            # 比较内容是否完全相同
            if contents1 == contents2:
                duplicates[dir1].append(dir2)
                processed.add(dir2)
    
    # 移动重复的目录到F目录
    for keep_dir, duplicate_dirs in duplicates.items():
        if duplicate_dirs:
            logger.info(f"保留目录: {keep_dir.name}")
            
            for duplicate in duplicate_dirs:
                try:
                    target_path = F_DIR / duplicate.name
                    shutil.move(str(duplicate), str(target_path))
                    logger.info(f"移动目录: {duplicate.name} -> F/{duplicate.name}")
                except Exception as e:
                    logger.error(f"移动目录 {duplicate} 失败: {e}")

def find_directory_containment():
    """
    找出文件夹之间的包含关系
    将被包含的文件夹移动到F目录
    """
    logger.info("开始查找文件夹包含关系...")
    
    # 获取所有一级子目录
    directories = [d for d in E_DIR.iterdir() if d.is_dir() and d != F_DIR]
    
    # 存储每个目录的内容
    dir_contents = {}
    for directory in directories:
        logger.info(f"分析目录: {directory.name}")
        contents = get_directory_contents(directory)
        # 转换为集合以便比较
        content_set = set(contents)
        dir_contents[directory] = content_set
    
    # 找出包含关系
    contained_dirs = set()
    containment_relations = {}
    
    for dir1, content_set1 in dir_contents.items():
        if dir1 in contained_dirs:
            continue
            
        for dir2, content_set2 in dir_contents.items():
            if dir1 == dir2 or dir2 in contained_dirs:
                continue
                
            # 检查是否包含关系
            if content_set1.issubset(content_set2):
                # dir1 被 dir2 包含
                if dir2 not in containment_relations:
                    containment_relations[dir2] = []
                containment_relations[dir2].append(dir1)
                contained_dirs.add(dir1)
                logger.info(f"{dir1.name} 被 {dir2.name} 包含")
            
            elif content_set2.issubset(content_set1):
                # dir2 被 dir1 包含
                if dir1 not in containment_relations:
                    containment_relations[dir1] = []
                containment_relations[dir1].append(dir2)
                contained_dirs.add(dir2)
                logger.info(f"{dir2.name} 被 {dir1.name} 包含")
    
    # 移动被包含的目录到F目录
    for keep_dir, contained_list in containment_relations.items():
        logger.info(f"保留目录: {keep_dir.name} (包含 {len(contained_list)} 个其他目录)")
        
        for contained in contained_list:
            try:
                target_path = F_DIR / contained.name
                shutil.move(str(contained), str(target_path))
                logger.info(f"移动目录: {contained.name} -> F/{contained.name}")
            except Exception as e:
                logger.error(f"移动目录 {contained} 失败: {e}")

def main():
    """主函数"""
    try:
        logger.info("脚本开始运行")
        
        # 检查7-Zip是否可用
        seven_zip_path = find_7zip_path()
        if not seven_zip_path:
            logger.error("7-Zip不可用,请安装7-Zip或确保其在PATH中")
            return
        
        logger.info(f"找到7-Zip: {seven_zip_path}")
        
        # 1. 设置目录
        setup_directories()
        
        # 2. 比较压缩包并去重
        compare_archives()
        
        # 3. 查找压缩包包含关系
        find_archive_containment()
        
        # 4. 比较文件夹并去重
        compare_directories()
        
        # 5. 查找文件夹包含关系
        find_directory_containment()
        
        logger.info("脚本运行完成")
        
    except Exception as e:
        logger.error(f"脚本执行出错: {e}")
        raise

if __name__ == "__main__":
    main()