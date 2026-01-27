/**
 * 声音播放组合式函数
 */
import { ref, computed, onUnmounted } from 'vue'

interface SoundOptions {
  volume?: number
  loop?: boolean
}

export function useSound() {
  const audioRef = ref<HTMLAudioElement | null>(null)
  const isPlaying = ref(false)
  const isMuted = ref(false)
  const volume = ref(1)

  // 创建音频元素
  const createAudio = (src: string): HTMLAudioElement => {
    const audio = new Audio(src)
    audio.volume = isMuted.value ? 0 : volume.value
    return audio
  }

  // 播放声音
  const play = (src: string, options: SoundOptions = {}) => {
    stop()

    audioRef.value = createAudio(src)
    audioRef.value.loop = options.loop || false

    if (options.volume !== undefined) {
      audioRef.value.volume = options.volume
    }

    audioRef.value.onplay = () => {
      isPlaying.value = true
    }

    audioRef.value.onended = () => {
      isPlaying.value = false
    }

    audioRef.value.onerror = (e) => {
      console.error('音频播放失败:', e)
      isPlaying.value = false
    }

    audioRef.value.play().catch(e => {
      console.warn('音频自动播放被阻止:', e)
    })
  }

  // 停止播放
  const stop = () => {
    if (audioRef.value) {
      audioRef.value.pause()
      audioRef.value.currentTime = 0
      audioRef.value = null
      isPlaying.value = false
    }
  }

  // 暂停播放
  const pause = () => {
    if (audioRef.value) {
      audioRef.value.pause()
      isPlaying.value = false
    }
  }

  // 继续播放
  const resume = () => {
    if (audioRef.value) {
      audioRef.value.play()
      isPlaying.value = true
    }
  }

  // 设置音量
  const setVolume = (vol: number) => {
    volume.value = Math.max(0, Math.min(1, vol))
    if (audioRef.value) {
      audioRef.value.volume = isMuted.value ? 0 : volume.value
    }
  }

  // 静音切换
  const toggleMute = () => {
    isMuted.value = !isMuted.value
    if (audioRef.value) {
      audioRef.value.volume = isMuted.value ? 0 : volume.value
    }
  }

  // 设置静音
  const setMuted = (muted: boolean) => {
    isMuted.value = muted
    if (audioRef.value) {
      audioRef.value.volume = muted ? 0 : volume.value
    }
  }

  // 播放告警声音
  const playAlarm = (level: 'critical' | 'major' | 'minor' | 'info') => {
    const soundMap: Record<string, string> = {
      critical: '/sounds/alarm_critical.mp3',
      major: '/sounds/alarm_major.mp3',
      minor: '/sounds/alarm_minor.mp3',
      info: '/sounds/alarm_info.mp3'
    }

    play(soundMap[level], {
      loop: level === 'critical'
    })
  }

  // 播放提示音
  const playNotification = () => {
    play('/sounds/notification.mp3')
  }

  // 清理
  onUnmounted(() => {
    stop()
  })

  return {
    isPlaying: computed(() => isPlaying.value),
    isMuted: computed(() => isMuted.value),
    volume: computed(() => volume.value),
    play,
    stop,
    pause,
    resume,
    setVolume,
    toggleMute,
    setMuted,
    playAlarm,
    playNotification
  }
}

export default useSound
