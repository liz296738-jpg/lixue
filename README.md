# Report Automator Pro 🚀

**力学仿真自动化后处理与 PPT 报告生成插件**

全自动有限元分析后处理流水线：从 CAE 数据到商业演示文稿，一键完成。

## 🔗 全链路架构

```
Mock数据生成 → 智能离屏渲染 → PPT全自动组装
   (Phase 1)      (Phase 2)        (Phase 3)
```

## 📁 项目结构

```
力学软件优化/
├── src/
│   ├── mock_data.py      # Mock 网格 + 场数据生成 (PyVista UnstructuredGrid)
│   ├── renderer.py       # 离屏渲染引擎 (智能运镜 + 1080p 输出)
│   └── ppt_generator.py  # PPT 全自动组装 (python-pptx)
├── output/               # 渲染图片 + 最终 PPTX
├── templates/            # PPT 母版模板
├── tests/                # pytest 测试
├── validate.py           # Phase 1 验证脚本
├── run_render.py         # Phase 2 渲染入口
├── run_ppt.py            # Phase 3 PPT 组装入口
└── requirements.txt      # Python 依赖
```

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行全流程：数据生成 → 渲染 → PPT 组装
python run_ppt.py
```

## 🧪 核心能力

| 能力 | 说明 |
|------|------|
| **Mock 数据** | 悬臂梁 UnstructuredGrid (9,600 节点 / 41,712 四面体)，含 Kirsch 孔边应力集中 |
| **智能运镜** | 自动锁定最大应力/位移节点，等轴测/前视/顶视多视角 |
| **离屏渲染** | 纯内存 FBO 渲染，无 GUI，1080p 输出，品牌配色 |
| **PPT 组装** | 占位符映射注入，7 页幻灯片，动态诊断文本，16:9 |

## 📊 典型输出

- `output/high_res_stress.png` — von Mises 应力主图 (1080p)
- `output/high_res_displacement.png` — 位移场主图 (1080p)
- `output/Final_Automated_Report.pptx` — 最终商业演示文稿 (7 页)

## 🔧 技术栈

- **PyVista / VTK** — 3D 可视化与网格处理
- **NumPy** — 场数据张量运算
- **python-pptx** — Office Open XML 文档生成
- **Matplotlib** — 色谱与辅助绘图

## 📄 License

MIT
