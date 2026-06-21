import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Slider,
  LinearProgress,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import { CloudUpload, Download, AutoFixHigh } from '@mui/icons-material'
import {
  uploadFile,
  startTTS,
  getTTSStatus,
  getTTSSpeakers,
  analyzeTTSEmotion,
  getTask,
} from '../services/api'

interface EmotionItem {
  sentence: string
  instruct: string
}

const EMOTION_PRESETS = [
  '用自然平和的语气说',
  '用兴奋开心的语气说',
  '用疑问好奇的语气说',
  '用低沉无奈的语气说',
  '用愤怒强烈的语气说',
  '用礼貌温和的语气说',
]

const AudioTTS: React.FC = () => {
  const [mode, setMode] = useState<'custom_voice' | 'voice_clone'>('custom_voice')
  const [speakers, setSpeakers] = useState<string[]>([])
  const [selectedSpeaker, setSelectedSpeaker] = useState('vivian')
  const [language, setLanguage] = useState('auto')
  const [text, setText] = useState('')
  const [emotions, setEmotions] = useState<EmotionItem[]>([])
  const [speed, setSpeed] = useState(1.0)
  const [temperature, setTemperature] = useState(0.9)
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusText, setStatusText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioPath, setAudioPath] = useState<string | null>(null)
  const [refFile, setRefFile] = useState<any>(null)
  const [refText, setRefText] = useState('')
  const [mlxAvailable, setMlxAvailable] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadStatus()
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const loadStatus = async () => {
    try {
      const status = await getTTSStatus()
      setMlxAvailable(status.mlx_audio_available || false)
      const speakerList = await getTTSSpeakers()
      setSpeakers(speakerList.speakers || [])
      if (speakerList.speakers?.length > 0 && !speakerList.speakers.includes(selectedSpeaker)) {
        setSelectedSpeaker(speakerList.speakers[0])
      }
    } catch (err) {
      console.error('Failed to load TTS status:', err)
    }
  }

  const handleAnalyze = async () => {
    if (!text.trim()) return
    try {
      const result = await analyzeTTSEmotion(text)
      setEmotions(result.emotions || [])
    } catch (err) {
      console.error('Failed to analyze:', err)
      setError('情感分析失败')
    }
  }

  const handleEmotionChange = (index: number, instruct: string) => {
    setEmotions((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], instruct }
      return updated
    })
  }

  const onDropRef = useCallback(async (acceptedFiles: globalThis.File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      try {
        setError(null)
        const uploaded = await uploadFile(file)
        setRefFile(uploaded)
      } catch (err: unknown) {
        const e = err as { response?: { data?: { error?: string } } }
        setError(e.response?.data?.error || '上传失败')
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: onDropRef,
    accept: {
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'audio/flac': ['.flac'],
    },
    maxFiles: 1,
  })

  const handleGenerate = async () => {
    if (!text.trim()) {
      setError('请输入文本')
      return
    }

    setIsProcessing(true)
    setProgress(0)
    setStatusText('开始生成...')
    setError(null)
    setAudioUrl(null)

    try {
      const params: any = {
        text,
        mode,
        speed,
        temperature,
        language,
        emotions: emotions.length > 0 ? emotions : undefined,
      }

      if (mode === 'custom_voice') {
        params.speaker = selectedSpeaker
      } else {
        params.ref_audio_id = refFile?.id
        params.ref_text = refText || undefined
      }

      const result = await startTTS(params)
      const taskId = result.task_id

      pollRef.current = setInterval(async () => {
        try {
          const task = await getTask(taskId)
          setProgress(task.progress || 0)
          setStatusText(task.status === 'processing' ? '生成中...' : task.status)

          if (task.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setProgress(100)
            setStatusText('完成')
            if (task.output_file) {
              setAudioPath(task.output_file)
              setAudioUrl(`http://localhost:5001/api/files/serve?path=${encodeURIComponent(task.output_file)}`)
            }
          } else if (task.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setIsProcessing(false)
            setError(task.error_message || '生成失败')
          }
        } catch (err) {
          console.error('Failed to poll task:', err)
        }
      }, 2000)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } }
      setError(e.response?.data?.error || '生成失败')
      setIsProcessing(false)
    }
  }

  const handleDownload = () => {
    if (audioPath) {
      const link = document.createElement('a')
      link.href = `http://localhost:5001/api/files/serve?path=${encodeURIComponent(audioPath)}&download=1`
      link.download = 'tts_output.wav'
      link.click()
    }
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          语音合成模式
        </Typography>

        {!mlxAvailable && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            mlx-audio 未安装，请运行: pip install mlx-audio==0.4.4
          </Alert>
        )}

        <ToggleButtonGroup
          value={mode}
          exclusive
          onChange={(_, v) => v && setMode(v)}
          sx={{ mb: 2 }}
        >
          <ToggleButton value="custom_voice">情感配音</ToggleButton>
          <ToggleButton value="voice_clone">声音克隆</ToggleButton>
        </ToggleButtonGroup>

        {mode === 'custom_voice' && (
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <FormControl sx={{ minWidth: 200 }}>
              <InputLabel>音色</InputLabel>
              <Select
                value={selectedSpeaker}
                label="音色"
                onChange={(e) => setSelectedSpeaker(e.target.value)}
              >
                {speakers.map((s) => (
                  <MenuItem key={s} value={s}>{s}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl sx={{ minWidth: 150 }}>
              <InputLabel>语言</InputLabel>
              <Select
                value={language}
                label="语言"
                onChange={(e) => setLanguage(e.target.value)}
              >
                <MenuItem value="auto">自动检测</MenuItem>
                <MenuItem value="Chinese">中文</MenuItem>
                <MenuItem value="English">英文</MenuItem>
              </Select>
            </FormControl>
          </Box>
        )}

        {mode === 'voice_clone' && (
          <Box>
            <Box
              {...getRootProps()}
              sx={{
                border: '2px dashed #ccc',
                borderRadius: 2,
                p: 3,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: isDragActive ? 'action.hover' : 'background.paper',
                mb: 2,
              }}
            >
              <input {...getInputProps()} />
              <CloudUpload sx={{ fontSize: 36, color: 'primary.main', mb: 1 }} />
              <Typography>
                {isDragActive ? '放下文件' : '上传参考音频（用于克隆声音）'}
              </Typography>
            </Box>

            {refFile && (
              <Alert severity="success" sx={{ mb: 2 }}>
                参考音频: {refFile.filename}
              </Alert>
            )}

            <TextField
              fullWidth
              label="参考音频文本（可选，不填则自动转录）"
              value={refText}
              onChange={(e) => setRefText(e.target.value)}
              sx={{ mb: 2 }}
            />
          </Box>
        )}
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          输入文本
        </Typography>

        <TextField
          fullWidth
          multiline
          minRows={6}
          maxRows={12}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="请输入要合成的文本..."
          sx={{ mb: 2 }}
        />

        <Button
          variant="outlined"
          startIcon={<AutoFixHigh />}
          onClick={handleAnalyze}
          disabled={!text.trim()}
          sx={{ mb: 2 }}
        >
          分析情感
        </Button>

        {emotions.length > 0 && (
          <TableContainer sx={{ maxHeight: 300, mb: 2 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 50 }}>#</TableCell>
                  <TableCell>句子</TableCell>
                  <TableCell sx={{ width: 250 }}>情感指令</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {emotions.map((em, index) => (
                  <TableRow key={index}>
                    <TableCell>{index + 1}</TableCell>
                    <TableCell>{em.sentence}</TableCell>
                    <TableCell>
                      <FormControl fullWidth size="small">
                        <Select
                          value={em.instruct}
                          onChange={(e) => handleEmotionChange(index, e.target.value)}
                        >
                          {EMOTION_PRESETS.map((p) => (
                            <MenuItem key={p} value={p}>{p}</MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          生成设置
        </Typography>

        <Typography gutterBottom>语速: {speed.toFixed(1)}x</Typography>
        <Slider
          value={speed}
          onChange={(_, v) => setSpeed(v as number)}
          min={0.5}
          max={2.0}
          step={0.1}
          sx={{ mb: 3 }}
        />

        <Typography gutterBottom>表现力: {temperature.toFixed(1)}</Typography>
        <Slider
          value={temperature}
          onChange={(_, v) => setTemperature(v as number)}
          min={0.5}
          max={1.0}
          step={0.1}
          sx={{ mb: 3 }}
        />

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Button
          variant="contained"
          color="primary"
          fullWidth
          size="large"
          onClick={handleGenerate}
          disabled={isProcessing || !text.trim() || !mlxAvailable}
        >
          生成语音
        </Button>
      </Paper>

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            生成中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% - {statusText}
          </Typography>
        </Paper>
      )}

      {audioUrl && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            生成结果
          </Typography>

          <audio
            src={audioUrl}
            controls
            style={{ width: '100%', marginBottom: 16 }}
          />

          <Button
            variant="contained"
            startIcon={<Download />}
            onClick={handleDownload}
          >
            下载 WAV
          </Button>
        </Paper>
      )}
    </Box>
  )
}

export default AudioTTS
