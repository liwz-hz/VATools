import React, { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import { Box, Typography, Paper, Chip } from '@mui/material'

interface WaveformViewerProps {
  audioUrl: string
  onRegionUpdate?: (start: number, end: number) => void
}

export interface WaveformViewerRef {
  playRegion: (start: number, end: number) => void
  play: () => void
  pause: () => void
  stop: () => void
}

const WaveformViewer = forwardRef<WaveformViewerRef, WaveformViewerProps>(
  ({ audioUrl, onRegionUpdate }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null)
    const wavesurferRef = useRef<WaveSurfer | null>(null)
    const regionsRef = useRef<any>(null)
    const [duration, setDuration] = useState(0)
    const [isPlaying, setIsPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [hasRegion, setHasRegion] = useState(false)

    useImperativeHandle(ref, () => ({
      playRegion: (start: number, end: number) => {
        if (wavesurferRef.current && regionsRef.current) {
          wavesurferRef.current.play(start, end)
          setIsPlaying(true)
        }
      },
      play: () => {
        if (wavesurferRef.current) {
          wavesurferRef.current.play()
          setIsPlaying(true)
        }
      },
      pause: () => {
        if (wavesurferRef.current) {
          wavesurferRef.current.pause()
          setIsPlaying(false)
        }
      },
      stop: () => {
        if (wavesurferRef.current) {
          wavesurferRef.current.stop()
          setIsPlaying(false)
        }
      }
    }))

    useEffect(() => {
      if (!containerRef.current) return

      // 清理旧的实例
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy()
      }

      const wavesurfer = WaveSurfer.create({
        container: containerRef.current,
        waveColor: '#1976d2',
        progressColor: '#dc004e',
        cursorColor: '#333',
        cursorWidth: 2,
        height: 128,
        responsive: true,
        hideScrollbar: false,
        normalize: true,
      })

      // 注册 Regions 插件
      const regions = wavesurfer.registerPlugin(RegionsPlugin.create())
      regionsRef.current = regions

      // 启用拖拽选择区域
      regions.enableDragSelection({
        color: 'rgba(25, 118, 210, 0.3)',
      })

      wavesurfer.load(audioUrl)

      wavesurfer.on('ready', () => {
        setDuration(wavesurfer.getDuration())
      })

      wavesurfer.on('timeupdate', (time) => {
        setCurrentTime(time)
      })

      wavesurfer.on('play', () => {
        setIsPlaying(true)
      })

      wavesurfer.on('pause', () => {
        setIsPlaying(false)
      })

      wavesurfer.on('finish', () => {
        setIsPlaying(false)
      })

      // 监听区域创建
      regions.on('region-created', (region: any) => {
        setHasRegion(true)
        if (onRegionUpdate) {
          onRegionUpdate(region.start, region.end)
        }
      })

      // 监听区域更新
      regions.on('region-updated', (region: any) => {
        if (onRegionUpdate) {
          onRegionUpdate(region.start, region.end)
        }
      })

      // 监听区域移除
      regions.on('region-removed', () => {
        setHasRegion(false)
      })

      wavesurferRef.current = wavesurfer

      return () => {
        wavesurfer.destroy()
      }
    }, [audioUrl, onRegionUpdate])

    const formatTime = (seconds: number) => {
      const mins = Math.floor(seconds / 60)
      const secs = Math.floor(seconds % 60)
      const ms = Math.floor((seconds % 1) * 100)
      return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`
    }

    return (
      <Box>
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'grey.50' }}>
          <Typography variant="body2" color="textSecondary" gutterBottom>
            💡 使用提示：在波形上拖拽鼠标选择片段区域
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Chip 
              label={`总时长: ${formatTime(duration)}`} 
              size="small" 
              color="primary"
              variant="outlined"
            />
            <Chip 
              label={`当前位置: ${formatTime(currentTime)}`} 
              size="small" 
              color="secondary"
              variant="outlined"
            />
            {hasRegion && (
              <Chip 
                label="已选择片段" 
                size="small" 
                color="success"
              />
            )}
          </Box>
        </Paper>
        
        <div 
          ref={containerRef} 
          style={{ 
            width: '100%', 
            minHeight: '128px',
            backgroundColor: '#f5f5f5',
            borderRadius: '4px'
          }} 
        />
        
        {!hasRegion && (
          <Typography variant="caption" color="textSecondary" sx={{ mt: 1, display: 'block' }}>
            ⚠️ 请在波形上拖拽选择要编辑的片段
          </Typography>
        )}
      </Box>
    )
  }
)

WaveformViewer.displayName = 'WaveformViewer'

export default WaveformViewer
