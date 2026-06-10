from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent / "test_fixtures"


@pytest.fixture
def sample_txt(fixtures_dir):
    return fixtures_dir / "sample.txt"


@pytest.fixture
def sample_txt_content():
    return """前言

这是一本关于学习方法的书。

第一章 为什么学习

第一节 学习的本质

学习是人类最基础的能力之一。通过刻意练习，任何人都能掌握新技能。
研究表明，间隔重复比集中练习更有效。

第二节 元认知

元认知是指对自己思维过程的理解和控制。善于学习的人往往具有高度的元认知能力。

第二章 如何学习

第一节 费曼技巧

理查德·费曼提出了一种高效的学习方法：用自己的话解释一个概念，
如果说不清楚，说明还没真正理解。

第二节 番茄工作法

将工作时间分割成25分钟的段落，中间休息5分钟。
这种方法可以有效防止疲劳，提高专注度。

后记

学习是一场终身的旅程。
"""
