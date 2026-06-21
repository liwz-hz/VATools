import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Grid,
  Chip,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
} from '@mui/material'
import { Save, Restore, Folder, Search, CheckCircle, ExpandMore } from '@mui/icons-material'
import { getConfig, updateConfig, resetConfig, scanModels, validateModelDir, getSeparationStatus, getSubtitleStatus } from '../services/api'

interface EngineStatus {
  name: string
  available: boolean
  error: string | null
  models: Record<string, {
    available: boolean
    description: string
    stems: string[]
  }>
}

const Settings: React.FC = () => {
  const [config, setConfig] = useState<Record<string, string>>({})
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [validating, setValidating] = useState(false)
  const [foundModels, setFoundModels] = useState<any>(null)
  const [modelValidation, setModelValidation] = useState<any>(null)
  const [engineStatus, setEngineStatus] = useState<Record<string, EngineStatus>>({})
  const [asrModels, setAsrModels] = useState<Record<string, any>>({})

  useEffect(() => {
    loadConfig()
    loadEngineStatus()
    loadAsrStatus()
  }, [])

  const loadConfig = async () => {
    try {
      const data = await getConfig()
      setConfig(data)
    } catch {
      setError('加载配置失败')
    }
  }

  const loadEngineStatus = async () => {
    try {
      const status = await getSeparationStatus()
      setEngineStatus(status.engines || {})
    } catch (err) {
      console.error('Failed to load engine status:', err)
    }
  }

  const loadAsrStatus = async () => {
    try {
      const status = await getSubtitleStatus()
      setAsrModels(status.models || {})
    } catch (err) {
      console.error('Failed to load ASR status:', err)
    }
  }

  const handleChange = (key: string, value: string) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }))
    // 清除验证状态
    if (key === 'separation_model_dir') {
      setModelValidation(null)
    }
  }

  const handleSave = async () => {
    try {
      await updateConfig(config)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('保存配置失败')
    }
  }

  const handleReset = async () => {
    try {
      const data = await resetConfig()
      setConfig(data)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {
      setError('重置配置失败')
    }
  }

  const handleScanModels = async () => {
    setScanning(true)
    setFoundModels(null)
    try {
      const models = await scanModels()
      setFoundModels(models)
    } catch (err: any) {
      setError('扫描模型失败: ' + (err.message || '未知错误'))
    } finally {
      setScanning(false)
    }
  }

  const handleValidateModelDir = async () => {
    if (!config.separation_model_dir) {
      setError('请先输入模型目录路径')
      return
    }

    setValidating(true)
    setModelValidation(null)
    try {
      const result = await validateModelDir(config.separation_model_dir)
      setModelValidation(result)
    } catch (err: any) {
      setModelValidation({
        valid: false,
        error: err.response?.data?.error || '验证失败'
      })
    } finally {
      setValidating(false)
    }
  }

  return (
    <Box>
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
          配置已保存
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          工作目录设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="上传目录"
              value={config.upload_dir || ''}
              onChange={(e) => handleChange('upload_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="输出目录"
              value={config.workspace_dir || ''}
              onChange={(e) => handleChange('workspace_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="最大文件大小 (MB)"
              value={parseInt(config.max_file_size || '0') / (1024 * 1024)}
              onChange={(e) => handleChange('max_file_size', String(parseInt(e.target.value) * 1024 * 1024))}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          日志设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="日志目录"
              value={config.log_dir || ''}
              onChange={(e) => handleChange('log_dir', e.target.value)}
            />
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>日志级别</InputLabel>
              <Select
                value={config.log_level || 'INFO'}
                label="日志级别"
                onChange={(e) => handleChange('log_level', e.target.value)}
              >
                <MenuItem value="DEBUG">DEBUG</MenuItem>
                <MenuItem value="INFO">INFO</MenuItem>
                <MenuItem value="WARNING">WARNING</MenuItem>
                <MenuItem value="ERROR">ERROR</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="日志大小 (MB)"
              value={parseInt(config.log_max_size || '0') / (1024 * 1024)}
              onChange={(e) => handleChange('log_max_size', String(parseInt(e.target.value) * 1024 * 1024))}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="保留天数"
              value={config.log_retention_days || '30'}
              onChange={(e) => handleChange('log_retention_days', e.target.value)}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          音频设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>默认格式</InputLabel>
              <Select
                value={config.default_audio_format || 'mp3'}
                label="默认格式"
                onChange={(e) => handleChange('default_audio_format', e.target.value)}
              >
                <MenuItem value="mp3">MP3</MenuItem>
                <MenuItem value="wav">WAV</MenuItem>
                <MenuItem value="flac">FLAC</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>默认比特率</InputLabel>
              <Select
                value={config.default_bitrate || '192k'}
                label="默认比特率"
                onChange={(e) => handleChange('default_bitrate', e.target.value)}
              >
                <MenuItem value="128k">128 kbps</MenuItem>
                <MenuItem value="192k">192 kbps</MenuItem>
                <MenuItem value="256k">256 kbps</MenuItem>
                <MenuItem value="320k">320 kbps</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              type="number"
              label="采样率 (Hz)"
              value={config.default_sample_rate || '44100'}
              onChange={(e) => handleChange('default_sample_rate', e.target.value)}
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          音源分离设置
        </Typography>

        <Alert severity="info" sx={{ mb: 2 }}>
          💡 音源分离需要手动配置模型路径。如果不配置，分离功能将无法使用。
        </Alert>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="模型目录路径"
              placeholder="例如: ~/models/audio_separation 或 /path/to/models"
              value={config.separation_model_dir || ''}
              onChange={(e) => handleChange('separation_model_dir', e.target.value)}
              helperText="请指定包含音源分离模型的目录（Spleeter或Demucs模型）"
              InputProps={{
                startAdornment: <Folder sx={{ mr: 1, color: 'action.active' }} />
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={validating ? <CircularProgress size={20} /> : <CheckCircle />}
                onClick={handleValidateModelDir}
                disabled={!config.separation_model_dir || validating}
              >
                {validating ? '验证中...' : '验证路径'}
              </Button>
              <Button
                variant="outlined"
                startIcon={scanning ? <CircularProgress size={20} /> : <Search />}
                onClick={handleScanModels}
                disabled={scanning}
              >
                {scanning ? '扫描中...' : '扫描系统模型'}
              </Button>
            </Box>
          </Grid>

          {modelValidation && (
            <Grid item xs={12}>
              <Alert severity={modelValidation.valid ? 'success' : 'error'}>
                {modelValidation.valid ? (
                  <Box>
                    <Typography variant="body2">✓ 模型目录有效</Typography>
                    {modelValidation.found_models && (
                      <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                        {modelValidation.found_models.map((model: string) => (
                          <Chip key={model} label={model} size="small" color="primary" />
                        ))}
                      </Box>
                    )}
                  </Box>
                ) : (
                  <Box>
                    <Typography variant="body2">✗ {modelValidation.error}</Typography>
                    {modelValidation.expected && (
                      <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                        期望的模型结构: {modelValidation.expected.join(', ')}
                      </Typography>
                    )}
                  </Box>
                )}
              </Alert>
            </Grid>
          )}

          {foundModels && (
            <Grid item xs={12}>
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography>扫描结果</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  {Object.entries(foundModels).map(([engine, models]: [string, any]) => (
                    <Box key={engine} sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" gutterBottom>
                        {engine.toUpperCase()}
                      </Typography>
                      {Object.keys(models).length > 0 ? (
                        <List dense>
                          {Object.entries(models).map(([modelName, path]: [string, any]) => (
                            <ListItem key={modelName}>
                              <ListItemText
                                primary={modelName}
                                secondary={path}
                              />
                            </ListItem>
                          ))}
                        </List>
                      ) : (
                        <Typography variant="body2" color="textSecondary">
                          未找到模型
                        </Typography>
                      )}
                    </Box>
                  ))}
                </AccordionDetails>
              </Accordion>
            </Grid>
          )}

          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>分离引擎</InputLabel>
              <Select
                value={config.separation_model || 'demucs'}
                label="分离引擎"
                onChange={(e) => handleChange('separation_model', e.target.value)}
              >
                {Object.entries(engineStatus).map(([id, status]) => (
                  <MenuItem key={id} value={id} disabled={!status.available}>
                    {status.name} {!status.available && '(不可用)'}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>默认模型</InputLabel>
              <Select
                value={config.separation_default_model || 'htdemucs_ft'}
                label="默认模型"
                onChange={(e) => handleChange('separation_default_model', e.target.value)}
                disabled={!engineStatus[config.separation_model]?.available}
              >
                {engineStatus[config.separation_model]?.available && 
                  Object.entries(engineStatus[config.separation_model].models).map(([id, info]) => (
                    <MenuItem key={id} value={id}>
                      {info.description || id}
                    </MenuItem>
                  ))
                }
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>加速方式</InputLabel>
              <Select
                value={config.acceleration_type || 'auto'}
                label="加速方式"
                onChange={(e) => handleChange('acceleration_type', e.target.value)}
              >
                <MenuItem value="auto">自动检测</MenuItem>
                <MenuItem value="mps">MPS (Metal Performance Shaders)</MenuItem>
                <MenuItem value="mlx">MLX (Apple MLX)</MenuItem>
                <MenuItem value="cpu">CPU</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>输出格式</InputLabel>
              <Select
                value={config.separation_output_format || 'wav'}
                label="输出格式"
                onChange={(e) => handleChange('separation_output_format', e.target.value)}
              >
                <MenuItem value="wav">WAV</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          ASR 语音识别设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="ASR 模型目录路径"
              placeholder="/Users/lwz/.cache/modelscope/hub/models/mlx-community"
              value={config.asr_model_dir || ''}
              onChange={(e) => handleChange('asr_model_dir', e.target.value)}
              helperText="包含 Qwen3-ASR 等模型的目录"
              InputProps={{
                startAdornment: <Folder sx={{ mr: 1, color: 'action.active' }} />
              }}
            />
          </Grid>

          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              检测到的 ASR 模型:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {Object.keys(asrModels).length > 0 ? (
                Object.keys(asrModels).map((name) => (
                  <Chip key={name} label={name} size="small" color="primary" />
                ))
              ) : (
                <Typography variant="body2" color="text.disabled">
                  未检测到 ASR 模型
                </Typography>
              )}
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Button
              variant="outlined"
              startIcon={<Search />}
              onClick={loadAsrStatus}
            >
              刷新模型列表
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          TTS 语音合成设置
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="TTS 模型目录路径"
              placeholder="/Users/lwz/.cache/modelscope/hub/models/mlx-community"
              value={config.tts_model_dir || ''}
              onChange={(e) => handleChange('tts_model_dir', e.target.value)}
              helperText="包含 Qwen3-TTS 模型的目录（默认与 ASR 共享）"
              InputProps={{
                startAdornment: <Folder sx={{ mr: 1, color: 'action.active' }} />
              }}
            />
          </Grid>
        </Grid>
      </Paper>

      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          variant="contained"
          startIcon={<Save />}
          onClick={handleSave}
        >
          保存配置
        </Button>
        <Button
          variant="outlined"
          startIcon={<Restore />}
          onClick={handleReset}
        >
          恢复默认
        </Button>
      </Box>
    </Box>
  )
}

export default Settings
