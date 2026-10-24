"""原战力模拟启动入口：支持--simulations参数。"""
import runpy

if __name__ == '__main__':
    runpy.run_module('engine.runner', run_name='__main__')
