import React, { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Box,
  Paper,
  Typography,
  Button,
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material'
import {
  CloudUpload,
  Download,
  ContentCut,
  AutoFixHigh,
} from '@mui/icons-material'
import {
  getBirefnetModels,
  segmentBirefnetImage,
  removeBirefnetBackground,
  loadBirefnetModel,
} from '../services/api'

interface BirefnetModel {
  type: string
  path: string
  loaded: boolean
}

const BiRefNetSegmentation: React.FC = () => {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string>('')
  const [operation, setOperation] = useState<'segment' | 'remove-bg'>('remove-bg')
  const [modelType, setModelType] = useState<string>('general')
  const [isProcessing, setIsProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [models, setModels] = useState<BirefnetModel[]>([])
  const [resultImage, setResultImage] = useState<string>('')
  const [maskImage, setMaskImage] = useState<string>('')

  useEffect(() => {
    checkModels()
  }, [])

  const checkModels = async () => {
    try {
      const result = await getBirefnetModels()
      if (result.success) {
        setModels(result.models)
      }
    } catch (err) {
      console.error('Failed to check BiRefNet models:', err)
    }
  }

  const handleLoadModel = async (type: string) => {
    setIsProcessing(true)
    setProgress(10)
    setError(null)
    try {
      await loadBirefnetModel(type)
      await checkModels()
      setProgress(100)
    } catch (err: any) {
      setError(err.response?.data?.error || '模型加载失败')
    }
    setIsProcessing(false)
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      setImageFile(file)
      setImagePreview(URL.createObjectURL(file))
      setResultImage('')
      setMaskImage('')
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

  const handleProcess = async () => {
    if (!imageFile) return

    setIsProcessing(true)
    setProgress(10)
    setError(null)
    setResultImage('')
    setMaskImage('')

    try {
      setProgress(30)

      if (operation === 'segment') {
        const result = await segmentBirefnetImage(imageFile, modelType)
        if (result.success) {
          setMaskImage(`data:image/png;base64,${result.mask}`)
          setProgress(100)
        } else {
          setError(result.error || '分割失败')
        }
      } else {
        setProgress(50)
        const blob = await removeBirefnetBackground(imageFile, modelType)
        const url = URL.createObjectURL(blob)
        setResultImage(url)
        setProgress(100)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || '处理失败')
    }
    setIsProcessing(false)
  }

  const handleDownload = (url: string, filename: string) => {
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
  }

  const currentModel = models.find(m => m.type === modelType)

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          BiRefNet 图像分割
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          高质量图像分割和抠图，支持通用分割和高分辨率抠图两种模式
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
      </Paper>

      {imageFile && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理设置
          </Typography>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>模型类型</InputLabel>
            <Select
              value={modelType}
              label="模型类型"
              onChange={(e) => setModelType(e.target.value)}
            >
              <MenuItem value="general">
                <Box>
                  <Typography>通用分割 (General)</Typography>
                  <Typography variant="caption" color="text.secondary">
                    1024x1024，适合一般场景
                  </Typography>
                </Box>
              </MenuItem>
              <MenuItem value="hr_matting">
                <Box>
                  <Typography>高分辨率抠图 (HR-Matting)</Typography>
                  <Typography variant="caption" color="text.secondary">
                    2048x2048，适合精细抠图（头发、边缘）
                  </Typography>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          {currentModel && !currentModel.loaded && (
            <Box sx={{ mb: 2 }}>
              <Alert severity="info" sx={{ mb: 1 }}>
                模型未加载，首次使用需要加载（约1-2秒）
              </Alert>
              <Button
                variant="outlined"
                onClick={() => handleLoadModel(modelType)}
                disabled={isProcessing}
              >
                加载模型
              </Button>
            </Box>
          )}

          {currentModel && currentModel.loaded && (
            <Chip label="模型已加载" color="success" size="small" sx={{ mb: 2 }} />
          )}

          <ToggleButtonGroup
            value={operation}
            exclusive
            onChange={(_, v) => v && setOperation(v)}
            sx={{ mb: 2 }}
          >
            <ToggleButton value="segment">
              <AutoFixHigh sx={{ mr: 1 }} /> 生成分割蒙版
            </ToggleButton>
            <ToggleButton value="remove-bg">
              <ContentCut sx={{ mr: 1 }} /> 去除背景
            </ToggleButton>
          </ToggleButtonGroup>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            size="large"
            onClick={handleProcess}
            disabled={isProcessing || (currentModel && !currentModel.loaded)}
            startIcon={operation === 'segment' ? <AutoFixHigh /> : <ContentCut />}
          >
            {operation === 'segment' ? '生成分割蒙版' : '去除背景'}
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
            {progress}% - {operation === 'segment' ? '正在生成分割蒙版...' : '正在去除背景...'}
          </Typography>
        </Paper>
      )}

      {(resultImage || maskImage) && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            处理结果
          </Typography>

          <Grid container spacing={2}>
            {maskImage && (
              <Grid item xs={12} md={6}>
                <Card>
                  <CardMedia
                    sx={{
                      height: 400,
                      background: '#000',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <img
                      src={maskImage}
                      alt="mask"
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                    />
                  </CardMedia>
                  <CardContent>
                    <Typography variant="subtitle1">分割蒙版</Typography>
                    <Typography variant="body2" color="text.secondary">
                      白色区域为前景，黑色区域为背景
                    </Typography>
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={<Download />}
                      onClick={() => handleDownload(maskImage, 'mask.png')}
                      fullWidth
                    >
                      下载蒙版
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            )}

            {resultImage && (
              <Grid item xs={12} md={6}>
                <Card>
                  <CardMedia
                    sx={{
                      height: 400,
                      background: 'repeating-conic-gradient(#e0e0e0 0% 25%, #fff 0% 50%) 50% / 20px 20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <img
                      src={resultImage}
                      alt="result"
                      style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                    />
                  </CardMedia>
                  <CardContent>
                    <Typography variant="subtitle1">去背景结果</Typography>
                    <Typography variant="body2" color="text.secondary">
                      透明背景 PNG 图像
                    </Typography>
                  </CardContent>
                  <CardActions>
                    <Button
                      size="small"
                      startIcon={<Download />}
                      onClick={() => handleDownload(resultImage, 'no_background.png')}
                      fullWidth
                    >
                      下载 PNG
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            )}
          </Grid>
        </Paper>
      )}
    </Box>
  )
}

export default BiRefNetSegmentation
