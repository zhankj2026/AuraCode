"""
测试 CD 命令 - 工作目录切换功能
"""

import os
import tempfile
from commands.builtin import cd_command
from tools.builtin import run_command


def test_cd_show_current_directory():
    """测试 1: 显示当前工作目录"""
    result = cd_command.cd_handler([])
    
    assert "📁 当前工作目录:" in result
    assert run_command._get_cwd() in result
    print("✓ 测试 1 通过: 显示当前工作目录")


def test_cd_to_absolute_path():
    """测试 2: 切换到绝对路径"""
    # 获取当前目录
    old_cwd = run_command._get_cwd()
    
    # 切换到临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        result = cd_command.cd_handler([tmpdir])
        
        assert "✅ 工作目录已切换:" in result
        assert tmpdir in result
        assert run_command._get_cwd() == tmpdir
        
        # 恢复原目录
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 2 通过: 切换到绝对路径")


def test_cd_to_relative_path():
    """测试 3: 切换到相对路径"""
    old_cwd = run_command._get_cwd()
    
    try:
        # 切换到上级目录
        result = cd_command.cd_handler([".."])
        
        expected_path = os.path.normpath(os.path.join(old_cwd, ".."))
        assert "✅ 工作目录已切换:" in result
        assert expected_path in result
        assert run_command._get_cwd() == expected_path
    finally:
        # 恢复原目录
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 3 通过: 切换到相对路径")


def test_cd_to_home_directory():
    """测试 4: 切换到用户主目录"""
    old_cwd = run_command._get_cwd()
    
    try:
        result = cd_command.cd_handler(["~"])
        
        home_dir = os.path.expanduser("~")
        assert "✅ 工作目录已切换:" in result
        assert home_dir in result
        assert run_command._get_cwd() == home_dir
    finally:
        # 恢复原目录
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 4 通过: 切换到用户主目录")


def test_cd_to_nonexistent_directory():
    """测试 5: 切换到不存在的目录"""
    result = cd_command.cd_handler(["/nonexistent/path/12345"])
    
    assert "❌ 目录不存在:" in result
    print("✓ 测试 5 通过: 切换到不存在的目录")


def test_cd_to_file_instead_of_directory():
    """测试 6: 切换到文件而不是目录"""
    # 创建一个临时文件
    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile_path = tmpfile.name
    
    try:
        result = cd_command.cd_handler([tmpfile_path])
        
        assert "❌ 不是目录:" in result
    finally:
        # 清理临时文件
        os.unlink(tmpfile_path)
    
    print("✓ 测试 6 通过: 切换到文件而不是目录")


def test_cd_previous_directory():
    """测试 7: cd - 返回上一个目录"""
    old_cwd = run_command._get_cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 先切换到临时目录
        cd_command.cd_handler([tmpdir])
        assert run_command._get_cwd() == tmpdir
        
        # 然后 cd - 返回
        result = cd_command.cd_handler(["-"])
        
        assert "✅ 工作目录已切换:" in result
        assert old_cwd in result
        assert run_command._get_cwd() == old_cwd
    
    print("✓ 测试 7 通过: cd - 返回上一个目录")


def test_pwd_command():
    """测试 8: pwd 命令（cd 的别名）"""
    result = cd_command.cd_handler([])
    
    assert "📁 当前工作目录:" in result
    print("✓ 测试 8 通过: pwd 命令")


def test_cd_parent_directory():
    """测试 9: cd .. 切换到上级目录"""
    old_cwd = run_command._get_cwd()
    
    try:
        result = cd_command.cd_handler([".."])
        
        parent_dir = os.path.dirname(old_cwd)
        assert "✅ 工作目录已切换:" in result
        assert run_command._get_cwd() == parent_dir
    finally:
        run_command._set_cwd(old_cwd)
    
    print("✓ 测试 9 通过: cd .. 切换到上级目录")


def test_cd_multiple_times():
    """测试 10: 多次切换目录"""
    old_cwd = run_command._get_cwd()
    
    with tempfile.TemporaryDirectory() as tmpdir1:
        with tempfile.TemporaryDirectory() as tmpdir2:
            # 第一次切换
            cd_command.cd_handler([tmpdir1])
            assert run_command._get_cwd() == tmpdir1
            
            # 第二次切换
            cd_command.cd_handler([tmpdir2])
            assert run_command._get_cwd() == tmpdir2
            
            # cd - 应该返回 tmpdir1
            result = cd_command.cd_handler(["-"])
            assert tmpdir1 in result
            assert run_command._get_cwd() == tmpdir1
    
    # 恢复原目录
    run_command._set_cwd(old_cwd)
    
    print("✓ 测试 10 通过: 多次切换目录")


if __name__ == "__main__":
    test_cd_show_current_directory()
    test_cd_to_absolute_path()
    test_cd_to_relative_path()
    test_cd_to_home_directory()
    test_cd_to_nonexistent_directory()
    test_cd_to_file_instead_of_directory()
    test_cd_previous_directory()
    test_pwd_command()
    test_cd_parent_directory()
    test_cd_multiple_times()
    
    print("\n" + "=" * 50)
    print("✅ 所有 CD 命令测试通过！")
    print("=" * 50)
