import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default [
  // 忽略构建产物和依赖
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'auto-imports.d.ts',
      'components.d.ts',
      '*.config.ts',
      '*.config.js'
    ]
  },

  // JS 基础规则
  js.configs.recommended,

  // TypeScript 规则
  ...tseslint.configs.recommended,

  // Vue 规则（essential = 错误检查，不含格式化意见）
  ...pluginVue.configs['flat/essential'],

  // Vue 文件使用 TypeScript parser
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser
      }
    }
  },

  // 项目自定义规则
  {
    files: ['**/*.{ts,tsx,vue}'],
    rules: {
      // 放宽 TypeScript 严格规则（适配现有代码）
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_'
      }],
      '@typescript-eslint/no-empty-function': 'off',
      '@typescript-eslint/ban-ts-comment': 'off',
      '@typescript-eslint/no-require-imports': 'off',

      // Vue 规则调整
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
      'vue/require-default-prop': 'off',
      'vue/no-setup-props-destructure': 'off',

      // 通用规则
      'no-console': 'off',
      'no-debugger': 'warn',
      'no-undef': 'off' // TypeScript 处理
    }
  },

  // 测试文件放宽规则
  {
    files: ['**/__tests__/**/*.ts', '**/*.test.ts', '**/*.spec.ts'],
    rules: {
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-empty-function': 'off'
    }
  }
]
