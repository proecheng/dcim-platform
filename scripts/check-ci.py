#!/usr/bin/env python3
"""
GitHub Actions CI 错误监控和解析工具

功能:
- 自动监控最新的 CI 运行
- 解析 Ruff 代码检查错误
- 解析 ESLint 错误
- 解析测试失败
- 提供修复建议

使用方法:
    python scripts/check-ci.py              # 检查最新的 CI 运行
    python scripts/check-ci.py --watch      # 实时监控 CI 运行
    python scripts/check-ci.py --run-id 123 # 检查特定的运行
"""

import subprocess
import json
import sys
import time
import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class CIError:
    """CI 错误信息"""
    job_name: str
    step_name: str
    error_type: str  # ruff, eslint, pytest, build, typecheck
    file_path: Optional[str]
    line_number: Optional[int]
    error_code: Optional[str]
    message: str
    suggestion: Optional[str] = None


class CIMonitor:
    """GitHub Actions CI 监控器"""
    
    def __init__(self):
        self.check_gh_cli()
    
    def check_gh_cli(self):
        """检查 gh CLI 是否可用"""
        try:
            subprocess.run(['gh', 'auth', 'status'], 
                         capture_output=True, check=True)
        except subprocess.CalledProcessError:
            print("❌ 错误: GitHub CLI 未认证")
            print("请运行: gh auth login")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ 错误: 未安装 GitHub CLI")
            print("请访问 https://cli.github.com/ 安装")
            sys.exit(1)
    
    def get_latest_run(self) -> Optional[Dict]:
        """获取最新的 CI 运行"""
        try:
            result = subprocess.run(
                ['gh', 'run', 'list', '--limit', '1', '--json', 
                 'databaseId,status,conclusion,name,headBranch,workflowName'],
                capture_output=True, text=True, check=True
            )
            runs = json.loads(result.stdout)
            return runs[0] if runs else None
        except Exception as e:
            print(f"❌ 获取 CI 运行失败: {e}")
            return None
    
    def watch_run(self, run_id: int) -> bool:
        """监控 CI 运行，返回是否成功"""
        print(f"⏳ 正在监控 CI 运行 #{run_id}...")
        print("(按 Ctrl+C 可以退出监控，CI 会继续运行)")
        print()
        
        try:
            result = subprocess.run(
                ['gh', 'run', 'watch', str(run_id), '--exit-status'],
                capture_output=False
            )
            return result.returncode == 0
        except KeyboardInterrupt:
            print("\n⚠️  监控已取消，CI 继续运行")
            return False
    
    def get_failed_jobs(self, run_id: int) -> List[Dict]:
        """获取失败的作业"""
        try:
            result = subprocess.run(
                ['gh', 'run', 'view', str(run_id), '--json', 'jobs'],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            return [job for job in data['jobs'] 
                   if job['conclusion'] == 'failure']
        except Exception as e:
            print(f"❌ 获取失败作业失败: {e}")
            return []
    
    def get_job_logs(self, run_id: int) -> str:
        """获取失败作业的日志"""
        try:
            result = subprocess.run(
                ['gh', 'run', 'view', str(run_id), '--log-failed'],
                capture_output=True, text=True, check=True
            )
            return result.stdout
        except Exception as e:
            print(f"❌ 获取日志失败: {e}")
            return ""
    
    def parse_ruff_errors(self, logs: str) -> List[CIError]:
        """解析 Ruff 错误"""
        errors = []
        
        # Ruff 错误格式: path/to/file.py:123:45: E501 Line too long
        pattern = r'([^\s:]+\.py):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)'
        
        for match in re.finditer(pattern, logs):
            file_path, line, col, code, message = match.groups()
            
            suggestion = self._get_ruff_suggestion(code)
            
            errors.append(CIError(
                job_name='后端测试',
                step_name='Ruff 代码检查',
                error_type='ruff',
                file_path=file_path,
                line_number=int(line),
                error_code=code,
                message=message.strip(),
                suggestion=suggestion
            ))
        
        return errors
    
    def parse_eslint_errors(self, logs: str) -> List[CIError]:
        """解析 ESLint 错误"""
        errors = []
        
        # ESLint 错误格式: /path/to/file.ts
        #   123:45  error  Message  rule-name
        current_file = None
        
        for line in logs.split('\n'):
            # 检测文件路径
            if line.strip() and not line.startswith(' ') and '.ts' in line or '.vue' in line:
                current_file = line.strip()
            
            # 检测错误行
            match = re.match(r'\s+(\d+):(\d+)\s+(error|warning)\s+(.+?)\s+([a-z-]+)$', line)
            if match and current_file:
                line_num, col, severity, message, rule = match.groups()
                
                if severity == 'error':
                    errors.append(CIError(
                        job_name='前端检查',
                        step_name='ESLint 代码检查',
                        error_type='eslint',
                        file_path=current_file,
                        line_number=int(line_num),
                        error_code=rule,
                        message=message.strip(),
                        suggestion=self._get_eslint_suggestion(rule)
                    ))
        
        return errors
    
    def parse_pytest_errors(self, logs: str) -> List[CIError]:
        """解析 Pytest 错误"""
        errors = []
        
        # Pytest 失败格式: FAILED tests/test_file.py::test_name - AssertionError
        pattern = r'FAILED\s+(tests/[^\s:]+)::([\w_]+)\s+-\s+(.+)'
        
        for match in re.finditer(pattern, logs):
            file_path, test_name, message = match.groups()
            
            errors.append(CIError(
                job_name='后端测试',
                step_name='运行测试',
                error_type='pytest',
                file_path=file_path,
                line_number=None,
                error_code=test_name,
                message=message.strip(),
                suggestion="检查测试用例和相关代码逻辑"
            ))
        
        return errors
    
    def _get_ruff_suggestion(self, code: str) -> str:
        """获取 Ruff 错误的修复建议"""
        suggestions = {
            'E501': '行太长，考虑拆分或使用 # noqa: E501',
            'F401': '未使用的导入，删除或使用 # noqa: F401',
            'F841': '未使用的变量，删除或重命名为 _variable',
            'W293': '空行包含空格，运行 ruff format 自动修复',
            'E402': '导入应在文件顶部',
        }
        return suggestions.get(code, f'运行 ruff check --fix 尝试自动修复')
    
    def _get_eslint_suggestion(self, rule: str) -> str:
        """获取 ESLint 错误的修复建议"""
        suggestions = {
            'no-unused-vars': '删除未使用的变量或添加前缀 _',
            'no-console': '移除 console.log 或使用 eslint-disable',
            '@typescript-eslint/no-explicit-any': '使用具体类型替代 any',
        }
        return suggestions.get(rule, f'运行 npm run lint -- --fix 尝试自动修复')
    
    def display_errors(self, errors: List[CIError]):
        """显示错误信息"""
        if not errors:
            print("✅ 未发现具体错误信息")
            return
        
        # 按作业分组
        by_job = {}
        for error in errors:
            key = f"{error.job_name} > {error.step_name}"
            if key not in by_job:
                by_job[key] = []
            by_job[key].append(error)
        
        print("\n" + "="*60)
        print(f"📋 发现 {len(errors)} 个错误")
        print("="*60 + "\n")
        
        for job_step, job_errors in by_job.items():
            print(f"❌ {job_step} ({len(job_errors)} 个错误)")
            print("-" * 60)
            
            for i, error in enumerate(job_errors, 1):
                print(f"\n{i}. ", end="")
                
                if error.file_path:
                    location = f"{error.file_path}"
                    if error.line_number:
                        location += f":{error.line_number}"
                    print(f"📄 {location}")
                
                if error.error_code:
                    print(f"   🔖 [{error.error_code}] {error.message}")
                else:
                    print(f"   💬 {error.message}")
                
                if error.suggestion:
                    print(f"   💡 建议: {error.suggestion}")
            
            print()
    
    def run(self, run_id: Optional[int] = None, watch: bool = False):
        """主运行逻辑"""
        # 获取运行信息
        if run_id is None:
            print("🔍 获取最新的 CI 运行...")
            run_info = self.get_latest_run()
            if not run_info:
                print("❌ 未找到 CI 运行记录")
                return
            
            run_id = run_info['databaseId']
            print(f"✓ 找到运行: {run_info['workflowName']}")
            print(f"  分支: {run_info['headBranch']}")
            print(f"  状态: {run_info['status']}")
            print(f"  运行 ID: {run_id}")
            print()
        
        # 监控运行
        if watch:
            success = self.watch_run(run_id)
            if success:
                print("\n✅ CI 检查全部通过！")
                return
            print()
        
        # 获取失败信息
        print("📊 分析失败原因...")
        logs = self.get_job_logs(run_id)
        
        if not logs:
            print("❌ 无法获取日志")
            return
        
        # 解析错误
        errors = []
        errors.extend(self.parse_ruff_errors(logs))
        errors.extend(self.parse_eslint_errors(logs))
        errors.extend(self.parse_pytest_errors(logs))
        
        # 显示错误
        self.display_errors(errors)
        
        # 显示帮助信息
        print("\n" + "="*60)
        print("🔧 快速修复命令:")
        print("="*60)
        print(f"  查看完整日志:  gh run view {run_id} --log")
        print(f"  重新运行:      gh run rerun {run_id} --failed")
        print(f"  浏览器查看:    gh run view {run_id} --web")
        print()
        print("  本地修复:")
        print("    后端: cd backend && ruff check --fix app/")
        print("    前端: cd frontend && npm run lint -- --fix")
        print("="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub Actions CI 错误监控')
    parser.add_argument('--run-id', type=int, help='指定运行 ID')
    parser.add_argument('--watch', action='store_true', help='实时监控运行')
    
    args = parser.parse_args()
    
    monitor = CIMonitor()
    monitor.run(run_id=args.run_id, watch=args.watch)


if __name__ == '__main__':
    main()
