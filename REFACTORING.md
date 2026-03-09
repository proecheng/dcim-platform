# 启动脚本重构说明

**重构日期：** 2026-03-09
**版本：** v8.0

## 重构目标

将复杂的单体脚本（389 行）拆分为模块化、可维护的结构。

## 新的文件结构

```
mytest1/
├── start-new.bat           # 新的主启动脚本 (v8.0, ~120 行)
├── stop-new.bat            # 新的停止脚本 (v4.0, ~90 行)
├── start-quick.bat         # 快速启动（跳过环境检查）
├── start.bat               # 旧版本（保留作为备份）
├── stop.bat                # 旧版本（保留作为备份）
└── scripts/
    ├── check-env.bat       # 环境检查模块
    ├── clean-ports.bat     # 端口清理模块
    ├── setup-backend.bat   # 后端准备模块
    ├── setup-proxy.bat     # 代理准备模块
    ├── setup-frontend.bat  # 前端准备模块
    └── start-services.bat  # 服务启动模块
```

## 模块说明

### 1. check-env.bat
**职责：** 检查 Python 和 Node.js 环境
**输出：** 将 Python 路径写入临时文件
**行数：** ~60 行

### 2. clean-ports.bat
**职责：** 清理指定端口的占用进程
**参数：** 端口号（默认 8080 和 3000）
**特性：**
- 双重进程终止（taskkill + PowerShell）
- 循环重试机制（最多 3 次）
- 智能等待
**行数：** ~95 行

### 3. setup-backend.bat
**职责：** 准备后端环境和数据库
**功能：**
- 检查并安装 Python 依赖
- 初始化数据库
- 运行数据一致性修复
**行数：** ~65 行

### 4. setup-proxy.bat
**职责：** 准备代理服务环境
**功能：** 检查并安装 Node.js 依赖
**行数：** ~30 行

### 5. setup-frontend.bat
**职责：** 准备前端环境和构建
**功能：**
- 检查并安装 Node.js 依赖
- 检查并构建前端
**行数：** ~45 行

### 6. start-services.bat
**职责：** 启动后端和代理服务
**功能：**
- 启动后端（8080）
- 启动代理（3000）
- 验证服务状态
**行数：** ~65 行

## 主脚本对比

### start-new.bat (v8.0)
```batch
[1/6] 检查环境        → check-env.bat
[2/6] 清理端口        → clean-ports.bat
[3/6] 准备后端        → setup-backend.bat
[4/6] 准备代理        → setup-proxy.bat
[5/6] 准备前端        → setup-frontend.bat
[6/6] 启动服务        → start-services.bat
```

**优点：**
- ✅ 模块化设计，职责单一
- ✅ 易于维护和测试
- ✅ 可复用模块
- ✅ 主脚本简洁清晰（~120 行）

### start.bat (v7.2) - 旧版
```batch
389 行单体脚本
- 所有逻辑在一个文件中
- 难以维护
- 代码重复
```

## 使用方式

### 完整启动（推荐）
```batch
start-new.bat
```
- 检查所有环境
- 安装缺失的依赖
- 构建前端（如果需要）
- 启动服务

### 快速启动
```batch
start-quick.bat
```
- 跳过环境检查
- 跳过依赖安装
- 直接启动服务
- 适合日常开发

### 停止服务
```batch
stop-new.bat
```
- 使用模块化端口清理
- 更可靠的进程终止

## 模块独立使用

### 单独清理端口
```batch
scripts\clean-ports.bat 8080 3000
```

### 单独检查环境
```batch
scripts\check-env.bat
```

### 单独准备后端
```batch
scripts\setup-backend.bat
```

## 向后兼容

旧版脚本保留为备份：
- `start.bat` (v7.2) - 保留
- `stop.bat` (v3.1) - 保留

如果新版本有问题，可以随时切换回旧版本。

## 测试建议

### 测试场景 1：首次安装
```batch
# 删除虚拟环境和 node_modules
rm -rf backend/.venv
rm -rf frontend/node_modules
rm -rf proxy/node_modules

# 运行新脚本
start-new.bat

# 预期：自动安装所有依赖并启动
```

### 测试场景 2：日常启动
```batch
# 正常停止
stop-new.bat

# 快速启动
start-quick.bat

# 预期：快速启动，无依赖检查
```

### 测试场景 3：端口被占用
```batch
# 先启动一次
start-new.bat

# 不停止，再次启动
start-new.bat

# 预期：自动清理旧进程，成功启动
```

### 测试场景 4：模块独立测试
```batch
# 测试端口清理
scripts\clean-ports.bat 8080 3000

# 测试环境检查
scripts\check-env.bat

# 预期：每个模块独立工作
```

## 迁移步骤

### 立即迁移（推荐）
```batch
# 1. 备份旧脚本（已完成）
# start.bat → start.bat (保留)
# stop.bat → stop.bat (保留)

# 2. 使用新脚本
start-new.bat
stop-new.bat

# 3. 如果有问题，回退到旧版本
start.bat
stop.bat
```

### 渐进迁移
```batch
# 1. 先测试新版本
start-new.bat

# 2. 确认无问题后，替换旧版本
move start.bat start-old.bat
move start-new.bat start.bat
move stop.bat stop-old.bat
move stop-new.bat stop.bat
```

## 优势总结

| 特性 | 旧版本 | 新版本 |
|------|--------|--------|
| 主脚本行数 | 389 行 | ~120 行 |
| 模块化 | ❌ | ✅ |
| 可维护性 | 低 | 高 |
| 可测试性 | 低 | 高 |
| 可复用性 | 低 | 高 |
| 代码重复 | 多 | 少 |
| 职责分离 | ❌ | ✅ |
| 独立测试 | ❌ | ✅ |

## 后续改进建议

1. **添加日志模块** - 统一的日志记录
2. **添加配置文件** - 端口号等可配置
3. **添加健康检查模块** - 更完善的服务验证
4. **添加回滚机制** - 启动失败时自动回滚
5. **添加单元测试** - 测试每个模块的功能

## 问题反馈

如果新版本有任何问题：
1. 立即切换回旧版本（start.bat / stop.bat）
2. 记录问题详情
3. 提交问题报告

---

**重构完成日期：** 2026-03-09
**测试状态：** 待测试
**建议：** 先在测试环境验证，确认无问题后再全面使用
