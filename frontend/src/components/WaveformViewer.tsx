import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
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
    const onRegionUpdateRef = useRef(onRegionUpdate)
    const [duration, setDuration] = useState(0)
    const [currentTime, setCurrentTime] = useState(0)
    const [hasRegion, setHasRegion] = useState(false)

    useEffect(() => {
      onRegionUpdateRef.current = onRegionUpdate
    }, [onRegionUpdate])

    useImperativeHandle(ref, () => ({
      playRegion: (start: number, end: number) => {
        if (wavesurferRef.current) {
          wavesurferRef.current.play(start, end)
        }
      },
      play: () => {
        wavesurferRef.current?.play()
      },
      pause: () => {
        wavesurferRef.current?.pause()
      },
      stop: () => {
        wavesurferRef.current?.stop()
      }
    }), [])

    useEffect(() => {
      if (!containerRef.current) return

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
        hideScrollbar: false,
        normalize: true,
      })

      const regions = wavesurfer.registerPlugin(RegionsPlugin.create())
      regionsRef.current = regions

      regions.enableDragSelection({
        color: 'rgba(25, 118, 210, 0.25)',
      })

      regions.on('region-created', (region: any) => {
        setHasRegion(true)
        const el = region.element as HTMLElement
        el.style.borderLeft = '4px solid #1976d2'
        el.style.borderRight = '4px solid #1976d2'
        el.style.cursor = 'grab'

        const leftHandle = document.createElement('div')
        leftHandle.style.cssText = 'position:absolute;left:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:10;background:linear-gradient(90deg,#1976d2,#1565c0);border-radius:3px 0 0 3px;'
        el.appendChild(leftHandle)

        const rightHandle = document.createElement('div')
        rightHandle.style.cssText = 'position:absolute;right:-6px;top:0;bottom:0;width:12px;cursor:ew-resize;z-index:10;background:linear-gradient(90deg,#1565c0,#1976d2);border-radius:0 3px 3px 0;'
        el.appendChild(rightHandle)

        onRegionUpdateRef.current?.(region.start, region.end)
      })

      regions.on('region-updated', (region: any) => {
        onRegionUpdateRef.current?.(region.start, region.end)
      })

      regions.on('region-removed', () => {
        setHasRegion(false)
      })

      wavesurfer.load(audioUrl)

      wavesurfer.on('ready', () => {
        setDuration(wavesurfer.getDuration())
      })

      wavesurfer.on('timeupdate', (time) => {
        setCurrentTime(time)
      })

      wavesurferRef.current = wavesurfer

      return () => {
        wavesurfer.destroy()
      }
    }, [audioUrl])

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
            在波形上拖拽鼠标选择片段区域，拖动左右蓝色手柄可调整范围
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
            请在波形上拖拽选择要编辑的片段
          </Typography>
        )}
      </Box>
    )
  }
)

WaveformViewer.displayName = 'WaveformViewer'

export default WaveformViewer
