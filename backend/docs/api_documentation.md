# 节能方案 API 文档

## 基础信息
- 基础路径: `/api/v1/proposals`
- 内容类型: `application/json`

## 端点列表

### 1. 生成方案
- **POST** `/proposals/generate`
- **请求体**:
  ```json
  {
    "template_id": "A1",  // A1-A5, B1
    "analysis_days": 30   // 1-365
  }
  ```
- **响应**: ProposalResponse

### 2. 获取方案详情
- **GET** `/proposals/{proposal_id}`
- **响应**: ProposalResponse

### 3. 获取方案列表
- **GET** `/proposals/`
- **查询参数**: template_id, status, skip, limit
- **响应**: List[ProposalResponse]

### 4. 接受方案
- **POST** `/proposals/{proposal_id}/accept`
- **请求体**:
  ```json
  {
    "selected_measure_ids": [1, 2, 3]
  }
  ```

### 5. 执行方案
- **POST** `/proposals/{proposal_id}/execute`

### 6. 获取监控数据
- **GET** `/proposals/{proposal_id}/monitoring`

## 模板类型

| ID | 名称 | 类型 |
|----|------|------|
| A1 | 峰谷套利优化方案 | 无需投资 |
| A2 | 需量控制方案 | 无需投资 |
| A3 | 设备运行优化方案 | 无需投资 |
| A4 | VPP需求响应方案 | 无需投资 |
| A5 | 负荷调度优化方案 | 无需投资 |
| B1 | 设备改造升级方案 | 需要投资 |
