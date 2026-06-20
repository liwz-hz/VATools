import React, { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Box, Typography } from '@mui/material'

interface WaveformViewerProps {
  audioUrl: string
  onRegionUpdate?: (start: number, end: number) => void
}

const WaveformViewer: React.FC<WaveformViewerProps> = ({ audioUrl, onRegionUpdate }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    if (!containerRef.current) return

    const wavesurfer = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#1976d2',
      progressColor: '#dc004e',
      cursorColor: '#333',
      cursorWidth: 2,
      height: 128,
      responsive: true,
    })

    wavesurfer.load(audioUrl)

    wavesurfer.on('ready', () => {
      setDuration(wavesurfer.getDuration())
      
      // Enable regions plugin
      wavesurfer.registerPlugin(
        (window as any).WaveSurfer.regions?.create({
          dragSelection: {
            slop: 5,
          },
        })
      )
    })

    wavesurfer.on('region-created', (region) => {
      if (onRegionUpdate) {
        onRegionUpdate(region.start, region.end)
      }
    })

    wavesurfer.on('region-updated', (region) => {
      if (onRegionUpdate) {
        onRegionUpdate(region.start, region.end)
      }
    })

    wavesurferRef.current = wavesurfer

    return () => {
      wavesurfer.destroy()
    }
  }, [audioUrl])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <Box>
      <div ref={containerRef} style={{ width: '100%' }} />
      <Typography variant="caption" color="textSecondary">
        总时长: {formatTime(duration)}
      </Typography>
    </Box>
  )
}

export default WaveformViewer
