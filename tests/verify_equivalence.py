"""使用相同随机种子验证拆分后的计算和打印项目。"""
from pathlib import Path
import contextlib
import io
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from numba import njit

@njit
def seed_random(seed):
    np.random.seed(seed)

def verify(original_path):
    source = Path(original_path).read_text(encoding='utf-8')
    source = source.replace('simulations = 100_0000', 'simulations = 100')
    outputs = []
    previous_argv = sys.argv[:]
    try:
        for seed in (7, 42, 2026):
            seed_random(seed)
            old_output = io.StringIO()
            with contextlib.redirect_stdout(old_output):
                exec(compile(source, str(original_path), 'exec'), {'__name__': '__main__'})
            seed_random(seed)
            new_output = io.StringIO()
            sys.argv = ['main.py', '--simulations', '100']
            with contextlib.redirect_stdout(new_output):
                runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
            old_lines = old_output.getvalue().splitlines()
            new_lines = new_output.getvalue().splitlines()
            assert len(old_lines) == len(new_lines), '输出项目数量不一致'
            assert old_lines[-1].startswith('程序运行时间: ')
            assert new_lines[-1].startswith('程序运行时间: ')
            assert old_lines[:-1] == new_lines[:-1], (
                f'随机种子 {seed} 的结果不同\n原版：{old_lines}\n新版：{new_lines}')
            outputs.append(f'随机种子 {seed}：100场模拟的全部统计数值和输出项目一致')
        print('\n'.join(outputs))
        print(f'验证通过：每次均打印 {len(new_lines)} 项，运行时间单独检查。')
    finally:
        sys.argv = previous_argv

if __name__ == '__main__':
    original = (sys.argv[1] if len(sys.argv) > 1 else
                r'F:\游戏攻略\地下城堡2\战力测试\人形魂碑\人形魂碑.py')
    verify(original)
