/**
 * 统一日志工具
 * Centralized logging utility for the frontend application.
 *
 * 在生产环境中会禁用 debug 和 info 日志，
 * error 和 warn 日志会保留以便问题追踪。
 *
 * Usage:
 *   import { logger } from '@/utils/logger'
 *   logger.info('Data loaded', data)
 *   logger.error('Failed to load', error)
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LoggerConfig {
  /** 是否启用日志（生产环境可禁用） */
  enabled: boolean
  /** 最小日志级别 */
  minLevel: LogLevel
  /** 是否显示时间戳 */
  showTimestamp: boolean
  /** 前缀标签 */
  prefix: string
}

const LOG_LEVELS: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3
}

const isDev = import.meta.env.DEV

const defaultConfig: LoggerConfig = {
  enabled: true,
  minLevel: isDev ? 'debug' : 'warn',  // 生产环境只显示 warn 和 error
  showTimestamp: true,
  prefix: '[DCIM]'
}

class Logger {
  private config: LoggerConfig

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = { ...defaultConfig, ...config }
  }

  private shouldLog(level: LogLevel): boolean {
    if (!this.config.enabled) return false
    return LOG_LEVELS[level] >= LOG_LEVELS[this.config.minLevel]
  }

  private formatMessage(level: LogLevel, message: string): string {
    const parts: string[] = []

    if (this.config.prefix) {
      parts.push(this.config.prefix)
    }

    if (this.config.showTimestamp) {
      parts.push(`[${new Date().toLocaleTimeString()}]`)
    }

    parts.push(`[${level.toUpperCase()}]`)
    parts.push(message)

    return parts.join(' ')
  }

  /**
   * 调试日志 - 仅开发环境
   */
  debug(message: string, ...args: unknown[]): void {
    if (this.shouldLog('debug')) {
      console.debug(this.formatMessage('debug', message), ...args)
    }
  }

  /**
   * 信息日志 - 仅开发环境
   */
  info(message: string, ...args: unknown[]): void {
    if (this.shouldLog('info')) {
      console.info(this.formatMessage('info', message), ...args)
    }
  }

  /**
   * 警告日志 - 开发和生产环境
   */
  warn(message: string, ...args: unknown[]): void {
    if (this.shouldLog('warn')) {
      console.warn(this.formatMessage('warn', message), ...args)
    }
  }

  /**
   * 错误日志 - 开发和生产环境
   */
  error(message: string, ...args: unknown[]): void {
    if (this.shouldLog('error')) {
      console.error(this.formatMessage('error', message), ...args)
    }
  }

  /**
   * 创建带有自定义前缀的子日志器
   */
  child(prefix: string): Logger {
    return new Logger({
      ...this.config,
      prefix: `${this.config.prefix}[${prefix}]`
    })
  }
}

// 导出默认日志器实例
export const logger = new Logger()

// 导出类以便创建自定义日志器
export { Logger, type LoggerConfig, type LogLevel }

// 便捷方法：创建模块专用日志器
export function createLogger(moduleName: string): Logger {
  return logger.child(moduleName)
}
