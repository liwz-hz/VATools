import React, { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Alert,
  LinearProgress,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Grid,
  Card,
  CardMedia,
  CardContent,
  CardActions,
} from '@mui/material'
import {
  CloudUpload,
  Search,
  Download,
  ContentCut,
} from '@mui/icons-material'
import {
  getSAMStatus,
  loadSAMModel,
  detectImageObjects,
  extractImageObject,
  removeImageBackground,
} from '../services/api'

interface DetectedObject {
  index: number
  box: number[]
  mask: string
  score: number
  label: string
}

const ImageSegmentation: React.FC = () => {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string>('')
  const [mode, setMode] = useState<'detect' | 'remove-bg'>('detect')
  const [prompt, setPrompt] = useState('a person')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [modelAvailable, setModelAvailable] = useState(false)
  const [modelLoaded, setModelLoaded] = useState(false)
  const [visualization, setVisualization] = useState<string>('')
  const [detectedObjects, setDetectedObjects] = useState<DetectedObject[]>([])
  const [extractedImages, setExtractedImages] = useState<string[]>([])

  useEffect(() => {
    checkStatusAndAutoLoad()
  }, [])

  const checkStatusAndAutoLoad = async () => {
    try {
      const status = await getSAMStatus()
      setModelAvailable(status.available)
      setModelLoaded(status.loaded)
      
      // Auto-load model if available but not loaded
      if (status.available && !status.loaded) {
        handleLoadModel()
      }
    } catch (err) {
      console.error('Failed to check SAM status:', err)
    }
  }

  const handleLoadModel = async () => {
    setIsProcessing(true)
    setProgress(10)
    setError(null)
    try {
      await loadSAMModel()
      setModelLoaded(true)
      setProgress(100)
    } catch (err: any) {
      setError(err.response?.data?.message || '模型加载失败')
    }
    setIsProcessing(false)
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      setImageFile(file)
      setImagePreview(URL.createObjectURL(file))
      setDetectedObjects([])
      setExtractedImages([])
      setVisualization('')
      setError(null)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    maxFiles: 1,
  })

  const handleDetect = async () => {
    if (!imageFile) return

    setIsProcessing(true)
    setProgress(10)
    setError(null)
    setDetectedObjects([])
    setExtractedImages([])

    try {
      setProgress(30)
      const result = await detectImageObjects(imageFile, prompt)
      setProgress(80)

      const objects: DetectedObject[] = result.boxes.map((box: number[], i: number) => ({
        index: i,
        box,
        mask: result.masks[i],
        score: result.scores[i],
        label: result.labels[i],
      }))

      setDetectedObjects(objects)
      setVisualization(`data:image/jpeg;base64,${result.visualization}`)
      setProgress(100)
    } catch (err: any) {
      setError(err.response?.data?.error || '检测失败')
    }
    setIsProcessing(false)
  }

  const handleRemoveBackground = async () => {
    if (!imageFile) return

    setIsProcessing(true)
    setProgress(10)
    setError(null)
    setExtractedImages([])

    try {
      setProgress(30)
      const blob = await removeImageBackground(imageFile, prompt)
      setProgress(90)

      const url = URL.createObjectURL(blob)
      setExtractedImages([url])
      setProgress(100)
    } catch (err: any) {
      setError(err.response?.data?.error || '背景移除失败')
    }
    setIsProcessing(false)
  }

  const handleExtractObject = async (obj: DetectedObject) => {
    if (!imageFile) return

    try {
      const blob = await extractImageObject(imageFile, obj.mask, obj.box)
      const url = URL.createObjectURL(blob)
      setExtractedImages((prev) => [...prev, url])
    } catch (err: any) {
      setError('提取失败')
    }
  }

  const handleExtractAll = async () => {
    if (!imageFile || detectedObjects.length === 0) return

    setIsProcessing(true)
    setProgress(0)
    setExtractedImages([])

    try {
      const urls: string[] = []
      for (let i = 0; i < detectedObjects.length; i++) {
        setProgress(Math.round(((i + 1) / detectedObjects.length) * 100))
        const blob = await extractImageObject(
          imageFile,
          detectedObjects[i].mask,
          detectedObjects[i].box
        )
        urls.push(URL.createObjectURL(blob))
      }
      setExtractedImages(urls)
    } catch (err: any) {
      setError('批量提取失败')
    }
    setIsProcessing(false)
  }

  const handleDownload = (url: string, filename: string) => {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          上传图片
        </Typography>

        <Box
          {...getRootProps()}
          sx={{
            border: '2px dashed #ccc',
            borderRadius: 2,
            p: 4,
            textAlign: 'center',
            cursor: 'pointer',
            bgcolor: isDragActive ? 'action.hover' : 'background.paper',
            mb: 2,
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'action.hover',
            },
          }}
        >
          <input {...getInputProps()} />
          <CloudUpload sx={{ fontSize: 48, color: 'primary.main', mb: 1 }} />
          <Typography>
            {isDragActive ? '放下文件以上传' : '拖拽图片到此处，或点击选择'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            支持格式：JPG, PNG, WebP
          </Typography>
        </Box>

        {imagePreview && (
          <Box sx={{ textAlign: 'center', mb: 2 }}>
            <img
              src={imagePreview}
              alt="preview"
              style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 8 }}
            />
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {!modelAvailable && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            SAM 模型未找到，请检查模型目录配置
          </Alert>
        )}

        {modelAvailable && !modelLoaded && (
          <Box sx={{ mb: 2 }}>
            {isProcessing ? (
              <Box>
                <LinearProgress sx={{ mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  正在加载 SAM 模型（首次约需8秒）...
                </Typography>
              </Box>
            ) : (
              <Button
                variant="outlined"
                onClick={handleLoadModel}
              >
                加载 SAM 模型
              </Button>
            )}
          </Box>
        )}

        {modelLoaded && (
          <Chip label="模型已加载" color="success" size="small" sx={{ mb: 2 }} />
        )}
      </Paper>

      {imageFile && modelLoaded && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            操作模式
          </Typography>

          <ToggleButtonGroup
            value={mode}
            exclusive
            onChange={(_, v) => v && setMode(v)}
            sx={{ mb: 2 }}
          >
            <ToggleButton value="detect">
              <Search sx={{ mr: 1 }} /> 目标检测与抠图
            </ToggleButton>
            <ToggleButton value="remove-bg">
              <ContentCut sx={{ mr: 1 }} /> 一键去背景
            </ToggleButton>
          </ToggleButtonGroup>

          <TextField
            fullWidth
            label="检测提示词（英文效果最佳）"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            helperText={
              mode === 'detect'
                ? '描述要检测的物体，如：a person, a cat, a car, clothing'
                : '描述要保留的物体（背景将被移除），如：a person'
            }
            sx={{ mb: 1 }}
          />

          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
            {['a person', 'a cat', 'a dog', 'a car', 'clothing', 'a phone', 'a cup', 'a book'].map((p) => (
              <Chip
                key={p}
                label={p}
                size="small"
                variant={prompt === p ? 'filled' : 'outlined'}
                color={prompt === p ? 'primary' : 'default'}
                onClick={() => setPrompt(p)}
                sx={{ cursor: 'pointer' }}
              />
            ))}
          </Box>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            size="large"
            onClick={mode === 'detect' ? handleDetect : handleRemoveBackground}
            disabled={isProcessing || !prompt.trim()}
            startIcon={mode === 'detect' ? <Search /> : <ContentCut />}
          >
            {mode === 'detect' ? '开始检测' : '移除背景'}
          </Button>
        </Paper>
      )}

      {isProcessing && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理中...
          </Typography>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            {progress}% - {mode === 'detect' ? '正在检测目标...' : '正在移除背景...'}
          </Typography>
        </Paper>
      )}

      {visualization && detectedObjects.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              检测结果 ({detectedObjects.length} 个目标)
            </Typography>
            <Button
              variant="outlined"
              startIcon={<Download />}
              onClick={handleExtractAll}
              disabled={isProcessing}
            >
              提取全部
            </Button>
          </Box>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                原图 + 检测标注
              </Typography>
              <img
                src={visualization}
                alt="detection"
                style={{ width: '100%', borderRadius: 8 }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                检测到的目标（点击提取）
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {detectedObjects.map((obj) => (
                  <Card
                    key={obj.index}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                    onClick={() => handleExtractObject(obj)}
                  >
                    <CardContent sx={{ pb: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="body2">
                          #{obj.index + 1} {obj.label}
                        </Typography>
                        <Chip
                          label={`${(obj.score * 100).toFixed(0)}%`}
                          size="small"
                          color={obj.score > 0.7 ? 'success' : obj.score > 0.4 ? 'warning' : 'default'}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        框: ({obj.box.map((v) => Math.round(v)).join(', ')})
                      </Typography>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {extractedImages.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            抠图结果 ({extractedImages.length} 张)
          </Typography>

          <Grid container spacing={2}>
            {extractedImages.map((url, i) => (
              <Grid item xs={6} sm={4} md={3} key={i}>
                <Card>
                  <CardMedia
                    sx={{
                      height: 200,
                      background: 'repeating-conic-gradient(#e0e0e0 0% 25%, #fff 0% 50%) 50% / 20px 20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <img
                      src={url}
                      alt={`extracted-${i}`}
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                    />
                  </CardMedia>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={<Download />}
                      onClick={() => handleDownload(url, `extracted_${i + 1}.png`)}
                      fullWidth
                    >
                      下载 PNG
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}
    </Box>
  )
}

export default ImageSegmentation
