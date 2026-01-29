import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
// 导入 Element Plus 官方暗色主题 CSS 变量
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import DataVVue3 from '@kjgl77/datav-vue3'
import App from './App.vue'
import router from './router'

// 自定义样式放在 Element Plus 暗色主题之后，进一步覆盖
import './styles/index.scss'

// 注册 ECharts 深色主题
import { registerDarkTechTheme } from './config/echartsTheme'
registerDarkTechTheme()

// 启用暗色模式：给 html 添加 dark class
document.documentElement.classList.add('dark')

const app = createApp(App)

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.use(DataVVue3)

app.mount('#app')

// 运行时注入 Element Plus 组件深色覆盖样式
// Element Plus 按需加载的组件 CSS 会在自定义样式之后加载，
// 导致 SCSS 中的覆盖被覆盖。此处用 JS 动态插入最高优先级样式。
const darkOverrideStyle = document.createElement('style')
darkOverrideStyle.setAttribute('data-dark-override', '')
darkOverrideStyle.textContent = `
  /* ========== 对话框深色主题 ========== */
  .el-dialog {
    background-color: #1a2a4a !important;
    border: 1px solid #7a9bb8 !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
  }
  .el-dialog .el-dialog__header,
  .el-dialog .el-dialog__body,
  .el-dialog .el-dialog__footer {
    background-color: #1a2a4a !important;
  }
  .el-message-box {
    background-color: #1a2a4a !important;
    border: 1px solid #7a9bb8 !important;
  }

  /* ========== 表格工业控制台高对比度主题 V6 ========== */
  .el-table {
    background-color: #0d1520 !important;
    border: 2px solid #7db8e8 !important;
    border-radius: 8px !important;
    box-shadow:
      0 0 0 1px rgba(125, 184, 232, 0.4),
      0 0 15px rgba(125, 184, 232, 0.15),
      0 4px 24px rgba(0, 0, 0, 0.5) !important;
  }
  .el-table::before {
    display: none !important;
  }
  .el-table th.el-table__cell {
    background: linear-gradient(180deg, #2d6090 0%, #1e4a70 100%) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px !important;
    border-bottom: 3px solid #7db8e8 !important;
    border-right: 1px solid #5a8ab0 !important;
    padding: 16px 14px !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4) !important;
  }
  .el-table th.el-table__cell .cell {
    color: #ffffff !important;
  }
  .el-table th.el-table__cell:last-child {
    border-right: none !important;
  }
  .el-table td.el-table__cell {
    background-color: transparent !important;
    color: rgba(255, 255, 255, 0.95) !important;
    border-bottom: 1px solid #2d4a66 !important;
    border-right: 1px solid #223a50 !important;
    padding: 14px !important;
  }
  .el-table td.el-table__cell .cell {
    color: rgba(255, 255, 255, 0.95) !important;
  }
  .el-table td.el-table__cell:last-child {
    border-right: none !important;
  }
  .el-table tr {
    background-color: #0d1520 !important;
  }
  .el-table tr:nth-child(even) {
    background-color: #111d2c !important;
  }
  .el-table tr:nth-child(even) td.el-table__cell {
    background-color: #111d2c !important;
  }
  .el-table tr:nth-child(odd) {
    background-color: #0d1520 !important;
  }
  .el-table tr:nth-child(odd) td.el-table__cell {
    background-color: #0d1520 !important;
  }
  .el-table tr:hover > td.el-table__cell {
    background-color: #1a3554 !important;
    border-bottom-color: #5a90b8 !important;
  }
  .el-table--border {
    border: 2px solid #7db8e8 !important;
  }
  .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
    background-color: #111d2c !important;
  }
  .el-table .el-table__inner-wrapper::before {
    display: none !important;
  }
  .el-table .el-table__header-wrapper {
    background: linear-gradient(180deg, #2d6090 0%, #1e4a70 100%) !important;
  }

  /* 表格内标签样式 - 更鲜艳 */
  .el-table .el-tag--primary {
    background: rgba(125, 184, 232, 0.2) !important;
    border: 1px solid #7db8e8 !important;
    color: #7db8e8 !important;
  }
  .el-table .el-tag--success {
    background: rgba(103, 194, 58, 0.2) !important;
    border: 1px solid #67c23a !important;
    color: #67c23a !important;
  }
  .el-table .el-tag--warning {
    background: rgba(230, 162, 60, 0.2) !important;
    border: 1px solid #e6a23c !important;
    color: #e6a23c !important;
  }
  .el-table .el-tag--danger {
    background: rgba(245, 108, 108, 0.2) !important;
    border: 1px solid #f56c6c !important;
    color: #f56c6c !important;
  }

  /* 表格内开关 */
  .el-table .el-switch.is-checked .el-switch__core {
    background-color: #409eff !important;
    border-color: #409eff !important;
  }

  /* 表格内按钮 */
  .el-table .el-button--link.el-button--primary,
  .el-table .el-button--text.el-button--primary {
    color: #7db8e8 !important;
  }
  .el-table .el-button--link.el-button--primary:hover,
  .el-table .el-button--text.el-button--primary:hover {
    color: #a0d0f5 !important;
  }
  .el-table .el-button--link.el-button--danger,
  .el-table .el-button--text.el-button--danger {
    color: #f56c6c !important;
  }
  .el-table .el-button--link.el-button--danger:hover,
  .el-table .el-button--text.el-button--danger:hover {
    color: #f89898 !important;
  }
`
document.head.appendChild(darkOverrideStyle)
